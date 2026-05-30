# Implementation Plan — Date Filtering & Archiving

Add the capability to view historical relative strength rankings by generating date-suffixed data files from the data pipeline and providing a date selector on the React dashboard.

## User Review Required

> [!IMPORTANT]
> - **Data Files:** For each calculation run, the pipeline will output:
>   - `data/latest.json` (latest JSON)
>   - `data/latest_YYYY-MM-DD.json` (archived JSON)
>   - `data/latest.csv` (latest CSV)
>   - `data/latest_YYYY-MM-DD.csv` (archived CSV)
> - **Date Selection UI:** The React app will render a styled date picker `<input type="date">`. Changing the date will query the corresponding date-suffixed file. If a file is not found (e.g. because the pipeline did not run on that date), the UI will display a helpful error message and a "Reset to Latest" option.
> - **Build & Serving:** To support dynamic runtime fetches, we will re-introduce a copy script hook `scripts/copy-data.js` to transfer all historical JSON/CSV files into the build folder (`frontend/dist/data/`) and configure Vite's dev server middleware to resolve data files locally in development mode.

## Proposed Changes

We will modify files inside the workspace root `c:\Users\ziyen\monthly_rs`.

---

### 1. Data Pipeline Updates

#### [MODIFY] [scripts/fetch.py](file:///c:/Users/ziyen/monthly_rs/scripts/fetch.py)
Update outputs:
- In addition to writing `data/latest.json`, write:
  - `data/latest_YYYY-MM-DD.json` (where YYYY-MM-DD is the benchmark date)
  - `data/latest.csv`
  - `data/latest_YYYY-MM-DD.csv`
- The CSV columns will be: `ticker,name,daily_pct,one_month_pct,rs_sts_spy,rs_sts_qqq,ibd_rs`.

---

### 2. Frontend React Updates

#### [MODIFY] [frontend/App.jsx](file:///c:/Users/ziyen/monthly_rs/frontend/App.jsx)
Introduce state and fetching logic:
- Add state variables: `data`, `loading`, `error`, `selectedDate` (initial state `""`).
- Create a `useEffect` fetch hook keyed on `selectedDate`.
  - If `selectedDate` is empty, fetch `/data/latest.json`.
  - Else, fetch `/data/latest_${selectedDate}.json`.
  - Handle success (render table) and fail (show error badge "No data found for this date").
- Add a styled date picker `<input type="date">` and a "Reset to Latest" button in the Controls row.

---

### 3. Build & Local Serving Configs

#### [NEW] [scripts/copy-data.js](file:///c:/Users/ziyen/monthly_rs/scripts/copy-data.js)
A node script that copies all `.json` and `.csv` files from the `data/` directory to `frontend/dist/data/` post-build.

#### [MODIFY] [frontend/package.json](file:///c:/Users/ziyen/monthly_rs/frontend/package.json)
Update build command to run the copy script:
- `"build": "vite build && node ../scripts/copy-data.js"`

#### [MODIFY] [frontend/vite.config.js](file:///c:/Users/ziyen/monthly_rs/frontend/vite.config.js)
Re-introduce the dev server middleware plugin `serve-data-dir` to serve local `/data/*` requests from the parent `data/` directory.

---

## Verification Plan

### Automated/Local Tests
- Run `python scripts/fetch.py` and verify it writes `latest_YYYY-MM-DD.json` and `latest_YYYY-MM-DD.csv` files.
- Run `npm run dev` inside `frontend/` and verify:
  - Default load displays latest data.
  - Picking a valid date updates the leaderboard.
  - Picking an invalid date displays a clean error state.
- Run `npm run build` and check `frontend/dist/data/` contains all date-suffixed files.
