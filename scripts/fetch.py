#!/usr/bin/env python3
import os
import csv
import json
import time
from datetime import datetime
import pandas as pd
import numpy as np
import yfinance as yf

# Static lookup mapping of popular stocks for instant execution without extra web calls
COMMON_NAMES = {
    "AAPL": "Apple Inc",
    "MSFT": "Microsoft Corporation",
    "GOOGL": "Alphabet Inc",
    "AMZN": "Amazon.com Inc",
    "NVDA": "NVIDIA Corporation",
    "META": "Meta Platforms Inc",
    "TSLA": "Tesla Inc",
    "NFLX": "Netflix Inc",
    "AVGO": "Broadcom Inc",
    "AMD": "Advanced Micro Devices",
    "UNH": "UnitedHealth Group",
    "BABA": "Alibaba Group",
    "SPY": "SPDR S&P 500 ETF Trust",
    "QQQ": "Invesco QQQ Trust"
}

def get_price_at_lookback(closes, lookback_days):
    """
    Returns the closing price at lookback_days ago.
    If there is not enough history, returns the oldest available price.
    """
    if len(closes) >= lookback_days + 1:
        return closes.iloc[-1 - lookback_days]
    else:
        return closes.iloc[0]

def normalise_series(series):
    """
    Normalises a series of values to 0.0 - 1.0.
    If all values are equal, returns a list of 1.0s.
    """
    vals = list(series)
    if not vals:
        return []
    min_val = min(vals)
    max_val = max(vals)
    if max_val == min_val:
        return [1.0] * len(vals)
    return [(x - min_val) / (max_val - min_val) for x in vals]

