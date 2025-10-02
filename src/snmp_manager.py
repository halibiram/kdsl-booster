"""
This module provides a manager class for handling SNMP operations by wrapping
command-line tools like snmpget, snmpset, and snmpwalk using the subprocess module.
"""

import subprocess
import re
from src.log_manager import LogManager

class SNMPManager:
    """A wrapper class for simplifying SNMP operations via command-line tools."""

    def __init__(self, log_manager: LogManager, host, community='public', port=161, timeout=2, retries=3, version='2c'):
        """
        Initializes the SNMPManager.

        Args:
            log_manager: An instance of the LogManager.
            host (str): The IP address or hostname of the SNMP agent.
            community (str): The SNMP community string.
            port (int): The port number for the SNMP agent.
            timeout (int): The SNMP request timeout in seconds.
            retries (int): The number of retries for an SNMP request.
            version (str): The SNMP version to use ('1', '2c', '3').
        """
        self.log_manager = log_manager
        self.host = host
        self.port = port
        self.community = community
        self.version = version
        self.timeout = timeout
        self.retries = retries

    def _execute_command(self, command_args):
        """A helper method to run subprocess commands."""
        try:
            return subprocess.run(
                command_args,
                capture_output=True,
                text=True,
                check=True,
                timeout=self.timeout
            )
        except subprocess.CalledProcessError as e:
            self.log_manager.log("snmp_command_failed", {"error": e.stderr}, level="error")
            return None
        except subprocess.TimeoutExpired:
            self.log_manager.log("snmp_command_timeout", {"command": " ".join(command_args)}, level="error")
            return None
        except FileNotFoundError:
            self.log_manager.log("snmp_command_not_found", {}, level="error")
            return None

    def get(self, oid):
        """
        Performs an SNMP GET operation.

        Args:
            oid (str): The OID to retrieve.

        Returns:
            The value of the OID as a string, or None if an error occurs.
        """
        command = [
            'snmpget',
            '-On',  # Use numeric OIDs for consistent output
            '-v' + self.version,
            '-c', self.community,
            '-t', str(self.timeout),
            '-r', str(self.retries),
            f"{self.host}:{self.port}",
            oid
        ]
        result = self._execute_command(command)
        if result and result.stdout:
            # Example output: SNMPv2-MIB::sysDescr.0 = STRING: Linux dsl-router 4.9.1
            match = re.search(r'=\s*\w+:\s*(.*)', result.stdout, re.IGNORECASE)
            if match:
                # Return just the value, stripping quotes if they exist
                return match.group(1).strip().strip('"')
        return None

    def set(self, oid, value, value_type='s'):
        """
        Performs an SNMP SET operation.

        Args:
            oid (str): The OID to set.
            value: The value to set for the OID.
            value_type (str): The type of the value ('i' for integer, 's' for string, etc.).

        Returns:
            True if the SET operation was successful, False otherwise.
        """
        command = [
            'snmpset',
            '-v' + self.version,
            '-c', self.community,
            '-t', str(self.timeout),
            '-r', str(self.retries),
            f"{self.host}:{self.port}",
            oid,
            value_type,
            str(value)
        ]
        result = self._execute_command(command)
        return result is not None and result.returncode == 0

    def walk(self, oid):
        """
        Performs an SNMP WALK operation.

        Args:
            oid (str): The base OID to walk.

        Returns:
            A list of (oid, value) tuples, or an empty list on error.
        """
        results = []
        command = [
            'snmpwalk',
            '-On',  # Use numeric OIDs for consistent output
            '-v' + self.version,
            '-c', self.community,
            '-t', str(self.timeout),
            '-r', str(self.retries),
            f"{self.host}:{self.port}",
            oid
        ]
        result = self._execute_command(command)
        if result and result.stdout:
            for line in result.stdout.strip().split('\n'):
                match = re.search(r'([\.\w]+)\s+=\s+\w+:\s*(.*)', line, re.IGNORECASE)
                if match:
                    results.append((match.group(1), match.group(2).strip().strip('"')))
        return results