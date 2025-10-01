# Türk Telekom Analysis

## DSLAM Model: Huawei MA5608T

### Potential Vulnerabilities and Exploitation Techniques

*   **Default Credentials:**
    *   **Username:** `root`
    *   **Password:** `admin` (for older firmware) or `admin123` (for R017 and newer firmware).
    *   **Exploitation:** An attacker could try to access the DSLAM's management interface using these default credentials if they have not been changed.

*   **Default IP Address:**
    *   **IP Address:** `10.11.104.2`
    *   **Exploitation:** If the management interface is exposed to the network, an attacker could attempt to connect to this default IP address.

*   **Access Methods:**
    *   Telnet is the primary management protocol.
    *   Serial console access is also available.
    *   SSH may be available on some models.

### Profile Unlocking (VDSL 50 -> 100 Mbps)

*   No public information was found on user-level profile unlocking. This is likely controlled by the ISP's provisioning system and not a simple setting on the DSLAM that can be exploited.

### G.inp Disabling for Lower Latency

*   No specific commands or exploits were found to disable G.inp. This is typically managed through line profile configurations on the DSLAM, which are controlled by the ISP. Some forum discussions suggest that G.inp itself may not be the primary cause of latency and that other factors, such as interleaving, might be more significant. Disabling G.inp might also negatively impact line stability.

### Recommended Security Countermeasures

*   **Change Default Credentials:** Immediately change the default `root` password to a strong, unique password.
*   **Network Segmentation:** Isolate the management interface of the DSLAM from the subscriber network. Use a dedicated management VLAN.
*   **Access Control Lists (ACLs):** Apply ACLs to the management interface to restrict access to authorized IP addresses only.
*   **Disable Unnecessary Services:** If Telnet is not required for management, it should be disabled in favor of SSH if available.
*   **Regular Firmware Updates:** Keep the DSLAM firmware up to date to patch any known vulnerabilities.