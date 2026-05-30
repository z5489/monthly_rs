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
    # Paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    universe_path = os.path.join(base_dir, 'data', 'universe.csv')
    output_path = os.path.join(base_dir, 'data', 'latest.json')
    
    # Read tickers from universe.csv
    raw_tickers = []
    if os.path.exists(universe_path):
        with open(universe_path, mode='r', encoding='utf-8') as f:
            for line in f:
                ticker = line.strip().upper()
                # Skip comments, blank lines, or the optional column header
                if ticker and ticker != 'TICKER' and not ticker.startswith('#'):
                    raw_tickers.append(ticker)
    else:
        print(f"Error: Watchlist not found at {universe_path}")
        return

    # Filter out tickers containing '/'
    tickers = [t for t in raw_tickers if '/' not in t]
    filtered_out_count = len(raw_tickers) - len(tickers)
    
    if filtered_out_count > 0:
        print(f"Filtered out {filtered_out_count} tickers containing '/' from query list.")

    if not tickers:
        print("No valid tickers found in watchlist.")
        return

    # Split tickers into exactly 3 batches using round-robin partitioning
    num_batches = 3
    batches = [[] for _ in range(num_batches)]
    for i, t in enumerate(tickers):
        batches[i % num_batches].append(t)

    print(f"Total tickers to process: {len(tickers)}")
    for b_idx, batch in enumerate(batches):
        print(f"  Batch {b_idx + 1}: {len(batch)} tickers")

    # Fetch benchmarks first
    print("Fetching benchmark data (SPY & QQQ)...")
    spy_df, _ = fetch_history_with_retry("SPY")
    qqq_df, _ = fetch_history_with_retry("QQQ")
    
    if spy_df.empty or qqq_df.empty:
        print("Error: Could not retrieve benchmark SPY or QQQ data.")
        return

    spy_close = spy_df['Close']
    qqq_close = qqq_df['Close']
    
    # We will accumulate data for tickers across all batches
    calculated_tickers = []
    raw_scores = {}

    # Process batches
    for b_idx, batch in enumerate(batches):
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
                    
                # Get company name
                name = COMMON_NAMES.get(ticker)
                if not name:
                    try:
                        # Fallback to info lookup for custom tickers
                        name = t_obj.info.get('longName', ticker)
                    except Exception:
                        name = ticker
                
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
    csv_headers = ['ticker', 'name', 'daily_pct', 'one_month_pct', 'rs_sts_spy', 'rs_sts_qqq', 'ibd_rs']
    csv_rows = []
    for t_data in calculated_tickers:
        csv_rows.append({
            'ticker': t_data['ticker'],
            'name': t_data['name'],
            'daily_pct': t_data['daily_pct'],
            'one_month_pct': t_data['one_month_pct'],
            'rs_sts_spy': t_data['rs_sts_spy'],
            'rs_sts_qqq': t_data['rs_sts_qqq'],
            'ibd_rs': t_data['ibd_rs']
        })
        
    csv_path = os.path.join(base_dir, 'data', 'latest.csv')
    csv_date_path = os.path.join(base_dir, 'data', f'latest_{benchmark_date}.csv')
    for path in [csv_path, csv_date_path]:
        with open(path, 'w', encoding='utf-8', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
            writer.writeheader()
            writer.writerows(csv_rows)
        
    print(f"\nSuccessfully calculated results for {N} tickers.")
    print(f"JSON outputs saved to {output_path} and {json_date_path}")
    print(f"CSV outputs saved to {csv_path} and {csv_date_path}")

if __name__ == "__main__":
    main()
