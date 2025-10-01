"""
This module contains a library of SNMP MIBs and OIDs for various DSLAM vendors.
The structure is based on the GLOBAL_DSLAM_VENDORS dictionary from the project specification.
"""

# Standard SNMP OIDs for system information
SYSTEM_OIDS = {
    'sysDescr': '1.3.6.1.2.1.1.1.0',
    'sysObjectID': '1.3.6.1.2.1.1.2.0',
    'sysName': '1.3.6.1.2.1.1.5.0',
}

# Vendor-specific OID bases for identification
VENDOR_OID_BASES = {
    "huawei": "1.3.6.1.4.1.2011",
    "nokia_alcatel": "1.3.6.1.4.1.637",
    "ericsson": "1.3.6.1.4.1.193",
    "zte": "1.3.6.1.4.1.3902",
    "adtran": "1.3.6.1.4.1.664",
    "calix": "1.3.6.1.4.1.6321",
}

# Comprehensive DSLAM Vendor MIBs
DSLAM_MIBS = {
    "huawei": {
        "models": ["MA5608T", "MA5680T", "MA5616", "MA5683T"],
        "oids": {
            "profile_assignment": "1.3.6.1.4.1.2011.5.14.5.2.1.19",
            "line_profile_config": "1.3.6.1.4.1.2011.5.14.5.2.1.20",
            # Add other relevant Huawei OIDs here
        }
    },
    "adtran": {
        "models": ["Total_Access_5000", "TA5004", "TA916e"],
        "oids": {
            "profile_config": "1.3.6.1.4.1.664.5.53.1.5.1",
            "line_config": "1.3.6.1.4.1.664.5.53.1.3.1",
            "rate_config": "1.3.6.1.4.1.664.5.53.1.6.1",
            # Add other relevant Adtran OIDs here
        }
    },
    "nokia_alcatel": {
        "models": ["7330_ISAM", "7302_ISAM", "7342_ISAM"],
        "oids": {
            # OIDs for Nokia/Alcatel-Lucent DSLAMs
        }
    },
    "zte": {
        "models": ["ZXA10", "ZXDSL_9806H", "ZXA10_C320"],
        "oids": {
            # OIDs for ZTE DSLAMs
        }
    },
    "calix": {
        "models": ["E7", "C7", "E5"],
        "oids": {
            # OIDs for Calix DSLAMs
        }
    },
    "ericsson": {
        "models": ["Mini_Link", "ISAM_FX", "ASN_DSLAM"],
        "oids": {
            # OIDs for Ericsson DSLAMs
        }
    },
}