# Task 2: SNMP Community String Security Assessment Methodology

This document outlines a methodology for conducting a thorough security assessment of SNMP configurations on Huawei DSLAMs, with a primary focus on the weaknesses inherent in SNMPv1/v2c community strings.

---

## Phase 1: SNMP Configuration Audit

This phase focuses on researching and documenting what constitutes a secure versus an insecure SNMP configuration, creating a baseline for the assessment.

### Methodology:

1.  **Document Default and Weak Strings:**
    *   **Objective:** Compile a comprehensive list of community strings likely to be found in a misconfigured environment.
    *   **Process:**
        *   Research official Huawei documentation for any factory-default community strings for the MA5600/MA5680 series.
        *   Compile a list of universally common default strings (e.g., `public`, `private`, `admin`, `manager`, `system`).
        *   Gather intelligence on commonly used weak strings, such as vendor names (`huawei`, `cisco`), device models, or simple variations (`private123`).

2.  **Analyze SNMP Access Patterns:**
    *   **Objective:** Understand how SNMP is typically used in carrier environments to inform testing.
    *   **Process:**
        *   Research common network management systems (NMS) and the SNMP access they require (read-only for monitoring, read-write for configuration).
        *   Document the security implications of using different SNMP versions (v1, v2c, v3), emphasizing the cleartext nature of v1/v2c vs. the security features of v3 (authentication and encryption).

3.  **Define Secure Baselines:**
    *   **Objective:** Establish a clear definition of a secure SNMP configuration.
    *   **Process:**
        *   Document best practices, including the mandatory use of SNMPv3 with `authPriv` security level.
        *   Formulate strong community string/password policies (e.g., minimum length, character complexity, no dictionary words).
        *   Outline the principle of least privilege for SNMP access, such as using read-only strings for monitoring and tightly restricting read-write access.
        *   Define best practices for Access Control Lists (ACLs), ensuring that SNMP access is limited to specific, trusted IP addresses of NMS platforms.

---

## Phase 2: Security Testing Framework

This phase provides a practical, educational framework for actively testing the security of an SNMP implementation.

### Methodology:

1.  **Dictionary Attack:**
    *   **Objective:** Systematically test for the presence of default or weak community strings.
    *   **Process:**
        *   Use the compiled list from Phase 1 as a dictionary file.
        *   Employ an SNMP auditing tool like `onesixtyone`, `snmp-brute`, or a custom script to attempt to query a target device with each string in the dictionary.
        *   The script should test for both read-only and read-write access with each string.
        *   **Example Tool Usage:** `onesixtyone -c community-strings.txt <target-ip>`

2.  **Pattern and Entropy Analysis:**
    *   **Objective:** Go beyond simple dictionary attacks by analyzing common organizational naming conventions and measuring the strength of discovered strings.
    *   **Process:**
        *   **Pattern Analysis:** Develop and test for patterns based on educated guesses about the target environment, such as `[site-name]_[role]_[access]`, (e.g., `london-dslam-ro`).
        *   **Entropy Analysis:** For any discovered community string, calculate its entropy to provide a quantifiable measure of its strength. A simple script can be written to assess length and character set diversity (e.g., upper, lower, numeric, special). This helps differentiate a weak string like `huawei1` from a strong one like `j!T7p@3s&bE#`.

---

## Phase 3: Access Control Testing

This phase focuses on verifying that configured security controls are working as expected.

### Methodology:

1.  **ACL Effectiveness Verification:**
    *   **Objective:** Ensure that IP-based ACLs correctly filter SNMP traffic.
    *   **Process:**
        *   From an IP address that is **not** in the allowed ACL, attempt to send an SNMP query using a known-valid community string.
        *   The expected result is a timeout (no response), proving the ACL is effective. If a response is received, the ACL is misconfigured.

2.  **Access Privilege Separation:**
    *   **Objective:** Verify that read-only and read-write permissions are correctly enforced.
    *   **Process:**
        *   Using a known read-only community string, attempt to perform an `SNMP SET` operation on a writable OID (e.g., `sysContact`).
        *   The expected result is an authorization error. If the write succeeds, there is a critical privilege separation flaw.

3.  **View-Based Access Control (VACM) Testing:**
    *   **Objective:** In SNMPv3, verify that view-based controls correctly restrict a user's access to a specific subset of the MIB tree.
    *   **Process:**
        *   Using valid SNMPv3 credentials for a user with restricted view, attempt to query an OID that is **outside** their permitted view.
        *   The expected result is an error indicating the OID is not in view. A successful response indicates a misconfiguration of the VACM.

---

## Phase 4: Protocol Security Analysis

This phase is designed to demonstrate the inherent risks of using insecure SNMP versions.

### Methodology:

1.  **Cleartext Credential Exposure:**
    *   **Objective:** Visually demonstrate that SNMPv1/v2c community strings are sent in cleartext.
    *   **Process:**
        *   In a lab environment, use a packet capture tool like `tcpdump` or Wireshark to record network traffic while an NMS polls a device using SNMPv1 or v2c.
        *   Filter for SNMP traffic (UDP port 161) and inspect the packet contents.
        *   Document with screenshots that the community string is clearly visible within the packet payload.

2.  **SNMPv3 Encryption Verification:**
    *   **Objective:** Demonstrate the security benefits of SNMPv3.
    *   **Process:**
        *   Repeat the traffic capture process, this time with a device configured for SNMPv3 using the `authPriv` security level.
        *   Inspect the captured packets and show that the SNMP payload is encrypted and the community string/credentials are not visible. This provides a powerful argument for migrating to SNMPv3.