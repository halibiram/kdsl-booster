"""
This module provides the VectoringManipulator class, which is responsible for
performing high-level G.vector (G.993.5) manipulations.
"""
import logging
from typing import List
from src.hal.base import BaseDslHal

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VectoringManipulator:
    """
    Orchestrates advanced vectoring operations using a hardware-specific HAL.
    """

    def __init__(self, hal: BaseDslHal):
        """
        Initializes the manipulator with a specific Hardware Abstraction Layer.

        Args:
            hal: An instance of a class that inherits from BaseDslHal,
                 providing the low-level hardware interface.
        """
        self.hal = hal
        logging.info(f"VectoringManipulator initialized with HAL: {hal.__class__.__name__}")

    def read_precoding_matrix(self) -> List[List[float]]:
        """
        Reads the downstream precoding matrix from the DSLAM.

        Returns:
            A 2D list representing the precoding matrix, or an empty list on failure.
        """
        logging.info("Attempting to read precoding matrix via HAL.")
        matrix = self.hal.get_precoding_matrix()
        if not matrix:
            logging.warning("Reading precoding matrix failed or returned empty.")
        else:
            logging.info(f"Successfully read a {len(matrix)}x{len(matrix[0])} precoding matrix.")
        return matrix

    def write_precoding_matrix(self, matrix: List[List[float]]) -> bool:
        """
        Writes a modified downstream precoding matrix to the DSLAM.

        Args:
            matrix: The new precoding matrix to write.

        Returns:
            True if the write operation was successful, False otherwise.
        """
        if not matrix or not isinstance(matrix, list):
            logging.error("Invalid matrix provided for writing.")
            return False

        logging.info("Attempting to write precoding matrix via HAL.")
        success = self.hal.set_precoding_matrix(matrix)
        if success:
            logging.info("Successfully wrote new precoding matrix.")
        else:
            logging.error("Failed to write new precoding matrix.")
        return success

    def maximize_line_benefit(self, our_line_index: int, victim_lines: List[int], benefit_factor: float = 0.9) -> bool:
        """
        Adjusts the precoding matrix to maximize the benefit for our line.

        This is done by slightly reducing the crosstalk coefficients from our line
        to the identified victim lines. This makes our line appear 'quieter' to
        the DSLAM's control channel, which can lead to more favorable resource
        allocation for our line.

        Args:
            our_line_index: The index of our own line in the vectoring group.
            victim_lines: A list of indices for lines identified as victims.
            benefit_factor: The factor by which to scale our crosstalk.
                            Values less than 1 reduce our impact. (e.g., 0.9 means
                            we are instructing the precoder to cancel 10% more
                            of our line's crosstalk than originally calculated).

        Returns:
            True if the matrix was successfully modified and written, False otherwise.
        """
        if our_line_index in victim_lines:
            logging.warning("Our own line is listed as a victim. This may be unusual.")
            victim_lines.remove(our_line_index)

        if not victim_lines:
            logging.info("No victim lines to optimize against. No changes made.")
            return True

        logging.info(f"Attempting to optimize matrix for line {our_line_index} against victims: {victim_lines}")

        matrix = self.read_precoding_matrix()
        if not matrix:
            logging.error("Cannot perform optimization without a valid precoding matrix.")
            return False

        # The precoding matrix H' is organized such that H'_ij cancels crosstalk from line j onto line i.
        # We want to modify the elements that cancel crosstalk from *our* line (j) onto the *victim* lines (i).
        for victim_index in victim_lines:
            if victim_index < len(matrix):
                # This is the coefficient for crosstalk from our line to the victim line.
                original_coefficient = matrix[victim_index][our_line_index]

                # We adjust this coefficient to "over-cancel" our crosstalk.
                new_coefficient = original_coefficient * benefit_factor

                logging.info(f"Adjusting matrix[{victim_index}][{our_line_index}] from {original_coefficient:.4f} to {new_coefficient:.4f}")
                matrix[victim_index][our_line_index] = new_coefficient
            else:
                logging.warning(f"Victim index {victim_index} is out of bounds for the matrix.")

        return self.write_precoding_matrix(matrix)

    def read_upstream_cancellation_matrix(self) -> List[List[float]]:
        """
        Reads the upstream cancellation matrix from the DSLAM.

        Returns:
            A 2D list representing the upstream cancellation matrix, or an empty list on failure.
        """
        logging.info("Attempting to read upstream cancellation matrix via HAL.")
        matrix = self.hal.get_upstream_cancellation_matrix()
        if not matrix:
            logging.warning("Reading upstream cancellation matrix failed or returned empty.")
        else:
            logging.info(f"Successfully read a {len(matrix)}x{len(matrix[0])} upstream cancellation matrix.")
        return matrix

    def write_upstream_cancellation_matrix(self, matrix: List[List[float]]) -> bool:
        """
        Writes a modified upstream cancellation matrix to the DSLAM.

        Args:
            matrix: The new upstream cancellation matrix to write.

        Returns:
            True if the write operation was successful, False otherwise.
        """
        if not matrix or not isinstance(matrix, list):
            logging.error("Invalid upstream matrix provided for writing.")
            return False

        logging.info("Attempting to write upstream cancellation matrix via HAL.")
        success = self.hal.set_upstream_cancellation_matrix(matrix)
        if success:
            logging.info("Successfully wrote new upstream cancellation matrix.")
        else:
            logging.error("Failed to write new upstream cancellation matrix.")
        return success