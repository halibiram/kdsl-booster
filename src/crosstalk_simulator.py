import logging
import pandas as pd
from src.advanced_dsl_physics import AdvancedDSLPhysics

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CableBundleSimulator:
    """
    Simulates the performance of multiple DSL lines within a single cable bundle,
    focusing on the impact of Far-End Crosstalk (FEXT) on achievable bitrates.
    """
    def __init__(self, num_pairs: int, distance_m: int, profile: str = '17a', cable_model: str = 'etsi_05mm'):
        """
        Initializes the cable bundle simulator.

        Args:
            num_pairs: The total number of twisted pairs in the cable bundle.
            distance_m: The length of the cable in meters.
            profile: The VDSL2 profile to be used for all lines.
            cable_model: The cable model to be used for all lines.
        """
        if num_pairs < 2:
            raise ValueError("Cable bundle must have at least 2 pairs to simulate crosstalk.")

        self.num_pairs = num_pairs
        self.distance_m = distance_m
        self.profile = profile
        self.cable_model = cable_model
        self.physics = AdvancedDSLPhysics(profile=self.profile, cable_model=self.cable_model)
        logging.info(f"Initialized Cable Bundle Simulator: {num_pairs} pairs, {distance_m}m, profile {profile}, model '{cable_model}'.")

    def run_simulation(self) -> pd.DataFrame:
        """
        Runs the simulation for the entire cable bundle.

        It calculates the performance of each line under two conditions:
        1. In isolation (no crosstalk).
        2. As a "victim" line, affected by FEXT from all other lines in the bundle.

        Returns:
            A pandas DataFrame containing the simulation results for each line.
        """
        logging.info(f"Starting simulation for {self.num_pairs}-pair bundle...")
        results = []

        # In this model, all other lines are considered disturbers.
        n_disturbers = self.num_pairs - 1

        # First, calculate the ideal bitrate with no crosstalk
        ideal_bitrate = self.physics.calculate_max_bitrate(
            distance_m=self.distance_m,
            n_disturbers=0
        )

        # Then, calculate the bitrate when subjected to FEXT from all other pairs
        crosstalk_bitrate = self.physics.calculate_max_bitrate(
            distance_m=self.distance_m,
            n_disturbers=n_disturbers
        )

        for i in range(self.num_pairs):
            line_id = i + 1
            performance_loss = ideal_bitrate - crosstalk_bitrate
            performance_loss_percent = (performance_loss / ideal_bitrate) * 100 if ideal_bitrate > 0 else 0

            results.append({
                "Line ID": line_id,
                "Distance (m)": self.distance_m,
                "Bitrate (No Crosstalk) Mbps": ideal_bitrate,
                "Bitrate (With FEXT) Mbps": crosstalk_bitrate,
                "Performance Loss (Mbps)": performance_loss,
                "Performance Loss (%)": performance_loss_percent
            })

        logging.info("Simulation complete.")

        # Create a pandas DataFrame for better visualization
        df = pd.DataFrame(results)
        df.set_index("Line ID", inplace=True)

        # Calculate and add summary statistics
        summary = {
            "Distance (m)": self.distance_m,
            "Bitrate (No Crosstalk) Mbps": df["Bitrate (No Crosstalk) Mbps"].mean(),
            "Bitrate (With FEXT) Mbps": df["Bitrate (With FEXT) Mbps"].mean(),
            "Performance Loss (Mbps)": df["Performance Loss (Mbps)"].mean(),
            "Performance Loss (%)": df["Performance Loss (%)"].mean()
        }
        df.loc['Average'] = summary

        return df.round(2)