#!/usr/bin/env python3
import os

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    universe_path = os.path.join(base_dir, 'data', 'universe.csv')
    
    if not os.path.exists(universe_path):
        print(f"Error: universe.csv not found at {universe_path}")
        return

    # Read clean tickers from universe.csv
    tickers = []
    with open(universe_path, mode='r', encoding='utf-8') as f:
        for line in f:
            ticker = line.strip().upper()
            if ticker and ticker != 'TICKER' and not ticker.startswith('#') and '/' not in ticker:
                tickers.append(ticker)

    print(f"Loaded {len(tickers)} tickers from universe.csv (filtered out comments and slashes).")

    # Split into 3 batches round-robin
    num_batches = 3
    batches = [[] for _ in range(num_batches)]
    for i, t in enumerate(tickers):
        batches[i % num_batches].append(t)

    # Write batch files
    for idx, batch_tickers in enumerate(batches):
        batch_num = idx + 1
        batch_path = os.path.join(base_dir, 'data', f'universe_batch_{batch_num}.csv')
        with open(batch_path, 'w', encoding='utf-8') as f:
            for t in batch_tickers:
                f.write(f"{t}\n")
        print(f"Saved Batch {batch_num} to {batch_path} ({len(batch_tickers)} tickers).")

if __name__ == "__main__":
    main()
