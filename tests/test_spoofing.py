import pytest
from src.spoofing import (
    calculate_realistic_attenuation,
    DynamicSNRSpoofer,
)

def test_calculate_realistic_attenuation():
    """
    Tests the attenuation calculation with various distances.
    """
    # Test based on the reference value from the project spec
    # 300m -> 18.5 dB
    assert calculate_realistic_attenuation(300) == 18.5

    # Test a shorter distance
    # 100m should be roughly a third of 300m, so ~6.2 dB
    assert calculate_realistic_attenuation(100) == 6.2

    # Test a very short distance
    assert calculate_realistic_attenuation(10) == 0.6

    # Test the edge case of zero or negative distance
    assert calculate_realistic_attenuation(0) == 0.5
    assert calculate_realistic_attenuation(-100) == 0.5


def test_dynamic_snr_spoofer_initialization():
    """
    Tests that the DynamicSNRSpoofer class initializes correctly.
    """
    spoofer = DynamicSNRSpoofer(base_rate_mbps=30, base_snr_db=25)
    assert spoofer.base_rate_mbps == 30
    assert spoofer.base_snr_db == 25
    assert spoofer.LOG2_FACTOR == 6.0


def test_calculate_optimal_snr_curve():
    """
    Tests the SNR calculation for various target data rates.
    """
    spoofer = DynamicSNRSpoofer(base_rate_mbps=30, base_snr_db=25)

    # Test doubling the rate (should add exactly 6 dB)
    # 30 -> 60 Mbps should require 25 + 6 = 31 dB
    assert spoofer.calculate_optimal_snr_curve(target_rate_mbps=60) == 31.0

    # Test quadrupling the rate (should add 12 dB)
    # 30 -> 120 Mbps should require 25 + 12 = 37 dB
    assert spoofer.calculate_optimal_snr_curve(target_rate_mbps=120) == 37.0

    # Test a non-integer rate increase
    # 30 -> 100 Mbps
    # SNR = 25 + 6 * log2(100/30) = 25 + 6 * 1.737 = 25 + 10.42 = 35.4
    assert spoofer.calculate_optimal_snr_curve(target_rate_mbps=100) == 35.4

    # Test a target rate lower than the base rate (should return base SNR)
    assert spoofer.calculate_optimal_snr_curve(target_rate_mbps=20) == 25.0

    # Test a target rate equal to the base rate (should return base SNR)
    assert spoofer.calculate_optimal_snr_curve(target_rate_mbps=30) == 25.0