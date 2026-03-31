"""Shared utilities for data ingestion."""

import functools
import time
import tempfile
from pathlib import Path
from typing import Any, Callable, TypeVar, Optional

import pandas as pd
import yaml
from loguru import logger

try:
    import pandas_market_calendars as mcal
    HAS_MARKET_CALENDARS = True
except ImportError:
    HAS_MARKET_CALENDARS = False


# Configure loguru logger
logger.remove()
logger.add(
    lambda msg: print(msg, end=""),
    format="<level>{level: <8}</level> | {name}:{function}:{line} - {message}",
    level="INFO",
)

T = TypeVar("T")


def retry(
    max_retries: int = 3,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """
    Decorator to retry a function call with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        backoff: Backoff multiplier for exponential delay (default: 2.0)
        exceptions: Tuple of exception types to catch (default: all Exceptions)

    Returns:
        Decorated function that retries on failure
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            attempt = 0
            delay = 1.0

            while attempt < max_retries:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_retries:
                        logger.error(
                            f"Failed after {max_retries} attempts: {func.__name__}",
                            exc_info=True,
                        )
                        raise
                    logger.warning(
                        f"Attempt {attempt}/{max_retries} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                    delay *= backoff

            return func(*args, **kwargs)

        return wrapper

    return decorator


def load_yaml_config(path: Path) -> dict:
    """
    Load configuration from YAML file.

    Args:
        path: Path to YAML configuration file

    Returns:
        Dictionary containing configuration

    Raises:
        FileNotFoundError: If config file not found
        yaml.YAMLError: If YAML parsing fails
    """
    path = Path(path)
    if not path.exists():
        logger.error(f"Configuration file not found: {path}")
        raise FileNotFoundError(f"Config file not found: {path}")

    try:
        with open(path, "r") as f:
            config = yaml.safe_load(f)
        logger.info(f"Loaded configuration from {path}")
        return config or {}
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse YAML config: {e}")
        raise


def get_trading_calendar(
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DatetimeIndex:
    """
    Get NYSE trading calendar dates between start and end dates.

    Uses pandas_market_calendars if available, falls back to pandas bdate_range.

    Args:
        start: Start date (inclusive)
        end: End date (inclusive)

    Returns:
        DatetimeIndex of trading days
    """
    start = pd.Timestamp(start)
    end = pd.Timestamp(end)

    if HAS_MARKET_CALENDARS:
        try:
            nyse = mcal.get_calendar("NYSE")
            trading_dates = nyse.valid_days(start_date=start, end_date=end)
            logger.info(
                f"Retrieved {len(trading_dates)} NYSE trading days "
                f"from {start.date()} to {end.date()}"
            )
            return trading_dates
        except Exception as e:
            logger.warning(f"Failed to get NYSE calendar: {e}. Using fallback.")

    # Fallback to business day range
    trading_dates = pd.bdate_range(start=start, end=end, freq="B")
    logger.info(
        f"Using {len(trading_dates)} business days (fallback) "
        f"from {start.date()} to {end.date()}"
    )
    return trading_dates


def safe_parquet_write(df: pd.DataFrame, path: Path) -> None:
    """
    Atomically write DataFrame to parquet file.

    Writes to temporary file first, then renames to target path to ensure
    atomicity and prevent corruption from partial writes.

    Args:
        df: DataFrame to write
        path: Target parquet file path

    Raises:
        IOError: If write operation fails
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Write to temporary file in same directory (ensures same filesystem)
        temp_fd, temp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=".tmp_",
            suffix=".parquet",
        )

        try:
            df.to_parquet(temp_path, engine="pyarrow", compression="snappy")
            # Atomic rename on POSIX systems
            Path(temp_path).replace(path)
            logger.info(f"Wrote {len(df)} rows to {path}")
        except Exception as e:
            # Clean up temp file on failure
            try:
                Path(temp_path).unlink()
            except Exception:
                pass
            raise e
    except Exception as e:
        logger.error(f"Failed to write parquet to {path}: {e}")
        raise IOError(f"Failed to write parquet: {e}") from e


def safe_parquet_read(path: Path) -> pd.DataFrame:
    """
    Read parquet file with error handling.

    Args:
        path: Path to parquet file

    Returns:
        DataFrame read from parquet

    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If read fails
    """
    path = Path(path)

    if not path.exists():
        logger.error(f"Parquet file not found: {path}")
        raise FileNotFoundError(f"Parquet file not found: {path}")

    try:
        df = pd.read_parquet(path, engine="pyarrow")
        logger.info(f"Read {len(df)} rows from {path}")
        return df
    except Exception as e:
        logger.error(f"Failed to read parquet from {path}: {e}")
        raise IOError(f"Failed to read parquet: {e}") from e
