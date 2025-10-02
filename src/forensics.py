import os
import json
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import base64
import secrets

class SecureLogger:
    """
    Handles encrypted, minimal-footprint logging with anti-forensics features.
    """

    def __init__(self, log_file: str, key: bytes, minimal_footprint: bool = False):
        self.log_file = log_file
        self.key = key
        self.fernet = Fernet(self.key)
        self.minimal_footprint = minimal_footprint
        self.logger = logging.getLogger(self.__class__.__name__)

    def _encrypt_log(self, data: str) -> bytes:
        """Encrypts a log entry."""
        return self.fernet.encrypt(data.encode())

    def _decrypt_log(self, token: bytes) -> str:
        """Decrypts a log entry."""
        return self.fernet.decrypt(token).decode()

    def log(self, event: str, details: dict):
        """
        Logs an event, encrypting it before writing to the log file.
        """
        if self.minimal_footprint:
            return

        log_entry = {
            "timestamp": logging.time.time(),
            "event": event,
            "details": details,
        }
        encrypted_entry = self._encrypt_log(json.dumps(log_entry))
        try:
            with open(self.log_file, 'ab') as f:
                f.write(encrypted_entry + b'\n')
        except IOError as e:
            self.logger.error(f"Failed to write to secure log file: {e}")

    def read_log(self) -> list[dict]:
        """
        Reads and decrypts all entries from the log file.
        """
        if not os.path.exists(self.log_file):
            return []

        entries = []
        try:
            with open(self.log_file, 'rb') as f:
                for line in f:
                    try:
                        decrypted_line = self._decrypt_log(line.strip())
                        entries.append(json.loads(decrypted_line))
                    except Exception as e:
                        self.logger.warning(f"Skipping malformed line in secure log: {e}")
                        continue
        except IOError as e:
            self.logger.error(f"Failed to read secure log file: {e}")
        return entries

    def secure_delete_log(self):
        """
        Securely deletes the log file by overwriting it with random data.
        """
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "ba+") as f:
                    length = f.tell()
                    f.seek(0)
                    f.write(os.urandom(length))
                os.remove(self.log_file)
                self.logger.info(f"Securely deleted log file: {self.log_file}")
            except (IOError, OSError) as e:
                self.logger.error(f"Error during secure deletion of {self.log_file}: {e}")

    def generate_decoy_log_entries(self, num_entries: int = 10):
        """
        Generates plausible but fake log entries to obfuscate real activity.
        """
        decoy_events = [
            ("user_login_failed", {"username": "admin", "ip_address": "192.168.1.101"}),
            ("database_connection_error", {"db_host": "db.internal", "error": "timeout"}),
            ("snmp_timeout", {"target": "10.0.0.1"}),
            ("firewall_rule_updated", {"rule_id": "FW0023", "action": "deny"}),
        ]

        for _ in range(num_entries):
            event, details = secrets.choice(decoy_events)
            self.log(event, details)
        self.logger.info(f"Generated {num_entries} decoy log entries.")

    @staticmethod
    def generate_key_from_password(password: str, salt: bytes) -> bytes:
        """
        Derives a key from a password and salt using PBKDF2.
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key