def fetch_history_with_retry(ticker, max_retries=3, initial_sleep=5):
    """
    Fetches 2-year history for a ticker, retrying with backoff if rate-limited or failed.
    """
    t_obj = yf.Ticker(ticker)
    for attempt in range(max_retries):
        try:
            # Fetch 2y daily history
            t_df = t_obj.history(period="2y")
            if not t_df.empty:
                return t_df, t_obj
            else:
                print(f"Warning: Empty data returned for {ticker} (Attempt {attempt + 1}/{max_retries})")
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e} (Attempt {attempt + 1}/{max_retries})")
        
        # Exponential backoff sleep
        sleep_time = initial_sleep * (2 ** attempt)
        print(f"Rate limiting or error detected. Sleeping for {sleep_time}s before retry...")
        time.sleep(sleep_time)
        
    return pd.DataFrame(), t_obj

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Relative Strength Data Fetcher")
    parser.add_argument("--batch", type=str, default="all", choices=["all", "1", "2", "3"],
                        help="Specify which batch to run (1, 2, 3, or all)")
    args = parser.parse_args()

    # Paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    universe_path = os.path.join(base_dir, 'data', 'universe.csv')
    output_path = os.path.join(base_dir, 'data', 'latest.json')
    sectors_path = os.path.join(base_dir, 'data', 'sectors.json')
    
    # Load sector cache
    sector_map = {}
    if os.path.exists(sectors_path):
        try:
            with open(sectors_path, 'r', encoding='utf-8') as sf:
                sector_map = json.load(sf)
            print(f"Loaded {len(sector_map)} sector classifications from cache.")
        except Exception as e:
            print(f"Warning: Could not read sectors.json: {e}")
    else:
        # Download and build cache automatically from NASDAQ screener
        print("sectors.json not found. Automatically downloading sector/industry mappings from NASDAQ...")
        try:
            import urllib.request
            url = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=25&download=true"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Origin': 'https://www.nasdaq.com',
                'Referer': 'https://www.nasdaq.com/'
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                rows = res_data.get("data", {}).get("rows", [])
                for row in rows:
                    symbol = row['symbol'].strip().upper()
                    sector = row.get('sector', '').strip()
                    industry = row.get('industry', '').strip()
                    if symbol:
                        sector_map[symbol] = {
                            "sector": sector if sector else "Unknown",
                            "industry": industry if industry else "Unknown"
                        }
            
            # Save it
            with open(sectors_path, 'w', encoding='utf-8') as sf:
                json.dump(sector_map, sf, indent=2)
            print(f"Successfully generated sectors.json with {len(sector_map)} records.")
        except Exception as e:
            print(f"Warning: Could not automatically generate sector cache: {e}")
    
    # Load batches from explicit universe_batch_1.csv, universe_batch_2.csv, universe_batch_3.csv files
    num_batches = 3
    batches = [[] for _ in range(num_batches)]
    loaded_from_batches = True

    for idx in range(num_batches):
        batch_file = os.path.join(base_dir, 'data', f'universe_batch_{idx + 1}.csv')
        if os.path.exists(batch_file):
            with open(batch_file, 'r', encoding='utf-8') as f:
                for line in f:
                    ticker = line.strip().upper()
                    if ticker:
                        batches[idx].append(ticker)
        else:
            loaded_from_batches = False

    if not loaded_from_batches:
        print("Explicit batch files not found. Splitting universe.csv dynamically...")
        # Read tickers from universe.csv
        raw_tickers = []
        if os.path.exists(universe_path):
            with open(universe_path, mode='r', encoding='utf-8') as f:
                for line in f:
                    ticker = line.strip().upper()
                    if ticker and ticker != 'TICKER' and not ticker.startswith('#'):
                        raw_tickers.append(ticker)
        else:
            print(f"Error: Watchlist not found at {universe_path}")
            return

        tickers = [t for t in raw_tickers if '/' not in t]
        batches = [[] for _ in range(num_batches)]
        for i, t in enumerate(tickers):
            batches[i % num_batches].append(t)

    # Print summary
    total_tickers = sum(len(b) for b in batches)
    print(f"Total tickers to process across all batches: {total_tickers}")
    for idx, batch in enumerate(batches):
        print(f"  Batch {idx + 1}: {len(batch)} tickers")

    # Fetch benchmarks first
    print("Fetching benchmark data (SPY & QQQ)...")
    spy_df, _ = fetch_history_with_retry("SPY")
    qqq_df, _ = fetch_history_with_retry("QQQ")
    
    if spy_df.empty or qqq_df.empty:
        print("Error: Could not retrieve benchmark SPY or QQQ data.")
        return

    spy_close = spy_df['Close']
    qqq_close = qqq_df['Close']
    
    # Determine which batches to run and pre-load other batches if running a single batch
    calculated_tickers = []
    raw_scores = {}
    
    batches_to_run = []
    if args.batch == "all":
        batches_to_run = [0, 1, 2]
        print("Running all 3 batches.")
    else:
        active_idx = int(args.batch) - 1
        batches_to_run = [active_idx]
        print(f"Running only Batch {args.batch} of 3.")
        
        # Load existing data to populate the other batches
        existing_lookup = {}
        if os.path.exists(output_path):
            try:
                with open(output_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    if "tickers" in existing_data:
                        existing_lookup = {t_item["ticker"]: t_item for t_item in existing_data["tickers"]}
                        print(f"Loaded {len(existing_lookup)} cached stock records from {output_path}")
            except Exception as e:
                print(f"Warning: Could not read existing latest.json for caching: {e}")
        
        # Copy cached data for the batches we are NOT running
        for idx in range(num_batches):
            if idx != active_idx:
                cached_count = 0
                for t in batches[idx]:
                    if t in existing_lookup:
                        cached_item = existing_lookup[t]
                        if "sector" not in cached_item or "industry" not in cached_item:
                            s_data = sector_map.get(t, {})
                            if isinstance(s_data, str):
                                cached_item["sector"] = s_data
                                cached_item["industry"] = s_data
                            else:
                                cached_item["sector"] = s_data.get("sector", "Unknown")
                                cached_item["industry"] = s_data.get("industry", "Unknown")
                        calculated_tickers.append(cached_item)
                        # Reconstruct raw score for ranking
                        raw_scores[t] = cached_item.get("ibd_raw", cached_item.get("ibd_rs", 50) / 99)
                        cached_count += 1
                print(f"Cached data loaded for Batch {idx + 1}: {cached_count}/{len(batches[idx])} tickers")

    # Process batches
    for b_idx in batches_to_run:
        batch = batches[b_idx]
        print(f"\n--- Processing Batch {b_idx + 1}/{num_batches} ({len(batch)} tickers) ---")
        
        for t_idx, ticker in enumerate(batch):
            print(f"[{t_idx + 1}/{len(batch)}] Fetching data for {ticker}...")
            
            # Rate limiting: polite sleep between requests
            time.sleep(0.1)
            
            try:
                t_df, t_obj = fetch_history_with_retry(ticker)
                if t_df.empty:
                    print(f"Skipping {ticker} due to fetch failure.")
                    continue
                    
                # Align ticker data with benchmarks by date (inner join on index)
                ticker_close = t_df['Close'].loc[~t_df.index.duplicated(keep='first')]
                
                merged = pd.DataFrame(index=ticker_close.index)
                merged['ticker'] = ticker_close
                merged['spy'] = spy_close
                merged['qqq'] = qqq_close
                merged = merged.dropna().sort_index(ascending=True)
                
                total_days = len(merged)
                if total_days < 2:
                    print(f"Warning: Insufficient history for {ticker} after aligning. Skipping.")
                    continue
                    
                # Get company name, sector & industry
                name = COMMON_NAMES.get(ticker)
                s_data = sector_map.get(ticker, {})
                if isinstance(s_data, str):
                    sector = s_data
                    industry = s_data
                else:
                    sector = s_data.get("sector", "Unknown")
                    industry = s_data.get("industry", "Unknown")
                
                if not name or sector == "Unknown" or industry == "Unknown":
                    try:
                        info = t_obj.info
                        if not name:
                            name = info.get('longName', ticker)
                        if sector == "Unknown":
                            sector = info.get('sector', 'Unknown')
                        if industry == "Unknown":
                            industry = info.get('industry', 'Unknown')
                        
                        sector_map[ticker] = {
                            "sector": sector,
                            "industry": industry
                        }
                    except Exception:
                        if not name:
                            name = ticker
                        if sector == "Unknown":
                            sector = 'Unknown'
                        if industry == "Unknown":
                            industry = 'Unknown'
                
                # Today's close
                c_today = merged['ticker'].iloc[-1]
                
                # Daily% and 1-Month%
                c_prev = get_price_at_lookback(merged['ticker'], 1)
                c_20 = get_price_at_lookback(merged['ticker'], 20)
                
                daily_pct = ((c_today / c_prev) - 1.0) * 100.0
                one_month_pct = ((c_today / c_20) - 1.0) * 100.0
                
                # RS Ratio (vs SPY and QQQ) for the last 20 trading days
                rs_window = merged.iloc[-20:]
                rs_series_spy = rs_window['ticker'] / rs_window['spy']
                rs_series_qqq = rs_window['ticker'] / rs_window['qqq']
                
                # Normalize 20-day RS ratio series
                rs_bar_spy = normalise_series(rs_series_spy)
                rs_bar_qqq = normalise_series(rs_series_qqq)
                
                # RS_STS% (today's percentile within the 20-day window)
                rs_sts_spy = round(rs_bar_spy[-1] * 100.0) if rs_bar_spy else 50.0
                rs_sts_qqq = round(rs_bar_qqq[-1] * 100.0) if rs_bar_qqq else 50.0
                
                # IBD-Style raw score
                c_63 = get_price_at_lookback(merged['ticker'], 63)
                c_126 = get_price_at_lookback(merged['ticker'], 126)
                c_189 = get_price_at_lookback(merged['ticker'], 189)
                c_252 = get_price_at_lookback(merged['ticker'], 252)
                
                rs_raw = (0.4 * (c_today / c_63) + 
                          0.2 * (c_today / c_126) + 
                          0.2 * (c_today / c_189) + 
                          0.2 * (c_today / c_252))
                
                raw_scores[ticker] = rs_raw
                
                # Store intermediate ticker values
                calculated_tickers.append({
                    "ticker": ticker,
                    "name": name,
                    "daily_pct": round(daily_pct, 2),
                    "one_month_pct": round(one_month_pct, 2),
                    "rs_sts_spy": int(rs_sts_spy),
                    "rs_sts_qqq": int(rs_sts_qqq),
                    "rs_bar_spy": [round(x, 4) for x in rs_bar_spy],
                    "rs_bar_qqq": [round(x, 4) for x in rs_bar_qqq],
                    "ibd_raw": round(rs_raw, 4),
                    "sector": sector,
                    "industry": industry
                })
                
            except Exception as e:
                print(f"Error processing {ticker}: {e}")
                continue
        
        # Cool down sleep between batches to avoid rate limit locks
        if b_idx < num_batches - 1:
            print(f"Batch {b_idx + 1} completed. Cooling down for 5 seconds...")
            time.sleep(5)

    if not calculated_tickers:
        print("No tickers were successfully calculated.")
        return

    # Calculate IBD RS ratings globally (1-99 percentile rank within consolidated universe)
    N = len(calculated_tickers)
    print(f"\nCalculating global IBD RS ratings for {N} stocks...")
    for ticker_data in calculated_tickers:
        t = ticker_data["ticker"]
        t_raw = raw_scores[t]
        rank = sum(1 for other_t in raw_scores if raw_scores[other_t] <= t_raw)
        pct = rank / N
        ibd_rs = round(pct * 99)
        ibd_rs = max(1, min(99, ibd_rs))
        ticker_data["ibd_rs"] = int(ibd_rs)

    # Latest benchmark date from SPY
    benchmark_date = spy_close.index[-1].strftime('%Y-%m-%d')
    generated_at = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Consolidate JSON data
    output_data = {
        "generated_at": generated_at,
        "benchmark_date": benchmark_date,
        "tickers": calculated_tickers
    }
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Save JSON files (latest.json and date-suffixed JSON)
    json_date_path = os.path.join(base_dir, 'data', f'latest_{benchmark_date}.json')
    for path in [output_path, json_date_path]:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)
            
    # Save CSV files (latest.csv and date-suffixed CSV)
    csv_headers = ['ticker', 'name', 'daily_pct', 'one_month_pct', 'rs_sts_spy', 'rs_sts_qqq', 'ibd_rs', 'sector', 'industry']
    csv_rows = []
    for t_data in calculated_tickers:
        csv_rows.append({
            'ticker': t_data['ticker'],
            'name': t_data['name'],
            'daily_pct': t_data['daily_pct'],
            'one_month_pct': t_data['one_month_pct'],
            'rs_sts_spy': t_data['rs_sts_spy'],
            'rs_sts_qqq': t_data['rs_sts_qqq'],
            'ibd_rs': t_data['ibd_rs'],
            'sector': t_data.get('sector', 'Unknown'),
            'industry': t_data.get('industry', 'Unknown')
        })
        
    csv_path = os.path.join(base_dir, 'data', 'latest.csv')
    csv_date_path = os.path.join(base_dir, 'data', f'latest_{benchmark_date}.csv')
    for path in [csv_path, csv_date_path]:
        with open(path, 'w', encoding='utf-8', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
            writer.writeheader()
            writer.writerows(csv_rows)
        
    # Save updated sector cache
    try:
        with open(sectors_path, 'w', encoding='utf-8') as sf:
            json.dump(sector_map, sf, indent=2)
        print("Updated sectors.json cache saved.")
    except Exception as e:
        print(f"Warning: Could not write sectors.json cache: {e}")
        
    print(f"\nSuccessfully calculated results for {N} tickers.")
    print(f"JSON outputs saved to {output_path} and {json_date_path}")
    print(f"CSV outputs saved to {csv_path} and {csv_date_path}")

    # Generate/update dates.json with list of available dates
    import glob
    data_dir = os.path.join(base_dir, 'data')
    json_files = glob.glob(os.path.join(data_dir, 'latest_*.json'))
    dates = []
    for f_path in json_files:
        basename = os.path.basename(f_path)
        parts = basename.split('_')
        if len(parts) >= 2:
            date_str = parts[1].split('.')[0]
            dates.append(date_str)
    # Deduplicate and sort descending (newest first)
    dates = sorted(list(set(dates)), reverse=True)
    dates_path = os.path.join(data_dir, 'dates.json')
    with open(dates_path, 'w', encoding='utf-8') as f:
        json.dump(dates, f, indent=2)
    print(f"Updated dates.json with available dates: {dates}")

if __name__ == "__main__":
    main()
