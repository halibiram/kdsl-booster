# -*- coding: utf-8 -*-
"""
This module provides a collection of advanced noise models for DSL simulations.
It includes models for various types of noise that can affect DSL lines,
such as impulse noise, SHINE, AM radio interference, and REIN.
"""

import numpy as np
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ImpulseNoise:
    """
    Models impulse noise events, characterized by sudden, short-duration energy bursts.
    This model uses a Poisson process to determine the arrival of impulses and
    allows for variable amplitude and duration.
    """

    def __init__(self, arrival_rate_per_sec=0.1, min_amplitude_mv=5, max_amplitude_mv=50,
                 min_duration_us=10, max_duration_us=100):
        """
        Initializes the impulse noise model.

        Args:
            arrival_rate_per_sec (float): The average number of impulses per second.
            min_amplitude_mv (float): The minimum amplitude of noise impulses in millivolts.
            max_amplitude_mv (float): The maximum amplitude of noise impulses in millivolts.
            min_duration_us (float): The minimum duration of an impulse in microseconds.
            max_duration_us (float): The maximum duration of an impulse in microseconds.
        """
        self.arrival_rate = arrival_rate_per_sec
        self.min_amplitude = min_amplitude_mv
        self.max_amplitude = max_amplitude_mv
        self.min_duration_us = min_duration_us
        self.max_duration_us = max_duration_us
        logging.info("Impulse noise model initialized.")

    def generate_noise_psd(self, tones: np.ndarray, symbol_rate: float, duration_sec: float) -> np.ndarray:
        """
        Generates the Power Spectral Density (PSD) of the impulse noise over a given duration.

        Args:
            tones (np.ndarray): Array of tone frequencies in Hz.
            symbol_rate (float): The symbol rate of the DSL signal (e.g., 4000 symbols/sec).
            duration_sec (float): The total duration of the simulation in seconds.

        Returns:
            np.ndarray: An array representing the noise PSD in dBm/Hz for each tone.
        """
        num_symbols = int(duration_sec * symbol_rate)
        num_impulses = np.random.poisson(self.arrival_rate * duration_sec)

        if num_impulses == 0:
            return np.full_like(tones, -200.0) # Return a very low noise floor if no impulses

        # Total energy will be distributed across the frequency spectrum
        total_noise_energy_mw = 0
        for _ in range(num_impulses):
            # For each impulse, determine its characteristics
            amplitude_v = np.random.uniform(self.min_amplitude, self.max_amplitude) / 1000.0 # to Volts
            duration_s = np.random.uniform(self.min_duration_us, self.max_duration_us) / 1e6 # to Seconds

            # Energy of a single rectangular pulse is proportional to A^2 * T
            # Assuming 1 Ohm impedance for energy calculation
            impulse_energy = (amplitude_v ** 2) * duration_s
            total_noise_energy_mw += impulse_energy * 1000 # Convert to milliwatts

        # Spread the total energy over the entire simulation duration and bandwidth
        total_bandwidth_hz = tones[-1] - tones[0]
        avg_power_mw = total_noise_energy_mw / duration_sec
        avg_psd_mw_hz = avg_power_mw / total_bandwidth_hz

        # Convert to dBm/Hz
        # Add a small epsilon to prevent log10(0)
        noise_psd_dbm_hz = 10 * np.log10(avg_psd_mw_hz + 1e-20)

        logging.info(f"Generated {num_impulses} impulses, resulting in an average noise PSD of {noise_psd_dbm_hz:.2f} dBm/Hz.")

        # For simplicity, we assume the impulse noise has a flat spectrum
        # A more advanced model could shape this based on pulse shape
        return np.full_like(tones, noise_psd_dbm_hz)


class SHINE:
    """
    Models SHINE (Stationary and Non-Stationary Hybrid Impulse Noise).
    This model combines a stationary background noise source with a non-stationary
    impulse noise source to create a more realistic noise environment.
    """

    def __init__(self, stationary_noise_psd_dbm_hz: np.ndarray, impulse_model: ImpulseNoise):
        """
        Initializes the SHINE model.

        Args:
            stationary_noise_psd_dbm_hz (np.ndarray): The PSD of the stationary background noise.
            impulse_model (ImpulseNoise): An instance of the ImpulseNoise model.
        """
        self.stationary_noise_psd = stationary_noise_psd_dbm_hz
        self.impulse_model = impulse_model
        logging.info("SHINE model initialized.")

    def generate_noise_psd(self, tones: np.ndarray, symbol_rate: float, duration_sec: float) -> np.ndarray:
        """
        Generates the combined noise PSD from stationary and impulse sources.

        Args:
            tones (np.ndarray): Array of tone frequencies in Hz.
            symbol_rate (float): The symbol rate of the DSL signal.
            duration_sec (float): The total duration of the simulation.

        Returns:
            np.ndarray: The combined noise PSD in dBm/Hz.
        """
        # Generate impulse noise PSD for the period
        impulse_noise_psd_dbm_hz = self.impulse_model.generate_noise_psd(
            tones, symbol_rate, duration_sec
        )

        # Convert both PSDs from dBm/Hz to mW/Hz
        stationary_noise_mw_hz = 10**(self.stationary_noise_psd / 10)
        impulse_noise_mw_hz = 10**(impulse_noise_psd_dbm_hz / 10)

        # Sum the powers in the linear domain
        total_noise_mw_hz = stationary_noise_mw_hz + impulse_noise_mw_hz

        # Convert the total noise back to dBm/Hz
        # Add a small epsilon to prevent log10(0)
        total_noise_dbm_hz = 10 * np.log10(total_noise_mw_hz + 1e-20)

        logging.info("Combined stationary and impulse noise for SHINE model.")
        return total_noise_dbm_hz


