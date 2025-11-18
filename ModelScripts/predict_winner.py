
import pandas as pd
from lightgbm import LGBMClassifier
from internal.model_script_base import ModelScriptBase

class ModelScript(ModelScriptBase):
    """
    A model script for predicting the winner based on simple features.
    """

    def prepare_data(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
        """
        Prepares the data by selecting the features and the target.
        """

        y = df['win']

        feature_columns = [
            'pov_ID',
            'enemy_ID',
            'pov_race',
            'enemy_race',
            'workers3',
            'army_supply3',
            'workers_adv3',
            'army_supply_adv3',

            'workers4',
            'army_supply4',
            'workers_adv4',
            'army_supply_adv4',

            'workers_delta_34',
            'army_supply_delta_34',

            'mpm_2_4',
            'vpm_2_4',
            'mpm_adv_2_4',
            'vpm_adv_2_4',
            'max_mineral_bank_4m',
            'max_vespene_bank_4m',
        ]
        X = df[feature_columns].copy()

        # Convert race and name columns to category dtype for LightGBM's native handling
        X['pov_ID'] = X['pov_ID'].astype('category')
        X['enemy_ID'] = X['enemy_ID'].astype('category')
        X['pov_race'] = X['pov_race'].astype('category')
        X['enemy_race'] = X['enemy_race'].astype('category')

        # Use one-hot encoding for the race columns
        #X = pd.get_dummies(X, columns=['pov_race', 'enemy_race'], drop_first=True)

        return X, y

    def get_model(self):
        """
        Instantiates and returns an untrained LGBMClassifier.
        """

        model = LGBMClassifier(random_state=42)
        return model

