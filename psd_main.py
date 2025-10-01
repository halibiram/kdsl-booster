import logging
from src.entware_ssh import EntwareSSHInterface
from src.spoofing import KernelDSLManipulator
from src.psd_analyzer import PSDAnalyzer
from src.ghs_handshake_analyzer import GHSHandshakeAnalyzer
from src.vendor_signatures import VENDOR_SIGNATURES

# Configure logging for the test script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    """
    Main function to test PSD manipulation features.
    """
    logging.info("Starting PSD manipulation test script...")

    # --- Configuration ---
    # Load credentials from environment variables for security
    # export ROUTER_IP="192.168.1.1"
    # export SSH_USER="root"
    # export SSH_PASS="your_password"
    import os
    ROUTER_IP = os.environ.get("ROUTER_IP", "192.168.1.1")
    SSH_USER = os.environ.get("SSH_USER", "root")
    SSH_PASS = os.environ.get("SSH_PASS")

    if not SSH_PASS:
        logging.error("FATAL: SSH_PASS environment variable not set. Please set it before running the script.")
        return

    try:
        # --- Initialization ---
        logging.info(f"Connecting to router at {ROUTER_IP}...")
        ssh_interface = EntwareSSHInterface(ROUTER_IP, username=SSH_USER, password=SSH_PASS)
        ssh_interface.connect()

        # Initialize the manipulator and analyzers
        # We pass dummy analyzers for this test since we are focusing on the new functions
        ghs_analyzer = GHSHandshakeAnalyzer(ssh_interface, "/tmp/ghs.pcap")
        psd_analyzer = PSDAnalyzer(ghs_analyzer, ssh_interface, VENDOR_SIGNATURES)
        manipulator = KernelDSLManipulator(ssh_interface, profile='17a')

        logging.info("Initialization complete. Starting tests...")

        # --- Test Cases ---

        # 1. Test PSD Mask Override
        logging.info("--- Test 1: Applying PSD Mask Override ---")
        recommended_mask = psd_analyzer.recommend_psd_mask(profile='35b')
        if recommended_mask:
            manipulator.apply_psd_mask_override(recommended_mask)
        else:
            logging.warning("No recommended PSD mask found for profile '35b'.")

        # 2. Test Upstream Power Boost
        logging.info("\n--- Test 2: Applying Upstream Power Boost ---")
        # In a real scenario, we would get attenuation from the device
        fake_attenuation = 30.0
        safe_boost = manipulator.physics.get_safe_power_boost_limit(fake_attenuation)
        manipulator.apply_upstream_power_boost(int(safe_boost))

        # 3. Test Downstream Power Request Manipulation
        logging.info("\n--- Test 3: Manipulating Downstream Power Request ---")
        # Requesting a specific power level, e.g., 14.5 dBm
        manipulator.manipulate_downstream_power_request(145)

        # 4. Test Per-Band PSD Optimization
        logging.info("\n--- Test 4: Optimizing Per-Band PSD ---")
        optimal_shape = manipulator.physics.generate_optimal_psd_shape(target_rate_mbps=100, distance_m=300)
        manipulator.optimize_per_band_psd(optimal_shape)

        # 5. Test Dynamic PSD Adaptation
        logging.info("\n--- Test 5: Starting Dynamic PSD Adaptation ---")
        # Run for a short duration for testing purposes
        adaptation_results = manipulator.start_dynamic_psd_adaptation(
            monitoring_duration_s=60,
            check_interval_s=10,
            crosstalk_threshold=50
        )
        logging.info(f"Dynamic adaptation finished with results: {adaptation_results}")

        logging.info("\nAll PSD manipulation tests completed successfully.")

    except Exception as e:
        logging.error(f"An error occurred during the test script: {e}", exc_info=True)
    finally:
        if 'ssh_interface' in locals() and ssh_interface.is_connected():
            ssh_interface.disconnect()
        logging.info("Test script finished.")

if __name__ == "__main__":
    main()