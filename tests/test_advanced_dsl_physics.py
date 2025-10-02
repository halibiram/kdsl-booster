import pytest
import numpy as np
from src.advanced_dsl_physics import AdvancedDSLPhysics, VDSL2_PROFILES, CABLE_MODELS
from src.noise_models import ImpulseNoise, AMRadioInterference, REIN

# --- Test Fixtures ---

@pytest.fixture
def physics_17a_etsi():
    """Provides a default model: 17a profile, ETSI 0.5mm cable."""
    return AdvancedDSLPhysics(profile='17a', cable_model='etsi_05mm')

@pytest.fixture
def physics_17a_ansi():
    """Provides a model with the ANSI 26AWG cable to test model differences."""
    return AdvancedDSLPhysics(profile='17a', cable_model='ansi_26awg')

# --- Initialization and Configuration Tests ---

def test_invalid_profile_raises_error():
    """Tests that initializing with an unsupported profile raises a ValueError."""
    with pytest.raises(ValueError, match="not supported"):
        AdvancedDSLPhysics(profile='invalid_profile')

def test_invalid_cable_model_raises_error():
    """Tests that initializing with an unsupported cable model raises a ValueError."""
    with pytest.raises(ValueError, match="not supported"):
        AdvancedDSLPhysics(cable_model='invalid_cable')

def test_cable_model_selection(physics_17a_etsi, physics_17a_ansi):
    """Tests that the correct cable model parameters are loaded."""
    assert physics_17a_etsi.cable_params['R0'] == CABLE_MODELS['etsi_05mm']['R0']
    assert physics_17a_ansi.cable_params['R0'] == CABLE_MODELS['ansi_26awg']['R0']
    # R0 should be different for the two models
    assert physics_17a_etsi.cable_params['R0'] != physics_17a_ansi.cable_params['R0']

# --- Physics Model Tests (RLCG and Attenuation) ---

def test_tone_generation(physics_17a_etsi):
    """Tests that tone frequencies are generated correctly, avoiding f=0."""
    assert np.all(physics_17a_etsi.tones > 0)
    assert len(physics_17a_etsi.tones) > 2500
    assert np.all(np.diff(physics_17a_etsi.tones) > 0)

def test_attenuation_increases_with_distance_and_frequency(physics_17a_etsi):
    """Tests that the RLCG attenuation model shows increased loss with distance and frequency."""
    attenuation_300m = physics_17a_etsi.model_attenuation_per_tone(distance_m=300)
    attenuation_800m = physics_17a_etsi.model_attenuation_per_tone(distance_m=800)
    assert np.all(attenuation_800m > attenuation_300m)
    assert attenuation_300m[-1] > attenuation_300m[0]

def test_different_cable_models_yield_different_attenuation(physics_17a_etsi, physics_17a_ansi):
    """Tests that the thinner ANSI cable has higher attenuation than the ETSI cable."""
    attenuation_etsi = physics_17a_etsi.model_attenuation_per_tone(distance_m=500)
    attenuation_ansi = physics_17a_ansi.model_attenuation_per_tone(distance_m=500)
    # Higher resistance of ANSI model should lead to higher attenuation
    assert np.all(attenuation_ansi > attenuation_etsi)

# --- Crosstalk (FEXT) Model Tests ---

def test_fext_noise_increases_with_disturbers(physics_17a_etsi):
    """Tests that FEXT noise PSD increases with the number of disturbers."""
    fext_10 = physics_17a_etsi.model_fext_noise_psd(n_disturbers=10, distance_m=500)
    fext_40 = physics_17a_etsi.model_fext_noise_psd(n_disturbers=40, distance_m=500)
    assert np.all(fext_40 > fext_10)

def test_snr_decreases_with_crosstalk(physics_17a_etsi):
    """Tests that SNR per tone decreases as the number of disturbers increases."""
    snr_no_fext = physics_17a_etsi.calculate_snr_per_tone(distance_m=500, n_disturbers=0)
    snr_with_fext = physics_17a_etsi.calculate_snr_per_tone(distance_m=500, n_disturbers=20)
    assert np.all(snr_with_fext < snr_no_fext)

# --- Bitrate Calculation Tests ---

