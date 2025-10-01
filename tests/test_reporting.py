"""
Unit tests for the ReportGenerator module.
"""
import pytest
import json
from src.reporting import ReportGenerator

@pytest.fixture
def full_detection_result():
    """
    Provides a comprehensive, nested result dictionary simulating a full
    capability discovery run.
    """
    return {
        "primary_vendor": "huawei",
        "overall_confidence": 98.75,
        "contributing_methods": [],
        "capability_analysis": {
            "vdsl2_profiles": {"consolidated_profiles": ["17a", "30a"]},
            "vectoring": {"hardware_support": True, "is_active": True},
            "bonding": {"supported_standards": ["G.998.2 (Ethernet)"], "is_active": False},
            "frequency": {"max_downstream_mhz": 30.0, "band_plan": "Custom"},
            "retransmission": {"g_inp_supported": True, "is_active": True},
            "psd": {"psd_mask_class": "ETSI Annex B"},
            "optimization_analysis": {
                "warnings": ["Test Warning"],
                "recommendations": ["Test Recommendation"]
            }
        }
    }

def test_text_report_generation(full_detection_result):
    """
    Tests that the text report correctly formats the full, nested data structure.
    """
    generator = ReportGenerator(full_detection_result)
    report = generator.generate_text_report()

    # Check for presence of all section headers
    assert "Basic Information" in report
    assert "VDSL2 Profile Support" in report
    assert "Vectoring Capabilities" in report
    assert "Bonding Capabilities" in report
    assert "Frequency Support" in report
    assert "Retransmission Support" in report
    assert "PSD Configuration" in report
    assert "Optimization Recommendations" in report

    # Check for specific data points
    assert "Vendor: huawei" in report
    assert "Supported Profiles: 17a, 30a" in report
    assert "Hardware Support: Yes" in report
    assert "Standards Supported: G.998.2 (Ethernet)" in report
    assert "Currently Active: No" in report # For bonding
    assert "Maximum Downstream: 30.0 MHz" in report
    assert "G.inp Support: Yes" in report
    assert "PSD Mask Class: ETSI Annex B" in report
    assert "Test Warning" in report
    assert "Test Recommendation" in report

def test_json_report_generation(full_detection_result):
    """
    Tests that the JSON report correctly structures the full profile.
    """
    generator = ReportGenerator(full_detection_result)
    report_str = generator.generate_json_report()
    report_data = json.loads(report_str)

    profile = report_data["DSLAM Capability Profile"]

    # Check for all top-level keys
    assert "Basic Information" in profile
    assert "VDSL2 Profile Support" in profile
    assert "Vectoring Capabilities" in profile
    assert "Bonding Capabilities" in profile
    assert "Frequency Support" in profile
    assert "Retransmission Support" in profile
    assert "PSD Configuration" in profile
    assert "Optimization Recommendations" in profile

    # Check specific nested values
    assert profile["Basic Information"]["Vendor"] == "huawei"
    assert profile["VDSL2 Profile Support"]["Supported Profiles"] == ["17a", "30a"]
    assert profile["Vectoring Capabilities"]["Currently Active"] is True
    assert profile["Bonding Capabilities"]["Currently Bonded"] is False
    assert profile["Optimization Recommendations"]["warnings"] == ["Test Warning"]
    assert profile["Optimization Recommendations"]["recommendations"] == ["Test Recommendation"]

def test_csv_report_generation(full_detection_result):
    """
    Tests that the CSV report still generates correctly and doesn't break.
    """
    generator = ReportGenerator(full_detection_result)
    report = generator.generate_csv_report()
    assert "timestamp,primary_vendor,overall_confidence" in report
    assert "huawei,98.75" in report