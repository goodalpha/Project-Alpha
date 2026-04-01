"""Fundamental data download and management from SEC EDGAR."""

from pathlib import Path
from typing import Optional, Union

import pandas as pd
import requests
from loguru import logger

from .utils import safe_parquet_read, safe_parquet_write, retry, get_trading_calendar


# XBRL concepts to extract from SEC EDGAR
EDGAR_CONCEPTS = {
    "Revenues": "us-gaap:Revenues",
    "NetIncomeLoss": "us-gaap:NetIncomeLoss",
    "Assets": "us-gaap:Assets",
    "Liabilities": "us-gaap:Liabilities",
    "StockholdersEquity": "us-gaap:StockholdersEquity",
    "EarningsPerShareDiluted": "us-gaap:EarningsPerShareDiluted",
    "OperatingIncomeLoss": "us-gaap:OperatingIncomeLoss",
    "CommonStockSharesOutstanding": "us-gaap:CommonStockSharesOutstanding",
}

# Reporting lag in days (SEC filings typically have 45-day lag)
REPORTING_LAG_DAYS = 45


@retry(max_retries=3, backoff=2.0)
def _get_cik_from_ticker(ticker: str) -> Optional[str]:
    """
    Retrieve CIK (Central Index Key) for a ticker from SEC EDGAR.

    Args:
        ticker: Stock ticker symbol

    Returns:
        CIK as string (without leading zeros), or None if not found
    """
    try:
        # SEC EDGAR company search endpoint
        url = (
            f"https://www.sec.gov/cgi-bin/browse-edgar?"
            f"action=getcompany&company=&CIK={ticker}&type=10-K&"
            f"dateb=&owner=include&count=1&search_text="
        )

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # Parse HTML to extract CIK (typically in form of /Archives/edgar/data/XXXXXX/)
        if "data/" in response.text:
            # Simple extraction from typical CIK path
            start = response.text.find("/data/")
            if start != -1:
                cik_str = response.text[start + 6 : start + 16].split("/")[0]
                if cik_str.isdigit():
                    logger.info(f"Retrieved CIK {cik_str} for ticker {ticker}")
                    return cik_str

        logger.warning(f"Could not find CIK for ticker {ticker}")
        return None

    except Exception as e:
        logger.warning(f"Failed to retrieve CIK for {ticker}: {e}")
        return None


@retry(max_retries=3, backoff=2.0)
def _download_edgar_facts(cik: str) -> Optional[dict]:
    """
    Download company facts from SEC EDGAR API.

    Args:
        cik: Central Index Key (CIK) without leading zeros

    Returns:
        Dictionary of XBRL facts or None if download fails
    """
    try:
        url = f"https://data.sec.gov/api/xbrl/companyfacts/{cik}.json"
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        facts = response.json()
        logger.info(f"Retrieved facts for CIK {cik}")
        return facts

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.warning(f"CIK {cik} not found in SEC EDGAR")
        else:
            logger.warning(f"HTTP error retrieving facts for CIK {cik}: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to download facts for CIK {cik}: {e}")
        return None


def parse_edgar_facts(
    facts_json: dict,
    concept: str,
) -> pd.DataFrame:
    """
    Parse one XBRL concept from EDGAR company facts JSON.

    Extracts filings for a specific concept and returns as DataFrame
    with reporting period as index.

    Args:
        facts_json: Company facts JSON from SEC EDGAR API
        concept: XBRL concept name (e.g., "us-gaap:Revenues")

    Returns:
        DataFrame with columns [filed_date, value, period_end]
        indexed by period_end date, or empty DataFrame if concept not found
    """
    try:
        # Navigate to concept in JSON structure
        us_gaap = facts_json.get("facts", {}).get("us-gaap", {})
        concept_data = us_gaap.get(concept, {})

        if not concept_data:
            logger.debug(f"Concept {concept} not found in facts")
            return pd.DataFrame()

        # Extract units (typically USD for financial metrics)
        units = concept_data.get("units", {})

        # Most financial metrics use USD
        unit_data = units.get("USD", [])
        if not unit_data:
            # Try other possible units
            unit_data = next(iter(units.values())) if units else []

        if not unit_data:
            return pd.DataFrame()

        # Convert to DataFrame
        records = []
        for filing in unit_data:
            # Skip non-10-K filings (use latest 10-K for each fiscal period)
            form = filing.get("form", "")
            if form not in ["10-K", "10-Q", "8-K", "20-F"]:
                continue

            record = {
                "period_end": pd.Timestamp(filing.get("end")),
                "filed_date": pd.Timestamp(filing.get("filed")),
                "form": form,
                "value": filing.get("val"),
                "frame": filing.get("frame", ""),
            }
            records.append(record)

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)

        # Sort by period end date
        df = df.sort_values("period_end")

        # For 10-K filings, keep latest filing per fiscal period
        df = df.loc[df.groupby("period_end")["filed_date"].idxmax()]

        logger.info(
            f"Parsed {len(df)} records for concept {concept}"
        )

        return df[["period_end", "filed_date", "value"]].set_index("period_end")

    except Exception as e:
        logger.warning(f"Failed to parse concept {concept}: {e}")
        return pd.DataFrame()


