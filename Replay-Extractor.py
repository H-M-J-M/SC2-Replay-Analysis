import re
import shutil
import argparse
import asyncio
import multiprocessing
from pathlib import Path
import pandas as pd
import numpy as np
import random

from loguru import logger

from sc2.main import _play_replay, get_replay_version
from sc2.observer_ai import ObserverAI
from sc2.data import Race
from sc2.sc2process import SC2Process
from sc2.client import Client
from sc2.protocol import ProtocolError

import internal.extractor_helper as exh

OUTPUT_DIR = Path("OutputRaw")
REPLAY_DIR = Path("Replays")

class ObserverBot(ObserverAI):
    def __init__(self, replay_path, observed_id, start_time=0, end_time=7200, interval=20):
        super().__init__()
        self.replay_path = replay_path
        self.observed_id = observed_id
        self.start_time = start_time
        self.end_time = end_time
        self.interval = interval

        # Unit/Death data
        self.unit_data = []
        self.death_data = []
        self.persistent_cache = {}
        self.interval_cache = {}

        # Resource data
        self.resource_totals_data = []

        # Upgrade data
        self.upgrade_time_data = []

    def _prepare_step(self, state, proto_game_info):
        self.race = Race.Terran #not sure why this is needed, but the program will crash without it. # pyright: ignore[reportAttributeAccessIssue] 
        super()._prepare_step(state, proto_game_info)

    async def on_step(self, iteration: int):
        if self.time > self.end_time:
            await self.client.leave()
            return

        if self.time < self.start_time:
            return
        
        ### RESOURCES ###
        current_resources = {'timestamp': self.time,
                             'minerals': self.minerals,
                             'vespene': self.vespene,
                             'supply_cap': self.supply_cap,
                             'supply_used': self.supply_used,
                             'supply_army': self.supply_army #supply_workers should be (supply_used - supply_army)
                             }
        self.resource_totals_data.append(current_resources)

        ### UNITS ###
        # filter out junk from self.all_units
        snapshots, real_units = exh.split_units(self.all_units, lambda u: u.is_snapshot)
        filtered_units = snapshots.filter(lambda u: not (exh.resource_snap(u) and u.is_structure)) + real_units

        # On every step, update both caches with the latest unit data.
        for unit in filtered_units:
            try: # owner id is weird sometimes.
                owner = unit.owner_id
            except AttributeError:
                owner = 0
            
            unit_state = {
                "timestamp": self.time,
                "unit_tag": unit.tag,
                "unit_type": unit.type_id.name,
                "player_id": owner,
                "position_x": unit.position.x,
                "position_y": unit.position.y,
                "is_snapshot": unit.is_snapshot,
                "health": unit.health,
                "shield": unit.shield,
                "energy": unit.energy,
                "build_progress": unit.build_progress,
                "resource_remaining": unit.mineral_contents if unit.is_mineral_field else (unit.vespene_contents if unit.is_vespene_geyser else np.nan),
            }
            self.persistent_cache[unit.tag] = unit_state
            self.interval_cache[unit.tag] = unit_state

        # At the specified interval, flush the interval_cache to the main data list and clear it.
        if iteration % self.interval == 0:
            self.unit_data.extend(self.interval_cache.values())
            self.interval_cache.clear()

    def close(self):
        # No files to close anymore
        pass

    async def on_end(self, game_result):
        # This callback is unreliable when the game ends by reaching the end of a replay file (but I'm using it anyway just in case).
        self.close()
        pass

    async def on_unit_destroyed(self, unit_tag):
        if unit_tag in self.persistent_cache:
            unit_data = self.persistent_cache.pop(unit_tag)
            row_dict = {
                "timestamp": self.time,
                "unit_tag": unit_tag,
                "unit_type": unit_data["unit_type"],
                "player_id": unit_data["player_id"],
                "position_x": unit_data["position_x"],
                "position_y": unit_data["position_y"],
            }
            self.death_data.append(row_dict)

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

    async def on_upgrade_complete(self, the_upgrade):
        up_data = self.game_data.upgrades[the_upgrade.value]
        t_start = self.time - ((up_data.cost.time or 0) / 22.4)
        new_upgrade = {'time_completed': self.time, 
                       'upgrade': up_data.name, 
                       'player_id': self.observed_id, 
                       'mineral_cost': up_data.cost.minerals, 
                       'vespene_cost': up_data.cost.vespene, 
                       'imputed_start': t_start}
        self.upgrade_time_data.append(new_upgrade)

    async def on_enemy_unit_entered_vision(self, unit):
        pass

    async def on_enemy_unit_left_vision(self, unit_tag):
        pass

