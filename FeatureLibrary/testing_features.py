import pandas as pd

class TestingFeaturesMixin:
    """
    A mixin class containing simple, verifiable feature calculations for testing the pipeline.
    """

    def count_p1_ground_truth_rows(self) -> int:
        """Counts the number of rows in the p1_pov ground_truth_units DataFrame."""
        try:
            df = self.bundle['p1_pov']['ground_truth_units']
            return len(df.index)
        except (KeyError, TypeError):
            return 0

    def get_p1_race_from_mixin(self) -> str | None:
        """Retrieves the race of Player 1 using the base class property."""
        return self.p1_race
