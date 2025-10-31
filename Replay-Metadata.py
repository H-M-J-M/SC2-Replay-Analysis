import mpyq
import json
from pathlib import Path
from io import BytesIO
import argparse
import re
from loguru import logger

def get_replay_info(replay_path: str | Path, output_path: Path | None = None):
    with Path(replay_path).open("rb") as f:
        replay_data = f.read()
        replay_io = BytesIO()
        replay_io.write(replay_data)
        replay_io.seek(0)
        archive = mpyq.MPQArchive(replay_io).extract()
        metadata = json.loads(archive[b"replay.gamemetadata.json"].decode("utf-8")) # pyright: ignore[reportOptionalMemberAccess]
        
        if output_path:
            with open(output_path, "w") as out_f:
                json.dump(metadata, out_f, indent=4)
            logger.info(f"Successfully wrote metadata to {output_path}")
        else:
            print(json.dumps(metadata, indent=4))

if __name__ == "__main__":
    logger.add("replay_metadata.log", level="INFO", rotation="5 MB", retention=5, format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}", enqueue=True)
    parser = argparse.ArgumentParser(
        description="A python tool for extracting game metadata from a starcraft 2 replay."
    )

    parser.add_argument("replay", nargs='?', default=None, type=str, help="The replay number, filename, or full path. If omitted, all new replays will be processed.")
    parser.add_argument("--no-file", help="Do not write output to a file, print to console instead.", action="store_true")
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
        
        if not replays_dir.is_dir():
            logger.error("The 'Replays' directory was not found.")
            exit()

        for replay_file in replays_dir.glob("*.SC2Replay"):
            replay_paths_to_process.append(replay_file)

    # Process all collected paths
    if not replay_paths_to_process:
        logger.info("No replays found or no new replays to process.")
    else:
        logger.info(f"Found {len(replay_paths_to_process)} replay(s) to process.")
        
        for rp in replay_paths_to_process:
            try:
                absolute_path = rp.resolve()
                if not absolute_path.is_file():
                    logger.error(f"Replay file not found at path: {absolute_path}")
                    continue
                
                output_path = None
                if not args.no_file:
                    match = re.search(r"^(\d+)_", absolute_path.name)
                    if match:
                        game_num = match.group(1)
                        output_dir = Path("Output") / game_num
                        output_dir.mkdir(parents=True, exist_ok=True)
                        output_path = output_dir / f"{game_num}_info.json"

                logger.info(f"Processing {absolute_path.name}...")
                get_replay_info(absolute_path, output_path)

            except Exception as e:
                logger.error(f"Failed to process replay {rp.name}. Error: {e}")
