import logging
import os
from src.forensics import SecureLogger

class LogManager:
    """
    Manages all logging activities, switching between standard and secure logging.
    """

    def __init__(self, secure_logging_enabled: bool = False, log_file: str = "secure_operational_log.enc", password: str = "default_password"):
        self.secure_logging_enabled = secure_logging_enabled
        self.standard_logger = logging.getLogger("StandardLogger")
        self.secure_logger = None

        if self.secure_logging_enabled:
            # In a real application, the password should be handled more securely.
            # For example, using environment variables or a secrets management system.
            salt_file = "log_salt.bin"
            if not os.path.exists(salt_file):
                with open(salt_file, "wb") as f:
                    f.write(os.urandom(16))

            with open(salt_file, "rb") as f:
                salt = f.read()

            key = SecureLogger.generate_key_from_password(password, salt)
            self.secure_logger = SecureLogger(log_file, key)
            self.standard_logger.info("Secure logging is enabled.")
        else:
            self.standard_logger.info("Standard logging is enabled. Secure logging is off.")

    def log(self, event: str, details: dict, level: str = "info"):
        """
        Logs an event to the appropriate logger.
        """
        if self.secure_logging_enabled and self.secure_logger:
            self.secure_logger.log(event, details)
        else:
            log_message = f"Event: {event}, Details: {details}"
            if level == "info":
                self.standard_logger.info(log_message)
            elif level == "warning":
                self.standard_logger.warning(log_message)
            elif level == "error":
                self.standard_logger.error(log_message)
            else:
                self.standard_logger.debug(log_message)

    def get_secure_logger(self) -> SecureLogger | None:
        """
        Returns the secure logger instance if it exists.
        """
        return self.secure_logger