"""
This module contains vendor-specific SNMP classes for interacting with DSLAMs.
These classes use the SNMPManager to perform high-level operations
and configurations on DSLAM devices.
"""

from src.snmp_manager import SNMPManager
from src.snmp_mib_library import DSLAM_MIBS


class BaseVendorSnmp:
    """A base class for vendor-specific SNMP interactions."""
    def __init__(self, host, community='public', port=161):
        self.snmp_manager = SNMPManager(host, community, port)
        self.vendor = "generic"

    def get_device_info(self):
        """Retrieves basic device information."""
        sys_descr = self.snmp_manager.get('1.3.6.1.2.1.1.1.0')
        sys_name = self.snmp_manager.get('1.3.6.1.2.1.1.5.0')
        return {
            "sysDescr": sys_descr,
            "sysName": sys_name
        }


class AdtranSnmp(BaseVendorSnmp):
    """SNMP interactions specific to Adtran DSLAMs."""
    def __init__(self, host, community='public', port=161):
        super().__init__(host, community, port)
        self.vendor = "adtran"
        self.oids = DSLAM_MIBS.get(self.vendor, {}).get("oids", {})

    def get_line_profile(self, interface_index=1):
        """Retrieves the line profile for a specific interface."""
        profile_oid = f"{self.oids.get('profile_config')}.{interface_index}"
        return self.snmp_manager.get(profile_oid)

    def set_line_profile(self, profile_name, interface_index=1):
        """Attempts to set the line profile for a specific interface."""
        profile_oid = f"{self.oids.get('profile_config')}.{interface_index}"
        # Use 's' for string type with the new SNMPManager
        return self.snmp_manager.set(profile_oid, profile_name, value_type='s')


class HuaweiSnmp(BaseVendorSnmp):
    """SNMP interactions specific to Huawei DSLAMs."""
    def __init__(self, host, community='public', port=161):
        super().__init__(host, community, port)
        self.vendor = "huawei"
        self.oids = DSLAM_MIBS.get(self.vendor, {}).get("oids", {})

    def get_line_profile_assignment(self, interface_index=1):
        """Retrieries the line profile assignment for a specific interface."""
        assignment_oid = f"{self.oids.get('profile_assignment')}.{interface_index}"
        return self.snmp_manager.get(assignment_oid)

    def set_line_profile_assignment(self, profile_index, interface_index=1):
        """Attempts to set the line profile for a specific interface by its index."""
        assignment_oid = f"{self.oids.get('profile_assignment')}.{interface_index}"
        # Use 'i' for integer type with the new SNMPManager
        return self.snmp_manager.set(assignment_oid, profile_index, value_type='i')

# Add other vendor-specific classes here as needed.