async def process_perspective(replay_path, observed_id, port, base_build, data_version, start_time, end_time, interval, placement=None):
    """Processes a single player's perspective of a replay and returns the collected data."""
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
            raise
    except Exception as e:
        logger.error(f"Caught exception in process_perspective: {e}")
        raise
    finally:
        bot.close()

    # Create DataFrames from the bot's collected data
    units_df = pd.DataFrame(bot.unit_data) if bot.unit_data else pd.DataFrame()
    deaths_df = pd.DataFrame(bot.death_data) if bot.death_data else pd.DataFrame()
    resources_df = pd.DataFrame(bot.resource_totals_data) if bot.resource_totals_data else pd.DataFrame()
    upgrades_df = pd.DataFrame(bot.upgrade_time_data) if bot.upgrade_time_data else pd.DataFrame()
    
    return units_df, deaths_df, resources_df, upgrades_df

def process_perspective_wrapper(args):
    """Synchronous wrapper to run the async process_perspective function for multiprocessing."""
    # Unpack all arguments for clarity
    replay_path, observed_id, port, base_build, data_version, start_time, end_time, interval, placement = args
    
    setup_logging() # Ensure logger is configured in the child process (prevents verbose logging from the SC2API)
    try:
        return asyncio.run(process_perspective(replay_path, observed_id, port, base_build, data_version, start_time, end_time, interval, placement))
    except Exception as e:
        logger.error(f"Error in process for player {observed_id} on port {port}: {e}")
        # Return None or empty DataFrames on failure to ensure the pool doesn't hang
        return None

def setup_logging():
    """Configures the logger to save logs to a file."""
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True) # Ensure the logs directory exists
    logger.add(log_dir / "replay_extractor.log", level="INFO", rotation="5 MB", retention=5, format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}", enqueue=True)

def rm_failed_extraction(game_out_dir, log_inst):
    if game_out_dir.is_dir():
                        try:
                            shutil.rmtree(game_out_dir)
                            log_inst.info(f"Removed directory: {game_out_dir}")
                        except OSError as e:
                            log_inst.critical(f"Error removing directory {game_out_dir}: {e}") #TODO Consider tracking all CRITICAL errors and displaying all of them again when the program exits.

