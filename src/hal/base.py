"""
This module defines the base Hardware Abstraction Layer (HAL) for DSL chipset interaction.
"""
from abc import ABC, abstractmethod
from typing import Any, List

class BaseDslHal(ABC):
    """
    Abstract Base Class for a DSL Hardware Abstraction Layer.

    This class defines the standard interface for interacting with the DSL
    chipset's low-level registers and memory. Specific chipset implementations
    (e.g., for Broadcom, Lantiq) should inherit from this class.
    """

    def __init__(self, ssh_interface):
        """
        Initializes the HAL with an SSH interface for command execution.
        """
        self.ssh = ssh_interface

    @abstractmethod
    def read_register(self, address: int) -> int:
        """
        Reads a value from a specific hardware register.
        """
        raise NotImplementedError

    @abstractmethod
    def write_register(self, address: int, value: int) -> bool:
        """
        Writes a value to a specific hardware register.
        """
        raise NotImplementedError

    @abstractmethod
    def get_precoding_matrix(self) -> List[List[float]]:
        """
        Retrieves the current downstream precoding matrix from the hardware.
        """
        raise NotImplementedError

    @abstractmethod
    def set_precoding_matrix(self, matrix: List[List[float]]) -> bool:
        """
        Writes a new downstream precoding matrix to the hardware.
        """
        raise NotImplementedError

    @abstractmethod
    def get_vectoring_pilot_sequence(self) -> List[int]:
        """
        Retrieves the pilot sequence data used for channel estimation.
        """
        raise NotImplementedError

    @abstractmethod
    def get_upstream_cancellation_matrix(self) -> List[List[float]]:
        """
        Retrieves the current upstream crosstalk cancellation matrix from the hardware.
        """
        raise NotImplementedError

    @abstractmethod
    def set_upstream_cancellation_matrix(self, matrix: List[List[float]]) -> bool:
        """
        Writes a new upstream crosstalk cancellation matrix to the hardware.
        """
        raise NotImplementedError