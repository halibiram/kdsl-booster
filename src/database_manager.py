"""
This module provides the DatabaseManager class, which serves as an
abstraction layer for accessing vendor signature and capability data.

Currently, it reads from a JSON file, but it is designed to be easily
extended to connect to a real database system in the future.
"""
import json
import logging
import os
from collections import defaultdict
from src.log_manager import LogManager

class DatabaseManager:
    """
    Manages access to the vendor signature database and logs exploitation attempts.
    """

    def __init__(self, log_manager: LogManager, signature_file_path: str = 'src/vendor_signatures.json', exploitation_log_path: str = 'exploitation_log.json'):
        """
        Initializes the manager, loads signature data, and sets up the exploitation log.

        Args:
            log_manager: An instance of the LogManager.
            signature_file_path: The path to the JSON file containing signatures.
            exploitation_log_path: The path to the file for logging exploitation attempts.
        """
        self.log_manager = log_manager
        self.signature_file_path = signature_file_path
        self.exploitation_log_path = exploitation_log_path
        self.signatures = self._load_signatures()

    def _load_signatures(self) -> dict:
        """
        Loads vendor signatures from the JSON file.
        In the future, this could be replaced with a database connection.
        """
        self.log_manager.log("load_signatures", {"path": self.signature_file_path})
        try:
            with open(self.signature_file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.log_manager.log("load_signatures_failed", {"path": self.signature_file_path, "error": str(e)}, level="error")
            return {}

    def get_all_signatures(self) -> dict:
        """
        Returns the entire dictionary of vendor signatures.
        """
        return self.signatures

    def get_vendor_signature(self, vendor: str) -> dict:
        """
        Retrieves the signature data for a specific vendor.

        Args:
            vendor: The name of the vendor.

        Returns:
            A dictionary containing the vendor's signature data, or an empty
            dictionary if the vendor is not found.
        """
        return self.signatures.get(vendor, {})

    def get_exploits_for_vendor(self, vendor: str) -> list | None:
        """
        Retrieves the list of available exploits for a specific vendor.

        Args:
            vendor: The name of the vendor.

        Returns:
            A list of exploit dictionaries, or None if the vendor is not found
            or has no exploits defined.
        """
        vendor_data = self.get_vendor_signature(vendor)
        return vendor_data.get("exploits") if vendor_data else None

    def log_exploitation_attempt(self, dslam_info: dict, strategy_name: str, success: bool):
        """
        Logs the result of an exploitation attempt.
        """
        log_details = {
            "dslam_vendor": dslam_info.get('primary_vendor', 'unknown'),
            "dslam_model": dslam_info.get('model', 'unknown'),
            "strategy_name": strategy_name,
            "success": success,
        }
        self.log_manager.log("exploitation_attempt", log_details)

    def get_strategy_success_rates(self) -> dict:
        """
        Calculates the success rate of each strategy based on the exploitation log.

        Returns:
            A dictionary where keys are strategy names and values are dictionaries
            containing 'successes', 'failures', and 'rate'.
        """
        if not os.path.exists(self.exploitation_log_path):
            return {}

        strategy_stats = defaultdict(lambda: {'successes': 0, 'failures': 0})
        try:
            with open(self.exploitation_log_path, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        strategy_name = entry.get("strategy_name")
                        if not strategy_name:
                            continue

                        if entry.get("success"):
                            strategy_stats[strategy_name]['successes'] += 1
                        else:
                            strategy_stats[strategy_name]['failures'] += 1
                    except json.JSONDecodeError:
                        self.logger.warning(f"Skipping malformed line in log file: {line.strip()}")
                        continue
        except IOError as e:
            self.logger.error(f"Failed to read exploitation log file at {self.exploitation_log_path}: {e}")
            return {}

        # Calculate success rates
        success_rates = {}
        for name, stats in strategy_stats.items():
            total = stats['successes'] + stats['failures']
            rate = stats['successes'] / total if total > 0 else 0
            success_rates[name] = {**stats, 'rate': rate}

        return success_rates