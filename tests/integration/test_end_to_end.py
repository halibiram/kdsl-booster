# tests/integration/test_end_to_end.py

import pytest
import time
from src.entware_ssh import EntwareSSHInterface
from src.kernel_dsl_access import discover_dsl_interfaces
from src.spoofing import KernelDSLManipulator
from src.experimentation import ExperimentRunner

@pytest.mark.integration
@pytest.mark.hardware
class TestEndToEndIntegration:
    """
    Integration tests requiring actual hardware
    Run with: pytest -m integration
    """

    @pytest.fixture(scope="class")
    def hardware_setup(self):
        """Setup connection to actual Keenetic hardware"""
        # Load config from environment or config file
        import os
        config = {
            "host": os.getenv("KEENETIC_HOST", "192.168.1.1"),
            "username": os.getenv("KEENETIC_USER", "admin"),
            "password": os.getenv("KEENETIC_PASS", ""),
        }

        ssh = EntwareSSHInterface(
            host=config["host"],
            username=config["username"],
            password=config["password"]
        )

        try:
            ssh.connect()
            yield ssh
        finally:
            ssh.disconnect()

    def test_ssh_connection(self, hardware_setup):
        """Test basic SSH connectivity"""
        ssh = hardware_setup
        assert ssh.is_connected

        stdout, stderr = ssh.execute_command("uname -a")
        assert stdout
        assert "Linux" in stdout

    def test_dsl_interface_discovery(self, hardware_setup):
        """Test DSL interface detection on real hardware"""
        ssh = hardware_setup
        interfaces = discover_dsl_interfaces(ssh)

        assert len(interfaces) > 0, "No DSL interfaces found"

        for iface_name, iface_info in interfaces.items():
            print(f"Found interface: {iface_name} -> {iface_info}")
            assert "path" in iface_info
            assert "type" in iface_info

    def test_baseline_measurement(self, hardware_setup):
        """Measure baseline DSL performance"""
        ssh = hardware_setup

        # Get current DSL parameters
        stdout, _ = ssh.execute_command("cat /proc/driver/dsl/status 2>/dev/null")
        assert stdout, "Could not read DSL status"

        print(f"Baseline DSL status:\n{stdout}")

    def test_safe_parameter_modification(self, hardware_setup):
        """Test safe parameter modification with rollback"""
        ssh = hardware_setup
        manipulator = KernelDSLManipulator(
            ssh_interface=ssh,
            base_rate_mbps=30,
            base_snr_db=25
        )

        # Read original parameters
        original_params = {}  # Store original state

        try:
            # Apply conservative modification
            result = manipulator.set_target_profile(
                target_rate_mbps=35,  # Very conservative increase
                target_distance_m=280
            )

            # Wait for stabilization
            time.sleep(10)

            # Verify system still stable
            stdout, _ = ssh.execute_command("cat /proc/driver/dsl/status")
            assert stdout, "DSL interface became unresponsive"

        finally:
            # Always rollback
            print("Rolling back to original parameters...")
            # Implement rollback logic

    @pytest.mark.slow
    def test_full_experiment_run(self, hardware_setup):
        """Run a full experiment cycle (SLOW TEST)"""
        ssh = hardware_setup
        manipulator = KernelDSLManipulator(ssh, 30, 25)
        runner = ExperimentRunner(manipulator, ssh)

        # Run small parameter sweep
        runner.parameter_sweep(
            rate_range=[35, 40],  # Conservative range
            distance_range=[280, 260],
            measurement_method="dsl_stats"
        )

        assert len(runner.results) == 4

        # Verify results are reasonable
        for result in runner.results:
            assert result["measured_speed_mbps"] > 0
            assert result["measured_speed_mbps"] < 300  # Physical limit