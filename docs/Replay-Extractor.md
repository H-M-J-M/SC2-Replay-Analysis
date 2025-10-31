# Replay Extractor Usage

Extracts detailed unit and game state data from StarCraft II replay files. It processes each player's perspective separately and in parallel to generate detailed logs.

## Synopsis

`py Replay-Extractor.py [replay_identifier] [options]`

## Description

This script can be run in two primary modes:

*   **Batch Mode:** When run without a `replay_identifier`, the script will automatically find and process all new replays in the `Replays/` directory. A replay is considered "new" if there is no corresponding output directory in the `Output/` folder.

*   **Single Replay Mode:** By providing a `replay_identifier`, you can process a single, specific replay. The identifier can be one of the following:
    *   **Match ID:** The numerical ID from a site like AIArena (e.g., `4309642`).
    *   **Filename:** The full name of the replay file (e.g., `4299043_Xena_negativeZero_LeyLinesAIE_v3.SC2Replay`).
    *   **Full Path:** An absolute path to the replay file on your system.

### Stopping a Batch Process

There are two ways to stop a batch process before it completes:

*   **Graceful Stop:** Create an empty file named `STOP` in the project's root directory. The script will finish processing the current replay and then abort the batch before starting the next one.

*   **Immediate Stop:** To stop the currently running replay and exit the entire batch process immediately, you must first create the `STOP` file and then press `Ctrl+C` in the terminal. The `python-sc2` library, which this script uses, has special handling for the `Ctrl+C` command (SIGINT). It will stop the active replay, allowing the main script to proceed, which will then detect the `STOP` file and exit.

## Options

*   `-s, --start SECONDS`
    *   The in-game time, in seconds, to begin recording data. Defaults to `0`.
*   `-e, --end SECONDS`
    *   The in-game time, in seconds, to stop recording data. Defaults to `7200` (2 hours).
*   `-i, --interval STEPS`
    *   The number of game steps between each data record. A game step is a very small unit of in-game time. Defaults to `20`.
*   `--single-thread`
    *   Disables parallel processing and runs the extraction for both player perspectives in a single thread, one after the other. By default, the script runs in parallel.

## Output Files

The script generates several CSV files for each processed replay, located in a subdirectory named after the game's match ID within the `Output/` directory (e.g., `Output/4309642/`).

The file naming convention is as follows:

*   `{game_id}_{player_name}_{map_name}_ground-truth.csv`: Contains all units belonging to the player whose perspective is being analyzed.
*   `{game_id}_{player_name}_{map_name}_observed-by-{observer_name}.csv`: Contains the opponent's units that are visible to the observing player.
*   `{game_id}_player-id-{id}_{map_name}_observed-by-{observer_name}.csv`: Contains neutral units on the map (e.g., mineral fields, vespene geysers) as seen by the observing player.

### CSV File Format

The output files are in CSV (Comma-Separated Values) format. Each file includes a header row that specifies the data in each column. Each row corresponds to a single unit at a specific in-game timestamp, providing a snapshot of its state. The exact columns may vary as the project evolves, but they will always be described by the header row in each file.

## Examples

*   **Process all new replays with default settings:**
    ```sh
    py Replay-Extractor.py
    ```

*   **Process a specific replay by ID with a custom time window:**
    ```sh
    py Replay-Extractor.py 4309642 -s 120 -e 300
    ```

*   **Process a replay using only a single thread:**
    ```sh
    py Replay-Extractor.py 4309642 --single-thread
    ```
