import pytest

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (requires hardware)"
    )
    config.addinivalue_line(
        "markers", "hardware: marks tests that require physical Keenetic device"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )