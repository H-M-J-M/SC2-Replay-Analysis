import argparse
from pathlib import Path
import pandas as pd
from loguru import logger
import sys
import importlib.util
import inspect
import json
import random
from datetime import datetime
from internal.feature_script_base import FeatureScriptBase
from internal.exceptions import EssentialDataMissingError

# Configure logger
log_dir = Path("logs")
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add(log_dir / "feature_engineer.log", rotation="10 MB", level="INFO")

def main():
    parser = argparse.ArgumentParser(description="Feature engineering script for StarCraft II replay data.")
    parser.add_argument("feature_script_name", type=str,
                        help="Name of the Python script in the 'FeatureScripts' directory (without .py extension).")
    parser.add_argument("--limit", type=int, default=None, help="Randomly select N replays to process instead of all of them.")
    parser.add_argument("--min-d", type=int, default=None, help="Skip replays shorter than this duration in seconds.")
    
    args = parser.parse_args()

    feature_script_path = Path("FeatureScripts") / f"{args.feature_script_name}.py"

    logger.info(f"Starting feature engineering with feature script: {feature_script_path}")

    # Load FeatureScript
    try:
        spec = importlib.util.spec_from_file_location("feature_definitions", str(feature_script_path))
        if spec is None:
            logger.error(f"Could not find or load feature script: {feature_script_path}")
            sys.exit(1)
        if spec.loader is None:
            logger.error(f"Could not determine a loader for feature script: {feature_script_path}")
            sys.exit(1)
        feature_module = importlib.util.module_from_spec(spec)
        sys.modules["feature_definitions"] = feature_module
        spec.loader.exec_module(feature_module)
        
        feature_class = None
        for name, obj in inspect.getmembers(feature_module, inspect.isclass):
            if issubclass(obj, FeatureScriptBase) and obj is not FeatureScriptBase:
                feature_class = obj
                break
        
        if not feature_class:
            logger.error(f"The feature script '{feature_script_path}' must contain a class that inherits from FeatureScriptBase.")
            sys.exit(1)
            
        feature_script_instance = feature_class()

    except FileNotFoundError:
        logger.error(f"Feature script not found: {feature_script_path}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error loading or executing feature script '{feature_script_path}': {e}")
        sys.exit(1)

    # Output file setup
    try:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = Path("OutputFeatures") / args.feature_script_name
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_filename = f"features_{timestamp}.csv"
        output_path = output_dir / output_filename
    except Exception as e:
        logger.error(f"Error setting up output path: {e}")
        sys.exit(1)

    # Replay processing loop
    is_first_write = True
    processed_count = 0
    raw_output_dir = Path("OutputRaw")
    replay_dirs = [entry.name for entry in raw_output_dir.iterdir() if entry.is_dir()]

    logger.info(f"Found {len(replay_dirs)} replay directories to process.")

    if args.limit and args.limit < len(replay_dirs):
        logger.info(f"Randomly selecting {args.limit} replays to process.")
        replay_dirs = random.sample(replay_dirs, args.limit)

    for replay_id in replay_dirs:
        replay_path = raw_output_dir / replay_id
        logger.info(f"Processing replay: {replay_id}")

        try:
            # Load metadata (now includes PlayerName from Replay-Metadata.py)
            info_file_path = list(replay_path.glob("*_info.json"))
            if not info_file_path:
                logger.warning(f"No _info.json file found for replay {replay_id}. Skipping.")
                continue
            with open(info_file_path[0], 'r') as f:
                metadata = json.load(f)

            # Filter by game duration
            if args.min_d is not None:
                duration = metadata.get("Duration", 0)
                if duration < args.min_d:
                    logger.info(f"Skipping replay {replay_id}: duration ({duration}s) is less than {args.min_d}s.")
                    continue

            # Extract player names and IDs from metadata
            p1_name, p2_name = None, None
            p1_id, p2_id = None, None

            for player_data in metadata.get('Players', []):
                if player_data.get('PlayerID') == 1:
                    p1_id = 1
                    p1_name = player_data.get('PlayerName')
                elif player_data.get('PlayerID') == 2:
                    p2_id = 2
                    p2_name = player_data.get('PlayerName')
            
            if not (p1_name and p2_name and p1_id and p2_id):
                logger.warning(f"Could not determine full player info from metadata for replay {replay_id}. Skipping.")
                continue

            # Load parquet data
            units_parquet_path = replay_path / "units.parquet"
            if not units_parquet_path.exists():
                logger.warning(f"No units.parquet file found for replay {replay_id}. Skipping.")
                continue
            full_unit_data = pd.read_parquet(units_parquet_path)
            # Add replay_id column to the unit data (useful for later phases)
            full_unit_data['replay_id'] = replay_id
            
            # Load resources.parquet (essential data)
            resources_parquet_path = replay_path / "resources.parquet"
            if not resources_parquet_path.exists():
                logger.warning(f"No resources.parquet file found for replay {replay_id}. Skipping.")
                continue
            consolidated_resource_data = pd.read_parquet(resources_parquet_path)
            consolidated_resource_data['replay_id'] = replay_id

            # Load deaths.parquet (optional data)
            deaths_parquet_path = replay_path / "deaths.parquet"
            consolidated_death_data = None
            if deaths_parquet_path.exists():
                consolidated_death_data = pd.read_parquet(deaths_parquet_path)
                consolidated_death_data['replay_id'] = replay_id

            # Load upgrades.parquet (optional data)
            upgrades_parquet_path = replay_path / "upgrades.parquet"
            consolidated_upgrade_data = None
            if upgrades_parquet_path.exists():
                consolidated_upgrade_data = pd.read_parquet(upgrades_parquet_path)
                consolidated_upgrade_data['replay_id'] = replay_id

            # Initialize the bundle and process the replay
            replay_bundle = {
                "metadata": metadata,
                "p1_name": p1_name,
                "p2_name": p2_name,
                "p1_id": p1_id,
                "p2_id": p2_id,
                "units": full_unit_data,
                "deaths": consolidated_death_data, # Will be None if file doesn't exist
                "resources": consolidated_resource_data,
                "upgrades": consolidated_upgrade_data # Will be None if file doesn't exist
            }

            feature_script_instance._init_bundle(replay_bundle)
            try:
                processed_df = feature_script_instance.process_replay(replay_bundle, replay_id)
            except EssentialDataMissingError as e:
                logger.error(f"A vital data file is missing for replay {replay_id}: {e}")
                logger.critical(f"Delete the folder for replay {replay_id} and re-run replay-extractor to fix this.")
                continue # Skip this replay and continue with the next
            except Exception as fe_e:
                logger.error(f"An unexpected error occurred in feature script '{args.feature_script_name}' for replay {replay_id}: {fe_e}")
                continue # Skip this replay and continue with the next

            # Append results to disk
            if processed_df is not None and not processed_df.empty:
                processed_df.to_csv(output_path, mode='a', header=is_first_write, index=False)
                if is_first_write:
                    is_first_write = False
                processed_count += 1
            else:
                logger.warning(f"No data returned from feature script for replay {replay_id}.")

        except Exception as e:
            logger.error(f"Failed to process replay {replay_id}: {e}")

    # Finalization
    if processed_count == 0:
        logger.error("No replays were successfully processed. No output file was generated.")
        # Clean up empty file if it was created
        if output_path.exists() and is_first_write:
            output_path.unlink()
        sys.exit(1)

    logger.info(f"Feature engineering process finished. {processed_count} replays processed.")
    logger.info(f"Engineered features saved to {output_path}.")

if __name__ == "__main__":
    main()

