#!/usr/bin/env python3
import os
import csv
import json
import time
import argparse
import glob
from datetime import datetime
import pandas as pd
import numpy as np
import yfinance as yf

# Re-use COMMON_NAMES lookup
from fetch import COMMON_NAMES, get_price_at_lookback, normalise_series, fetch_history_with_retry

def main():
    parser = argparse.ArgumentParser(description="Fill missing tickers for a specific date")
    parser.add_argument("--date", type=str, default="", help="Date in YYYY-MM-DD format (defaults to latest available date)")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, 'data')

    # Resolve date if empty
    target_date = args.date.strip()
    if not target_date:
        dates_path = os.path.join(data_dir, 'dates.json')
        if os.path.exists(dates_path):
            with open(dates_path, 'r', encoding='utf-8') as f:
                dates = json.load(f)
                if dates:
                    target_date = dates[0]
        if not target_date:
            print("Error: No date specified and no dates found in dates.json.")
            return

    print(f"Target Date: {target_date}")
    
    # Paths
    json_path = os.path.join(data_dir, f'latest_{target_date}.json')
    universe_path = os.path.join(data_dir, 'universe.csv')

    if not os.path.exists(universe_path):
        print(f"Error: universe.csv not found at {universe_path}")
        return

    # Read tickers from universe.csv (excluding comments/slashes)
    universe_tickers = []
    with open(universe_path, mode='r', encoding='utf-8') as f:
        for line in f:
            ticker = line.strip().upper()
            if ticker and ticker != 'TICKER' and not ticker.startswith('#') and '/' not in ticker:
                universe_tickers.append(ticker)

    # Read processed tickers from latest_<date>.json
    existing_data = {}
    processed_tickers = {}
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                if "tickers" in existing_data:
                    processed_tickers = {t["ticker"]: t for t in existing_data["tickers"]}
        except Exception as e:
            print(f"Warning: Could not read existing {json_path}: {e}")
    else:
        print(f"Warning: {json_path} does not exist. Running as a fresh fetch for all tickers.")

    # Find missing tickers
    missing_tickers = sorted(list(set(universe_tickers) - set(processed_tickers.keys())))
    print(f"Total tickers in universe: {len(universe_tickers)}")
    print(f"Already processed tickers: {len(processed_tickers)}")
    print(f"Missing tickers to fetch: {len(missing_tickers)}")

    if not missing_tickers:
        print("No missing tickers found. Everything is up to date!")
        return

    # Fetch benchmarks (needed for date aligning)
    print("Fetching benchmark data (SPY & QQQ)...")
    spy_df, _ = fetch_history_with_retry("SPY")
    qqq_df, _ = fetch_history_with_retry("QQQ")
    
    if spy_df.empty or qqq_df.empty:
        print("Error: Could not retrieve benchmark SPY or QQQ data.")
        return

    spy_close = spy_df['Close']
    qqq_close = qqq_df['Close']

    # Keep track of scores for raw ranking
    raw_scores = {}
    for t_sym, t_data in processed_tickers.items():
        raw_scores[t_sym] = t_data.get("ibd_raw", t_data.get("ibd_rs", 50) / 99)

    # Fetch missing tickers
    new_tickers_data = []
    for idx, ticker in enumerate(missing_tickers):
        print(f"[{idx + 1}/{len(missing_tickers)}] Fetching data for {ticker}...")
        time.sleep(0.1)  # polite sleep

        try:
            t_df, t_obj = fetch_history_with_retry(ticker)
            if t_df.empty:
                print(f"Skipping {ticker} due to fetch failure.")
                continue

            ticker_close = t_df['Close'].loc[~t_df.index.duplicated(keep='first')]
            merged = pd.DataFrame(index=ticker_close.index)
            merged['ticker'] = ticker_close
            merged['spy'] = spy_close
            merged['qqq'] = qqq_close
            merged = merged.dropna().sort_index(ascending=True)

            if len(merged) < 2:
                print(f"Warning: Insufficient history for {ticker}. Skipping.")
                continue

            name = COMMON_NAMES.get(ticker)
            if not name:
                try:
                    name = t_obj.info.get('longName', ticker)
                except Exception:
                    name = ticker

            c_today = merged['ticker'].iloc[-1]
            c_prev = get_price_at_lookback(merged['ticker'], 1)
            c_20 = get_price_at_lookback(merged['ticker'], 20)

            daily_pct = ((c_today / c_prev) - 1.0) * 100.0
            one_month_pct = ((c_today / c_20) - 1.0) * 100.0

            rs_window = merged.iloc[-20:]
            rs_series_spy = rs_window['ticker'] / rs_window['spy']
            rs_series_qqq = rs_window['ticker'] / rs_window['qqq']

            rs_bar_spy = normalise_series(rs_series_spy)
            rs_bar_qqq = normalise_series(rs_series_qqq)

            rs_sts_spy = round(rs_bar_spy[-1] * 100.0) if rs_bar_spy else 50.0
            rs_sts_qqq = round(rs_bar_qqq[-1] * 100.0) if rs_bar_qqq else 50.0

            c_63 = get_price_at_lookback(merged['ticker'], 63)
            c_126 = get_price_at_lookback(merged['ticker'], 126)
            c_189 = get_price_at_lookback(merged['ticker'], 189)
            c_252 = get_price_at_lookback(merged['ticker'], 252)

            rs_raw = (0.4 * (c_today / c_63) + 
                      0.2 * (c_today / c_126) + 
                      0.2 * (c_today / c_189) + 
                      0.2 * (c_today / c_252))

            raw_scores[ticker] = rs_raw

            new_tickers_data.append({
                "ticker": ticker,
                "name": name,
                "daily_pct": round(daily_pct, 2),
                "one_month_pct": round(one_month_pct, 2),
                "rs_sts_spy": int(rs_sts_spy),
                "rs_sts_qqq": int(rs_sts_qqq),
                "rs_bar_spy": [round(x, 4) for x in rs_bar_spy],
                "rs_bar_qqq": [round(x, 4) for x in rs_bar_qqq],
                "ibd_raw": round(rs_raw, 4)
            })

        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            continue

    if not new_tickers_data:
        print("No new tickers were successfully fetched.")
        return

    # Combine processed + new
    combined_tickers = list(processed_tickers.values()) + new_tickers_data

    # Recalculate IBD RS ratings globally
    N = len(combined_tickers)
    print(f"\nRecalculating global IBD RS ratings for {N} stocks...")
    for ticker_data in combined_tickers:
        t = ticker_data["ticker"]
        t_raw = raw_scores.get(t, 1.0)
        rank = sum(1 for other_t in raw_scores if raw_scores[other_t] <= t_raw)
        pct = rank / N
        ibd_rs = max(1, min(99, round(pct * 99)))
        ticker_data["ibd_rs"] = int(ibd_rs)

    # Save JSON files
    generated_at = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    output_data = {
        "generated_at": generated_at,
        "benchmark_date": target_date,
        "tickers": combined_tickers
    }

    # Write target date and latest.json
    for path in [json_path, os.path.join(data_dir, 'latest.json')]:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

    # Save CSV files
    csv_headers = ['ticker', 'name', 'daily_pct', 'one_month_pct', 'rs_sts_spy', 'rs_sts_qqq', 'ibd_rs']
    csv_rows = []
    for t_data in combined_tickers:
        csv_rows.append({
            'ticker': t_data['ticker'],
            'name': t_data['name'],
            'daily_pct': t_data['daily_pct'],
            'one_month_pct': t_data['one_month_pct'],
            'rs_sts_spy': t_data['rs_sts_spy'],
            'rs_sts_qqq': t_data['rs_sts_qqq'],
            'ibd_rs': t_data['ibd_rs']
        })

    csv_date_path = os.path.join(data_dir, f'latest_{target_date}.csv')
    for path in [csv_date_path, os.path.join(data_dir, 'latest.csv')]:
        with open(path, 'w', encoding='utf-8', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
            writer.writeheader()
            writer.writerows(csv_rows)

    print(f"\nSuccessfully filled {len(new_tickers_data)} missing tickers for {target_date}.")
    print(f"Recalculated ranks across all {N} tickers.")

if __name__ == "__main__":
    main()
