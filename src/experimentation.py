"""
This module provides a framework for running automated experiments.

It allows for systematic testing of different DSL parameter combinations,
measuring their impact on performance, and collecting data. This data
is crucial for later analysis and for training machine learning models
to find optimal settings.
"""

from src.spoofing import KernelDSLManipulator


class ExperimentRunner:
    """
    Manages and executes automated experiments to test DSL parameters.
    """

    def __init__(self, manipulator: KernelDSLManipulator):
        """
        Initializes the ExperimentRunner.

        Args:
            manipulator: An instance of KernelDSLManipulator to apply settings.
        """
        self.manipulator = manipulator
        self.results = []

    def parameter_sweep(self, rate_range, distance_range):
        """
        Runs a series of experiments by sweeping through parameter ranges.

        Args:
            rate_range (iterable): A range or list of target rates (Mbps) to test.
            distance_range (iterable): A range or list of target distances (m) to test.
        """
        print(f"Starting parameter sweep for {len(rate_range)} rates and {len(distance_range)} distances...")
        self.results = []  # Clear previous results

        for rate in rate_range:
            for distance in distance_range:
                print(f"--- Running experiment: Rate={rate} Mbps, Distance={distance}m ---")

                # Apply the new profile using the manipulator
                result = self.manipulator.set_target_profile(
                    target_rate_mbps=rate,
                    target_distance_m=distance
                )

                # Simulate measuring the actual performance
                measured_speed = self._measure_performance(result, rate)

                # Store the outcome
                self.results.append({
                    "target_rate_mbps": rate,
                    "target_distance_m": distance,
                    "manipulation_success": result,
                    "measured_speed_mbps": measured_speed,
                })

        print("Parameter sweep complete.")

    def _measure_performance(
        self, manipulation_result: dict, target_rate_mbps: float
    ) -> float:
        """
        Simulates a performance measurement (e.g., a speed test).

        In a real-world scenario, this would trigger a tool like iperf3 or a
        web-based speed test and parse the result. Here, we simulate it.

        Args:
            manipulation_result: The result from the manipulator.
            target_rate_mbps: The rate that was targeted in this experiment.

        Returns:
            The simulated speed in Mbps. Returns 0 if manipulation failed.
        """
        if not all(manipulation_result.values()):
            print("Manipulation failed, performance measurement skipped. Speed: 0 Mbps")
            return 0.0

        # This is a highly simplified simulation. We assume the spoofing was
        # 95% effective in achieving the target rate.
        simulated_speed = target_rate_mbps * 0.95
        print(f"Simulated speed test result: {simulated_speed:.2f} Mbps")
        return round(simulated_speed, 2)