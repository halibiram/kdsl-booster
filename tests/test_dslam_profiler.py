"""
Unit tests for the DSLAMProfiler module.
"""
import pytest
from src.dslam_profiler import DSLAMProfiler

def test_profiler_no_issues():
    """
    Tests the profiler with a fully consistent and optimized capabilities profile.
    It should produce no warnings and no recommendations.
    """
    capabilities = {
        "vdsl2_profiles": {"consolidated_profiles": ["8a", "17a"]},
        "frequency": {"max_downstream_mhz": 30.0},
        "vectoring": {"hardware_support": True, "is_active": True},
        "retransmission": {"g_inp_supported": True, "is_active": True},
        "bonding": {"supported_standards": ["G.998.2 (Ethernet)"], "is_active": True}
    }
    profiler = DSLAMProfiler(capabilities)
    analysis = profiler.generate_profile_analysis()
    assert not analysis["warnings"]
    assert not analysis["recommendations"]

def test_profiler_frequency_warning():
    """
    Tests that a warning is generated when a high-level profile is supported
    but the maximum frequency is insufficient.
    """
    capabilities = {
        "vdsl2_profiles": {"consolidated_profiles": ["30a", "17a"]},
        "frequency": {"max_downstream_mhz": 17.664} # Not enough for 30a
    }
    profiler = DSLAMProfiler(capabilities)
    analysis = profiler.generate_profile_analysis()
    assert len(analysis["warnings"]) == 1
    assert "Inconsistency Detected" in analysis["warnings"][0]
    assert "Profile 30a" in analysis["warnings"][0]
    assert "17.664 MHz" in analysis["warnings"][0]
    assert not analysis["recommendations"]

def test_profiler_optimization_recommendations():
    """
    Tests that recommendations are generated for supported but inactive features.
    """
    capabilities = {
        "vectoring": {"hardware_support": True, "is_active": False},
        "retransmission": {"g_inp_supported": True, "is_active": False},
        "bonding": {"supported_standards": ["G.998.1 (ATM)"], "is_active": False}
    }
    profiler = DSLAMProfiler(capabilities)
    analysis = profiler.generate_profile_analysis()
    assert len(analysis["recommendations"]) == 3
    assert "Enable Vectoring" in analysis["recommendations"][0]
    assert "Enable G.inp" in analysis["recommendations"][1]
    assert "Enable Bonding" in analysis["recommendations"][2]
    assert not analysis["warnings"]

def test_profiler_mixed_warnings_and_recommendations():
    """
    Tests that the profiler can generate both warnings and recommendations
    from the same profile.
    """
    capabilities = {
        "vdsl2_profiles": {"consolidated_profiles": ["35b"]},
        "frequency": {"max_downstream_mhz": 17.0}, # Inconsistent
        "vectoring": {"hardware_support": True, "is_active": False} # Needs recommendation
    }
    profiler = DSLAMProfiler(capabilities)
    analysis = profiler.generate_profile_analysis()
    assert len(analysis["warnings"]) == 1
    assert "Profile 35b" in analysis["warnings"][0]
    assert len(analysis["recommendations"]) == 1
    assert "Enable Vectoring" in analysis["recommendations"][0]

def test_profiler_empty_capabilities():
    """
    Tests that the profiler handles an empty capabilities dictionary gracefully.
    """
    profiler = DSLAMProfiler({})
    analysis = profiler.generate_profile_analysis()
    assert not analysis["warnings"]
    assert not analysis["recommendations"]