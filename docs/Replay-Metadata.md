# Replay Metadata Usage

Extracts game metadata from StarCraft II replay files.

## Synopsis

`py Replay-Metadata.py [replay_identifier] [options]`

## Description

This script can be run in two modes:

*   **Batch Mode:** Run without a `replay_identifier` to process all replays in the `Replays/` directory. For each replay, it creates a corresponding JSON file in the `Output/<game_id>/` directory. By default, already processed replays are skipped.

*   **Single Replay Mode:** Provide a `replay_identifier` to process one replay. This can be a match ID (`4309642`), filename, or full path.

## Options

*   `--no-file`: Prints the metadata to the console instead of writing to a file.
*   `--regen`: Forces the regeneration of metadata for specified replays, even if the output file already exists.

## Examples

*   **Process all new replays and write to files:**
    ```sh
    py Replay-Metadata.py
    ```

*   **Process a specific replay by ID and write to a file:**
    ```sh
    py Replay-Metadata.py 4309642
    ```

*   **Process a specific replay and print to the console:**
    ```sh
    py Replay-Metadata.py 4309642 --no-file
    ```

*   **Force regeneration of metadata for all replays:**
    ```sh
    py Replay-Metadata.py --regen
    ```
