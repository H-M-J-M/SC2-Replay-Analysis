import json
import uuid
import os
import re
import csv
import argparse
import asyncio
import multiprocessing
from pathlib import Path

from loguru import logger

from sc2.main import run_replay, _play_replay, get_replay_version
from sc2.observer_ai import ObserverAI
from sc2.data import Race
from sc2.sc2process import KillSwitch, SC2Process
from sc2.client import Client


from sc2.protocol import ProtocolError


class ObserverBot(ObserverAI):
    def __init__(self, replay_path, observed_id, start_time=0, end_time=7200, interval=20):
        super().__init__()
        self.replay_path = replay_path
        self.observed_id = observed_id
        self.start_time = start_time
        self.end_time = end_time
        self.interval = interval

        self.output_dir = Path("Output")
        self.temp_file = None
        self.csv_writer = None
        self.temp_file_path = None
        self.temp_schema_path = None

        self.unit_cache = {}
        self.death_temp_file = None
        self.death_csv_writer = None
        self.death_temp_file_path = None

    def _prepare_step(self, state, proto_game_info):
        self.race = Race.Terran #not sure why this is needed, but the program will crash without it. # pyright: ignore[reportAttributeAccessIssue] 
        super()._prepare_step(state, proto_game_info)

    async def on_start(self):
        game_number = Path(self.replay_path).stem.split("_")[0]
        temp_dir = self.output_dir / game_number
        temp_dir.mkdir(parents=True, exist_ok=True)
        self.temp_file_path = temp_dir / f"temp_{uuid.uuid4()}.csv"
        self.death_temp_file_path = temp_dir / f"death_temp_{uuid.uuid4()}.csv"

    async def on_step(self, iteration: int):
        if self.time > self.end_time:
            await self.client.leave()
            return

        if self.time < self.start_time:
            return
        
        if iteration % self.interval != 0:
            return

        for unit in self.all_units:
            
            try:
                owner = unit.owner_id
            except AttributeError:
                owner = 0

            row_dict = {
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
                "resource_remaining": unit.mineral_contents if unit.is_mineral_field  else (unit.vespene_contents if unit.is_vespene_geyser else -1),
            }

            if self.csv_writer is None:
                if self.temp_file_path is None:
                    logger.error("temp_file_path was not set in on_start.")
                    return
                self.temp_file = open(self.temp_file_path, "w", newline="")
                self.csv_writer = csv.DictWriter(self.temp_file, fieldnames=row_dict.keys())
                self.csv_writer.writeheader()

                schema = {k: type(v).__name__ for k, v in row_dict.items()}
                self.temp_schema_path = self.temp_file_path.with_suffix('.json')
                with open(self.temp_schema_path, 'w') as f:
                    json.dump(schema, f)
            
            self.csv_writer.writerow(row_dict)

        # Update unit cache
        self.unit_cache.clear()
        for unit in self.all_units:
            try:
                owner = unit.owner_id
            except AttributeError:
                owner = 0
            self.unit_cache[unit.tag] = {
                "unit_type": unit.type_id.name,
                "player_id": owner,
                "position_x": unit.position.x,
                "position_y": unit.position.y,
            }

    def close(self):
        if self.temp_file and not self.temp_file.closed:
            self.temp_file.close()
        if self.death_temp_file and not self.death_temp_file.closed:
            self.death_temp_file.close()

    async def on_end(self, game_result):
        # This callback is unreliable when the game ends by reaching the end of a replay file.
        self.close()
        pass

    async def on_unit_destroyed(self, unit_tag):
        if unit_tag in self.unit_cache:
            unit_data = self.unit_cache[unit_tag]

            row_dict = {
                "timestamp": self.time,
                "unit_tag": unit_tag,
                "unit_type": unit_data["unit_type"],
                "player_id": unit_data["player_id"],
                "position_x": unit_data["position_x"],
                "position_y": unit_data["position_y"],
            }

            if self.death_csv_writer is None:
                if self.death_temp_file_path is None:
                    logger.error("death_temp_file_path was not set in on_start.")
                    return
                self.death_temp_file = open(self.death_temp_file_path, "w", newline="")
                self.death_csv_writer = csv.DictWriter(self.death_temp_file, fieldnames=row_dict.keys())
                self.death_csv_writer.writeheader()

            self.death_csv_writer.writerow(row_dict)

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
    # Process main unit data
    if not bot.temp_file_path or not bot.temp_file_path.exists() or bot.temp_file_path.stat().st_size == 0:
        logger.warning(f"No unit data to write for POV = player {bot.observed_id} in replay '{Path(bot.replay_path).name}'. This may be due to an incorrect time window.")
        if bot.temp_file_path and bot.temp_file_path.exists():
            os.remove(bot.temp_file_path)
        if bot.temp_schema_path and bot.temp_schema_path.exists():
            os.remove(bot.temp_schema_path)
    else:
        # Read schema
        schema = {}
        if bot.temp_schema_path and bot.temp_schema_path.exists():
            with open(bot.temp_schema_path, 'r') as f:
                schema = json.load(f)

        type_map = {'int': int, 'float': float, 'str': str}

        # Group data by player_id
        player_data = {}
        with open(bot.temp_file_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert types based on the schema
                for key, type_str in schema.items():
                    if key in row and row[key]:
                        target_type = type_map.get(type_str)
                        if target_type:
                            try:
                                # Special handling for int conversion from float strings (e.g., "1.0")
                                if target_type is int:
                                    row[key] = int(float(row[key]))
                                else:
                                    row[key] = target_type(row[key])
                            except (ValueError, TypeError):
                                logger.warning(f"Could not convert '{row[key]}' to {type_str} for key '{key}'. Keeping as string.")
                                pass
                
                player_id = row.get("player_id")
                if player_id is not None:
                    if player_id not in player_data:
                        player_data[player_id] = []
                    player_data[player_id].append(row)

        # Clean up temporary files
        os.remove(bot.temp_file_path)
        if bot.temp_schema_path and bot.temp_schema_path.exists():
            os.remove(bot.temp_schema_path)

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

    # Process death data
    if bot.death_temp_file_path and bot.death_temp_file_path.exists() and bot.death_temp_file_path.stat().st_size > 0:
        all_death_data = []
        with open(bot.death_temp_file_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                all_death_data.append(row)

        os.remove(bot.death_temp_file_path)

        if all_death_data:
            replay_name_parts = Path(bot.replay_path).stem.split("_")
            game_number = replay_name_parts[0]
            player_1_name = replay_name_parts[1]
            player_2_name = replay_name_parts[2]
            map_name = "_".join(replay_name_parts[3:])
            
            observer_name = player_1_name if bot.observed_id == 1 else player_2_name
            output_dir = Path("Output") / game_number

            output_filename = f"{game_number}_deaths_observed-by-{observer_name}_{map_name}.csv"
            output_file = output_dir / output_filename

            with open(output_file, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=all_death_data[0].keys())
                writer.writeheader()
                writer.writerows(all_death_data)
            logger.info(f"Successfully wrote unit death data observed by {observer_name} to {output_file}")

async def process_perspective(replay_path, observed_id, port, base_build, data_version, start_time, end_time, interval, placement=None):
    """Processes a single player's perspective of a replay using a specific port."""
    bot = ObserverBot(replay_path, observed_id=observed_id, start_time=start_time, end_time=end_time, interval=interval)
    try:
        async with SC2Process(port=port, base_build=base_build, data_hash=data_version, placement=placement) as server:
            await server.ping()
            client = Client(server._ws)
            await server.start_replay(
                replay_path=str(replay_path),
                realtime=False,
                observed_id=observed_id
            )
            await _play_replay(client, bot, realtime=False, player_id=observed_id) # pyright: ignore[reportGeneralTypeIssues]
    except ProtocolError as e:
        # This is expected when the replay ends.
        if "Game over" in str(e):
            pass
        else:
            logger.error(f"Caught unexpected ProtocolError in process_perspective: {e}")
    except Exception as e:
        logger.error(f"Caught exception in process_perspective: {e}")
    finally:
        bot.close()
        save_data_from_bot(bot)

def process_perspective_wrapper(replay_path, observed_id, port, base_build, data_version, start_time, end_time, interval, placement=None):
    """Synchronous wrapper to run the async process_perspective function for multiprocessing."""
    setup_logging() # Ensure logger is configured in the child process
    try:
        asyncio.run(process_perspective(replay_path, observed_id, port, base_build, data_version, start_time, end_time, interval, placement))
    except Exception as e:
        logger.error(f"Error in process for player {observed_id} on port {port}: {e}")

def extract_replay(rpath, start_time, end_time, interval):
    # Get Player 1's perspective
    observer_1 = ObserverBot(rpath, observed_id=1, start_time=start_time, end_time=end_time, interval=interval)
    try:
        run_replay(observer_1, replay_path=str(rpath), observed_id=1)
    except Exception:
        # This is expected when the replay ends before the specified end_time.
        pass
    finally:
        observer_1.close()
        save_data_from_bot(observer_1)

    # Get Player 2's perspective
    observer_2 = ObserverBot(rpath, observed_id=2, start_time=start_time, end_time=end_time, interval=interval)
    try:
        run_replay(observer_2, replay_path=str(rpath), observed_id=2)
    except Exception:
        # This is expected when the replay ends before the specified end_time.
        pass
    finally:
        observer_2.close()
        save_data_from_bot(observer_2)

def setup_logging():
    """Configures the logger to save logs to a file."""
    logger.add("replay_extractor.log", level="INFO", rotation="5 MB", retention=5, format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}", enqueue=True)

if __name__ == "__main__":
    # On Windows, multiprocessing requires this protection.
    multiprocessing.freeze_support()

    setup_logging()
    parser = argparse.ArgumentParser(
        description="""A python tool for extracting game data from a starcraft 2 replay."""
    )

    parser.add_argument("replay", nargs='?', default=None, type=str, help="The replay number, filename, or full path. If omitted, all new replays will be processed.")
    parser.add_argument("-s", "--start", help="The in-game time to start recording data (in seconds).", default=0, type=int)
    parser.add_argument("-e", "--end", help="The in-game time to stop recording and end the replay (in seconds).", default=7200, type=int)
    parser.add_argument("-i", "--interval", help="The time between record entries (in game steps).", default=20, type=int)
    parser.add_argument("--single-thread", help="Run the extraction in a single thread instead of in parallel.", action="store_true")
    args = parser.parse_args()

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
        
        stop_file_path = Path("STOP")

        total_replays = len(replay_paths_to_process)
        for i, rp in enumerate(replay_paths_to_process):
            current_replay_number = i + 1
            logger.info(f"Starting replay {current_replay_number}/{total_replays}")
            if stop_file_path.exists():
                logger.info("'STOP' file detected. Aborting batch process.")
                stop_file_path.unlink() # Clean up the stop file
                break # Exit the batch processing loop

            try:
                absolute_path = rp.resolve()
                if not absolute_path.is_file():
                    logger.error(f"Replay file not found at path: {absolute_path}")
                    continue
                
                print("\nTo halt batch early, create a file named 'STOP' in the project directory.")
                logger.info(f"Processing {absolute_path.name}...")

                if args.single_thread:
                    logger.info("Running in single-threaded mode.")
                    extract_replay(absolute_path, args.start, args.end, args.interval)
                else:
                    logger.info("Running in parallel mode.")
                    try:
                        base_build, data_version = get_replay_version(absolute_path)
                    except Exception as e:
                        logger.error(f"Could not get replay version for {absolute_path.name}: {e}")
                        continue

                    port1 = 5001
                    port2 = 5002
                    placement1 = (0, 0)
                    placement2 = (960, 0)
                    p1_args = (absolute_path, 1, port1, base_build, data_version, args.start, args.end, args.interval, placement1)
                    p2_args = (absolute_path, 2, port2, base_build, data_version, args.start, args.end, args.interval, placement2)
                    p1 = multiprocessing.Process(target=process_perspective_wrapper, args=p1_args)
                    p2 = multiprocessing.Process(target=process_perspective_wrapper, args=p2_args)
                    
                    p1.start()
                    p2.start()
                    
                    p1.join()
                    p2.join()

            except Exception as e:
                # Log error for a single replay (e.g. client crash) and continue
                logger.error(f"Failed to process replay {rp.name}. Error: {e}")