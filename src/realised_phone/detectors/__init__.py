"""Contrast-specific acoustic detectors (HANDOFF §1b source 3). Small, interpretable,
thresholds from data/calibration/*.yaml -- never hard-coded."""

from realised_phone.detectors.rhotic import RhoticDetector  # noqa: F401

DETECTORS = {"rhotic": RhoticDetector}