def download_fundamentals(
    tickers: list[str],
    cache_dir: Path,
    cik_map: Optional[dict[str, str]] = None,
) -> dict:
    """
    Download fundamental data from SEC EDGAR for list of tickers.

    Downloads company facts for each ticker, extracts key metrics,
    applies reporting lag, and caches results.

    Args:
        tickers: List of ticker symbols
        cache_dir: Directory for caching downloaded data
        cik_map: Optional pre-computed mapping of ticker -> CIK

    Returns:
        Dictionary mapping ticker -> DataFrame of fundamentals
        with columns for each metric and MultiIndex (date, ticker)
        when combined
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    if cik_map is None:
        cik_map = {}

    fundamentals_data = {}
    failed_tickers = []

    logger.info(f"Downloading fundamentals for {len(tickers)} tickers...")

    for i, ticker in enumerate(tickers):
        if i % 10 == 0:
            logger.info(f"Processing ticker {i + 1}/{len(tickers)}: {ticker}")

        # Get CIK if not already mapped
        if ticker not in cik_map:
            cik = _get_cik_from_ticker(ticker)
            if cik is None:
                logger.warning(f"Skipping {ticker}: could not find CIK")
                failed_tickers.append(ticker)
                continue
            cik_map[ticker] = cik
        else:
            cik = cik_map[ticker]

        # Download facts for this CIK
        facts_json = _download_edgar_facts(cik)
        if facts_json is None:
            failed_tickers.append(ticker)
            continue

        # Parse each concept
        ticker_fundamentals = {}
        for concept_name, xbrl_name in EDGAR_CONCEPTS.items():
            df = parse_edgar_facts(facts_json, xbrl_name)
            if not df.empty:
                ticker_fundamentals[concept_name] = df["value"]

        if ticker_fundamentals:
            # Combine concepts into single DataFrame
            ticker_df = pd.DataFrame(ticker_fundamentals)

            # Apply reporting lag (shift forward by 45 days)
            ticker_df.index = ticker_df.index + pd.Timedelta(days=REPORTING_LAG_DAYS)

            fundamentals_data[ticker] = ticker_df
            logger.info(f"Retrieved fundamentals for {ticker} ({len(ticker_df)} periods)")
        else:
            failed_tickers.append(ticker)

    if failed_tickers:
        logger.warning(f"Failed to download fundamentals for {len(failed_tickers)} tickers")

    # Save to cache
    cache_path = cache_dir / "fundamentals_raw.parquet"

    if fundamentals_data:
        # Create combined DataFrame for caching
        combined = pd.concat(
            [df.assign(ticker=ticker) for ticker, df in fundamentals_data.items()],
            ignore_index=False,
        )
        combined = combined.reset_index().rename(columns={"index": "date"})
        combined = combined.set_index(["date", "ticker"]).sort_index()

        safe_parquet_write(combined, cache_path)

    return fundamentals_data


def build_fundamental_panel(
    tickers: list[str],
    cache_dir: Path,
    cik_map: Optional[dict[str, str]] = None,
) -> pd.DataFrame:
    """
    Build fundamental data panel from raw EDGAR data.

    Downloads fundamentals for all tickers and combines into a single
    point-in-time safe DataFrame with (date, ticker) MultiIndex.

    Args:
        tickers: List of ticker symbols
        cache_dir: Directory for caching
        cik_map: Optional pre-computed CIK mapping

    Returns:
        DataFrame with MultiIndex (date, ticker) and fundamental metrics
    """
    fundamentals_dict = download_fundamentals(
        tickers,
        cache_dir,
        cik_map=cik_map,
    )

    if not fundamentals_dict:
        logger.warning("No fundamentals data retrieved")
        return pd.DataFrame()

    # Create panel
    panel_list = []
    for ticker, df in fundamentals_dict.items():
        df_copy = df.copy()
        df_copy["ticker"] = ticker
        df_copy = df_copy.reset_index().rename(columns={"index": "date"})
        panel_list.append(df_copy)

    if not panel_list:
        return pd.DataFrame()

    panel = pd.concat(panel_list, ignore_index=True)
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.set_index(["date", "ticker"]).sort_index()

    logger.info(
        f"Built fundamental panel with {len(panel)} observations "
        f"({len(panel.index.get_level_values('ticker').unique())} tickers)"
    )

    return panel


def load_fundamentals(cache_dir: Path) -> pd.DataFrame:
    """
    Load fundamental data from cache.

    Args:
        cache_dir: Directory containing cached fundamental parquet files

    Returns:
        DataFrame with MultiIndex (date, ticker) and fundamental metrics
    """
    cache_dir = Path(cache_dir)

    # Find fundamental parquet files
    fund_files = list(cache_dir.glob("fundamentals*.parquet"))

    if not fund_files:
        logger.warning(f"No fundamental files found in {cache_dir}")
        return pd.DataFrame()

    # Load all fundamental files
    all_fundamentals = []
    for file in sorted(fund_files):
        try:
            df = safe_parquet_read(file)
            all_fundamentals.append(df)
        except Exception as e:
            logger.warning(f"Failed to load {file}: {e}")

    if not all_fundamentals:
        return pd.DataFrame()

    fund_df = pd.concat(all_fundamentals, ignore_index=False)
    fund_df = fund_df.sort_index()

    # Remove duplicates, keeping latest
    fund_df = fund_df[~fund_df.index.duplicated(keep="last")]

    logger.info(
        f"Loaded fundamentals with {len(fund_df)} observations "
        f"({len(fund_df.index.get_level_values('ticker').unique())} tickers)"
    )

    return fund_df
