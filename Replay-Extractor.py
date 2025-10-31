import platform
import os
import re
import csv
import argparse
from pathlib import Path

from loguru import logger

from sc2.main import run_replay
from sc2.observer_ai import ObserverAI
from sc2.data import Race
from sc2.sc2process import KillSwitch


DATA_INTERVAL = 20  #Time between data records (in game steps)
DATA_START_TIME = 0 #Time to start gathering data (in seconds)
DATA_END_TIME = 7200 #Time to stop gathering data (in seconds)

class ObserverBot(ObserverAI):
    def __init__(self, replay_path, observed_id):
        super().__init__()
        self.unit_data = []
        self.replay_path = replay_path
        self.observed_id = observed_id

    def _prepare_step(self, state, proto_game_info):
        self.race = Race.Terran #not sure why this is needed, but the program will crash without it.
        super()._prepare_step(state, proto_game_info)

    async def on_start(self):
        pass

    async def on_step(self, iteration: int):
        if self.time > DATA_END_TIME:
            await self.client.leave()
            return

        if self.time < DATA_START_TIME:
            return
        
        if iteration % DATA_INTERVAL != 0:
            return

        for unit in self.all_units:
            
            try:
                owner = unit.owner_id
            except AttributeError:
                owner = 0

            self.unit_data.append(
                {
                    "timestamp": self.time,
                    "unit_tag": unit.tag,
                    "unit_type": unit.type_id.name,
                    "player_id": owner,
                    "position_x": unit.position.x,
                    "position_y": unit.position.y,
                    "health": unit.health,
                    "shield": unit.shield,
                    "energy": unit.energy,
                    "build_progress": unit.build_progress,
                    "resource_remaining": unit.mineral_contents if unit.is_mineral_field  else (unit.vespene_contents if unit.is_vespene_geyser else 0),
                }
            )

    async def on_end(self, game_result):
        # This callback is unreliable when the game ends by reaching the end of a replay file.
        pass

    async def on_unit_destroyed(self, unit_tag):
        pass

    async def on_unit_created(self, unit):
        pass

    async def on_unit_took_damage(self, unit, amount):
        pass

    async def on_unit_type_changed(self, unit, previous_type):
        pass

    async def on_building_construction_started(self, unit):
        pass

    async def on_building_construction_complete(self, unit):
        pass

    async def on_upgrade_complete(self, upgrade):
        pass

    async def on_enemy_unit_entered_vision(self, unit):
        pass

    async def on_enemy_unit_left_vision(self, unit_tag):
        pass

