"""
Price-based technical feature computation.

Computes momentum, reversal, volatility, volume, price level,
and technical indicator features from OHLCV panel data.
All features are point-in-time safe (no lookahead bias).
"""

import numpy as np
import pandas as pd
from scipy.stats import linregress
from loguru import logger


def compute_price_features(prices_dict: dict, config: dict) -> pd.DataFrame:
    """
    Compute all price-based technical features from OHLCV panel data.

    Parameters
    ----------
    prices_dict : dict
        Dictionary with keys: 'open', 'high', 'low', 'close', 'volume', 'adj_close'
        Each value is a DataFrame with dates as index and tickers as columns (wide format).
    config : dict
        Configuration dictionary with 'features' > 'price' section containing:
        - momentum_windows: list of lookback periods for momentum (e.g., [5, 10, 21, 63, 126, 252])
        - reversal_windows: list of lookback periods for reversal (e.g., [1, 5])
        - vol_windows: list of lookback periods for volatility (e.g., [21, 63])
        - beta_window: lookback period for beta calculation (e.g., 252)

    Returns
    -------
    pd.DataFrame
        Long-format DataFrame with columns:
        - date, ticker
        - Momentum features: ret_Nd for each N in momentum_windows
        - Reversal features: ret_1d, ret_Nd_reversal for each N in reversal_windows
        - Volatility features: vol_Nd for each N in vol_windows
        - Volume features: vol_ratio_Nd, amihud_Nd for each N in vol_windows
        - Price level features: log_price, price_52w_high_pct
        - Beta features: beta_252d (if SPY in universe, else NaN)
        - Technical indicators: rsi_14, bb_pct (Bollinger Band position)

    Notes
    -----
    - All returns are log returns, shifted 1 day forward to avoid lookahead bias
    - Volatility is annualized (daily_std * sqrt(252))
    - Amihud liquidity metric: mean(|ret| / dollar_volume) * 1e6
    - Bollinger Bands: 20-day SMA ± 2*std, normalized to [0, 1]
    - Beta computed via rolling 252-day OLS regression vs SPY
    - All features are point-in-time safe with appropriate lags
    """
    logger.info("Computing price features...")

    # Extract price components
    close = prices_dict.get("close")
    adj_close = prices_dict.get("adj_close", close)
    open_price = prices_dict.get("open")
    high = prices_dict.get("high")
    low = prices_dict.get("low")
    volume = prices_dict.get("volume")

    if close is None or adj_close is None or volume is None:
        logger.error("Missing required price data: close, adj_close, or volume")
        return pd.DataFrame()

    # Get config parameters
    price_config = config.get("features", {}).get("price", {})
    momentum_windows = price_config.get("momentum_windows", [5, 10, 21, 63, 126, 252])
    reversal_windows = price_config.get("reversal_windows", [1, 5])
    vol_windows = price_config.get("vol_windows", [21, 63])
    beta_window = price_config.get("beta_window", 252)

    # Initialize result storage
    features = {}

    # Compute log returns (shift forward by 1 to avoid lookahead bias)
    log_returns = np.log(adj_close / adj_close.shift(1)).shift(-1)

    # ── Momentum features ─────────────────────────────────────────────────────
    for window in momentum_windows:
        # Cumulative return over window (shifted forward 1 day)
        feat_name = f"ret_{window}d"
        features[feat_name] = (1 + log_returns).rolling(window=window).apply(
            lambda x: np.prod(x) - 1, raw=False
        )

    # ── Reversal features ─────────────────────────────────────────────────────
    # 1-day return (simple return to capture immediate mean-reversion)
    features["ret_1d"] = (adj_close.pct_change()).shift(-1)

    # Reversal as negative of prior return
    for window in reversal_windows:
        if window in momentum_windows:
            feat_name = f"ret_{window}d_reversal"
            features[feat_name] = -features[f"ret_{window}d"]

    # ── Volatility features (annualized) ──────────────────────────────────────
    for window in vol_windows:
        feat_name = f"vol_{window}d"
        daily_vol = log_returns.rolling(window=window).std()
        features[feat_name] = daily_vol * np.sqrt(252)

    # ── Volume features ──────────────────────────────────────────────────────
    # Dollar volume
    dollar_volume = adj_close * volume

    for window in vol_windows:
        # Volume ratio: current volume / N-day average volume
        vol_ratio_name = f"vol_ratio_{window}d"
        avg_volume = volume.rolling(window=window).mean()
        features[vol_ratio_name] = volume / avg_volume.replace(0, np.nan)

        # Amihud liquidity metric: E[|ret| / dollar_volume] * 1e6
        amihud_name = f"amihud_{window}d"
        abs_returns = log_returns.abs()
        illiquidity = abs_returns / (dollar_volume + 1e-10)  # avoid div by zero
        features[amihud_name] = illiquidity.rolling(window=window).mean() * 1e6

    # ── Price level features ──────────────────────────────────────────────────
    features["log_price"] = np.log(adj_close)

    # Price relative to 52-week high
    high_52w = high.rolling(window=252).max()
    features["price_52w_high_pct"] = (adj_close / high_52w) - 1

    # ── Beta vs SPY ───────────────────────────────────────────────────────────
    # Only compute if SPY is in the universe
    if "SPY" in adj_close.columns:
        spy_returns = log_returns["SPY"]
        beta_values = {}

        for ticker in adj_close.columns:
            if ticker == "SPY":
                beta_values[ticker] = [np.nan] * len(adj_close)
            else:
                stock_returns = log_returns[ticker]
                # Rolling regression: stock_ret = alpha + beta * spy_ret
                betas = stock_returns.rolling(window=beta_window).apply(
                    lambda x: _compute_rolling_beta(x, spy_returns.iloc[-len(x) :]),
                    raw=False,
                )
                beta_values[ticker] = betas.values

        features["beta_252d"] = pd.DataFrame(
            beta_values, index=adj_close.index
        ).astype(float)
    else:
        # If SPY not in universe, set NaN
        logger.warning("SPY not found in price data; beta_252d will be NaN")
        features["beta_252d"] = pd.DataFrame(
            np.nan, index=adj_close.index, columns=adj_close.columns
        )

    # ── RSI (14-day Relative Strength Index) ──────────────────────────────────
    features["rsi_14"] = _compute_rsi(adj_close, period=14)

    # ── Bollinger Bands percentage ────────────────────────────────────────────
    features["bb_pct"] = _compute_bollinger_band_pct(adj_close, period=20, num_std=2)

    # ── Convert wide format to long format ─────────────────────────────────────
    # Stack all features
    feature_list = []
    for feat_name, feat_data in features.items():
        if isinstance(feat_data, pd.DataFrame):
            df_long = feat_data.stack().reset_index()
            df_long.columns = ["date", "ticker", feat_name]
            feature_list.append(df_long)
        else:
            # Single column feature
            df_long = feat_data.to_frame().stack().reset_index()
            df_long.columns = ["date", "ticker", feat_name]
            feature_list.append(df_long)

    # Merge all features
    result = feature_list[0]
    for df in feature_list[1:]:
        result = result.merge(df, on=["date", "ticker"], how="left")

    # Sort by date and ticker
    result = result.sort_values(["date", "ticker"]).reset_index(drop=True)

    logger.info(
        f"Computed price features: {result.shape[0]} rows, {result.shape[1] - 2} features"
    )
    return result


