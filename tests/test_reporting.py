import pytest
import json
from src.reporting import ReportGenerator

# Mock detection result for a successful identification
MOCK_SUCCESS_RESULT = {
    "primary_vendor": "huawei",
    "overall_confidence": 43.25,
    "contributing_methods": [
        {"vendor": "huawei", "certainty": 95, "method": "g_hs", "raw_data": "VSI: MA5608T"},
        {"vendor": "huawei", "certainty": 100, "method": "timing", "raw_data": "195.00ms"}
    ],
    "all_results": {"huawei": 43.25}
}

# Mock detection result for a failed identification
MOCK_FAILURE_RESULT = None


@pytest.fixture
def success_reporter():
    """Fixture for a ReportGenerator with a successful result."""
    return ReportGenerator(MOCK_SUCCESS_RESULT)


@pytest.fixture
def failure_reporter():
    """Fixture for a ReportGenerator with a failed result."""
    return ReportGenerator(MOCK_FAILURE_RESULT)


def test_text_report_success(success_reporter):
    """Tests the text report format for a successful detection."""
    report = success_reporter.generate_text_report()
    assert "Primary Vendor Identified: huawei" in report
    assert "Overall Confidence: 43.25%" in report
    assert "Contributing Evidence:" in report
    assert "Method: g_hs" in report
    assert "Certainty:  95%" in report
    assert "Data: VSI: MA5608T" in report
    assert "Method: timing" in report
    assert "Data: 195.00ms" in report

def test_text_report_failure(failure_reporter):
    """Tests the text report format for a failed detection."""
    report = failure_reporter.generate_text_report()
    assert "Result: No vendor identified." in report
    assert "Primary Vendor Identified" not in report

def test_json_report_success(success_reporter):
    """Tests the JSON report format for a successful detection."""
    report_str = success_reporter.generate_json_report()
    report_data = json.loads(report_str)

    assert "detection_timestamp" in report_data
    assert report_data["detection_result"] == MOCK_SUCCESS_RESULT

def test_json_report_failure(failure_reporter):
    """Tests the JSON report format for a failed detection."""
    report_str = failure_reporter.generate_json_report()
    report_data = json.loads(report_str)

    assert "detection_timestamp" in report_data
    assert report_data["detection_result"] is None

def test_csv_report_success(success_reporter):
    """Tests the CSV report format for a successful detection."""
    report = success_reporter.generate_csv_report()
    lines = report.strip().split('\n')
    assert len(lines) == 2 # Header + 1 data row

    header = "timestamp,primary_vendor,overall_confidence,evidence_count,contributing_methods_summary"
    assert lines[0].strip() == header

    assert "huawei" in lines[1]
    assert "43.25" in lines[1]
    assert "2" in lines[1] # evidence_count
    assert "g_hs:VSI: MA5608T|timing:195.00ms" in lines[1]

def test_csv_report_failure(failure_reporter):
    """Tests the CSV report format for a failed detection."""
    report = failure_reporter.generate_csv_report()
    lines = report.strip().split('\n')
    assert len(lines) == 2 # Header + 1 data row

    assert "N/A" in lines[1]
    assert "0.0" in lines[1]
    assert ",0," in lines[1] # evidence_count is 0
    # Ensure summary is empty
    assert lines[1].endswith(',')