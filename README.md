# DSL Bypass Ultra v1.1

## 🚀 Overview

DSL Bypass Ultra is a proof-of-concept Python framework designed to explore advanced DSL (Digital Subscriber Line) parameter manipulation. It provides a suite of tools to simulate, test, and optimize DSL line settings with the goal of achieving higher data rates.

The project is built around a modular architecture that includes:
- A resilient SSH client for connecting to network devices.
- Low-level functions for interacting with kernel parameters.
- Physics-based models for calculating optimal SNR and attenuation values.
- An automated experimentation framework for data collection.
- An AI-powered optimizer that uses machine learning to predict the best parameters for a target speed.

## ✨ Features

- **Resilient SSH Communication**: Automatically reconnects and maintains the session.
- **Kernel-Level Interaction**: Provides tools to read and write system-level DSL parameters.
- **Physics-Based Modeling**: Calculates ideal SNR and attenuation based on target performance.
- **Automated Experimentation**: Systematically sweeps through parameter ranges to collect performance data.
- **AI-Powered Optimization**: Uses a `scikit-learn` model to predict optimal settings from collected data, moving beyond brute-force testing.

## 🛠️ Getting Started

### Prerequisites

- Python 3.10+
- `pip` for installing dependencies

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd dsl-bypass-ultra
   ```

2. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Demonstration

The `main.py` script provides a full end-to-end demonstration of the project's capabilities. It runs a simulated workflow that includes data collection, AI model training, and prediction.

To run the demo, execute the following command from the project root:
```bash
python3 main.py
```

You will see output detailing each step of the process, culminating in an AI-powered prediction for the optimal DSL parameters to achieve a target speed of 125 Mbps.

## 📄 Project Specification

For a deep dive into the project's technical architecture, phase-by-phase roadmap, and detailed specifications, please see the `PROJECT_SPECIFICATION.md` file.

## ⚠️ LEGAL DISCLAIMER

**IMPORTANT:** This project is for RESEARCH and EDUCATIONAL purposes only.

- Manipulating ISP infrastructure may violate Terms of Service
- Unauthorized modification of DSL parameters may be illegal in your jurisdiction
- Use at your own risk - the authors assume no liability
- Always obtain proper authorization before testing on production systems
- This tool is intended for security research and academic study

## 🔧 Hardware Requirements

### Minimum Requirements:
- Keenetic DSL router (Skipper DSL KN-2112 or compatible)
- SSH access enabled
- USB storage for Entware (minimum 1GB)
- Stable power supply
- Physical access to the router

### Recommended Setup:
- Keenetic Skipper DSL (KN-2112) - Native supervectoring support
- 4GB+ USB 3.0 drive for Entware
- Backup router for safety
- Isolated test network
- UPS for power stability

## 📋 Step-by-Step Setup Guide

### Step 1: Enable SSH Access
```bash
# Via Keenetic Web Interface:
# 1. Go to Management > System
# 2. Enable "SSH access"
# 3. Set password for SSH
```
### Step 2: Install Entware
```bash
# Connect via SSH
ssh admin@192.168.1.1

# Install Entware (via USB)
# Follow official Keenetic Entware guide
```
### Step 3: Install DSL Bypass Ultra
```bash
# Clone repository
cd /opt
git clone https://github.com/yourusername/DSL-Bypass-Ultra.git
cd DSL-Bypass-Ultra

# Install dependencies
pip3 install -r requirements.txt
```
## 🛡️ Safety Precautions
CRITICAL SAFETY RULES:

- Always have a backup router - Don't test on your only internet connection
- Start with conservative parameters - Gradual increases only
- Monitor temperature - DSL chipsets can overheat
- Keep original firmware - Be ready to factory reset
- Document baseline - Record original parameters before any changes

### Recovery Procedure:
```bash
# If router becomes unstable:
1. Factory reset via hardware button (hold 10+ seconds)
2. Restore from backup configuration
3. Reflash original firmware if necessary
```