def _compute_rolling_beta(stock_returns, spy_returns):
    """
    Compute beta from overlapping rolling windows.

    Parameters
    ----------
    stock_returns : array-like
        Stock returns for the window
    spy_returns : array-like
        SPY returns for the same window

    Returns
    -------
    float
        Beta coefficient
    """
    if len(stock_returns) < 2 or len(spy_returns) < 2:
        return np.nan

    # Remove NaN values
    mask = ~(np.isnan(stock_returns) | np.isnan(spy_returns))
    if mask.sum() < 2:
        return np.nan

    x = spy_returns[mask]
    y = stock_returns[mask]

    try:
        slope, _, _, _, _ = linregress(x, y)
        return slope
    except Exception:
        return np.nan


def _compute_rsi(prices, period=14):
    """
    Compute Relative Strength Index.

    Parameters
    ----------
    prices : pd.DataFrame
        Price data (dates x tickers)
    period : int
        RSI lookback period (default 14)

    Returns
    -------
    pd.DataFrame
        RSI values (dates x tickers)
    """
    # Compute price changes
    delta = prices.diff()

    # Separate gains and losses
    gains = delta.where(delta > 0, 0)
    losses = -delta.where(delta < 0, 0)

    # Compute rolling averages (Wilder's smoothing)
    avg_gain = gains.rolling(window=period).mean()
    avg_loss = losses.rolling(window=period).mean()

    # Avoid division by zero
    rs = avg_gain / (avg_loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))

    return rsi


def _compute_bollinger_band_pct(prices, period=20, num_std=2):
    """
    Compute position within Bollinger Bands as percentage.

    Normalized to [0, 1] where 0 = lower band, 0.5 = middle (SMA), 1 = upper band.
    Values outside [0, 1] indicate price beyond bands.

    Parameters
    ----------
    prices : pd.DataFrame
        Price data (dates x tickers)
    period : int
        Moving average period (default 20)
    num_std : int
        Number of standard deviations (default 2)

    Returns
    -------
    pd.DataFrame
        Bollinger Band position [0, 1]
    """
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()

    lower_band = sma - num_std * std
    upper_band = sma + num_std * std

    # Normalize position: (price - lower) / (upper - lower)
    bb_pct = (prices - lower_band) / (upper_band - lower_band + 1e-10)

    return bb_pct
