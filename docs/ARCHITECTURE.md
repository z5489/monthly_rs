# RS Dashboard — Architecture Plan

---

## Stack & Hosting

- **Frontend:** Static `index.html` (vanilla JS) → deployed to **Vercel**
- **Data pipeline:** Python script run nightly via **GitHub Actions** → output committed to repo as `data/latest.json`
- **Vercel** serves the static site; the dashboard fetches `data/latest.json` on load

---

## Repo Structure

```
rs-dashboard/
├── .github/
│   └── workflows/
│       └── nightly_fetch.yml     # GitHub Actions cron job (weeknights)
├── data/
│   ├── latest.json               # Output consumed by dashboard
│   └── universe.csv              # Your watchlist (you maintain this)
├── scripts/
│   └── fetch.py                  # Python data fetcher & calculator
├── dashboard/
│   └── index.html                # The UI
└── README.md
```

---

## universe.csv Format

You maintain this file. To add or remove a stock, edit the CSV and push — the next nightly run picks it up automatically.

```csv
ticker,name
GOOGL,Alphabet Inc
UNH,UnitedHealth Group
BABA,Alibaba Group
...
```

---

## Data Pipeline (`fetch.py`)

Runs nightly at ~11pm ET (4am UTC) via GitHub Actions on weeknights.

### Inputs
- `data/universe.csv` — ticker list
- Yahoo Finance via `yfinance` — 1 year+ of daily OHLCV for all tickers + `SPY` + `QQQ`

### Price history required
| Lookback | Trading Days | Purpose |
|---|---|---|
| 1 month | ~20 days | RS_STS%, Daily%, 1-Month% |
| 3 months | ~63 days | IBD RS component (C₆₃) |
| 6 months | ~126 days | IBD RS component (C₁₂₆) |
| 9 months | ~189 days | IBD RS component (C₁₈₉) |
| 12 months | ~252 days | IBD RS component (C₂₅₂) |

**Pull ~270 trading days (~14 months) to safely cover all lookbacks.**

### Calculations per ticker

#### Daily% and 1-Month%
```
Daily%      = (close[0] / close[1]) - 1
1-Month%    = (close[0] / close[20]) - 1
```

#### RS Ratio (vs SPY and vs QQQ)
```
RS_ratio_SPY[t] = close_ticker[t] / close_SPY[t]
RS_ratio_QQQ[t] = close_ticker[t] / close_QQQ[t]
```
Computed daily for each of the past ~20 trading days.

#### RS_STS% (1-Month Relative Strength Strength, vs SPY and QQQ)
Percentile rank of today's RS ratio within its own 20-day window:
```
RS_STS%_SPY = percentile_rank(RS_ratio_SPY[0], RS_ratio_SPY[0:20])
RS_STS%_QQQ = percentile_rank(RS_ratio_QQQ[0], RS_ratio_QQQ[0:20])
```
- 100% = today's RS ratio is the highest point in the 20-day window (peak momentum)
- 0%   = today's RS ratio is the lowest point (weakest)
- Values ≥ 80% highlighted green; values ≤ 20% highlighted red

#### 1-Month RS Bar (for horizontal bar visualisation)
The 20-day RS ratio series, normalised to 0–1 within its own min/max range, stored as an array of 20 values. The bar width in the dashboard reflects today's RS_STS% (rightmost value). This mirrors the screenshot's bar style.

```
rs_bar_SPY = normalise(RS_ratio_SPY[0:20])   # array of 20 floats [0.0–1.0]
rs_bar_QQQ = normalise(RS_ratio_QQQ[0:20])
```

#### IBD-Style RS Rating (1–99)
Replicates IBD's weighted 12-month relative strength ranking methodology.

**Step 1 — Raw strength factor per ticker:**
```
RS_raw = 0.4 × (C / C₆₃) + 0.2 × (C / C₁₂₆) + 0.2 × (C / C₁₈₉) + 0.2 × (C / C₂₅₂)
```
Where:
- `C`    = today's closing price
- `C₆₃`  = close ~63 trading days ago  (3 months)
- `C₁₂₆` = close ~126 trading days ago (6 months)
- `C₁₈₉` = close ~189 trading days ago (9 months)
- `C₂₅₂` = close ~252 trading days ago (12 months)