def save_data_from_bot(bot: ObserverBot):
    if not bot.unit_data:
        logger.warning(f"No unit data to write for POV = player {bot.observed_id} in replay '{Path(bot.replay_path).name}'. This may be due to an incorrect time window.")
        return

    # Group data by player_id
    player_data = {}
    for row in bot.unit_data:
        player_id = row["player_id"]
        if player_id not in player_data:
            player_data[player_id] = []
        player_data[player_id].append(row)

    replay_name_parts = Path(bot.replay_path).stem.split("_")
    game_number = replay_name_parts[0]
    player_1_name = replay_name_parts[1]
    player_2_name = replay_name_parts[2]
    map_name = "_".join(replay_name_parts[3:])
    
    observer_name = player_1_name if bot.observed_id == 1 else player_2_name

    output_dir = Path("Output") / game_number
    output_dir.mkdir(parents=True, exist_ok=True)

    for player_id, data in player_data.items():

        if player_id in [1, 2]:
            player_name = player_1_name if player_id == 1 else player_2_name
            if player_id == bot.observed_id:
                output_filename = f"{game_number}_{player_name}_{map_name}_ground-truth.csv"
            else:
                output_filename = f"{game_number}_{player_name}_{map_name}_observed-by-{observer_name}.csv"
        else:
            output_filename = f"{game_number}_player-id-{player_id}_{map_name}_observed-by-{observer_name}.csv" #These are (probably) neutral objects on the map (e.g., minerals).
        
        output_file = output_dir / output_filename

        # Check if data is not empty before writing
        if data:
            with open(output_file, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            logger.info(f"Successfully wrote unit data for player {player_id} to {output_file}")

def extract_replay(rpath):
    # Get Player 1's perspective
    observer_1 = ObserverBot(rpath, observed_id=1)
    try:
        run_replay(observer_1, replay_path=str(rpath), observed_id=1)
    except Exception:
        # This is expected when the replay ends before DATA_END_TIME.
        pass
    finally:
        save_data_from_bot(observer_1)

    # Get Player 2's perspective
    observer_2 = ObserverBot(rpath, observed_id=2)
    try:
        run_replay(observer_2, replay_path=str(rpath), observed_id=2)
    except Exception:
        # This is expected when the replay ends before DATA_END_TIME.
        pass
    finally:
        save_data_from_bot(observer_2)

if __name__ == "__main__":
    logger.add("replay_extractor.log", level="INFO", rotation="5 MB", retention=5, format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}")
    parser = argparse.ArgumentParser(
        description="""A python tool for extracting game data from a starcraft 2 replay."""
    )

    parser.add_argument("replay", nargs='?', default=None, type=str, help="The replay number, filename, or full path. If omitted, all new replays will be processed.")
    parser.add_argument("-s", "--start", help="The in-game time to start recording data (in seconds).", default=0, type=int)
    parser.add_argument("-e", "--end", help="The in-game time to stop recording and end the replay (in seconds).", default=7200, type=int)
    parser.add_argument("-i", "--interval", help="The time between record entries (in game steps).", default=20, type=int)
    args = parser.parse_args()
    DATA_START_TIME = args.start
    DATA_END_TIME = args.end
    DATA_INTERVAL = args.interval


    replay_paths_to_process = []

    if args.replay:
        # Single replay processing
        replay_path = None
        
        # Absolute path
        if Path(args.replay).is_absolute():
            replay_path = Path(args.replay)
        # AIArena match ID
        elif args.replay.isdigit():
            replays_dir = Path("Replays")
            if replays_dir.is_dir():
                match_pattern = f"{args.replay}_*.SC2Replay"
                found_files = list(replays_dir.glob(match_pattern))
                if len(found_files) == 1:
                    replay_path = found_files[0]
                elif len(found_files) > 1:
                    logger.error(f"Multiple replays found for number '{args.replay}'. Please use a more specific name.")
        # Full filename
        elif ".SC2Replay" in args.replay:
            replay_path = Path("Replays") / args.replay
        
        else:
            logger.warning(f"Invalid replay identifier: '{args.replay}'")

        if replay_path:
            replay_paths_to_process.append(replay_path)

    else:
        # No replay specified, so analyze all new replays
        replays_dir = Path("Replays")
        output_dir = Path("Output")
        
        if not replays_dir.is_dir():
            logger.error("The 'Replays' directory was not found.")
            exit()
        output_dir.mkdir(exist_ok=True) # Creates /Output/ if needed

        preexisting_outputs = {d.name for d in output_dir.iterdir() if d.is_dir()}
        
        for replay_file in replays_dir.glob("*.SC2Replay"):
            match = re.search(r"^(\d+)_", replay_file.name)
            if match:
                game_num = match.group(1)
                if game_num not in preexisting_outputs:
                    replay_paths_to_process.append(replay_file)

    # Process all collected paths
    if not replay_paths_to_process:
        logger.info("No replays found or no new replays to process.")
    else:
        logger.info(f"Found {len(replay_paths_to_process)} replay(s) to process.")
        print("\nTo halt batch early, create a file named 'STOP' in the project directory.")
        
        stop_file_path = Path("STOP")

        for rp in replay_paths_to_process:
            if stop_file_path.exists():
                logger.info("'STOP' file detected. Aborting batch process.")
                stop_file_path.unlink() # Clean up the stop file
                break # Exit the batch processing loop

            try:
                absolute_path = rp.resolve()
                if absolute_path.is_file():
                    logger.info(f"Processing {absolute_path.name}...")
                    extract_replay(absolute_path)
                else:
                    logger.error(f"Replay file not found at path: {absolute_path}")
            except Exception as e:
                # Log error for a single replay (e.g. client crash) and continue
                logger.error(f"Failed to process replay {rp.name}. Error: {e}")