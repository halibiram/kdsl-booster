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