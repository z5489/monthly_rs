# Watchlist Relative Strength (RS) Dashboard

A premium, interactive dashboard that computes and tracks relative strength metrics for a customized stock watchlist. The dashboard is populated by a nightly data pipeline running via GitHub Actions, which processes historical data from Yahoo Finance and commits the results as static JSON and CSV files.

## Features

- **Short-Term Momentum (RS_STS%):** Calculates the percentile rank of the stock's relative strength ratio (Ticker price divided by SPY or QQQ benchmark price) within the last 20 trading days. Highlights extreme momentum peaks (>= 80% in green) or underperformance (<= 20% in red).
- **Long-Term Ranking (IBD-Style RS Rating):** Replicates the IBD relative strength rating method (1-99) within the watchlist universe, double-weighting the most recent quarter:
  $$RS_{\text{raw}} = 0.4 \times (C / C_{63}) + 0.2 \times (C / C_{126}) + 0.2 \times (C / C_{189}) + 0.2 \times (C / C_{252})$$
  The raw scores are then ranked as a percentile score (1-99) within the universe.
- **Sparklines & Progress Bars:** Visually represents the 20-day relative strength trajectory against SPY and QQQ using HTML Canvas sparklines overlaid on colored progress bars.
- **Date Filtering & Historical Archives:** Let users jump to a specific market date in the past via a date picker. The dashboard loads the corresponding archived dataset (or falls back to the latest dataset by default).
- **Search & Filters:** Real-time search by symbol/name and quick-action buttons to filter by Leaders or Underperformers.
- **Interactive Sorting:** Sort all columns (Ticker, RS_STS%, IBD RS, Daily%, 1-Month%) dynamically.

---

## Repo Structure

```
├── .github/
│   └── workflows/
│       └── nightly_fetch.yml     # Nightly weeknight GitHub Actions cron job
├── data/
│   ├── latest.json               # Consolidated latest JSON payload
│   ├── latest_YYYY-MM-DD.json    # Date-suffixed archived JSON payload
│   ├── latest.csv                # Consolidated latest CSV spreadsheet
│   ├── latest_YYYY-MM-DD.csv     # Date-suffixed archived CSV spreadsheet
│   └── universe.csv              # Custom stock watchlist (ticker symbols, one per line)
├── scripts/
│   ├── fetch.py                  # Python data fetching and processing pipeline
│   └── copy-data.js              # Post-build data copy script for production
├── frontend/
│   ├── App.jsx                   # React App container with state and date filters
│   ├── main.jsx                  # React DOM mounting entry point
│   ├── index.css                 # Premium dark theme stylesheet
│   ├── index.html                # Entry point loaded by Vite
│   ├── package.json              # NPM packages and dev/build scripts
│   └── vite.config.js            # Vite configurations (with dev server middleware)
```

---

## Watchlist & Pipeline Restructuring

To handle large watchlist databases (e.g. 5,000+ tickers) efficiently and avoid Yahoo Finance endpoint rate limits, the system operates with the following optimizations:

- **Simplified Watchlist Format:** `data/universe.csv` is now a simple list of ticker symbols (one per line, no column headers, no name entries). The original dataset consists of US-listed stocks with a market capitalization greater than $1B.
- **Slash Filter:** Tickers containing `/` (such as preferred shares `JPM/PD`) are automatically skipped from querying to ensure API compatibility.
- **Three-Batch Round-Robin Partitioning:** Tickers are divided into 3 equal batches and processed sequentially.
- **Throttling & Cool-Down Sleeps:**
  - The pipeline pauses for `0.1` seconds between individual ticker history requests.
  - The pipeline pauses for `5` seconds between each of the 3 batches.
- **Rate-Limit Retry Handler:** If Yahoo Finance returns empty data or throttling errors occur, the script retries up to 3 times per ticker using progressive backoff delays (5s, 10s, and 20s).
- **Data File Outputs:** Each pipeline run generates both standard files (`latest.json`, `latest.csv`) and date-suffixed archive files (`latest_YYYY-MM-DD.json`, `latest_YYYY-MM-DD.csv` based on the market close date).

---

## Quick Start (Local Setup)

### 1. Prerequisites

Ensure Python 3 and Node.js are installed. Navigate to the project root and install the required Python dependencies:

```bash
pip install -r requirements.txt
```

### 2. Configure Your Watchlist

You can modify `data/universe.csv` to add or remove stock symbols (simply add one ticker symbol per line):

```csv
NVDA
GOOGL
AAPL
MSFT
AMZN
```

### 3. Run the Data Pipeline

Execute the data pipeline to retrieve market data, divide the queries into batches, and output the consolidated and archived rankings:

```bash
python scripts/fetch.py
```

This generates `latest.json`, `latest.csv` and their date-suffixed counterparts inside `data/`.

### 4. Run the React Dashboard

Navigate to the `frontend/` folder, install the packages, and run the dev server:

```bash
cd frontend
npm install
npm run dev
```

Now open [http://localhost:5173](http://localhost:5173) in your browser. 

---

## Deployment & Automations

- **Data Updates (GitHub Actions):** The `.github/workflows/nightly_fetch.yml` cron job runs automatically on weeknights (Midnight ET / 4:00 AM UTC). It fetches the latest prices, recalculates ratings across the 3 batches, and commits all updated and new date-suffixed calculations back to the repository.
- **UI Hosting (Vercel):** Connect the GitHub repository to **Vercel** as a Vite application:
  - **Framework Preset:** Vite
  - **Root Directory:** `frontend`
  - **Build Command:** `npm run build` (vite build + our copy script to transfer all JSON/CSV archives to the deploy static assets folder)
  - **Output Directory:** `dist`
