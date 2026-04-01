"""Targets module for computing forward-looking returns and labels."""

from src.targets.targets import (
    compute_targets,
    load_targets,
    align_features_targets,
)

__all__ = [
    "compute_targets",
    "load_targets",
    "align_features_targets",
]