def test_calculate_max_bitrate_realism_with_fext(physics_17a_etsi):
    """
    Tests bitrate calculation for realistic scenarios using the new RLCG model,
    including a standard level of crosstalk (10 disturbers).
    NOTE: Expected values are updated for the more accurate RLCG + FEXT model.
    """
    # Short distance (300m)
    rate_300m = physics_17a_etsi.calculate_max_bitrate(distance_m=300, n_disturbers=10)
    assert 85 < rate_300m < 110  # Adjusted expectation for the new RLCG model

    # Medium distance (700m)
    rate_700m = physics_17a_etsi.calculate_max_bitrate(distance_m=700, n_disturbers=10)
    assert 70 < rate_700m < 80  # Expect ~73 Mbps, adjusted for the new model

    # Long distance (1200m) - bitrate should not drop off dramatically due to FEXT dominance
    rate_1200m = physics_17a_etsi.calculate_max_bitrate(distance_m=1200, n_disturbers=10)
    assert 60 < rate_1200m < 70  # Expect ~64 Mbps

def test_bitrate_decreases_with_crosstalk(physics_17a_etsi):
    """Tests that the final bitrate is lower when more disturbers are present."""
    rate_no_fext = physics_17a_etsi.calculate_max_bitrate(distance_m=600, n_disturbers=0)
    rate_with_fext = physics_17a_etsi.calculate_max_bitrate(distance_m=600, n_disturbers=20)
    assert rate_with_fext < rate_no_fext
    assert rate_with_fext > 0

def test_bitrate_lower_for_inferior_cable(physics_17a_etsi, physics_17a_ansi):
    """
    Tests that the bitrate for the inferior cable is not greater than the
    bitrate for the standard cable.
    """
    # In a FEXT-limited scenario, the bitrates may be nearly identical.
    # The key is to ensure the model doesn't produce a nonsensical result
    # where the worse cable performs better.
    rate_etsi = physics_17a_etsi.calculate_max_bitrate(distance_m=800, n_disturbers=10)
    rate_ansi = physics_17a_ansi.calculate_max_bitrate(distance_m=800, n_disturbers=10)
    assert rate_ansi <= rate_etsi

# --- Noise Model Integration Tests ---

def test_snr_with_impulse_noise(physics_17a_etsi):
    """Tests that SNR is lower when impulse noise is added."""
    snr_baseline = physics_17a_etsi.calculate_snr_per_tone(distance_m=500)

    impulse_model = ImpulseNoise(arrival_rate_per_sec=5)
    physics_with_noise = AdvancedDSLPhysics(
        profile='17a',
        cable_model='etsi_05mm',
        noise_models={'impulse': impulse_model}
    )
    snr_with_impulse = physics_with_noise.calculate_snr_per_tone(distance_m=500, duration_sec=10)

    # The average SNR should be lower when impulse noise is present
    assert np.mean(snr_with_impulse) < np.mean(snr_baseline)

def test_bitrate_with_am_radio_interference(physics_17a_etsi):
    """Tests that bitrate is reduced by AM radio interference."""
    rate_baseline = physics_17a_etsi.calculate_max_bitrate(distance_m=400)

    stations = [{'frequency_hz': 1e6, 'power_dbm': -60, 'bandwidth_hz': 10e3}]
    am_model = AMRadioInterference(stations)
    physics_with_rfi = AdvancedDSLPhysics(
        profile='17a',
        cable_model='etsi_05mm',
        noise_models={'am_radio': am_model}
    )
    rate_with_rfi = physics_with_rfi.calculate_max_bitrate(distance_m=400)

    assert rate_with_rfi < rate_baseline

def test_background_noise_adaptation(physics_17a_etsi):
    """Tests that updating the background noise affects SNR."""
    snr_before = physics_17a_etsi.calculate_snr_per_tone(distance_m=500)

    # Create a new, higher noise floor
    new_noise_floor = np.full_like(physics_17a_etsi.tones, -120.0)
    physics_17a_etsi.update_background_noise(new_noise_floor)

    snr_after = physics_17a_etsi.calculate_snr_per_tone(distance_m=500)

    assert np.all(snr_after < snr_before)

def test_update_background_noise_with_wrong_shape_raises_error(physics_17a_etsi):
    """Tests that updating background noise with a mismatched shape raises a ValueError."""
    invalid_noise_profile = np.array([-140.0, -130.0])
    with pytest.raises(ValueError, match="must have the same shape"):
        physics_17a_etsi.update_background_noise(invalid_noise_profile)