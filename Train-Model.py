import argparse
import pandas as pd
import importlib
import sys
from pathlib import Path
from datetime import datetime
from sklearn.model_selection import GroupShuffleSplit
from loguru import logger

log_dir = Path("logs")

# Add the ModelScripts directory to the Python path
MODEL_SCRIPTS_DIR = Path(__file__).parent / 'ModelScripts'
sys.path.append(str(MODEL_SCRIPTS_DIR))

def main():
    parser = argparse.ArgumentParser(description="Train and evaluate a machine learning model.")
    parser.add_argument("features_csv_path", type=str, help="Absolute path to the input CSV file containing engineered features.")
    parser.add_argument("model_script_name", type=str, help="Name of the model script to use from the ModelScripts/ directory (without .py).")
    parser.add_argument("--visualize", "-v", action="store_true", help="Generate and save visualizations of the results.")
    parser.add_argument("--save", "-s", action="store_true", help="Save the trained model to the OutputModels/ directory.")
    args = parser.parse_args()

    # Load data
    logger.info(f"Loading data from: {args.features_csv_path}")
    try:
        df = pd.read_csv(args.features_csv_path)
    except FileNotFoundError:
        logger.error(f"File not found: {args.features_csv_path}")
        return

    # Load ModelScript
    logger.info(f"Loading model script: {args.model_script_name}")
    try:
        model_module = importlib.import_module(args.model_script_name)
        model_script_class = getattr(model_module, 'ModelScript')
        model_script = model_script_class()
    except (ImportError, AttributeError) as e:
        logger.error(f"Could not load ModelScript from 'ModelScripts/{args.model_script_name}.py'. Error: {e}")
        return

    # Split data using GroupShuffleSplit, grouping by replay number. (found to perform better when both perspectives are being trained on)
    logger.debug("Splitting data into training and testing sets based on replay_id...")
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    
    groups = df['replay_id']
    train_idx, test_idx = next(gss.split(df, groups=groups))
    
    train_df = df.iloc[train_idx]
    test_df = df.iloc[test_idx]

    # Prepare Data
    logger.debug("Preparing training data...")
    X_train, y_train = model_script.prepare_data(train_df)

    logger.debug("Preparing testing data...")
    X_test, y_test = model_script.prepare_data(test_df)


    # Train the model
    logger.debug("Instantiating model...")
    model = model_script.get_model()

    logger.info("Training model...")
    model.fit(X_train, y_train)

    # Evaluate the model
    logger.info("Evaluating model on the test set...")
    model_script.evaluate_model(model, X_test, y_test)

    # Save model
    #TODO Look into compressing the model files.
    if args.save:
        output_models_dir = Path(__file__).parent / "OutputModels"
        output_models_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        model_filename = f"{args.model_script_name}_{timestamp}.txt"
        model_path = output_models_dir / model_filename
        
        logger.debug(f"Saving model to: {model_path}")
        model.booster_.save_model(model_path)
        logger.success(f"Model saved to: {model_path}")

    # Visualize results (optional)
    if args.visualize:
        logger.info("Generating visualizations...")
        output_vis_dir = Path(__file__).parent / "OutputVisualizations"
        output_vis_dir.mkdir(exist_ok=True)
        model_script.visualize_results(model, X_test, y_test, str(output_vis_dir))

    logger.success("Training and evaluation complete.")

if __name__ == "__main__":
    # Configure logging
    logger.add(log_dir / "train_model.log", rotation="10 MB", level="INFO")
    main()
