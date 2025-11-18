# Feature Engineer Usage

Orchestrates the feature engineering process by loading raw replay data, applying a set of feature generation rules, and outputting a final, flat CSV file for analysis.

## Synopsis

`py Feature-Engineer.py <feature_script_name> [options]`

## Description

This script serves as the bridge between raw, time-series data extracted by `Replay-Extractor.py` and a final, model-ready dataset. It dynamically loads a specified feature script from the `FeatureScripts/` directory and applies its logic to every processed replay in the `Output/` directory.

The core responsibility of this script is to:
1.  Discover all processed replay data in the `Output/` directory.
2.  For each replay, load all associated raw CSV files and metadata into a single `replay_bundle`.
3.  Pass this bundle to the specified feature script.
4.  Take the resulting features and append them to a single output CSV file.

### Feature Scripts

All feature generation logic resides in Python files within the `FeatureScripts/` directory. Each script must contain a class that inherits from `feature_script_base.py`. This design allows for rapid prototyping and testing of different feature sets without altering the main data processing pipeline.

## Options

*   `<feature_script_name>` (Required)
    *   The name of the Python file in the `FeatureScripts/` directory to use for feature generation (e.g., `simple_features` for `simple_features.py`).
*   `--limit N`
    *   Randomly select `N` replays to process from the `Output/` directory instead of all of them. This is extremely useful for quick, small-scale tests to verify that a feature script works before committing to a full run.

## Output Files

The script generates a single CSV file containing the engineered features from all processed replays. The file is placed in a subdirectory within `OutputFeatures/` named after the feature script used.

*   **Location:** `OutputFeatures/<feature_script_name>/`
*   **Filename:** `features_<timestamp>.csv` (e.g., `features_20251106-143000.csv`)

Each row in the output CSV corresponds to a single replay, and each column corresponds to a feature.

## Examples

*   **Run the `simple_features` script on all replays:**
    ```sh
    py Feature-Engineer.py simple_features
    ```

*   **Test the `my_features` script on a random sample of 20 replays:**
    ```sh
    py Feature-Engineer.py my_features --limit 20
    ```
