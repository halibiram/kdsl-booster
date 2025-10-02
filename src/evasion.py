"""
This module provides the EvasionManager class, which encapsulates all logic
for stealth, anti-detection, and evading ISP monitoring.

It includes functionalities for:
- Gradual parameter adaptation to avoid sudden, suspicious changes.
- Detection of ISP monitoring tools like TR-069 and SNMP.
- Bypassing monitoring by blocking traffic from known management servers.
- Emulating the "normal" behavior of a physical line by adding realistic noise
  to reported parameters.
"""

import time
import logging
import random
import threading
import numpy as np
from typing import Callable, Any, Optional

from src.entware_ssh import EntwareSSHInterface
from src.keenetic_dsl_interface import DslHalBase


class EvasionManager:
    """
    Manages stealth and anti-detection operations for DSL manipulation.
    """

    def __init__(self, ssh_interface: EntwareSSHInterface, hal: DslHalBase):
        """
        Initializes the EvasionManager.

        Args:
            ssh_interface: An active EntwareSSHInterface instance.
            hal: An initialized hardware abstraction layer instance.
        """
        self.ssh = ssh_interface
        self.hal = hal
        self._behavior_emulation_thread: Optional[threading.Thread] = None
        self._stop_emulation = threading.Event()

    def gradually_adapt_parameter(
        self,
        setter_func: Callable[[int], bool],
        param_name: str,
        current_value: float,
        target_value: float,
        duration_s: int,
        step_interval_s: float = 1.0,
        value_multiplier: int = 10
    ):
        """
        Gradually changes a parameter from a current value to a target value.

        This method is designed to avoid sudden changes that could be flagged
        by ISP monitoring systems.

        Args:
            setter_func: The HAL function to call to set the parameter (e.g., self.hal.set_snr_margin).
            param_name: The human-readable name of the parameter for logging (e.g., "SNR Margin").
            current_value: The starting value (e.g., 25.0 for an SNR of 25.0 dB).
            target_value: The final value.
            duration_s: The total time the adaptation should take.
            step_interval_s: The time to wait between steps.
            value_multiplier: The multiplier to convert the float value to the integer expected
                              by the HAL function (e.g., 10 for parameters in 0.1 dB units).
        """
        logging.info(
            f"Starting gradual adaptation for {param_name} from {current_value} to {target_value} "
            f"over {duration_s} seconds."
        )
        num_steps = int(duration_s / step_interval_s)
        if num_steps < 1:
            num_steps = 1

        values = np.linspace(current_value, target_value, num=num_steps)

        for i, value in enumerate(values):
            register_value = int(value * value_multiplier)
            logging.debug(f"Step {i+1}/{num_steps}: Setting {param_name} to {value:.2f}")

            try:
                success = setter_func(register_value)
                if not success:
                    logging.warning(
                        f"Failed to set {param_name} to {value:.2f} during gradual adaptation. Stopping."
                    )
                    return
            except Exception as e:
                logging.error(
                    f"Exception during {param_name} adaptation at value {value:.2f}: {e}. Stopping."
                )
                return

            if i < num_steps - 1:  # Don't sleep after the last step
                time.sleep(step_interval_s)

        logging.info(f"Gradual adaptation for {param_name} complete. Final value: {target_value:.2f}")

    def detect_tr069_activity(self, tr069_port: int = 7547) -> bool:
        """
        Detects if a TR-069 client has an active connection.

        TR-069 typically runs over HTTP/S on port 7547. This method checks
        for established connections on that port.

        Args:
            tr069_port: The port used for TR-069 communication.

        Returns:
            True if an active TR-069 connection is detected, False otherwise.
        """
        logging.info("Checking for active TR-069 connections...")
        # Use netstat to find established connections on the standard TR-069 port.
        command = f"netstat -anp | grep ':{tr069_port}' | grep ESTABLISHED"
        try:
            result = self.ssh.run_command(command)
            if result and result.strip():
                logging.warning(f"Active TR-069 connection detected: {result.strip()}")
                return True
            logging.info("No active TR-069 connections found.")
            return False
        except Exception as e:
            logging.error(f"Error while checking for TR-069 activity: {e}")
            return False

    def detect_snmp_polling(self, isp_mgmt_ip: Optional[str] = None, timeout_s: int = 5) -> bool:
        """
        Detects incoming SNMP polling traffic using tcpdump.

        Listens for a short period for SNMP requests on UDP port 161.

        Args:
            isp_mgmt_ip: If provided, only listens for traffic from this specific IP.
            timeout_s: How long to listen for SNMP traffic.

        Returns:
            True if SNMP polling is detected, False otherwise.
        """
        logging.info("Listening for SNMP polling traffic...")
        # Use tcpdump to capture one SNMP packet (udp dst port 161).
        # The command will timeout and exit if no packet is captured.
        interface = "any"
        filter_expr = "udp dst port 161"
        if isp_mgmt_ip:
            filter_expr += f" and src host {isp_mgmt_ip}"

        command = f"tcpdump -i {interface} -c 1 -W {timeout_s} -n '{filter_expr}'"

        try:
            # We check the return code. tcpdump exits with 0 if packets were captured.
            # A non-zero exit code usually means it timed out without capturing.
            stdout, stderr, exit_code = self.ssh.run_command_with_exit_code(command)
            if exit_code == 0 and stdout:
                logging.warning(f"Detected incoming SNMP polling traffic: {stdout.strip()}")
                return True
            logging.info("No SNMP polling traffic detected within the timeout period.")
            return False
        except Exception as e:
            logging.error(f"Error while sniffing for SNMP traffic: {e}")
            return False

    def bypass_monitoring(self, acs_url: Optional[str] = None, snmp_ip: Optional[str] = None) -> bool:
        """
        Installs iptables firewall rules to block TR-069 and/or SNMP traffic.

        This requires `iptables` and `nslookup` to be installed on the device.

        Args:
            acs_url: The URL of the TR-069 Auto Configuration Server (ACS).
            snmp_ip: The IP address of the SNMP management server.

        Returns:
            True if all requested firewall rules were successfully applied, False otherwise.
        """
        logging.info("Attempting to bypass ISP monitoring with firewall rules...")
        commands = []

        if not acs_url and not snmp_ip:
            logging.warning("Bypass called without specifying an ACS URL or SNMP IP.")
            return True # Nothing to do.

        # 1. Handle TR-069 bypass
        if acs_url:
            logging.info(f"Resolving ACS URL: {acs_url}")
            try:
                # Resolve the hostname to an IP from the device's perspective
                # The awk script filters for the first IP address found.
                resolve_cmd = f"nslookup {acs_url} | awk '/^Address: / {{ print $2; exit }}'"
                acs_ip = self.ssh.run_command(resolve_cmd)
                if not acs_ip or not acs_ip.strip():
                    logging.error(f"Could not resolve ACS URL '{acs_url}' to an IP address.")
                    return False
                acs_ip = acs_ip.strip()
                logging.info(f"Resolved {acs_url} to {acs_ip}. Blocking traffic on port 7547.")
                # Block outgoing connections to the ACS
                commands.append(f"iptables -I OUTPUT 1 -d {acs_ip} -p tcp --dport 7547 -j DROP")
                # Block incoming connections from the ACS
                commands.append(f"iptables -I INPUT 1 -s {acs_ip} -p tcp --sport 7547 -j DROP")
            except Exception as e:
                logging.error(f"Error during TR-069 bypass preparation: {e}")
                return False

        # 2. Handle SNMP bypass
        if snmp_ip:
            logging.info(f"Blocking SNMP traffic from management IP: {snmp_ip}")
            # Block incoming SNMP requests
            commands.append(f"iptables -I INPUT 1 -s {snmp_ip} -p udp --dport 161 -j DROP")

        # 3. Execute all generated commands
        if not commands:
            return False # Should not happen if we passed the initial check, but for safety.

        all_successful = True
        for cmd in commands:
            try:
                logging.info(f"Executing firewall command: {cmd}")
                stdout, stderr, exit_code = self.ssh.run_command_with_exit_code(cmd)
                if exit_code != 0:
                    logging.error(f"Failed to execute iptables command. Exit code: {exit_code}, Stderr: {stderr}")
                    all_successful = False
                    # Don't break; try to apply other rules.
            except Exception as e:
                logging.error(f"Exception while executing iptables command: {e}")
                all_successful = False

        if all_successful:
            logging.info("Successfully applied all monitoring bypass rules.")
        else:
            logging.error("One or more monitoring bypass rules failed to apply.")

        return all_successful

    def _emulate_behavior_loop(
        self,
        snr_fluctuation_db: float,
        attenuation_fluctuation_db: float,
        interval_s: int
    ):
        """The main loop for the behavior emulation thread."""
        logging.info("Behavior emulation thread started.")
        while not self._stop_emulation.is_set():
            try:
                # 1. Get current base values from the hardware
                current_snr = self.hal.get_snr_margin()
                current_ds_atten, current_us_atten = self.hal.get_attenuation()

                if current_snr is None or current_ds_atten is None:
                    logging.warning("Could not retrieve current line parameters for emulation. Skipping cycle.")
                    self._stop_emulation.wait(interval_s)
                    continue

                # 2. Calculate and apply SNR fluctuation
                snr_noise = random.uniform(-snr_fluctuation_db, snr_fluctuation_db)
                new_snr = current_snr + snr_noise
                self.hal.set_snr_margin(int(new_snr * 10))
                logging.debug(f"Emulation: SNR set to {new_snr:.2f} dB (Base: {current_snr:.2f}, Noise: {snr_noise:.2f})")

                # 3. Calculate and apply Attenuation fluctuation (apply same noise to both)
                atten_noise = random.uniform(-attenuation_fluctuation_db, attenuation_fluctuation_db)
                new_ds_atten = current_ds_atten + atten_noise
                new_us_atten = current_us_atten + atten_noise
                self.hal.set_attenuation(int(new_ds_atten * 10), int(new_us_atten * 10))
                logging.debug(f"Emulation: Attenuation set to {new_ds_atten:.2f} dB (Base: {current_ds_atten:.2f}, Noise: {atten_noise:.2f})")

            except Exception as e:
                logging.error(f"Exception in behavior emulation loop: {e}")

            # 4. Wait for the next cycle, but check for stop event periodically
            self._stop_emulation.wait(interval_s)
        logging.info("Behavior emulation thread stopped.")

    def start_behavior_emulation(
        self,
        snr_fluctuation_db: float = 0.2,
        attenuation_fluctuation_db: float = 0.1,
        interval_s: int = 15
    ):
        """
        Starts a background thread to add realistic noise to line parameters.

        This makes the line appear more "natural" to monitoring systems.

        Args:
            snr_fluctuation_db: The max random fluctuation to apply to SNR (in dB).
            attenuation_fluctuation_db: The max random fluctuation to apply to attenuation (in dB).
            interval_s: How often to apply the fluctuations.
        """
        if self._behavior_emulation_thread and self._behavior_emulation_thread.is_alive():
            logging.warning("Behavior emulation is already running. Stopping it before restarting.")
            self.stop_behavior_emulation()

        logging.info("Starting behavior emulation...")
        self._stop_emulation.clear()
        self._behavior_emulation_thread = threading.Thread(
            target=self._emulate_behavior_loop,
            args=(snr_fluctuation_db, attenuation_fluctuation_db, interval_s),
            daemon=True
        )
        self._behavior_emulation_thread.start()

    def stop_behavior_emulation(self):
        """
        Stops the background behavior emulation thread.
        """
        if self._behavior_emulation_thread and self._behavior_emulation_thread.is_alive():
            logging.info("Stopping behavior emulation...")
            self._stop_emulation.set()
            self._behavior_emulation_thread.join(timeout=5)
            if self._behavior_emulation_thread.is_alive():
                logging.warning("Behavior emulation thread did not stop gracefully.")
            self._behavior_emulation_thread = None
        else:
            logging.info("Behavior emulation is not running.")