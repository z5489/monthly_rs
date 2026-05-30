import React, { useState, useEffect, useRef } from 'react';
import latestData from '../data/latest.json';

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
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [sortConfig, setSortConfig] = useState({
    column: 'one_month_pct',
    direction: 'desc'
  });

  const { benchmark_date, generated_at, tickers } = latestData;

  // Sorting handler
  const handleSort = (col) => {
    setSortConfig(prev => {
      if (prev.column === col) {
        return { column: col, direction: prev.direction === 'asc' ? 'desc' : 'asc' };
      }
      return { column: col, direction: 'desc' }; // Default to desc for rankings
    });
  };

  // Format generate time
  const genDate = new Date(generated_at);
  const formattedGen = genDate.toLocaleDateString() + ' ' + genDate.toLocaleTimeString();

  // Filter & Search stock list
  const filteredTickers = tickers.filter(t => {
    const matchQuery = searchQuery.trim().toLowerCase();
    const matchesSearch = t.ticker.toLowerCase().includes(matchQuery) ||
                          t.name.toLowerCase().includes(matchQuery);
    
    if (!matchesSearch) return false;

    if (activeFilter === 'ibd-leads') {
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
          <h1>Watchlist Relative Strength Leaderboard</h1>
          <p>Nightly calculations of short-term (1-month) and long-term (12-month) Relative Strength</p>
        </div>
        <div className="header-meta">
          Market Date: <span>{benchmark_date}</span><br />
          Updated: <span>{formattedGen}</span>
        </div>
      </header>

      <div className="controls-row">
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

        <div className="filter-buttons">
          <button
            className={`btn ${activeFilter === 'all' ? 'active' : ''}`}
            onClick={() => setActiveFilter('all')}
          >
            All Watchlist
          </button>
          <button
            className={`btn ${activeFilter === 'ibd-leads' ? 'active' : ''}`}
            onClick={() => setActiveFilter('ibd-leads')}
          >
            IBD Leads (≥ 80)
          </button>
          <button
            className={`btn ${activeFilter === 'sts-leads' ? 'active' : ''}`}
            onClick={() => setActiveFilter('sts-leads')}
          >
            STS Leads (≥ 80)
          </button>
          <button
            className={`btn ${activeFilter === 'weak' ? 'active' : ''}`}
            onClick={() => setActiveFilter('weak')}
          >
            Underperforming (≤ 40)
          </button>
        </div>
      </div>

      <div className="table-card">
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th className={`sortable ${getSortClass('ticker')}`} onClick={() => handleSort('ticker')}>Ticker</th>
                <th style={{ width: '140px' }}>1-Mo RS vs SPY</th>
                <th style={{ width: '140px' }}>1-Mo RS vs QQQ</th>
                <th className={`sortable ${getSortClass('rs_sts_spy')}`} onClick={() => handleSort('rs_sts_spy')}>RS_STS% SPY</th>
                <th className={`sortable ${getSortClass('rs_sts_qqq')}`} onClick={() => handleSort('rs_sts_qqq')}>RS_STS% QQQ</th>
                <th className={`sortable ${getSortClass('ibd_rs')}`} onClick={() => handleSort('ibd_rs')}>IBD RS</th>
                <th className={`sortable ${getSortClass('daily_pct')}`} onClick={() => handleSort('daily_pct')}>Daily%</th>
                <th className={`sortable ${getSortClass('one_month_pct')}`} onClick={() => handleSort('one_month_pct')}>1-Month%</th>
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
                sortedTickers.map(t => {
                  const dailyClass = t.daily_pct > 0 ? 'badge-green' : (t.daily_pct < 0 ? 'badge-red' : 'badge-neutral');
                  const monthlyClass = t.one_month_pct > 0 ? 'badge-green' : (t.one_month_pct < 0 ? 'badge-red' : 'badge-neutral');
                  const stsSpyClass = t.rs_sts_spy >= 80 ? 'badge-green' : (t.rs_sts_spy <= 20 ? 'badge-red' : 'badge-neutral');
                  const stsQqqClass = t.rs_sts_qqq >= 80 ? 'badge-green' : (t.rs_sts_qqq <= 20 ? 'badge-red' : 'badge-neutral');
                  const ibdClass = t.ibd_rs >= 80 ? 'badge-green' : (t.ibd_rs <= 40 ? 'badge-red' : 'badge-neutral');

                  // Sparkline line colors
                  const spyColor = t.rs_sts_spy >= 80 ? '#3fb950' : (t.rs_sts_spy <= 20 ? '#f85149' : '#58a6ff');
                  const qqqColor = t.rs_sts_qqq >= 80 ? '#3fb950' : (t.rs_sts_qqq <= 20 ? '#f85149' : '#58a6ff');

                  return (
                    <tr key={t.ticker}>
                      <td>
                        <div className="ticker-cell">
                          <span className="ticker-symbol">{t.ticker}</span>
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
      </div>
    </div>
  );
}
