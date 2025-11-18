# Py Replay Analysis

A collection of Python scripts for analyzing StarCraft II replay files, from raw data extraction to model training.

## Installation

1.  **Clone the Repository:**
    ```sh
    git clone https://github.com/your-username/Py-Replay-Analysis.git
    cd Py-Replay-Analysis
    ```

2.  **Install Python Dependencies:**
    It is recommended to use a virtual environment.
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

3.  **Install StarCraft II:**
    The `Replay-Extractor.py` script requires a local installation of the StarCraft II game client to analyze replays. You can download it from the official [Battle.net website](https://starcraft2.com/).

    **Important:** For the replay analysis to work, the StarCraft II client must have access to the map file (`.SC2Map`) on which the replay was played. You must place any required map files into the `maps` folder within your StarCraft II installation directory (if this folder doesn't exist you will need to create it). 

4.  **Install Graphviz (Optional):**
    If you plan to generate model visualizations (decision tree graphs), you will need to install Graphviz.
    -   Download and install the Graphviz software from the [official website](https://graphviz.org/download/).
    -   During installation, you will be prompted to add Graphviz to your PATH.

## Scripts

*   **`Replay-Extractor.py`**: Extracts detailed unit and game state data from replay files into parquet format.
*   **`Replay-Metadata.py`**: Extracts high-level game metadata (players, map, winner, etc.) from replay files.
*   **`Feature-Engineer.py`**: Runs the feature engineering process, converting raw data into a model-ready feature set. This process is specified in a FeatureScript.
*   **`Train-Model.py`**: Trains a LightGBM model on a set of engineered features, evaluates its performance, and saves the model. This process is specified in a ModelScript.

## Typical Workflow

### 1. Create Metadata

Run Replay-Metadata.py

```sh
py Replay-Metadata.py
```

### 2. Extract Raw Data

Process all (or just some) replays in the `Replays/` directory. The script will automatically skip replays that have already been processed. (This may take a while.)

```sh
py Replay-Extractor.py
```

### 2. Engineer Features

Run a feature script (e.g., `simple_features`) on the extracted raw data to produce a feature set for training.

```sh
py Feature-Engineer.py simple_features
```

### 3. Train a Model

Train a model using the newly generated feature file. The example below uses the `predict_winner` model script, generates visualizations (`-v`), and saves the final trained model (`-s`).

```sh
# Note: Replace the path with the actual path to your generated feature file.
py Train-Model.py OutputFeatures/simple_features/features_20251107-220000.csv predict_winner -v -s
```

## Documentation

For detailed usage, options, and examples for each script, please refer to the documentation in the `docs/` directory. An example FeatureScript and ModelScript is included in the repo. Together they can be used to train a LightGBM model that predicts the outcome of games, with 79% accuracy, based on the first 4 minutes of game data (your mileage may vary based on your training data). That model is included in the OutputModels folder.

## Troubleshooting
<b>Question:</b> A starcraft crash message appeared after Replay-Extractor completed processing a batch of replays. Do I need to restart the whole batch?
<details>
<summary><b>Answer: No</b>. <i>(click to expand)</i></summary>

Replay-Extractor has a roughly 1% failure rate when processing large batches of replays (caused by the SC2 engine crashing). The script should automatically detect when a replay fails to process and delete the corresponding output folder. If you encounter a StarCraft crash message, simply re-run `Replay-Extractor.py` once the batch has been stopped (by you or by completing). The script will identify the missing replay and process it again.  
If Replay-Extractor does not indentify the replay as missing you may need to manually delete the corresponding folder `\Output\[REPLAY NUMBER]`.
</details>