if __name__ == "__main__":
    multiprocessing.freeze_support() # For windows OS

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
        
        # Absolute path arg
        if Path(args.replay).is_absolute():
            replay_path = Path(args.replay)
        # AIArena match ID arg
        elif args.replay.isdigit():
            replays_dir = REPLAY_DIR
            if replays_dir.is_dir():
                match_pattern = f"{args.replay}_*.SC2Replay"
                found_files = list(replays_dir.glob(match_pattern))
                if len(found_files) == 1:
                    replay_path = found_files[0]
                elif len(found_files) > 1:
                    logger.error(f"Multiple replays found for number '{args.replay}'. Please use a more specific name.")
        # Full filename arg
        elif ".SC2Replay" in args.replay:
            replay_path = REPLAY_DIR / args.replay
        
        else:
            logger.warning(f"Invalid replay identifier: '{args.replay}'")

        if replay_path:
            replay_paths_to_process.append(replay_path)

    else:
        # No replay specified, so analyze all new replays
        replays_dir = REPLAY_DIR
        output_dir = OUTPUT_DIR
        
        if not replays_dir.is_dir():
            logger.error("The 'Replays' directory was not found.")
            exit()
        output_dir.mkdir(exist_ok=True) # Creates output directory if needed

        for replay_file in replays_dir.glob("*.SC2Replay"):
            match = re.search(r"^(\d+)_", replay_file.name)
            if match:
                game_num = match.group(1)
                game_output_dir = output_dir / game_num
                
                # Check if the directory exists and contains the final parquet file (because the metadata script could have created the directory)
                if game_output_dir.is_dir() and any(game_output_dir.glob('units.parquet')):
                    logger.debug(f"Skipping replay {game_num} as it has already been processed.")
                    continue
                
                replay_paths_to_process.append(replay_file)

    # Process all collected paths
    if not replay_paths_to_process:
        logger.info("No replays found or no new replays to process.")
    else:
        random.shuffle(replay_paths_to_process)
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

                # Get game number from current replay filename
                game_num_match = re.search(r"^(\d+)_", rp.name)
                if not game_num_match:
                    logger.warning(f"Could not extract game number from {rp.name}. Skipping.")
                    continue
                game_num = game_num_match.group(1)
                game_output_dir = OUTPUT_DIR / game_num
                game_output_dir.mkdir(parents=True, exist_ok=True)

                # Set processing mode for the replay
                # 2 for parallel, 1 for single-threaded.
                num_processes = 1 if args.single_thread else 2
                if args.single_thread:
                    logger.info("Running in single-threaded mode.")
                else:
                    logger.info("Running in parallel mode.")

                try:
                    base_build, data_version = get_replay_version(absolute_path)
                except Exception as e:
                    logger.error(f"Could not get replay version for {absolute_path.name}: {e}")
                    continue

                # Prepare arguments for workers
                ports = [5001, 5002]
                placements = [(0, 0), (960, 0)]
                tasks = [] # Tasks are hardcoded at 2, because there are 2 perspectives. Hypothetically for team games, this would still be true because vision is shared between team members.
                           # It isn't exactly that simple though because you would have to work out which player_ids correspond to each team (maybe it's just 1 + 2 vs. 3 + 4).
                for i in range(2):
                    player_id = i + 1
                    task_args = (
                        absolute_path, player_id, ports[i], base_build, data_version, 
                        args.start, args.end, args.interval, placements[i]
                    )
                    tasks.append(task_args)

                # Run workers and collect results
                with multiprocessing.Pool(processes=num_processes) as pool:
                    results = pool.map(process_perspective_wrapper, tasks)

                # Check for failures
                if any(r is None for r in results):
                    logger.error(f"A process failed for replay {rp.name}. Cleaning up output directory.")
                    rm_failed_extraction(game_output_dir, logger)
                    continue # Move to the next replay
                else:
                    # Consolidate successful results
                    
                    # Earlier check for None results passed, these asserts are always valid by definition of the if statement. They are included to make the linter happy.
                    assert results[0] is not None
                    assert results[1] is not None

                    # Unpack results
                    p1_units_df, p1_deaths_df, p1_resources_df, p1_upgrades_df = results[0]
                    p2_units_df, p2_deaths_df, p2_resources_df, p2_upgrades_df = results[1]

                    # A successful run can never have empty resource data (because 0 minerals != null minerals).
                    if p1_resources_df.empty or p2_resources_df.empty:
                        logger.error(f"A process for replay {rp.name} returned empty resource data. This is impossible. Cleaning up output directory.")
                        rm_failed_extraction(game_output_dir, logger)
                        continue # Move to the next replay

                    # A successful run can never have empty unit data (because of starting workers and bases).
                    if p1_units_df.empty or p2_units_df.empty:
                        logger.error(f"A process for replay {rp.name} returned empty unit data. This is impossible. Cleaning up output directory.")
                        rm_failed_extraction(game_output_dir, logger)
                        continue # Move to the next replay

                    logger.info(f"Consolidating data for {game_output_dir.name}...")

                    # Consolidate Unit data
                    p1_units_df["is_visible_to_player_1"] = True
                    p2_units_df["is_visible_to_player_2"] = True
                    
                    combined_units_df = pd.concat([p1_units_df, p2_units_df], ignore_index=True)
                    
                    bool_cols = ["is_visible_to_player_1", "is_visible_to_player_2"]
                    for col in bool_cols:
                        combined_units_df[col] = combined_units_df[col].astype('boolean').fillna(False).astype(bool)
                    # Handle situations where units leave vision between the logging intervals:
                    combined_units_df.loc[combined_units_df["player_id"] == 1, "is_visible_to_player_1"] = True
                    combined_units_df.loc[combined_units_df["player_id"] == 2, "is_visible_to_player_2"] = True
                    # NB: This does not apply to neutral units in the same way.

                    agg_dict = {col: 'first' for col in combined_units_df.columns if col not in bool_cols}
                    for col in bool_cols:
                        agg_dict[col] = 'max'
                    
                    final_units_df = combined_units_df.groupby(["timestamp", "unit_tag"], as_index=False).agg(agg_dict)
                    final_units_df["is_ground_truth_for_player_1"] = final_units_df["player_id"] == 1
                    final_units_df["is_ground_truth_for_player_2"] = final_units_df["player_id"] == 2
                    final_units_df["is_neutral"] = ~final_units_df["player_id"].isin([1, 2])

                    final_units_df = exh.optimize_unit_dtypes(final_units_df)
                    final_units_path = game_output_dir / "units.parquet"
                    final_units_df.to_parquet(final_units_path)
                    logger.info(f"Successfully created consolidated units file: {final_units_path}")

                    # Consolidate Death data
                    if not p1_deaths_df.empty:
                        p1_deaths_df["is_visible_to_player_1"] = True
                    if not p2_deaths_df.empty:
                        p2_deaths_df["is_visible_to_player_2"] = True

                    death_dfs = [df for df in [p1_deaths_df, p2_deaths_df] if not df.empty]
                    if death_dfs:
                        combined_deaths_df = pd.concat(death_dfs, ignore_index=True)
                        
                        death_bool_cols = ["is_visible_to_player_1", "is_visible_to_player_2"]
                        for col in death_bool_cols:
                            if col not in combined_deaths_df.columns:
                                combined_deaths_df[col] = False
                            else:
                                combined_deaths_df[col] = combined_deaths_df[col].astype('boolean').fillna(False).astype(bool)

                        death_agg_dict = {col: 'first' for col in combined_deaths_df.columns if col not in death_bool_cols}
                        for col in death_bool_cols:
                            death_agg_dict[col] = 'max'

                        final_deaths_df = combined_deaths_df.groupby(["timestamp", "unit_tag"], as_index=False).agg(death_agg_dict)
                        
                        final_deaths_df = exh.optimize_death_dtypes(final_deaths_df)
                        final_deaths_path = game_output_dir / "deaths.parquet"
                        final_deaths_df.to_parquet(final_deaths_path)
                        logger.info(f"Successfully created consolidated deaths file: {final_deaths_path}")

                    # Consolidate Resources data
                    p1_resources_df.rename(columns={"minerals": "p1_minerals","vespene": "p1_vespene","supply_cap": "p1_supply_cap","supply_used": "p1_supply_used","supply_army": "p1_supply_army"}, inplace = True)
                    p2_resources_df.rename(columns={"minerals": "p2_minerals","vespene": "p2_vespene","supply_cap": "p2_supply_cap","supply_used": "p2_supply_used","supply_army": "p2_supply_army"}, inplace = True)

                    # Double supply values to make 0.5 supply values integers. Supply values can now become uint16_t.
                    supply_cols = ['p1_supply_cap', 'p1_supply_used','p1_supply_army']
                    p1_resources_df[supply_cols] = p1_resources_df[supply_cols] * 2
                    supply_cols = ['p2_supply_cap', 'p2_supply_used','p2_supply_army']
                    p2_resources_df[supply_cols] = p2_resources_df[supply_cols] * 2

                    # Fill missing (in case of desync) then merge.
                    combined_resources_df = pd.merge(p1_resources_df, p2_resources_df, on= 'timestamp', how= 'outer')
                    combined_resources_df.sort_values(by='timestamp', inplace=True)
                    combined_resources_df.ffill(inplace=True)

                    # Optimize final DF and save.
                    final_resources_df = exh.optimize_resource_dtypes(combined_resources_df)
                    final_resources_path = game_output_dir / "resources.parquet"
                    final_resources_df.to_parquet(final_resources_path)
                    logger.info(f"Successfully created consolidated resources file: {final_resources_path}")

                    # Optimize upgrade data and save.
                    upgrade_dfs = [df for df in [p1_upgrades_df, p2_upgrades_df] if not df.empty]
                    if upgrade_dfs:
                        combined_upgrades_df = pd.concat(upgrade_dfs, ignore_index=True)
                        combined_upgrades_df.sort_values(by='time_completed', inplace=True)
                        final_upgrades_path = game_output_dir / "upgrades.parquet"
                        final_upgrades_df = exh.optimize_upgrade_dtypes(combined_upgrades_df)
                        final_upgrades_df.to_parquet(final_upgrades_path)
                        logger.info(f"Successfully created upgrades file: {final_upgrades_path}")
                    else:
                        logger.info(f"No upgrades found in game {game_num}.")

            except Exception as e:
                # Log error for a single replay (e.g. client crash) and continue
                logger.error(f"Failed to process replay {rp.name}. Error: {e}")