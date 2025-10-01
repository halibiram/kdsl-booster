# Task 7: Lab Environment Setup and Safety Protocols

This document outlines the critical design requirements and safety protocols for establishing a secure and isolated lab environment for DSLAM security research. Adherence to these protocols is mandatory to prevent accidental damage to equipment and to ensure that research activities do not impact any production networks.

---

## 1. Network Isolation

The single most important principle of the research lab is network isolation. The lab environment must be treated as potentially hostile and must never be allowed to connect to any other network.

### Requirements:

*   **Physical Separation (Air-Gapping):**
    *   The lab network must be physically disconnected from any production, corporate, or public network. There should be no physical cable connecting the lab's network switch to any other network infrastructure. This is the most effective form of isolation.

*   **Isolated VLAN:**
    *   If a shared physical switch must be used, the lab must be placed in a dedicated VLAN. The VLAN must have no Layer 3 interface (SVI) and no routing enabled to any other VLAN or network.

*   **Firewall Rules:**
    *   A dedicated firewall should be placed at the edge of the lab network (if any external access for tools is temporarily required).
    *   The default policy must be **deny all** for both inbound and outbound traffic.
    *   Explicit rules should only be created for specific, temporary needs (e.g., allowing a researcher's laptop to access a device's web UI) and should be removed immediately after use. Outbound connections from the DSLAM or other lab equipment must be strictly forbidden.

*   **Wireless Isolation:**
    *   Disable all Wi-Fi and Bluetooth capabilities on lab equipment. Do not set up a wireless access point within the lab network.

---

## 2. Equipment Configuration

All research equipment must be configured in a controlled and documented manner.

### Requirements:

*   **Factory Reset:**
    *   Every piece of equipment (DSLAM, switches, CPEs) must be factory reset before being introduced into the lab environment. This ensures that no residual configuration from a previous environment poses a security risk.

*   **Disable Cloud Management:**
    *   If the device supports any form of cloud-based management or "phone home" features, these must be explicitly disabled. This is critical to prevent the device from attempting to make outbound connections.

*   **Baseline Configuration:**
    *   A minimal, documented baseline configuration should be applied to the device to enable basic management access (e.g., setting a management IP address and local user credentials).
    *   This baseline configuration must be saved and version-controlled.

*   **Configuration Backups:**
    *   Before beginning any research that involves modifying the configuration, take a full backup of the current state. This allows for a quick rollback if the device becomes unstable.

---

## 3. Monitoring and Logging

Comprehensive logging of all research activities is essential for reproducibility and analysis.

### Requirements:

*   **Dedicated Log Server:**
    *   Set up a dedicated syslog server within the isolated lab network.
    *   Configure all lab devices to send their logs to this server. This creates a centralized, persistent record of all system events.

*   **Session Logging:**
    *   Use terminal emulators (like `screen` or `tmux` with logging enabled) or proxy tools to capture all interactive CLI sessions and web interface requests. Every command issued and every request sent should be logged.

*   **System State Snapshots:**
    *   At key points in the research (e.g., before and after a fuzzing run), document the device's state by running a series of `display` commands (e.g., `display version`, `display device`, `display logbuffer`) and saving the output.

---

## 4. Safety Protocols

These protocols are designed to prevent equipment damage and ensure the integrity of the research process.

### Requirements:

*   **Emergency Shutdown Procedure:**
    *   Clearly label and ensure easy access to the power switches for all equipment. In the event of a device becoming completely unresponsive or behaving erratically, the first step is to physically power it off.

*   **Equipment Damage Prevention:**
    *   Research should be conducted in a way that minimizes the risk of permanent damage ("bricking") to the device.
    *   Avoid making physical hardware modifications.
    *   Be extremely cautious when modifying bootloader variables or attempting to flash untrusted firmware images. Have a documented plan for recovery (e.g., using a serial console and TFTP to load a known-good firmware image) before attempting such actions.

*   **Data Sanitization:**
    *   At the conclusion of the research project, all equipment must be sanitized.
    *   This involves performing a full factory reset and, if possible, overwriting the device's storage to ensure no research artifacts (scripts, logs, modified configurations) remain.

*   **Responsible Handling of Findings:**
    *   Any discovered vulnerabilities must be handled according to a responsible disclosure policy. They should be reported to the vendor in a private and detailed manner, allowing them time to develop a patch before any public disclosure. The goal is to improve security, not to enable exploitation.