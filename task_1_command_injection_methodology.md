# Task 1: Command Injection Research Methodology

This document outlines a systematic methodology for researching command injection vulnerabilities in Huawei MA5600/MA5680 series DSLAMs. The focus is on creating a repeatable and responsible research process.

---

## Step 1: Vulnerability Surface Discovery

The initial phase focuses on comprehensively mapping all potential input vectors where external data is processed by the device. This creates a clear roadmap for targeted testing.

### Methodology:

1.  **Web Interface Enumeration:**
    *   **Objective:** Document every user-configurable parameter in the web management interface.
    *   **Process:**
        *   Systematically navigate every page, menu, and form within the web UI.
        *   Use a proxy like Burp Suite or OWASP ZAP to intercept and log all HTTP/S requests.
        *   Create a spreadsheet or database mapping every parameter to its corresponding endpoint (e.g., `POST /cgi-bin/set_hostname`), noting the expected data type and constraints.
        *   Pay special attention to functions involving file uploads (firmware, configuration), diagnostics (ping, traceroute), and any fields that accept complex strings.

2.  **CLI Parameter Analysis:**
    *   **Objective:** Identify all CLI commands that accept user-supplied strings or complex parameters.
    *   **Process:**
        *   Log into the device via SSH/Telnet and use the help system (`?`) to enumerate all available commands in each context (user, system, interface, etc.).
        *   For each command, analyze its parameters. Prioritize commands that take file paths, URLs, server addresses, descriptions, or other free-form text.
        *   Document these commands and parameters, noting the required privilege level for each.

3.  **SNMP Writable OID Identification:**
    *   **Objective:** Discover all SNMP OIDs that can be modified via SNMP SET operations.
    *   **Process:**
        *   Perform an SNMP walk of the device's MIB tree to discover all available OIDs.
        *   Use an SNMP scanning tool (e.g., `snmp-set` from Net-SNMP) to attempt to write to various OIDs.
        *   Consult vendor MIB files to identify OIDs with read-write (`RW`) access.
        *   Document all identified writable OIDs, their purpose, and the data types they accept.

4.  **TR-069 RPC Method Mapping:**
    *   **Objective:** Identify all TR-069 RPC methods exposed by the device.
    *   **Process:**
        *   If possible, set up a test ACS (Auto Configuration Server) to interact with the device.
        *   Capture and analyze the CWMP (CPE WAN Management Protocol) traffic between the device and the ACS.
        *   Document all supported RPCs (e.g., `SetParameterValues`, `Download`, `Upload`) and the parameters they expose.

---

## Step 2: Input Fuzzing Framework

This phase involves designing a systematic and semi-automated approach to test the identified input vectors for command injection flaws.

### Methodology:

1.  **Payload Generation:**
    *   **Objective:** Create a comprehensive list of fuzzing payloads.
    *   **Categories:**
        *   **Metacharacters:** `|`, `||`, `&`, `&&`, `;`, `\n`, `\r\n`
        *   **Command Substitution:** `` `command` ``, `$(command)`
        *   **Path Traversal:** `../`, `/`, `//`
        *   **Input/Output Redirection:** `>`, `<`, `>>`, `2>&1`
        *   **Globbing:** `*`, `?`, `[]`
        *   **Time-based/Out-of-Band Payloads:** `sleep 10`, `ping attacker.com`, `nslookup attacker.com` to test for blind injection.

2.  **Fuzzing Automation:**
    *   **Objective:** Develop scripts to automate the testing process.
    *   **Process:**
        *   For the web interface, use tools like Burp Intruder or custom Python scripts with the `requests` library to iterate through the mapped endpoints and parameters, injecting the payload list into each one.
        *   For the CLI, create scripts using libraries like `paramiko` (for SSH) or `telnetlib` to automate logging in and executing commands with fuzzed parameters.
        *   For SNMP, use scripting libraries (e.g., PySNMP) to send `SNMP SET` requests with fuzzed string values to the identified writable OIDs.

3.  **Result Analysis:**
    *   **Objective:** Monitor device behavior to detect successful injections.
    *   **Techniques:**
        *   **Direct Feedback:** Look for command output directly in HTTP responses or CLI output.
        *   **Behavioral Changes:** Monitor for unexpected device reboots, new processes, or created files (`ls -lart /tmp`).
        *   **Time Delays:** For time-based payloads, measure response times to detect successful `sleep` command execution.
        *   **Network Egress:** Use a network monitoring tool to watch for out-of-band connections (e.g., DNS lookups, pings) to a controlled external server.

---

## Step 3: Authentication Bypass Research

This research track runs in parallel, focusing on weaknesses that could lower the barrier to exploitation.

### Methodology:

1.  **Default Credential Analysis:**
    *   Research and document all known factory default credentials for the hardware and firmware versions under test.
    *   Test these credentials across all access vectors (Web, CLI, SNMP).

2.  **Session Management Analysis:**
    *   For the web interface, analyze how session tokens are generated, transmitted, and validated.
    *   Look for weaknesses such as predictable tokens, insecure transmission (HTTP), or lack of server-side validation.

3.  **Privilege Escalation Vectors:**
    *   Once low-privilege access is achieved, repeat the fuzzing process to identify vulnerabilities that are only exposed to authenticated users.
    *   Specifically look for flaws where a command that should be restricted to a high-privilege user can be accessed or triggered from a low-privilege context.

---

## Step 4: Proof-of-Concept (PoC) Development

For any documented and confirmed vulnerability, a clear and responsible PoC must be developed.

### Methodology:

1.  **Minimal Viable PoC:**
    *   Create the simplest possible exploit to demonstrate the vulnerability.
    *   A non-destructive command like `id` or `uname -a` is preferred. For blind injection, `sleep 5` is a good choice.

2.  **Clear Documentation:**
    *   Follow the "Vulnerability Research Report" structure provided in the project outline.
    *   Provide precise, step-by-step reproduction instructions.
    *   Include the exact payload used and describe the expected vs. actual behavior.

3.  **Impact Assessment:**
    *   Analyze and document the potential impact of the vulnerability (Confidentiality, Integrity, Availability).
    *   Clearly state the prerequisites for exploitation (e.g., "attacker must have network access to the management interface").

4.  **Responsible Disclosure:**
    *   The goal of this research is defensive. All findings should be handled according to a responsible disclosure policy, reporting them to the vendor (Huawei PSIRT) before public release.