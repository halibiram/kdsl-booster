from enum import Enum

class SRAState(Enum):
    """Represents the operational state of the SRA controller."""
    STABLE = "Stable"
    UNSTABLE = "Unstable"
    OPTIMIZING_UP = "Optimizing for Higher Rate"
    OPTIMIZING_DOWN = "Optimizing for Lower Rate"
    POWER_SAVING = "Power Saving"

class LineQuality(Enum):
    """Represents the assessed quality of the DSL line."""
    EXCELLENT = "Excellent"
    GOOD = "Good"
    POOR = "Poor"
    VERY_POOR = "Very Poor"