import pandas as pd
from loguru import logger
from internal.feature_script_base import FeatureScriptBase

class SimpleFeatures(FeatureScriptBase):
    def process_replay(self, replay_bundle: dict, replay_id: str) -> pd.DataFrame:
        self._init_bundle(replay_bundle)
        logger.info(f"Processing replay {replay_id}.")

        p1_win = (self.winner == 1)
        p2_win = (self.winner == 2)

        # Initialize features dictionaries
        p1_features = {
            'replay_id': replay_id,
            'pov_race': self.p1_race,
            'enemy_race': self.p2_race,
            'pov_ID': self.p1_name,
            'enemy_ID': self.p2_name,
            'win': p1_win,
            'workers3': 0,
            'army_supply3': 0,
            'workers_adv3': 0,
            'army_supply_adv3': 0,

            'workers4': 0,
            'army_supply4': 0,
            'workers_adv4': 0,
            'army_supply_adv4': 0,

            'workers_delta_34': 0,
            'army_supply_delta_34': 0,

            'mpm_2_4': 0,
            'vpm_2_4': 0,
            'mpm_adv_2_4': 0,
            'vpm_adv_2_4': 0,

            'max_mineral_bank_4m': 0,
            'max_vespene_bank_4m': 0,
        }
        p2_features = {
            'replay_id': replay_id,
            'pov_race': self.p2_race,
            'enemy_race': self.p1_race,
            'pov_ID': self.p2_name,
            'enemy_ID': self.p1_name,
            'win': p2_win,
            'workers3': 0,
            'army_supply3': 0,
            'workers_adv3': 0,
            'army_supply_adv3': 0,

            'workers4': 0,
            'army_supply4': 0,
            'workers_adv4': 0,
            'army_supply_adv4': 0,

            'workers_delta_34': 0,
            'army_supply_delta_34': 0,

            'mpm_2_4': 0,
            'vpm_2_4': 0,
            'mpm_adv_2_4': 0,
            'vpm_adv_2_4': 0,

            'max_mineral_bank_4m': 0,
            'max_vespene_bank_4m': 0,
        }

        # Helper to get supply counts at t seconds
        def get_supply_at_t(df: pd.DataFrame | None, time: int):
            if df is None or df.empty:
                return 0, 0, 0, 0 # p1_workers, p1_army, p2_workers, p2_army

            # Get the latest row at or before the specified time
            snapshot = df[df['timestamp'] <= time].iloc[-1]

            # Extract supply values
            p1_army_supply = snapshot.get('p1_supply_army', 0)
            p1_total_supply = snapshot.get('p1_supply_used', 0)
            p2_army_supply = snapshot.get('p2_supply_army', 0)
            p2_total_supply = snapshot.get('p2_supply_used', 0)

            # Worker supply is total used supply minus army supply.
            # The raw supply values are doubled to handle 0.5 supply units, so we divide by 2 to get the actual count.
            p1_worker_supply = (p1_total_supply - p1_army_supply) / 2
            p2_worker_supply = (p2_total_supply - p2_army_supply) / 2
            
            # Army supply also needs to be divided by 2
            p1_army_supply /= 2
            p2_army_supply /= 2

            return p1_worker_supply, p1_army_supply, p2_worker_supply, p2_army_supply

        # Helper to get resource collection rates between two times
        def get_collection_rates(df: pd.DataFrame | None, start_time: int, end_time: int):
            if df is None or df.empty:
                return 0, 0, 0, 0 # p1_mpm, p1_vpm, p2_mpm, p2_vpm

            start_snapshot = df[df['timestamp'] <= start_time].iloc[-1]
            end_snapshot = df[df['timestamp'] <= end_time].iloc[-1]

            p1_minerals_start = start_snapshot.get('p1_minerals', 0)
            p1_vespene_start = start_snapshot.get('p1_vespene', 0)
            p2_minerals_start = start_snapshot.get('p2_minerals', 0)
            p2_vespene_start = start_snapshot.get('p2_vespene', 0)

            p1_minerals_end = end_snapshot.get('p1_minerals', 0)
            p1_vespene_end = end_snapshot.get('p1_vespene', 0)
            p2_minerals_end = end_snapshot.get('p2_minerals', 0)
            p2_vespene_end = end_snapshot.get('p2_vespene', 0)

            # Calculate resources gathered during the interval, casting to signed integers to prevent overflow
            p1_minerals_gathered = int(p1_minerals_end) - int(p1_minerals_start)
            p1_vespene_gathered = int(p1_vespene_end) - int(p1_vespene_start)
            p2_minerals_gathered = int(p2_minerals_end) - int(p2_minerals_start)
            p2_vespene_gathered = int(p2_vespene_end) - int(p2_vespene_start)

            # Calculate rate per minute
            interval_minutes = (end_time - start_time) / 60
            p1_mpm = p1_minerals_gathered / interval_minutes
            p1_vpm = p1_vespene_gathered / interval_minutes
            p2_mpm = p2_minerals_gathered / interval_minutes
            p2_vpm = p2_vespene_gathered / interval_minutes

            return p1_mpm, p1_vpm, p2_mpm, p2_vpm

        # Helper to get the max resource bank for each player up to a certain time
        def get_max_bank(df: pd.DataFrame | None, end_time: int):
            if df is None or df.empty:
                return 0, 0, 0, 0 # p1_max_min, p1_max_vesp, p2_max_min, p2_max_vesp

            # Filter the dataframe up to the end time
            df_filtered = df[df['timestamp'] <= end_time]

            if df_filtered.empty:
                return 0, 0, 0, 0

            p1_max_minerals = df_filtered['p1_minerals'].max()
            p1_max_vespene = df_filtered['p1_vespene'].max()
            p2_max_minerals = df_filtered['p2_minerals'].max()
            p2_max_vespene = df_filtered['p2_vespene'].max()

            return p1_max_minerals, p1_max_vespene, p2_max_minerals, p2_max_vespene


        # Feature calculation

        # Get supply values at 3 and 4 minutes
        p1_workers3, p1_army_supply3, p2_workers3, p2_army_supply3 = get_supply_at_t(self.resources, (3*60))
        p1_workers4, p1_army_supply4, p2_workers4, p2_army_supply4 = get_supply_at_t(self.resources, (4*60))

        # Get resource collection rates between 2 and 4 minutes
        p1_mpm, p1_vpm, p2_mpm, p2_vpm = get_collection_rates(self.resources, (2*60), (4*60))

        # Get max resource bank up to 4 minutes
        p1_max_min, p1_max_vesp, p2_max_min, p2_max_vesp = get_max_bank(self.resources, (4*60))


        # --- Player 1 Feature Population ---
        # Time 3
        p1_features['workers3'] = p1_workers3
        p1_features['army_supply3'] = p1_army_supply3
        p1_features['workers_adv3'] = p1_workers3 - p2_workers3
        p1_features['army_supply_adv3'] = p1_army_supply3 - p2_army_supply3
        # Time 4
        p1_features['workers4'] = p1_workers4
        p1_features['army_supply4'] = p1_army_supply4
        p1_features['workers_adv4'] = p1_workers4 - p2_workers4
        p1_features['army_supply_adv4'] = p1_army_supply4 - p2_army_supply4
        # Delta
        p1_features['workers_delta_34'] = p1_workers4 - p1_workers3
        p1_features['army_supply_delta_34'] = p1_army_supply4 - p1_army_supply3
        # Collection Rates
        p1_features['mpm_2_4'] = p1_mpm
        p1_features['vpm_2_4'] = p1_vpm
        p1_features['mpm_adv_2_4'] = p1_mpm - p2_mpm
        p1_features['vpm_adv_2_4'] = p1_vpm - p2_vpm
        # Max Bank
        p1_features['max_mineral_bank_4m'] = p1_max_min
        p1_features['max_vespene_bank_4m'] = p1_max_vesp


        # Player 2 feature population
        # Time 3
        p2_features['workers3'] = p2_workers3
        p2_features['army_supply3'] = p2_army_supply3
        p2_features['workers_adv3'] = p2_workers3 - p1_workers3
        p2_features['army_supply_adv3'] = p2_army_supply3 - p1_army_supply3
        # Time 4
        p2_features['workers4'] = p2_workers4
        p2_features['army_supply4'] = p2_army_supply4
        p2_features['workers_adv4'] = p2_workers4 - p1_workers4
        p2_features['army_supply_adv4'] = p2_army_supply4 - p1_army_supply4
        # Delta
        p2_features['workers_delta_34'] = p2_workers4 - p2_workers3
        p2_features['army_supply_delta_34'] = p2_army_supply4 - p2_army_supply3
        # Collection Rates
        p2_features['mpm_2_4'] = p2_mpm
        p2_features['vpm_2_4'] = p2_vpm
        p2_features['mpm_adv_2_4'] = p2_mpm - p1_mpm
        p2_features['vpm_adv_2_4'] = p2_vpm - p1_vpm
        # Max Bank
        p2_features['max_mineral_bank_4m'] = p2_max_min
        p2_features['max_vespene_bank_4m'] = p2_max_vesp


        df = pd.DataFrame([p1_features, p2_features])
        df['pov_race'] = df['pov_race'].astype('category')
        df['enemy_race'] = df['enemy_race'].astype('category')
        df['pov_ID'] = df['pov_ID'].astype('category')
        df['enemy_ID'] = df['enemy_ID'].astype('category')
        
        return df
