"""
DSL Bypass Ultra - Main Execution Script

This script demonstrates the full end-to-end capabilities of the project.
It simulates the entire workflow:
1. Establishes a (mocked) SSH connection.
2. Initializes the core components: KernelDSLManipulator, ExperimentRunner, and AIOptimizer.
3. Runs an automated parameter sweep to collect performance data.
4. Trains an AI model on the collected data.
5. Uses the trained model to predict optimal parameters for a target speed.
"""
from unittest.mock import MagicMock
import numpy as np

from src.spoofing import KernelDSLManipulator
from src.experimentation import ExperimentRunner
from src.ai_optimizer import AIOptimizer

def main():
    print("🚀 Starting DSL Bypass Ultra Demonstration 🚀")

    # --- 1. Setup and Initialization ---
    # In a real scenario, this would be a live SSH connection.
    # For this demo, we mock the interface to allow the script to run.
    print("\n[Step 1] Initializing components...")
    mock_ssh_interface = MagicMock()
    mock_ssh_interface.execute_command.return_value = ("-", "") # Default mock response

    # Initialize the core components with baseline performance values
    # These would typically be read from the device initially.
    manipulator = KernelDSLManipulator(
        ssh_interface=mock_ssh_interface,
        base_rate_mbps=30,
        base_snr_db=25,
    )
    experiment_runner = ExperimentRunner(manipulator=manipulator)
    ai_optimizer = AIOptimizer()
    print("Components initialized successfully.")

    # --- 2. Automated Data Collection ---
    print("\n[Step 2] Running automated parameter sweep to collect data...")

    # To keep the demo fast, we'll test a small but effective range of parameters.
    rate_range = np.arange(40, 151, 10)  # 40, 50, ..., 150 Mbps
    distance_range = np.arange(20, 301, 40) # 20, 60, ..., 300 m

    # The manipulator's `set_target_profile` is mocked to simulate success.
    # In a real run, this would be writing to the device.
    manipulator.set_target_profile = MagicMock(return_value={'snr_margin_set': True, 'attenuation_set': True})

    experiment_runner.parameter_sweep(rate_range, distance_range)
    print(f"Data collection complete. {len(experiment_runner.results)} experiments run.")

    # --- 3. AI Model Training ---
    print("\n[Step 3] Training AI model on collected data...")
    ai_optimizer.train(experiment_runner.results)

    # --- 4. AI-Powered Prediction ---
    print("\n[Step 4] Using trained AI model to predict optimal parameters...")
    target_speed = 125.0
    predicted_params = ai_optimizer.predict_optimal_params(target_speed)

    if predicted_params:
        print("\n✅ --- FINAL RESULT --- ✅")
        print(f"To achieve a target speed of {target_speed} Mbps, the AI suggests:")
        print(f"  - Predicted SNR Margin: {predicted_params['predicted_snr']} dB")
        print(f"  - Predicted Attenuation: {predicted_params['predicted_attenuation']} dB")
    else:
        print("\n❌ Could not generate a prediction. The model may not be trained.")

    print("\n🎉 Demonstration Complete 🎉")

if __name__ == "__main__":
    main()