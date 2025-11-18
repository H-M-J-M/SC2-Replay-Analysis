
from abc import ABC, abstractmethod
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import pandas as pd
import lightgbm

# Optional imports for visualization
try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    import graphviz
    VISUALIZATIONS_AVAILABLE = True
except ImportError:
    VISUALIZATIONS_AVAILABLE = False

class ModelScriptBase(ABC):
    """
    An abstract base class for defining model training scripts.
    It provides a standardized structure and reusable evaluation logic.
    """

    @abstractmethod
    def prepare_data(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
        """
        Prepares the data for modeling.

        This method should be implemented by the subclass to select the feature
        columns (X) and the target column (y), and perform any necessary
        transformations.

        Args:
            df: The input DataFrame.

        Returns:
            A tuple containing the features (X) and the target (y).
        """
        pass

    @abstractmethod
    def get_model(self):
        """
        Instantiates and returns an untrained scikit-learn compatible model.

        This method should be implemented by the subclass to define the model
        and its hyperparameters.

        Returns:
            An untrained scikit-learn compatible model instance.
        """
        pass

    def evaluate_model(self, model, X_test: pd.DataFrame, y_test: pd.Series):
        """
        Evaluates the trained model and prints a standardized report.

        Args:
            model: The trained model instance.
            X_test: The test features.
            y_test: The test target.
        """
        print("--- Model Evaluation ---")
        
        predictions = model.predict(X_test)
        
        # Metrics
        accuracy = accuracy_score(y_test, predictions)
        print(f"Accuracy: {accuracy:.4f}\n")
        
        print("Classification Report:")
        print(classification_report(y_test, predictions))
        
        print("Confusion Matrix:")
        print(confusion_matrix(y_test, predictions))
        
        # Feature importance
        if hasattr(model, 'feature_importances_'):
            print("\n--- Feature Importances ---")
            importances = model.feature_importances_
            feature_names = X_test.columns
            
            feature_importance_df = pd.DataFrame({
                'feature': feature_names,
                'importance': importances
            }).sort_values(by='importance', ascending=False)
            
            print(feature_importance_df)

    def visualize_results(self, model, X_test: pd.DataFrame, y_test: pd.Series, output_folder: str):
        """
        Generates and saves visualizations for the model's performance.

        Args:
            model: The trained model instance.
            X_test: The test features.
            y_test: The test target.
            output_folder: The folder to save the visualizations in.
        """
        if not VISUALIZATIONS_AVAILABLE:
            print("\nPlease install matplotlib, seaborn, and graphviz to generate visualizations (e.g., 'pip install matplotlib seaborn graphviz').")
            return

        # Feature importance bar chart
        if hasattr(model, 'feature_importances_'):
            plt.figure(figsize=(10, 6))
            importances = model.feature_importances_
            feature_names = X_test.columns
            feature_importance_df = pd.DataFrame({
                'feature': feature_names,
                'importance': importances
            }).sort_values(by='importance', ascending=False)
            
            sns.barplot(x='feature', y='importance', data=feature_importance_df, orient="v")
            plt.title('Feature Importance')
            plt.tight_layout()
            plt.savefig(f"{output_folder}/feature_importance.png")
            print(f"\nSaved feature importance plot to {output_folder}/feature_importance.png")
            plt.close()

        # Confusion matrix heatmap
        plt.figure(figsize=(8, 6))
        predictions = model.predict(X_test)
        cm = confusion_matrix(y_test, predictions)
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=['Loss', 'Win'], yticklabels=['Loss', 'Win'])
        plt.title('Confusion Matrix')
        plt.xlabel('Predicted Label')
        plt.ylabel('True Label')
        plt.tight_layout()
        plt.savefig(f"{output_folder}/confusion_matrix.png")
        print(f"Saved confusion matrix plot to {output_folder}/confusion_matrix.png")
        plt.close()

        # Decision tree plot of the first tree
        if isinstance(model, lightgbm.LGBMClassifier):
            plt.figure(figsize=(20, 10))
            lightgbm.plot_tree(model, ax=plt.gca(), show_info=['split_gain', 'internal_value', 'internal_count', 'leaf_count'])
            plt.title('Decision Tree')
            plt.tight_layout()
            plt.savefig(f"{output_folder}/decision_tree.png")
            print(f"Saved decision tree plot to {output_folder}/decision_tree.png")
            plt.close()