The most recent quarter (3 months) is double-weighted at 40%, rewarding accelerating momentum over slow steady performance.

**Step 2 — Rank within the universe:**
All tickers in `universe.csv` are ranked from highest to lowest `RS_raw`. The ranking is then converted to a percentile score (1–99):
```
IBD_RS = round(percentile_rank(RS_raw, all_RS_raw) * 99)
IBD_RS = clamp(IBD_RS, 1, 99)
```
- 99 = top 1% of universe (strongest)
- 80+ = top 20%, generally considered a leading stock
- Below 40 = underperforming the broad universe

> **Note:** This is a *relative ranking within your universe*, not IBD's full ~8,000-stock database. Scores will differ from investors.com but the methodology and signal quality is equivalent for a focused watchlist.

### Output — `data/latest.json`

```json
{
  "generated_at": "2026-05-30T23:00:00",
  "benchmark_date": "2026-05-30",
  "tickers": [
    {
      "ticker": "GOOGL",
      "name": "Alphabet Inc",
      "daily_pct": 0.60,
      "one_month_pct": 10.56,
      "rs_sts_spy": 98,
      "rs_sts_qqq": 95,
      "rs_bar_spy": [0.10, 0.25, 0.40, ..., 1.00],
      "rs_bar_qqq": [0.15, 0.30, 0.45, ..., 0.95],
      "ibd_rs": 87
    }
  ]
}
```

---

## GitHub Actions (`nightly_fetch.yml`)

- **Trigger:** `cron: '0 4 * * 1-5'` — midnight ET, Monday–Friday
- **Steps:**
  1. Checkout repo
  2. Install dependencies: `yfinance pandas numpy`
  3. Run `scripts/fetch.py`
  4. `git commit && git push` — commits updated `data/latest.json` to repo
- No secrets required — `yfinance` uses Yahoo Finance's free public endpoints
- Vercel auto-redeploys on push, so the dashboard is always serving the latest data

---

## Dashboard (`index.html`)

### On load
`fetch('data/latest.json')` → parse → render table

### Columns (left → right)

| Column | Description | Visual treatment |
|---|---|---|
| Ticker | Symbol + full name | White on dark |
| 1-Month RS vs SPY | Horizontal bar (20-day normalised) | Green gradient bar |
| 1-Month RS vs QQQ | Horizontal bar (20-day normalised) | Green gradient bar |
| RS_STS% SPY | Today's percentile within 20-day RS window | Green ≥80%, Red ≤20% |
| RS_STS% QQQ | Same vs QQQ | Green ≥80%, Red ≤20% |
| IBD RS | Weighted 12-month RS rating (1–99, universe-relative) | Green ≥80, Red <40 |
| Daily% | Today's price change | Green/red gradient |
| 1-Month% | 20-day price change | Green/red gradient |

### Sorting
- **Default:** `1-Month%` descending
- **Interactive:** click any column header to sort ascending/descending

### Theme
- Dark charcoal background
- Subtle grid lines
- Monospace figures
- Header shows: `Last updated: [generated_at]` from JSON

---

## What's Excluded (by design)

| Field | Reason |
|---|---|
| Intraday% | Requires paid real-time feed |
| Beta | Excluded per preference; noisy at watchlist scale |
| Long/short ETF tickers | Require a separate mapping file; not in scope |

---

## Open Questions (resolved)

| Question | Decision |
|---|---|
| RS vs SPY or QQQ? | Both, side by side |
| 1-Month RS bar style | Single bar showing RS_STS% width, like the screenshot |
| IBD RS | Yes — calculate from price history, rank within universe |
| Benchmark | SPY + QQQ |
| Lookback for RS_STS% | 20 trading days |
| Refresh cadence | Nightly GitHub Actions cron |
| Hosting | Vercel |
| Theme | Dark charcoal |
| Cell colouring | Green/red gradient (like screenshot) |
