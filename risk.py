"""
PROJECT ATLAS - Risk Management System
5-layer risk architecture with automatic controls
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import config

logger = logging.getLogger(__name__)
logger.setLevel(config.LOG_LEVEL)


class RiskManager:
    """
    Implements 5-layer risk management system from ATLAS blueprint.
    L1: Position-level (stop-loss)
    L2: Sector-level (concentration)
    L3: Portfolio-level (drawdown)
    L4: Volatility (vol targeting)
    L5: Regime (crisis detection)
    """

    def __init__(self):
        self.portfolio_value = 1_000_000  # Default portfolio value
        self.high_water_mark = self.portfolio_value
        self.positions = {}  # ticker -> position_data
        self.trades_log = []
        self.alerts = []

    # ========================================================================
    # L1: POSITION-LEVEL CONTROLS
    # ========================================================================

    def check_position_stop_loss(
        self,
        ticker: str,
        current_price: float,
        entry_price: float,
        stop_loss_pct: float = -0.15
    ) -> bool:
        """
        Check if position hit stop-loss.

        Args:
            ticker: Ticker symbol
            current_price: Current market price
            entry_price: Entry price
            stop_loss_pct: Stop-loss threshold (e.g., -0.15 = -15%)

        Returns:
            True if stop-loss triggered, False otherwise
        """
        pnl = (current_price - entry_price) / entry_price if entry_price > 0 else 0

        if pnl <= stop_loss_pct:
            logger.warning(f"STOP-LOSS triggered for {ticker}: {pnl:.2%}")
            self.alerts.append({
                'timestamp': datetime.now(),
                'level': 'L1_POSITION',
                'ticker': ticker,
                'message': f"Stop-loss triggered: {pnl:.2%}",
                'action': 'EXIT_POSITION',
            })
            return True

        return False

    # ========================================================================
    # L2: SECTOR-LEVEL CONTROLS
    # ========================================================================

    def check_sector_concentration(
        self,
        positions: Dict[str, Dict],
        sector_map: Dict[str, str],
        max_sector_exposure: float = 0.25
    ) -> Dict[str, float]:
        """
        Check sector concentration limits.

        Args:
            positions: Dict of ticker → position data (with size_pct)
            sector_map: Dict of ticker → sector
            max_sector_exposure: Max % of portfolio per sector

        Returns:
            Dict of sector → exposure_pct
        """
        sector_exposure = {}

        for ticker, pos_data in positions.items():
            sector = sector_map.get(ticker, 'Other')
            size = pos_data.get('size_pct', 0)

            if sector not in sector_exposure:
                sector_exposure[sector] = 0
            sector_exposure[sector] += size

        # Check limits
        violations = {}
        for sector, exposure in sector_exposure.items():
            if exposure > max_sector_exposure:
                violations[sector] = exposure
                logger.warning(f"SECTOR CONCENTRATION: {sector} at {exposure:.1%} (limit={max_sector_exposure:.1%})")
                self.alerts.append({
                    'timestamp': datetime.now(),
                    'level': 'L2_SECTOR',
                    'sector': sector,
                    'exposure': exposure,
                    'message': f"Sector {sector} exceeds {max_sector_exposure:.1%} limit",
                    'action': 'TRIM_SECTOR',
                })

        return sector_exposure

    # ========================================================================
    # L3: PORTFOLIO-LEVEL CONTROLS
    # ========================================================================

    def check_drawdown_circuit_breaker(
        self,
        current_portfolio_value: float,
        max_loss_pct: float = -0.10
    ) -> bool:
        """
        Check portfolio-level circuit breaker.

        Args:
            current_portfolio_value: Current portfolio NAV
            max_loss_pct: Max drawdown from HWM (e.g., -0.10 = -10%)

        Returns:
            True if circuit breaker triggered
        """
        # Update HWM
        if current_portfolio_value > self.high_water_mark:
            self.high_water_mark = current_portfolio_value

        # Compute drawdown
        drawdown = (current_portfolio_value - self.high_water_mark) / self.high_water_mark

        if drawdown <= max_loss_pct:
            logger.critical(f"DRAWDOWN CIRCUIT BREAKER: {drawdown:.2%}")
            self.alerts.append({
                'timestamp': datetime.now(),
                'level': 'L3_PORTFOLIO',
                'drawdown': drawdown,
                'message': f"Portfolio drawdown: {drawdown:.2%}",
                'action': 'REDUCE_EXPOSURE_50PCT',
            })
            return True

        return False

    # ========================================================================
    # L4: VOLATILITY CONTROL
    # ========================================================================

    def check_volatility_limit(
        self,
        returns_history: List[float],
        target_vol: float = 0.12,
        vol_threshold: float = 1.5
    ) -> Tuple[bool, float]:
        """
        Check if realized volatility exceeds target.

        Args:
            returns_history: List of daily returns
            target_vol: Target annualized volatility
            vol_threshold: Trigger if realized_vol > target_vol * threshold

        Returns:
            Tuple of (triggered, scaling_factor)
        """
        if len(returns_history) < 20:
            return False, 1.0

        realized_vol = np.std(returns_history[-20:]) * np.sqrt(252)
        vol_ratio = realized_vol / target_vol if target_vol > 0 else 1.0

        if vol_ratio > vol_threshold:
            scale_factor = target_vol / realized_vol
            logger.warning(f"VOLATILITY LIMIT: realized={realized_vol:.1%}, target={target_vol:.1%}, scale_factor={scale_factor:.2f}")
            self.alerts.append({
                'timestamp': datetime.now(),
                'level': 'L4_VOLATILITY',
                'realized_vol': realized_vol,
                'target_vol': target_vol,
                'message': f"Realized vol {realized_vol:.1%} > {target_vol:.1%}",
                'action': 'SCALE_POSITIONS',
                'scaling_factor': scale_factor,
            })
            return True, scale_factor

        return False, 1.0

    # ========================================================================
    # L5: REGIME / CRISIS DETECTION
    # ========================================================================

    def detect_crisis_regime(
        self,
        vix_level: float = None,
        credit_spread_change: float = None,
        vix_threshold: float = 35,
        spread_threshold: float = 0.005  # 50 bps
    ) -> bool:
        """
        Detect crisis regime: VIX > 35 AND credit spreads widening.

        Args:
            vix_level: Current VIX level
            credit_spread_change: Change in credit spreads (absolute)
            vix_threshold: VIX trigger level
            spread_threshold: Credit spread change trigger

        Returns:
            True if crisis detected
        """
        crisis_triggered = False

        if vix_level and vix_level > vix_threshold:
            logger.critical(f"CRISIS ALERT: VIX = {vix_level:.1f}")
            crisis_triggered = True

        if credit_spread_change and credit_spread_change > spread_threshold:
            logger.critical(f"CRISIS ALERT: Credit spreads widening by {credit_spread_change:.1%}")
            crisis_triggered = True

        if crisis_triggered:
            self.alerts.append({
                'timestamp': datetime.now(),
                'level': 'L5_CRISIS',
                'vix': vix_level,
                'credit_spread_change': credit_spread_change,
                'message': "CRISIS REGIME DETECTED",
                'action': 'GO_50PCT_CASH',
            })

        return crisis_triggered

    # ========================================================================
    # POSITION SIZING
    # ========================================================================

    def compute_position_size_kelly(
        self,
        edge: float,
        odds: float,
        portfolio_vol_target: float = 0.12,
        stock_realized_vol: float = 0.20
    ) -> float:
        """
        Compute position size using half-Kelly with volatility scaling.

        Formula:
            weight = (edge / odds) × 0.5 × (target_vol / realized_vol)

        Args:
            edge: Predicted alpha (0-1, probability of outperformance)
            odds: Downside odds (predicted loss magnitude)
            portfolio_vol_target: Target portfolio volatility
            stock_realized_vol: Stock's realized volatility

        Returns:
            Position size as % of portfolio
        """
        if odds <= 0 or stock_realized_vol <= 0:
            return 0

        # Half-Kelly: reduces full Kelly by 50% for risk management
        kelly_weight = (edge / odds) * 0.5

        # Scale by volatility
        vol_scale = portfolio_vol_target / stock_realized_vol
        position_size = kelly_weight * vol_scale

        # Cap at maximum position size
        position_size = min(position_size, config.MAX_POSITION_SIZE)

        return max(0, position_size)

    # ========================================================================
    # CONSTRAINT VALIDATION
    # ========================================================================

    def validate_portfolio_constraints(
        self,
        positions: Dict[str, Dict],
        sector_map: Dict[str, str]
    ) -> Dict:
        """
        Validate all portfolio constraints.

        Returns:
            Dict with constraint violations
        """
        violations = {
            'single_position': [],
            'sector_concentration': [],
            'min_positions': None,
            'max_positions': None,
        }

        # Single position limit
        for ticker, pos in positions.items():
            size = pos.get('size_pct', 0)
            if size > config.MAX_POSITION_SIZE:
                violations['single_position'].append({
                    'ticker': ticker,
                    'size': size,
                    'limit': config.MAX_POSITION_SIZE,
                })

        # Sector concentration
        sector_exposure = self.check_sector_concentration(positions, sector_map, config.MAX_SECTOR_EXPOSURE)
        for sector, exposure in sector_exposure.items():
            if exposure > config.MAX_SECTOR_EXPOSURE:
                violations['sector_concentration'].append({
                    'sector': sector,
                    'exposure': exposure,
                    'limit': config.MAX_SECTOR_EXPOSURE,
                })

        # Number of positions
        num_positions = len(positions)
        if num_positions < config.MIN_POSITIONS:
            violations['min_positions'] = num_positions
        if num_positions > config.MAX_POSITIONS:
            violations['max_positions'] = num_positions

        return violations

    # ========================================================================
    # ALERT & REPORTING
    # ========================================================================

    def get_alerts(self) -> List[Dict]:
        """Get all active risk alerts."""
        return self.alerts

    def clear_alerts(self):
        """Clear alert history."""
        self.alerts = []

    def generate_risk_report(self) -> Dict:
        """Generate comprehensive risk report."""
        return {
            'timestamp': datetime.now(),
            'portfolio_value': self.portfolio_value,
            'high_water_mark': self.high_water_mark,
            'current_drawdown': (self.portfolio_value - self.high_water_mark) / self.high_water_mark,
            'alerts': self.alerts,
            'num_positions': len(self.positions),
        }


class VolatilityTargeting:
    """Volatility targeting module."""

    @staticmethod
    def get_vol_target_scaler(
        realized_vol: float,
        target_vol: float = 0.12
    ) -> float:
        """
        Get multiplier to scale positions to achieve target volatility.

        Args:
            realized_vol: Realized portfolio volatility
            target_vol: Target portfolio volatility

        Returns:
            Scaling factor (typically <1 if realized vol is too high)
        """
        if realized_vol <= 0:
            return 1.0

        return target_vol / realized_vol


if __name__ == "__main__":
    logging.basicConfig(format=config.LOG_FORMAT)
    logger.info("Risk management module loaded")
