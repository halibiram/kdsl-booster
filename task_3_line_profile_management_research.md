# Task 3: SNMP-based Line Profile Management Research Framework

This document establishes a research framework for understanding and securing the management of DSL line profiles on Huawei DSLAMs, with a focus on SNMP as the management vector. The goal is purely defensive: to understand risks and develop protective controls.

---

## Phase 1: Profile Management API Documentation

This initial phase is dedicated to reverse-engineering and documenting the management interfaces used to control DSL line profiles. A complete understanding of the API is essential for analyzing its security.

### Methodology:

1.  **Map SNMP OIDs for Profile Operations:**
    *   **Objective:** Identify every SNMP OID related to the creation, modification, deletion, and assignment of DSL line profiles.
    *   **Process:**
        *   Obtain Huawei-specific MIBs for the MA5600/MA5680 series. Use a MIB browser to parse these files and identify tables and OIDs related to "profile," "service," "line," "spectrum," etc.
        *   Perform a full SNMP walk of a test device and compare the output against the MIBs to find both documented and potentially undocumented OIDs.
        *   In a lab, perform profile configuration changes via the CLI or web interface while running an SNMP trace (capturing SNMP traps or polling relevant tables) to see which OID values change.
        *   Document the OID, its name, data type, read/write access, and its function (e.g., `1.3.6.1.4.1.2011.5.2.1.12.3.1.1.2` - `hwDslLineProfileName`).

2.  **Document CLI Equivalents:**
    *   **Objective:** Create a mapping between SNMP operations and their equivalent CLI commands.
    *   **Process:**
        *   For each identified SNMP profile operation (e.g., setting a profile name), find the corresponding command in the VRP CLI (e.g., `dsl line-profile modify <profile-id> name <new-name>`).
        *   This mapping is crucial for understanding the underlying logic and for validating changes made via SNMP.

3.  **Study Profile Hierarchy:**
    *   **Objective:** Understand the relationships between different types of profiles.
    *   **Process:**
        *   Research and document the hierarchy: how a top-level service profile might inherit from or contain other profiles like a spectrum profile, alarm profile, or DBA profile.
        *   This helps in understanding the full impact of a single change. Modifying a parent profile could have wide-ranging, unintended consequences on all associated DSL ports.

---

## Phase 2: Change Control Analysis

This phase evaluates the security mechanisms that govern how profile configurations are modified and applied.

### Methodology:

1.  **Analyze Authentication and Authorization:**
    *   **Objective:** Determine the credentials and privilege levels required to make profile changes via each management interface.
    *   **Process:**
        *   **SNMP:** Determine if changes require a read-write community string (SNMPv1/v2c) or a specific user with write privileges (SNMPv3). Test if a read-only user can make changes.
        *   **CLI:** Document the minimum privilege level required to enter the profile configuration mode and execute modification commands.
        *   **Web:** Analyze if specific user roles (e.g., "admin" vs. "operator") have different rights regarding profile management.

2.  **Investigate Audit Logging:**
    *   **Objective:** Determine if and how profile modifications are logged.
    *   **Process:**
        *   Make a change to a line profile using each interface (SNMP, CLI, Web).
        *   Immediately check all available system logs (`display logbuffer`, syslog server).
        *   Document whether the change was logged, the level of detail (who, what, when, from where), and whether logging can be disabled. A lack of detailed, immutable logging is a significant security gap.

3.  **Examine Change Validation and Commit Procedures:**
    *   **Objective:** Understand the process for validating and applying changes.
    *   **Process:**
        *   Determine if the device uses a two-step commit model (e.g., `commit` command) or if changes are applied instantly. Instant activation is riskier.
        *   Test the input validation on profile parameters. For example, try to set a data rate that is technically impossible. Does the device reject it gracefully, or does it crash?
        *   Investigate if there are rollback capabilities to revert to a previous known-good configuration.

---

## Phase 3: Impact Assessment Research

This phase focuses on modeling and understanding the potential consequences of unauthorized or malicious profile changes.

### Methodology:

1.  **Model Service Degradation Scenarios:**
    *   **Objective:** Document how specific profile changes could degrade customer service.
    *   **Process:**
        *   In a lab with test CPEs, create profiles that intentionally limit service (e.g., set upstream/downstream rates to a minimal value, increase latency parameters).
        *   Apply these "malicious" profiles to test ports and measure the impact on throughput and latency using network testing tools (e.g., iperf).

2.  **Identify Network Stability Risks:**
    *   **Objective:** Explore how profile changes could impact the stability of the DSLAM itself.
    *   **Process:**
        *   Research parameters related to power management or spectrum allocation.
        *   Hypothesize how misconfiguring these (e.g., setting invalid power levels) could potentially cause instability on a DSL line card. This research must be theoretical and not risk damaging lab equipment.

3.  **Analyze SLA and Regulatory Compliance Violations:**
    *   **Objective:** Connect technical changes to business impact.
    *   **Process:**
        *   Theoretically map how an unauthorized profile change (e.g., lowering a customer's speed) would constitute a direct violation of their Service Level Agreement (SLA).
        *   Research any regulatory requirements for broadband service delivery that could be violated through malicious configuration changes.

---

## Phase 4: Security Control Development

This final, defensive-oriented phase involves designing tools and procedures to mitigate the identified risks.

### Methodology:

1.  **Design a Change Detection System:**
    *   **Objective:** Create a script that can detect unauthorized profile modifications.
    *   **Process:**
        *   Develop a Python or shell script that periodically polls the key SNMP OIDs related to line profiles.
        *   The script will store a "known-good" baseline of these OID values.
        *   During each run, it compares the current values against the baseline and sends an alert (e.g., email, syslog message) if any discrepancies are found.

2.  **Develop Configuration Backup Automation:**
    *   **Objective:** Create a reliable, automated process for backing up DSLAM configurations.
    *   **Process:**
        *   Design a script that logs into the DSLAM via CLI or uses SNMP to trigger and retrieve a full configuration backup on a regular schedule (e.g., daily).
        *   Store these backups in a secure, version-controlled location.

3.  **Formulate Integrity Monitoring and Verification Procedures:**
    *   **Objective:** Create a process to ensure the running configuration matches the intended configuration.
    *   **Process:**
        *   Design a procedure where the automated backup is periodically compared against a master "golden" configuration template.
        *   This helps detect not just profile changes, but any unauthorized modification to the device's configuration.
        *   The change detection script from step 1 can be integrated into this larger integrity verification framework.