class AMRadioInterference:
    """
    Models interference from AM radio stations, which are a common source of RFI.
    This model allows defining multiple interfering stations with specific frequencies,
    power levels, and bandwidths.
    """

    def __init__(self, stations: list):
        """
        Initializes the AM radio interference model.

        Args:
            stations (list): A list of dictionaries, where each dictionary defines
                             a station with 'frequency_hz', 'power_dbm', and 'bandwidth_hz'.
        """
        self.stations = stations
        logging.info(f"AM Radio Interference model initialized with {len(stations)} stations.")

    def generate_noise_psd(self, tones: np.ndarray) -> np.ndarray:
        """
        Generates the noise PSD caused by AM radio interference.

        Args:
            tones (np.ndarray): Array of tone frequencies in Hz.

        Returns:
            np.ndarray: An array representing the RFI noise PSD in dBm/Hz for each tone.
        """
        noise_psd_mw_hz = np.zeros_like(tones, dtype=float)

        for station in self.stations:
            center_freq = station['frequency_hz']
            power_dbm = station['power_dbm']
            bandwidth_hz = station['bandwidth_hz']

            # Convert station power from dBm to mW
            power_mw = 10**(power_dbm / 10)
            psd_mw_hz = power_mw / bandwidth_hz # Average PSD over the station's bandwidth

            # Find the tones that fall within the station's bandwidth
            lower_bound = center_freq - (bandwidth_hz / 2)
            upper_bound = center_freq + (bandwidth_hz / 2)
            affected_tones_mask = (tones >= lower_bound) & (tones <= upper_bound)

            # Add the station's PSD to the affected tones
            noise_psd_mw_hz[affected_tones_mask] += psd_mw_hz
            logging.debug(f"Applied interference from station at {center_freq} Hz.")

        # Convert the total noise PSD from mW/Hz to dBm/Hz
        # Add a small epsilon to prevent log10(0)
        noise_psd_dbm_hz = 10 * np.log10(noise_psd_mw_hz + 1e-20)

        # For tones with no interference, set a very low noise floor
        noise_psd_dbm_hz[noise_psd_mw_hz == 0] = -200.0

        return noise_psd_dbm_hz


class REIN:
    """
    Models REIN (Repetitive Electrical Impulse Noise), often caused by AC power cycles.
    This noise is characterized by impulses occurring at a fixed frequency, typically
    related to the AC line frequency (e.g., 50 or 60 Hz).
    """

    def __init__(self, frequency_hz=50, power_dbm=-60, bandwidth_hz=1000):
        """
        Initializes the REIN model.

        Args:
            frequency_hz (int): The fundamental frequency of the repetitive impulses.
            power_dbm (float): The total power of the REIN interference in dBm.
            bandwidth_hz (float): The bandwidth over which the REIN power is spread.
        """
        self.frequency = frequency_hz
        self.power_dbm = power_dbm
        self.bandwidth = bandwidth_hz
        logging.info(f"REIN model initialized at {frequency_hz} Hz fundamental frequency.")

    def generate_noise_psd(self, tones: np.ndarray) -> np.ndarray:
        """
        Generates the noise PSD for REIN. The noise appears as spectral lines
        at multiples of the fundamental frequency.

        Args:
            tones (np.ndarray): Array of tone frequencies in Hz.

        Returns:
            np.ndarray: An array representing the REIN noise PSD in dBm/Hz.
        """
        noise_psd_mw_hz = np.zeros_like(tones, dtype=float)

        # Convert total power to mW and calculate PSD in mW/Hz
        total_power_mw = 10**(self.power_dbm / 10)
        psd_mw_hz = total_power_mw / self.bandwidth

        # Find the number of harmonics that fall within the DSL frequency range
        max_freq = tones[-1]
        num_harmonics = int(max_freq // self.frequency)

        for i in range(1, num_harmonics + 1):
            harmonic_freq = i * self.frequency

            # Find the tone closest to the harmonic frequency
            closest_tone_idx = (np.abs(tones - harmonic_freq)).argmin()

            # For simplicity, we apply the noise power to the single closest tone.
            # A more complex model would distribute this power over a small bandwidth.
            # We need to calculate the equivalent power for a single tone's bandwidth
            tone_spacing = tones[1] - tones[0] if len(tones) > 1 else 4312.5
            noise_psd_mw_hz[closest_tone_idx] += psd_mw_hz * tone_spacing

        # Convert back to dBm/Hz
        noise_psd_dbm_hz = 10 * np.log10(noise_psd_mw_hz + 1e-20)
        noise_psd_dbm_hz[noise_psd_mw_hz == 0] = -200.0

        logging.info(f"Generated REIN noise with {num_harmonics} harmonics.")
        return noise_psd_dbm_hz