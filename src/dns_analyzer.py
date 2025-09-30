"""
This module provides the DNSAnalyzer class, responsible for performing
reverse DNS lookups to identify hostnames associated with IP addresses.
"""
import logging
import socket

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class DNSAnalyzer:
    """
    Performs reverse DNS lookups to find hostnames for vendor identification.
    """

    def get_hostname_by_ip(self, ip_address: str) -> str | None:
        """
        Performs a reverse DNS lookup for a given IP address.

        Args:
            ip_address: The IP address to look up.

        Returns:
            The hostname string if found, otherwise None.
        """
        logging.info(f"Performing reverse DNS lookup for IP: {ip_address}")
        try:
            # gethostbyaddr returns (hostname, aliaslist, ipaddrlist)
            hostname, _, _ = socket.gethostbyaddr(ip_address)
            logging.info(f"Found hostname: {hostname} for IP: {ip_address}")
            return hostname
        except socket.herror as e:
            # Host not found, which is a common case.
            logging.warning(f"Could not resolve hostname for {ip_address}: {e}")
            return None
        except Exception as e:
            # Catch other potential socket errors
            logging.error(f"An unexpected error occurred during DNS lookup for {ip_address}: {e}")
            return None