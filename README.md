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

### 🔧 Entware MIPS Installation

This project can be run on MIPS-based devices (like many routers) that support Entware. Due to package availability limitations on this platform, the AI-powered optimization features are not available, but the core functionalities will work.

#### Prerequisites

- A MIPS-based device with Entware installed and a working `opkg` package manager.
- A separate machine with Docker installed to cross-compile Python packages.

#### Step 1: Cross-Compile Python Wheels

Some Python dependencies are not available in the Entware repository and must be cross-compiled. A `Dockerfile` is provided to simplify this process.

1.  **Build the Docker Image**:
    On a machine with Docker, run the following command from the project root:
    ```bash
    docker build -t mips-builder .
    ```

2.  **Extract the Compiled Wheels**:
    Create a `wheelhouse` directory in your project root and run the container to copy the compiled wheels into it:
    ```bash
    mkdir wheelhouse
    docker run --rm -v $(pwd)/wheelhouse:/opt/wheelhouse mips-builder
    ```
    The `wheelhouse` directory will now contain the MIPS-compatible Python wheels.

#### Step 2: Set Up the MIPS Device

1.  **Install Python and Pip**:
    On your MIPS device, install Python 3 and pip using `opkg`:
    ```bash
    opkg update
    opkg install python3 python3-pip
    ```

2.  **Copy Project Files**:
    Transfer the entire project directory, including the `wheelhouse` directory, to your MIPS device (e.g., using `scp`).

#### Step 3: Install Python Dependencies

1.  Navigate to the project directory on your MIPS device.

2.  Install the cross-compiled Python packages using the wheels you created:
    ```bash
    pip3 install --no-index --find-links=./wheelhouse -r requirements-mips.txt
    ```

#### Step 4: Run the Application

You can now run the main application:
```bash
python3 main.py
```

## 📄 Project Specification

For a deep dive into the project's technical architecture, phase-by-phase roadmap, and detailed specifications, please see the `PROJECT_SPECIFICATION.md` file.

## 🏛️ Architecture and Extensibility

The system is designed with a modular and extensible architecture to facilitate future enhancements, such as database integration and machine learning-powered predictions.

### Database Abstraction

Vendor-specific data, such as SNMP OIDs and capability mappings, is managed through the `DatabaseManager` class in `src/database_manager.py`. Currently, this class loads data from the `vendor_signatures.json` file, but it serves as an abstraction layer. To integrate a real database (e.g., SQL, NoSQL), you would only need to update the methods within this class to fetch data from the new source, without changing any of the analyzer classes that consume the data.

### Machine Learning Integration

The `MLEnhancer` class in `src/ml_enhancer.py` is a placeholder designed to showcase how machine learning models could be integrated into the workflow. Future work could involve:
- **Capability Prediction**: Training a model to predict a DSLAM's full capabilities from a partial set of observations (e.g., predicting SNMP settings based on G.hs data).
- **DSLAM Classification**: Training a model to classify a DSLAM vendor or model based on performance "fingerprints" like timing data and error rates, providing an alternative identification method when primary methods fail.