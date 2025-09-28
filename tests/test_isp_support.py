import pytest
from unittest.mock import MagicMock
from src.isp_support import TurkishISPDSLAMSupport

@pytest.fixture
def mock_dslam_detector():
    """Provides a mock UniversalDSLAMDetector for testing."""
    return MagicMock()

@pytest.fixture
def isp_support(mock_dslam_detector):
    """Provides a TurkishISPDSLAMSupport instance with a mocked detector."""
    return TurkishISPDSLAMSupport(mock_dslam_detector)

def test_get_isp_profile_success(isp_support):
    """
    Tests that the correct profile is returned for a known ISP.
    """
    profile = isp_support.get_isp_profile('turk_telekom')
    assert profile is not None
    assert profile['primary_vendor'] == 'huawei'

    profile_superonline = isp_support.get_isp_profile('superonline')
    assert profile_superonline['primary_vendor'] == 'nokia'

def test_get_isp_profile_not_found(isp_support):
    """
    Tests that None is returned for an unknown ISP.
    """
    profile = isp_support.get_isp_profile('unknown_isp')
    assert profile is None

def test_select_strategy_with_matching_vendor(isp_support, mock_dslam_detector):
    """
    Tests strategy selection when the detected vendor matches the ISP's primary vendor.
    """
    # Simulate the detector successfully identifying 'huawei'
    mock_dslam_detector.identify_vendor.return_value = 'huawei'

    strategy = isp_support.select_exploitation_strategy('turk_telekom')

    assert strategy is not None
    assert strategy['vendor'] == 'huawei'
    assert strategy['confidence'] == 'high'
    assert 'g_hs_injection' in strategy['recommended_methods']

    # Verify the detector was called
    mock_dslam_detector.identify_vendor.assert_called_once()

def test_select_strategy_with_non_matching_vendor(isp_support, mock_dslam_detector):
    """
    Tests strategy selection when the detected vendor is different from the
    ISP's primary known vendor, but is known from another ISP's profile.
    """
    # Simulate that the user is on Turk Telekom, but the detector finds a Nokia DSLAM
    mock_dslam_detector.identify_vendor.return_value = 'nokia'

    strategy = isp_support.select_exploitation_strategy('turk_telekom')

    assert strategy is not None
    assert strategy['vendor'] == 'nokia'
    assert strategy['confidence'] == 'medium' # Confidence is medium due to mismatch
    assert 'profile_unlock' in strategy['recommended_methods'] # Should suggest Nokia's methods

def test_select_strategy_when_detection_fails(isp_support, mock_dslam_detector):
    """
    Tests strategy selection when the DSLAM detector cannot identify the vendor.
    """
    # Simulate the detector failing
    mock_dslam_detector.identify_vendor.return_value = None

    strategy = isp_support.select_exploitation_strategy('superonline')

    assert strategy is not None
    # It should fall back to the ISP's primary known vendor
    assert strategy['vendor'] == 'nokia'
    assert strategy['confidence'] == 'low' # Confidence is low because it's a guess
    assert 'cli_override' in strategy['recommended_methods']

def test_select_strategy_for_unknown_isp(isp_support, mock_dslam_detector):
    """
    Tests that no strategy is returned if the target ISP is not in the database.
    """
    strategy = isp_support.select_exploitation_strategy('unknown_isp')

    assert strategy is None
    # The detector should not even be called if the ISP is unknown
    mock_dslam_detector.identify_vendor.assert_not_called()