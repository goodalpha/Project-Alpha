"""
Feature engineering module for quantitative trading.

Exports:
    - compute_price_features: Compute price-based technical features
    - compute_cross_sectional_features: Apply cross-sectional transformations
    - compute_fundamental_features: Compute fundamental valuation ratios
    - compute_macro_features: Compute macro regime features
    - build_feature_matrix: Orchestrate full feature engineering pipeline
"""

from src.features.price_features import compute_price_features
from src.features.cross_sectional import compute_cross_sectional_features
from src.features.fundamental_features import compute_fundamental_features
from src.features.macro_features import compute_macro_features
from src.features.pipeline import build_feature_matrix, load_feature_matrix

__all__ = [
    "compute_price_features",
    "compute_cross_sectional_features",
    "compute_fundamental_features",
    "compute_macro_features",
    "build_feature_matrix",
    "load_feature_matrix",
]
