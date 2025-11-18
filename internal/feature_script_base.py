from abc import ABC, abstractmethod
import pandas as pd
from internal.exceptions import EssentialDataMissingError

class FeatureScriptBase(ABC):
    """
    Abstract Base Class for feature engineering scripts.
    """

    units: pd.DataFrame
    deaths: pd.DataFrame | None
    resources: pd.DataFrame
    upgrades: pd.DataFrame | None
    
    def _init_bundle(self, replay_bundle: dict):
        """Initializes the instance with the data bundle for a single replay."""

        self.metadata = replay_bundle.get("metadata", {})
        
        self.p1_name = replay_bundle.get("p1_name")
        self.p2_name = replay_bundle.get("p2_name")
        self.p1_id = replay_bundle.get("p1_id")
        self.p2_id = replay_bundle.get("p2_id")
        
        try:
            self.units = replay_bundle["units"]
            self.resources = replay_bundle["resources"]
        except KeyError as e:
            raise EssentialDataMissingError(f"Replay bundle is missing data: {e}.") from e

        self.deaths = replay_bundle.get("deaths")
        self.upgrades = replay_bundle.get("upgrades")

    @property
    def p1_race(self) -> str | None:
        """Returns the race of Player 1."""
        try:
            return self.metadata['Players'][0]['SelectedRace']
        except (KeyError, IndexError):
            return None

    @property
    def p2_race(self) -> str | None:
        """Returns the race of Player 2."""
        try:
            return self.metadata['Players'][1]['SelectedRace']
        except (KeyError, IndexError):
            return None

    @property
    def winner(self) -> int | None:
        """Returns the winning player number (1 or 2)."""
        try:
            for player in self.metadata.get('Players', []):
                if player.get('Result') == 'Win':
                    return player.get('PlayerID')
            return None
        except (KeyError, IndexError):
            return None

    @abstractmethod
    def process_replay(self, replay_bundle: dict, replay_id: str) -> pd.DataFrame:
        """
        This method must be implemented by all feature scripts.
        It processes the data bundle for a single replay and returns a summarized DataFrame.
        """
        pass