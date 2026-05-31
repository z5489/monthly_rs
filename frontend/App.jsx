import React, { useState, useEffect, useRef } from 'react';

// Self-contained Sparkline canvas cell component
function SparklineCell({ series, color }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !series || series.length === 0) return;

    const draw = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;

      const ctx = canvas.getContext('2d');
      ctx.scale(dpr, dpr);

      const w = rect.width;
      const h = rect.height;

      ctx.clearRect(0, 0, w, h);

      ctx.beginPath();
      ctx.lineWidth = 1.5;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.strokeStyle = color;

      const padTop = 3;
      const padBottom = 3;
      const drawH = h - padTop - padBottom;

      for (let i = 0; i < series.length; i++) {
        const val = series[i]; // 0.0 to 1.0
        const x = (i / (series.length - 1)) * w;
        const y = padTop + (1.0 - val) * drawH; // Invert y: 1.0 is top, 0.0 is bottom

        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
    };

    draw();
    window.addEventListener('resize', draw);
    return () => window.removeEventListener('resize', draw);
  }, [series, color]);

  return <canvas ref={canvasRef} className="rs-sparkline" />;
}

export default function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedDate, setSelectedDate] = useState('');
  const [availableDates, setAvailableDates] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSector, setSelectedSector] = useState('All');
  const [sectorsList, setSectorsList] = useState([]);
  const [selectedIndustry, setSelectedIndustry] = useState('All');
  const [industriesList, setIndustriesList] = useState([]);
  const [activeFilter, setActiveFilter] = useState('key');
  const [keyTickers, setKeyTickers] = useState([]);
  const [sortConfig, setSortConfig] = useState({
    column: 'one_month_pct',
    direction: 'desc'
  });
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 100;
  const [theme, setTheme] = useState(() => {
    const stored = localStorage.getItem('theme');
    if (stored) return stored;
    return 'dark';
  });

  useEffect(() => {
    document.body.className = theme === 'light' ? 'light-theme' : '';
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  // Extract unique sectors list when data loads
  useEffect(() => {
    if (data && data.tickers) {
      const sectors = new Set();
      data.tickers.forEach(t => {
        if (t.sector) {
          sectors.add(t.sector);
        }
      });
      setSectorsList(['All', ...Array.from(sectors).sort()]);
    }
  }, [data]);

  // Extract unique industries list based on currently selected sector
  useEffect(() => {
    if (data && data.tickers) {
      const industries = new Set();
      data.tickers.forEach(t => {
        if (selectedSector === 'All' || t.sector === selectedSector) {
          if (t.industry) {
            industries.add(t.industry);
          }
        }
      });
      setIndustriesList(['All', ...Array.from(industries).sort()]);
      setSelectedIndustry('All'); // Reset selected industry when sector changes
    }
  }, [data, selectedSector]);

  // Reset pagination when search query, filter, sector, industry, or date changes
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, activeFilter, selectedSector, selectedIndustry, selectedDate]);

  // Fetch available dates on mount
  useEffect(() => {
    const fetchDates = async () => {
      const paths = ['/data/dates.json', 'data/dates.json', '../data/dates.json', './data/dates.json'];
      for (const p of paths) {
        try {
          const res = await fetch(p);
          if (res.ok) {
            const json = await res.json();
            setAvailableDates(json);
            if (json && json.length > 0) {
              setSelectedDate(json[0]);
            }
            break;
          }
        } catch (e) {
          // ignore
        }
      }
    };
    fetchDates();
  }, []);

  // Fetch key.csv on mount
  useEffect(() => {
    const fetchKeyTickers = async () => {
      const paths = ['/data/key.csv', 'data/key.csv', '../data/key.csv', './data/key.csv'];
      for (const p of paths) {
        try {
          const res = await fetch(p);
          if (res.ok) {
            const text = await res.text();
            const tickersList = text.split('\n')
              .map(line => line.trim().toUpperCase())
              .filter(line => line && !line.startsWith('#'));
            setKeyTickers(tickersList);
            break;
          }
        } catch (e) {
          // ignore
        }
      }
    };
    fetchKeyTickers();
  }, []);

  // Fetch relative strength analytics based on selectedDate
  useEffect(() => {
    if (!selectedDate && availableDates.length > 0) {
      setSelectedDate(availableDates[0]);
      return;
    }
    if (!selectedDate) return;

    const loadData = async () => {
      setLoading(true);
      setError(null);

      const fileName = `latest_${selectedDate}.json`;
      const paths = [`/data/${fileName}`, `data/${fileName}`, `../data/${fileName}`, `./data/${fileName}`];
      let response;
      let success = false;

      for (const p of paths) {
        try {
          response = await fetch(p);
          if (response.ok) {
            const json = await response.json();
            setData(json);
            success = true;
            break;
          }
        } catch (e) {
          // try next path
        }
      }

      if (!success) {
        throw new Error(selectedDate ? `No relative strength data found for ${selectedDate}.` : "Could not find latest.json in any standard path.");
      }
      setLoading(false);
    };

    loadData().catch(err => {
      console.error(err);
      setError(err.message);
      setLoading(false);
    });
  }, [selectedDate, availableDates]);

  // Sorting handler
  const handleSort = (col) => {
    setSortConfig(prev => {
      if (prev.column === col) {
        return { column: col, direction: prev.direction === 'asc' ? 'desc' : 'asc' };
      }
      return { column: col, direction: 'desc' }; // Default to desc for rankings
    });
  };

  if (loading) {
    return (
      <div className="container">
        <header>
          <div className="header-title">
            <h1>Relative Strength Leaderboard</h1>
            <p>Short-term (1-month) and long-term (12-month) Relative Strength</p>
          </div>
          <div className="header-meta">
            <div className="header-controls">
              <div className="header-control-group">
                <span>Market Date:</span>
                <select
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  className="date-select"
                  disabled={availableDates.length === 0}
                >
                  {availableDates.length === 0 && <option value="">Loading dates...</option>}
                  {availableDates.map(d => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
              </div>

              <button
                onClick={toggleTheme}
                className="theme-toggle-btn"
                title={theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
              >
                {theme === 'light' ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                  </svg>
                ) : (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="5"></circle>
                    <line x1="12" y1="1" x2="12" y2="3"></line>
                    <line x1="12" y1="21" x2="12" y2="23"></line>
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                    <line x1="1" y1="12" x2="3" y2="12"></line>
                    <line x1="21" y1="12" x2="23" y2="12"></line>
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
                  </svg>
                )}
              </button>
            </div>
          </div>
        </header>
        <div className="status-message">
          <div className="spinner"></div>
          <p>Loading relative strength analytics...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container">
        <header>
          <div className="header-title">
            <h1>Relative Strength Leaderboard</h1>
            <p>Short-term (1-month) and long-term (12-month) Relative Strength</p>
          </div>
          <div className="header-meta">
            <div className="header-controls">
              <div className="header-control-group">
                <span>Market Date:</span>
                <select
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  className="date-select"
                >
                  {availableDates.map(d => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
              </div>

              <button
                onClick={toggleTheme}
                className="theme-toggle-btn"
                title={theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
              >
                {theme === 'light' ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                  </svg>
                ) : (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="5"></circle>
                    <line x1="12" y1="1" x2="12" y2="3"></line>
                    <line x1="12" y1="21" x2="12" y2="23"></line>
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                    <line x1="1" y1="12" x2="3" y2="12"></line>
                    <line x1="21" y1="12" x2="23" y2="12"></line>
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
                  </svg>
                )}
              </button>
            </div>
          </div>
        </header>
        <div className="status-message">
          <p style={{ color: 'var(--red-text)' }}>⚠️ {error}</p>
          <p style={{ fontSize: '0.85rem', marginTop: '-0.5rem' }}>
            Ensure the pipeline has run on this date, or select another date.
          </p>
          <button
            className="btn"
            style={{ borderColor: 'var(--accent-color)', color: 'var(--accent-color)', marginTop: '0.5rem' }}
            onClick={() => {
              if (availableDates.length > 0) {
                setSelectedDate(availableDates[0]);
              }
            }}
          >
            Reset to Latest Date
          </button>
        </div>
      </div>
    );
  }

  const { benchmark_date, generated_at, tickers } = data;

  // Format generate time
  const genDate = new Date(generated_at);
  const formattedGen = genDate.toLocaleDateString() + ' ' + genDate.toLocaleTimeString();

  // Filter & Search stock list
  const filteredTickers = tickers.filter(t => {
    const tickerVal = t.ticker || '';
    const nameVal = t.name || '';
    const matchQuery = searchQuery.trim().toLowerCase();
    const matchesSearch = tickerVal.toLowerCase().includes(matchQuery) ||
      nameVal.toLowerCase().includes(matchQuery);

    if (!matchesSearch) return false;

    // Sector Filter
    if (selectedSector !== 'All') {
      const tickerSector = t.sector || 'Unknown';
      if (tickerSector !== selectedSector) return false;
    }

    // Industry Filter
    if (selectedIndustry !== 'All') {
      const tickerIndustry = t.industry || 'Unknown';
      if (tickerIndustry !== selectedIndustry) return false;
    }

    if (activeFilter === 'key') {
      return keyTickers.includes(t.ticker.toUpperCase());
    } else if (activeFilter === 'ibd-leads') {
      return t.ibd_rs >= 80;
    } else if (activeFilter === 'sts-leads') {
      return t.rs_sts_spy >= 80 || t.rs_sts_qqq >= 80;
    } else if (activeFilter === 'weak') {
      return t.ibd_rs <= 40 || t.rs_sts_spy <= 20 || t.rs_sts_qqq <= 20;
    }
    return true;
  });

  // Sort stock list
  const sortedTickers = [...filteredTickers].sort((a, b) => {
    const valA = a[sortConfig.column];
    const valB = b[sortConfig.column];

    if (typeof valA === 'string') {
      return sortConfig.direction === 'asc'
        ? valA.localeCompare(valB)
        : valB.localeCompare(valA);
    }
    return sortConfig.direction === 'asc' ? valA - valB : valB - valA;
  });

  const totalPages = Math.max(1, Math.ceil(sortedTickers.length / pageSize));
  const paginatedTickers = sortedTickers.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  // Sort indicator helper
  const getSortClass = (col) => {
    if (sortConfig.column === col) {
      return sortConfig.direction === 'asc' ? 'sorted-asc' : 'sorted-desc';
    }
    return '';
  };

  return (
    <div className="container">
      <header>
        <div className="header-title">
          <h1>Relative Strength Leaderboard</h1>
          <p>Short-term (1-month) and long-term (12-month) Relative Strength</p>
        </div>
        <div className="header-meta">
          <div className="header-controls">
            <div className="header-control-group">
              <span>Market Date:</span>
              <select
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="date-select"
              >
                {availableDates.map(d => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>

            <button
              onClick={toggleTheme}
              className="theme-toggle-btn"
              title={theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
            >
              {theme === 'light' ? (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                </svg>
              ) : (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="5"></circle>
                  <line x1="12" y1="1" x2="12" y2="3"></line>
                  <line x1="12" y1="21" x2="12" y2="23"></line>
                  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                  <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                  <line x1="1" y1="12" x2="3" y2="12"></line>
                  <line x1="21" y1="12" x2="23" y2="12"></line>
                  <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                  <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
                </svg>
              )}
            </button>
          </div>
          <div>Updated: <span>{formattedGen}</span></div>
        </div>
      </header>

      <div className="controls-row">
        <div className="search-group">
          <div className="search-container">
            <svg className="search-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
            </svg>
            <input
              type="text"
              className="search-input"
              placeholder="Search symbol or name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <select
            value={selectedSector}
            onChange={(e) => setSelectedSector(e.target.value)}
            className="sector-select"
            title="Filter stocks by broad sector"
          >
            <option value="All">All Sectors</option>
            {sectorsList.filter(s => s !== 'All').map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          <select
            value={selectedIndustry}
            onChange={(e) => setSelectedIndustry(e.target.value)}
            className="industry-select"
            title="Filter stocks by specific industry sub-sector"
            disabled={industriesList.length <= 1}
          >
            <option value="All">All Industries</option>
            {industriesList.filter(i => i !== 'All').map(i => (
              <option key={i} value={i}>{i}</option>
            ))}
          </select>
        </div>

        <div className="filter-buttons">
          <button
            className={`btn ${activeFilter === 'key' ? 'active' : ''}`}
            onClick={() => setActiveFilter('key')}
            title="Show only key tickers from key.csv"
          >
            ⭐ Key Tickers
          </button>
          <button
            className={`btn ${activeFilter === 'all' ? 'active' : ''}`}
            onClick={() => setActiveFilter('all')}
            title="Show all tickers in the watchlist without filtering"
          >
            All Tickers
          </button>
          <button
            className={`btn ${activeFilter === 'ibd-leads' ? 'active' : ''}`}
            onClick={() => setActiveFilter('ibd-leads')}
            title="Show stocks with a 12-month IBD Relative Strength rating of 80 or higher"
          >
            IBD RS Leads (≥ 80)
          </button>
          <button
            className={`btn ${activeFilter === 'sts-leads' ? 'active' : ''}`}
            onClick={() => setActiveFilter('sts-leads')}
            title="Show stocks with a 1-month Short-Term Strength (STS) percentile rank of 80 or higher vs SPY or QQQ"
          >
            STS Leads (≥ 80 vs SPY/QQQ)
          </button>
          <button
            className={`btn ${activeFilter === 'weak' ? 'active' : ''}`}
            onClick={() => setActiveFilter('weak')}
            title="Show stocks with weak 12-month strength (IBD RS ≤ 40) or weak short-term strength (STS ≤ 20 vs SPY/QQQ)"
          >
            Underperforming (IBD ≤ 40 or STS ≤ 20)
          </button>
        </div>
      </div>

      <div className="table-card">
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th className={`sortable ${getSortClass('ticker')}`} onClick={() => handleSort('ticker')} title="Stock ticker symbol and company name">Ticker</th>
                <th style={{ width: '140px' }} title="Visual 1-month Relative Strength (bar represents percentile rank, sparkline shows daily ratio vs SPY)">1-Mo RS vs SPY</th>
                <th style={{ width: '140px' }} title="Visual 1-month Relative Strength (bar represents percentile rank, sparkline shows daily ratio vs QQQ)">1-Mo RS vs QQQ</th>
                <th className={`sortable ${getSortClass('rs_sts_spy')}`} onClick={() => handleSort('rs_sts_spy')} title="1-month Short-Term Strength (STS) percentile rank vs SPY. High values indicate short-term market leaders.">RS_STS% SPY</th>
                <th className={`sortable ${getSortClass('rs_sts_qqq')}`} onClick={() => handleSort('rs_sts_qqq')} title="1-month Short-Term Strength (STS) percentile rank vs QQQ. High values indicate short-term tech leaders.">RS_STS% QQQ</th>
                <th className={`sortable ${getSortClass('ibd_rs')}`} onClick={() => handleSort('ibd_rs')} title="12-month traditional IBD-style Relative Strength percentile rank vs the whole market (weighted: 40% Q4, 20% each Q3/Q2/Q1)">IBD RS</th>
                <th className={`sortable ${getSortClass('daily_pct')}`} onClick={() => handleSort('daily_pct')} title="Single-day price change percentage">Daily%</th>
                <th className={`sortable ${getSortClass('one_month_pct')}`} onClick={() => handleSort('one_month_pct')} title="Trailing 1-month price change percentage">1-Month%</th>
              </tr>
            </thead>
            <tbody>
              {sortedTickers.length === 0 ? (
                <tr>
                  <td colSpan="8" className="empty-state">
                    No tickers match the selected filters or search query.
                  </td>
                </tr>
              ) : (
                paginatedTickers.map(t => {
                  const dailyClass = t.daily_pct > 0 ? 'badge-green' : (t.daily_pct < 0 ? 'badge-red' : 'badge-neutral');
                  const monthlyClass = t.one_month_pct > 0 ? 'badge-green' : (t.one_month_pct < 0 ? 'badge-red' : 'badge-neutral');
                  const stsSpyClass = t.rs_sts_spy >= 80 ? 'badge-green' : (t.rs_sts_spy <= 20 ? 'badge-red' : 'badge-neutral');
                  const stsQqqClass = t.rs_sts_qqq >= 80 ? 'badge-green' : (t.rs_sts_qqq <= 20 ? 'badge-red' : 'badge-neutral');
                  const ibdClass = t.ibd_rs >= 80 ? 'badge-green' : (t.ibd_rs <= 40 ? 'badge-red' : 'badge-neutral');

                  // Sparkline line colors (adapted for light/dark themes)
                  const isLight = theme === 'light';
                  const spyColor = t.rs_sts_spy >= 80 ? (isLight ? '#059669' : '#10b981') : (t.rs_sts_spy <= 20 ? (isLight ? '#dc2626' : '#ef4444') : (isLight ? '#4f46e5' : '#6366f1'));
                  const qqqColor = t.rs_sts_qqq >= 80 ? (isLight ? '#059669' : '#10b981') : (t.rs_sts_qqq <= 20 ? (isLight ? '#dc2626' : '#ef4444') : (isLight ? '#4f46e5' : '#6366f1'));

                  return (
                    <tr key={t.ticker}>
                      <td>
                        <div className="ticker-cell">
                          <div className="ticker-symbol-row">
                            <span className="ticker-symbol">{t.ticker}</span>
                            {t.sector && t.sector !== 'Unknown' && (
                              <span className="sector-pill" title={`Sector: ${t.sector}`}>{t.sector}</span>
                            )}
                            {t.industry && t.industry !== 'Unknown' && (
                              <span className="industry-pill" title={`Industry: ${t.industry}`}>{t.industry}</span>
                            )}
                          </div>
                          <span className="ticker-name" title={t.name}>{t.name}</span>
                        </div>
                      </td>
                      <td className="rs-bar-cell">
                        <div className="rs-bar-container">
                          <div
                            className={`rs-bar-fill ${t.rs_sts_spy >= 80 ? 'lead' : (t.rs_sts_spy <= 20 ? 'weak' : '')}`}
                            style={{ width: `${t.rs_sts_spy}%` }}
                          />
                          <SparklineCell series={t.rs_bar_spy} color={spyColor} />
                        </div>
                      </td>
                      <td className="rs-bar-cell">
                        <div className="rs-bar-container">
                          <div
                            className={`rs-bar-fill ${t.rs_sts_qqq >= 80 ? 'lead' : (t.rs_sts_qqq <= 20 ? 'weak' : '')}`}
                            style={{ width: `${t.rs_sts_qqq}%` }}
                          />
                          <SparklineCell series={t.rs_bar_qqq} color={qqqColor} />
                        </div>
                      </td>
                      <td>
                        <span className={`badge ${stsSpyClass} number-val`}>{t.rs_sts_spy}%</span>
                      </td>
                      <td>
                        <span className={`badge ${stsQqqClass} number-val`}>{t.rs_sts_qqq}%</span>
                      </td>
                      <td>
                        <span className={`badge ${ibdClass} number-val`}>{t.ibd_rs}</span>
                      </td>
                      <td>
                        <span className={`badge ${dailyClass} number-val`}>
                          {t.daily_pct > 0 ? '+' : ''}{t.daily_pct.toFixed(2)}%
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${monthlyClass} number-val`}>
                          {t.one_month_pct > 0 ? '+' : ''}{t.one_month_pct.toFixed(2)}%
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
        {sortedTickers.length > 0 && (
          <div className="pagination-row">
            <div>
              Showing <span>{((currentPage - 1) * pageSize) + 1}</span> to{' '}
              <span>{Math.min(currentPage * pageSize, sortedTickers.length)}</span> of{' '}
              <span>{sortedTickers.length}</span> entries
            </div>
            {totalPages > 1 && (
              <div className="pagination-controls">
                <button
                  className="pagination-btn"
                  onClick={() => setCurrentPage(1)}
                  disabled={currentPage === 1}
                >
                  First
                </button>
                <button
                  className="pagination-btn"
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={currentPage === 1}
                >
                  Previous
                </button>
                <span className="pagination-status">
                  Page <strong>{currentPage}</strong> of <strong>{totalPages}</strong>
                </span>
                <button
                  className="pagination-btn"
                  onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                  disabled={currentPage === totalPages}
                >
                  Next
                </button>
                <button
                  className="pagination-btn"
                  onClick={() => setCurrentPage(totalPages)}
                  disabled={currentPage === totalPages}
                >
                  Last
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
