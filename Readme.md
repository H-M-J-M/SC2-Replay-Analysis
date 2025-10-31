# Replay Extractor Usage

Extracts detailed unit data from StarCraft II replay files. Processes both player's perspectives separately in parallel (this can be disabled).

## Synopsis

`py Replay-Extractor.py [replay_identifier] [options]`

## Description

This script can be run in two modes:

*   **Batch Mode:** Run without a `replay_identifier` to process all new replays in the `Replays/` directory.
    *   **To Stop Early:** Create an empty file named `STOP` in the project root. The script will abort before starting the next replay. To exit immediately, create the `STOP` file and then press `Ctrl+C` in the command line.

*   **Single Replay Mode:** Provide a `replay_identifier` to process one replay. This can be a match ID (`4309642`), filename, or full path.

## Options

*   `-s, --start SECONDS`: Time (seconds) to start recording. Default: `0`.
*   `-e, --end SECONDS`: Time (seconds) to stop recording. Default: `7200`.
*   `-i, --interval STEPS`: Game steps between records. Default: `20`.
*   `--single-thread`: Run extraction in a single thread. (Default is parallel).

## Examples

*   **Process all new replays:**
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