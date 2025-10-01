"""
This module provides the DatabaseManager class, which serves as an
abstraction layer for accessing vendor signature and capability data.

Currently, it reads from a JSON file, but it is designed to be easily
extended to connect to a real database system in the future.
"""
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DatabaseManager:
    """
    Manages access to the vendor signature database.
    """

    def __init__(self, signature_file_path: str = 'src/vendor_signatures.json'):
        """
        Initializes the manager and loads the signature data.

        Args:
            signature_file_path: The path to the JSON file containing signatures.
        """
        self.signature_file_path = signature_file_path
        self.signatures = self._load_signatures()

    def _load_signatures(self) -> dict:
        """
        Loads vendor signatures from the JSON file.
        In the future, this could be replaced with a database connection.
        """
        logging.info(f"Loading signatures from {self.signature_file_path}...")
        try:
            with open(self.signature_file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.critical(f"Failed to load signature database from {self.signature_file_path}: {e}")
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