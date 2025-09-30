import yaml
from pathlib import Path
from typing import Dict, Any

class ConfigLoader:
    """
    Load and validate configuration from YAML file
    """
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._validate_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def _validate_config(self):
        """Validate configuration values"""
        # Validate DSL parameters
        dsl = self.config.get('dsl', {})
        baseline = dsl.get('baseline', {})
        limits = dsl.get('safety_limits', {})

        # Check baseline values
        assert 0 < baseline.get('rate_mbps', 0) < 1000, "Invalid baseline rate"
        assert 0 < baseline.get('snr_db', 0) < 100, "Invalid baseline SNR"

        # Check safety limits
        assert limits.get('min_snr_db', 0) < limits.get('max_snr_db', 100), \
            "Invalid SNR limits"

    def get(self, key_path: str, default=None):
        """
        Get configuration value using dot notation
        Example: config.get('dsl.baseline.rate_mbps')
        """
        keys = key_path.split('.')
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value