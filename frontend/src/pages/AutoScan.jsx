import { useState, useEffect, useRef } from "react";
import { PageHeader, Spinner } from "../components/shared";
import { api } from "../services/api";
import * as XLSX from "xlsx";

const CATS = [
  { id: "electronics",   icon: "📱", label: "Electronics & Gadgets" },
  { id: "apparel",       icon: "👜", label: "Apparel & Accessories" },
  { id: "auto",          icon: "🚗", label: "Auto & Car Accessories" },
  { id: "jewelry",       icon: "💎", label: "Jewelry & Watches" },
  { id: "collectibles",  icon: "🎨", label: "Collectibles & Crafts" },
  { id: "health_beauty", icon: "💊", label: "Health & Beauty" },
  { id: "home_garden",   icon: "🏠", label: "Home & Garden" },
  { id: "kitchen",       icon: "🍳", label: "Kitchen & Dining" },
  { id: "pets",          icon: "🐾", label: "Pet Supplies" },
  { id: "office",        icon: "💼", label: "Office & Desk" },
  { id: "sports",        icon: "💪", label: "Sports & Fitness" },
  { id: "toys",          icon: "🧸", label: "Toys & Hobbies" },
  { id: "baby",          icon: "👶", label: "Baby & Kids" },
  { id: "outdoor",       icon: "🌿", label: "Outdoor & Recreation" },
];

// ── Demand badge ──────────────────────────────────────────────
const demandBadge = (d) => ({
  hot:      { label: "🔥 Hot",      bg: "#fef2f2", color: "#dc2626", border: "#fca5a5" },
  good:     { label: "📈 Active",   bg: "#f0fdf4", color: "#16a34a", border: "#86efac" },
  moderate: { label: "📊 Moderate", bg: "#fef9c3", color: "#a16207", border: "#fde047" },
  low:      { label: "💤 Slow",     bg: "#f1f5f9", color: "#64748b", border: "#cbd5e1" },
}[d] || { label: "—", bg: "#f1f5f9", color: "#64748b", border: "#e2e8f0" });

// ── Competition badge ─────────────────────────────────────────
const compBadge = (c) => ({
  low:    { label: "🟢 Low",    bg: "#f0fdf4", color: "#16a34a", border: "#86efac" },
  medium: { label: "🟡 Medium", bg: "#fef9c3", color: "#a16207", border: "#fde047" },
  high:   { label: "🔴 High",   bg: "#fef2f2", color: "#dc2626", border: "#fca5a5" },
}[c] || { label: "—", bg: "#f1f5f9", color: "#64748b", border: "#e2e8f0" });

// ── Full-scan match badge ─────────────────────────────────────
const matchBadge = (score) => {
  if (score >= 60) return { icon: "🟢", label: "Great",  bg: "#dcfce7", color: "#15803d", border: "#86efac", bar: "#16a34a" };
  if (score >= 40) return { icon: "🟡", label: "Good",   bg: "#fef9c3", color: "#a16207", border: "#fde047", bar: "#eab308" };
  return             { icon: "🟠", label: "Weak",   bg: "#fff7ed", color: "#c2410c", border: "#fdba74", bar: "#f97316" };
};

// ── Opportunity score color ───────────────────────────────────
const oppColor = (s) => s >= 70 ? "#16a34a" : s >= 40 ? "#d97706" : "#94a3b8";

export default function AutoScan({ showToast, scanState, setScanState }) {
  const [mode,         setMode]         = useState(scanState.mode || "scout");
  const [selectedCats, setSelectedCats] = useState(
    scanState.selectedCats?.length ? scanState.selectedCats : ["electronics", "home_garden", "pets"]
  );
  const [sortBy,       setSortBy]       = useState("opp_score");
  const [checkingAmz,  setCheckingAmz]  = useState({});
  const [expandedRow,  setExpandedRow]  = useState(null);
  const [importing,    setImporting]    = useState({});
  const pollRef = useRef(null);

  const isRunning = scanState.active && !scanState.done;
  const results   = scanState.results || [];
  const pct = scanState.total > 0 ? Math.round(scanState.progress / scanState.total * 100) : 0;

  // ── Polling ──────────────────────────────────────────────────
  const startPolling = (scanId) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const s = await api.scanStatus(scanId);
        setScanState(prev => ({
          ...prev,
          results:    s.results,
          progress:   s.progress,
          total:      s.total,
          totalFound: s.total_found,
          done:       s.done,
          active:     !s.done,
        }));
        if (s.done) stopPolling();
      } catch { stopPolling(); }
    }, 2000);
  };
  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  useEffect(() => {
    if (scanState.scanId && scanState.active && !scanState.done) startPolling(scanState.scanId);
    return () => stopPolling();
  }, []); // eslint-disable-line

  // ── Start scan ───────────────────────────────────────────────
  const startScan = async () => {
    if (!selectedCats.length) { showToast("Select at least one category", "error"); return; }
    try {
      const r = await api.startScan({ mode, category_ids: selectedCats });
      setScanState({ scanId: r.scan_id, active: true, mode, selectedCats,
                     results: [], progress: 0, total: r.total, totalFound: 0, done: false });
      startPolling(r.scan_id);
      showToast(`${mode === "scout" ? "⚡ eBay Scout" : "🔍 Full Profit Scan"} started — ${r.total} keyword sets`);
    } catch (e) { showToast(e.message, "error"); }
  };

  const cancelScan = async () => {
    if (!scanState.scanId) return;
    try { await api.cancelScan(scanState.scanId); } catch {}
    stopPolling();
    setScanState(prev => ({ ...prev, active: false, done: true }));
    showToast("Scan stopped");
  };

  const clearResults = () => {
    stopPolling();
    setScanState({ scanId: null, active: false, mode, selectedCats,
                   results: [], progress: 0, total: 0, totalFound: 0, done: false });
    setCheckingAmz({}); setExpandedRow(null);
  };

  // ── Category toggles ─────────────────────────────────────────
  const toggleCat  = (id) => setSelectedCats(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id]);
  const selectAll  = () => setSelectedCats(CATS.map(c => c.id));
  const clearCats  = () => setSelectedCats([]);

  // ── Inline Amazon check ──────────────────────────────────────
  const checkAmazon = async (row) => {
    const key = row.ebay_title;
    setCheckingAmz(p => ({ ...p, [key]: { loading: true } }));
    setExpandedRow(key);
    try {
      const r = await api.checkAmazon({ ebay_title: row.ebay_title, ebay_sell_price: row.ebay_sell_price });
      setCheckingAmz(p => ({ ...p, [key]: { loading: false, result: r } }));
    } catch (e) {
      setCheckingAmz(p => ({ ...p, [key]: { loading: false, error: e.message } }));
    }
  };

  // ── Import opportunity ───────────────────────────────────────
  const importOpp = async (item) => {
    const key = item.amazon_asin || item.ebay_title;
    setImporting(p => ({ ...p, [key]: true }));
    try {
      await api.importOpportunity({ amazon_asin: item.amazon_asin, ebay_avg_sold: item.ebay_avg_sold });
      showToast("✓ Imported to Products");
    } catch (e) { showToast(e.message, "error"); }
    setImporting(p => ({ ...p, [key]: false }));
  };

  // ── Download XLSX ─────────────────────────────────────────────
  const downloadXLSX = () => {
    const mode = scanState.mode;
    const rows = sortedResults;
    const date = new Date().toISOString().slice(0, 10);
    const wb   = XLSX.utils.book_new();

    // Helper: convert URL columns into HYPERLINK() formulas (works in Excel + Google Sheets)
    // urlColNames = { "Header Name": "Display Label" }
    const applyHyperlinks = (ws, urlColNames) => {
      const range = XLSX.utils.decode_range(ws["!ref"]);
      // Map header name → column index
      const colIndex = {};
      for (let C = range.s.c; C <= range.e.c; C++) {
        const hdr = ws[XLSX.utils.encode_cell({ r: 0, c: C })];
        if (hdr && urlColNames[hdr.v] !== undefined) colIndex[C] = urlColNames[hdr.v];
      }
      // Write HYPERLINK formula into each data row cell
      for (let R = 1; R <= range.e.r; R++) {
        for (const [C, label] of Object.entries(colIndex)) {
          const addr = XLSX.utils.encode_cell({ r: R, c: +C });
          const cell = ws[addr];
          if (cell && cell.v && typeof cell.v === "string" && cell.v.startsWith("http")) {
            const safeUrl = cell.v.replace(/"/g, '""'); // escape any quotes in URL
            cell.f = `HYPERLINK("${safeUrl}","${label}")`;
            cell.v = label;
            cell.t = "s";
          }
        }
      }
    };

    if (mode === "scout") {
      const data = rows.map((r, i) => ({
        "#":                i + 1,
        "Product Title":    r.ebay_title || "",
        "eBay Avg Sold $":  r.ebay_avg_sold   != null ? +r.ebay_avg_sold.toFixed(2)   : "",
        "Your Sell Price $":r.ebay_sell_price  != null ? +r.ebay_sell_price.toFixed(2)  : "",
        "Price Min $":      r.price_min        != null ? +r.price_min.toFixed(2)        : "",
        "Price Max $":      r.price_max        != null ? +r.price_max.toFixed(2)        : "",
        "Est Profit Low $": r.est_profit_low   != null ? +r.est_profit_low.toFixed(2)   : "",
        "Est Profit High $":r.est_profit_high  != null ? +r.est_profit_high.toFixed(2)  : "",
        "Est ROI Low %":    r.est_roi_low  || 0,
        "Est ROI High %":   r.est_roi_high || 0,
        "Opp Score":        r.opp_score    || 0,
        "Demand":           r.demand       || "",
        "Competition":      r.competition  || "",
        "Total Sold":       r.total_sold   || 0,
        "Active Listings":  r.active_listings || 0,
        "Unique Sellers":   r.unique_sellers  || 0,
        "% New Items":      r.new_pct || 0,
        "eBay Sold Search": r.ebay_search_url   || "",
        "eBay Listing":     r.ebay_item_url     || "",
        "Amazon Search":    r.amazon_search_url || "",
      }));
      const ws = XLSX.utils.json_to_sheet(data);
      ws["!cols"] = [
        {wch:4},{wch:55},{wch:16},{wch:16},{wch:12},{wch:12},
        {wch:16},{wch:16},{wch:14},{wch:14},{wch:10},
        {wch:10},{wch:12},{wch:12},{wch:15},{wch:15},{wch:12},
        {wch:16},{wch:14},{wch:16},
      ];
      applyHyperlinks(ws, {
        "eBay Sold Search": "eBay Sold ↗",
        "eBay Listing":     "Listing ↗",
        "Amazon Search":    "Amazon ↗",
      });
      XLSX.utils.book_append_sheet(wb, ws, "eBay Scout");

    } else {
      const data = rows.map((r, i) => ({
        "#":                i + 1,
        "eBay Title":       r.ebay_title    || "",
        "Amazon Title":     r.amazon_title  || "",
        "Match Score %":    r.match_score   || 0,
        "Amazon Cost $":    r.amazon_cost   != null ? +r.amazon_cost.toFixed(2)  : "",
        "eBay Sell Price $":r.ebay_sell_price != null ? +r.ebay_sell_price.toFixed(2) : "",
        "eBay Fees $":      r.fees          != null ? +r.fees.toFixed(2)         : "",
        "Net Profit $":     r.net_profit    != null ? +r.net_profit.toFixed(2)   : "",
        "ROI %":            r.roi_pct       || 0,
        "Amazon ASIN":      r.amazon_asin   || "",
        "Amazon URL":       r.amazon_url    || "",
        "eBay Sold Search": r.ebay_search_url || "",
        "Amazon Rating":    r.amazon_rating || "",
      }));
      const ws = XLSX.utils.json_to_sheet(data);
      ws["!cols"] = [
        {wch:4},{wch:55},{wch:55},{wch:13},
        {wch:14},{wch:16},{wch:12},{wch:13},{wch:8},
        {wch:14},{wch:16},{wch:16},{wch:13},
      ];
      applyHyperlinks(ws, {
        "Amazon URL":       "Amazon ↗",
        "eBay Sold Search": "eBay Sold ↗",
      });
      XLSX.utils.book_append_sheet(wb, ws, "Full Profit Scan");
    }

    XLSX.writeFile(wb, `dropship-${mode}-scan-${date}.xlsx`);
    showToast(`✓ Downloaded ${rows.length} results as Excel file`);
  };

  // ── Sort results ─────────────────────────────────────────────
  const sortedResults = [...results].sort((a, b) => {
    if (sortBy === "opp_score")  return (b.opp_score  || 0) - (a.opp_score  || 0);
    if (sortBy === "demand")     return (b.total_sold  || 0) - (a.total_sold  || 0);
    if (sortBy === "price")      return (b.ebay_sell_price || 0) - (a.ebay_sell_price || 0);
    if (sortBy === "profit_est") return (b.est_profit_high || b.net_profit || 0) - (a.est_profit_high || a.net_profit || 0);
    if (sortBy === "roi")        return (b.roi_pct    || 0) - (a.roi_pct    || 0);
    if (sortBy === "match")      return (b.match_score || 0) - (a.match_score || 0);
    if (sortBy === "comp_low")   return (a.active_listings || 9999) - (b.active_listings || 9999);
    return 0;
  });

  return (
    <div>
      <PageHeader
        title="Auto Scan"
        sub={isRunning
          ? `Scanning ${scanState.progress}/${scanState.total} keyword sets · ${scanState.totalFound} found so far`
          : results.length
          ? `${results.length} results · ${scanState.mode === "scout" ? "eBay Scout" : "Full Profit Scan"} complete`
          : "Find profitable dropship products automatically"
        }
      >
        {isRunning  && <button className="btn btn-danger btn-sm"  onClick={cancelScan}>⏹ Stop</button>}
        {!isRunning && results.length > 0 && <button className="btn btn-ghost btn-sm" onClick={clearResults}>✕ Clear</button>}
      </PageHeader>

      {/* ── Config panel ── */}
      {!isRunning && (
        <div className="card" style={{ padding: "20px 22px", marginBottom: 18 }}>

          {/* Mode tabs */}
          <div style={{ display: "flex", gap: 8, marginBottom: 18 }}>
            {[
              { id: "scout", icon: "⚡", label: "eBay Scout",
                sub: "Fast · eBay market data only · Check Amazon per row" },
              { id: "full",  icon: "🔍", label: "Full Profit Scan",
                sub: "eBay + Amazon · Needs Rainforest API for best results" },
            ].map(m => (
              <button key={m.id} onClick={() => setMode(m.id)} style={{
                flex: 1, padding: "12px 16px", borderRadius: 10, cursor: "pointer",
                border: `2px solid ${mode === m.id ? "#1a54cc" : "#e2e8f0"}`,
                background: mode === m.id ? "#eff6ff" : "#f8fafc", textAlign: "left",
              }}>
                <div style={{ fontSize: 14, fontWeight: 700,
                  color: mode === m.id ? "#1d4ed8" : "#334155", marginBottom: 2 }}>
                  {m.icon} {m.label}
                </div>
                <div style={{ fontSize: 11, color: mode === m.id ? "#3b82f6" : "#94a3b8" }}>{m.sub}</div>
              </button>
            ))}
          </div>

          {/* Category grid */}
          <div style={{ marginBottom: 14 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: "#475569" }}>
                Categories ({selectedCats.length}/{CATS.length})
              </span>
              <div style={{ display: "flex", gap: 6 }}>
                <button className="btn btn-ghost btn-sm" onClick={selectAll}>All</button>
                <button className="btn btn-ghost btn-sm" onClick={clearCats}>None</button>
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 6 }}>
              {CATS.map(cat => {
                const sel = selectedCats.includes(cat.id);
                return (
                  <button key={cat.id} onClick={() => toggleCat(cat.id)} style={{
                    padding: "10px 6px", borderRadius: 8, cursor: "pointer", textAlign: "center",
                    border: `1.5px solid ${sel ? "#93c5fd" : "#e2e8f0"}`,
                    background: sel ? "#eff6ff" : "#f8fafc", transition: "all .12s",
                  }}>
                    <div style={{ fontSize: 18, marginBottom: 3 }}>{cat.icon}</div>
                    <div style={{ fontSize: 9.5, fontWeight: sel ? 600 : 400,
                      color: sel ? "#1d4ed8" : "#64748b", lineHeight: 1.3,
                      overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {cat.label.split(" ")[0]}
                    </div>
                    {sel && <div style={{ fontSize: 8, color: "#3b82f6", marginTop: 2 }}>✓</div>}
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 14,
            padding: "8px 12px", background: "#f8fafc", borderRadius: 7, border: "1px solid #e2e8f0" }}>
            {mode === "scout"
              ? `⚡ Scout scans ${selectedCats.length * 40} keyword sets — runs eBay sold + active searches concurrently. Each result shows real demand, competition and estimated profit range. Use "Check Amazon $" on interesting rows.`
              : `🔍 Full Scan checks eBay listings against Amazon. Works best with Rainforest API. For now, try 1–2 categories only.`
            }
          </div>

          <button className="btn btn-primary" onClick={startScan} disabled={!selectedCats.length}
            style={{ width: "100%", padding: "11px", fontSize: 14, fontWeight: 700 }}>
            {mode === "scout"
              ? `⚡ Start eBay Scout — ${selectedCats.length} categories · ${selectedCats.length * 40} keyword sets`
              : `🔍 Start Full Profit Scan — ${selectedCats.length} categories`}
          </button>
        </div>
      )}

      {/* ── Progress bar ── */}
      {isRunning && (
        <div className="card" style={{ padding: "16px 20px", marginBottom: 18 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#1a54cc",
                animation: "pulse-dot 1.4s infinite", display: "inline-block" }}/>
              <span style={{ fontSize: 13, fontWeight: 600, color: "#334155" }}>
                {scanState.mode === "scout" ? "⚡ eBay Scout running..." : "🔍 Full Profit Scan running..."}
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <span style={{ fontSize: 11, color: "#16a34a", fontWeight: 600 }}>
                {scanState.totalFound} found
              </span>
              <span className="mono" style={{ fontSize: 11, color: "#64748b" }}>
                {scanState.progress}/{scanState.total}
              </span>
              <button className="btn btn-ghost btn-sm" onClick={cancelScan}
                style={{ fontSize: 11 }}>⏹ Stop</button>
            </div>
          </div>
          <div style={{ background: "#e2e8f0", borderRadius: 99, height: 6, overflow: "hidden" }}>
            <div style={{ height: "100%", borderRadius: 99, background: "linear-gradient(90deg,#1a54cc,#3b82f6)",
              width: `${pct}%`, transition: "width .4s ease" }}/>
          </div>
          <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 6 }}>{pct}% complete</div>
        </div>
      )}

      {/* ── Results toolbar ── */}
      {results.length > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#334155" }}>
            {results.length} results
            {isRunning && <span style={{ fontSize: 11, color: "#94a3b8", fontWeight: 400 }}> · live</span>}
          </div>
          <div style={{ flex: 1 }}/>
          {!isRunning && results.length > 0 && (
            <button className="btn btn-ghost btn-sm" onClick={downloadXLSX}
              style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 4 }}>
              ⬇ Download Excel
            </button>
          )}
          <select className="input" style={{ width: 160, fontSize: 12 }}
            value={sortBy} onChange={e => setSortBy(e.target.value)}>
            {scanState.mode === "scout" && <>
              <option value="opp_score">Best Opportunity</option>
              <option value="demand">Most Demand</option>
              <option value="comp_low">Least Competition</option>
              <option value="profit_est">Est. Profit (high)</option>
              <option value="price">Highest Price</option>
            </>}
            {scanState.mode === "full" && <>
              <option value="roi">Highest ROI</option>
              <option value="profit_est">Most Profit</option>
              <option value="match">Best Match</option>
              <option value="price">Highest Price</option>
            </>}
          </select>
        </div>
      )}

      {/* ── SCOUT CARDS ── */}
      {results.length > 0 && scanState.mode === "scout" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {sortedResults.map((row, i) => {
            const key  = row.ebay_title;
            const chk  = checkingAmz[key];
            const isExp = expandedRow === key;
            const db   = demandBadge(row.demand);
            const cb   = compBadge(row.competition);

            return (
              <div key={i} style={{ background: "#fff", borderRadius: 10,
                border: "1px solid #e2e8f0", overflow: "hidden" }}>

                {/* Main row */}
                <div style={{ padding: "14px 18px", display: "flex", gap: 14, alignItems: "flex-start" }}>

                  {/* Image */}
                  {row.image
                    ? <img src={row.image} alt="" style={{ width: 64, height: 64, objectFit: "cover",
                        borderRadius: 8, border: "1px solid #e2e8f0", flexShrink: 0 }}/>
                    : <div style={{ width: 64, height: 64, borderRadius: 8, background: "#f1f5f9",
                        flexShrink: 0, display: "flex", alignItems: "center",
                        justifyContent: "center", fontSize: 24 }}>📦</div>
                  }

                  {/* Content */}
                  <div style={{ flex: 1, minWidth: 0 }}>

                    {/* Title + links */}
                    <div style={{ display: "flex", alignItems: "flex-start",
                      gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: "#1e293b",
                        flex: 1, minWidth: 200, lineHeight: 1.35 }}>
                        {row.ebay_title}
                      </span>
                      <div style={{ display: "flex", gap: 5, flexShrink: 0 }}>
                        <a href={row.ebay_search_url} target="_blank" rel="noreferrer"
                          style={linkStyle("#fff7ed","#c2410c","#fed7aa")}>eBay Sold ↗</a>
                        <a href={row.amazon_search_url} target="_blank" rel="noreferrer"
                          style={linkStyle("#fffbeb","#92400e","#fde68a")}>Amazon ↗</a>
                        {row.ebay_item_url && (
                          <a href={row.ebay_item_url} target="_blank" rel="noreferrer"
                            style={linkStyle("#f0fdf4","#166534","#86efac")}>Listing ↗</a>
                        )}
                      </div>
                    </div>

                    {/* Metrics row */}
                    <div style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "center" }}>

                      {/* Prices */}
                      <MetricBlock label="eBay Avg Sold" val={`$${row.ebay_avg_sold?.toFixed(2)}`} color="#16a34a" />
                      <MetricBlock label="Your Sell Price" val={`$${row.ebay_sell_price?.toFixed(2)}`} color="#1a54cc" />
                      <MetricBlock label="Price Range"
                        val={`$${row.price_min?.toFixed(0)}–$${row.price_max?.toFixed(0)}`}
                        color="#475569" />

                      {/* Est. profit */}
                      <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: 9, color: "#94a3b8", marginBottom: 2 }}>EST. PROFIT *</div>
                        <div className="mono" style={{ fontSize: 14, fontWeight: 700, color: "#7c3aed" }}>
                          ${row.est_profit_low?.toFixed(0)}–${row.est_profit_high?.toFixed(0)}
                        </div>
                        <div style={{ fontSize: 8, color: "#a78bfa" }}>
                          {row.est_roi_low}–{row.est_roi_high}% ROI
                        </div>
                      </div>

                      <div style={{ width: 1, height: 36, background: "#e2e8f0", flexShrink: 0 }}/>

                      {/* Market intel */}
                      <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: 9, color: "#94a3b8", marginBottom: 3 }}>DEMAND</div>
                        <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px",
                          borderRadius: 5, background: db.bg, color: db.color,
                          border: `1px solid ${db.border}` }}>
                          {db.label}
                        </span>
                        <div style={{ fontSize: 8, color: "#94a3b8", marginTop: 2 }}>
                          {(row.total_sold || 0).toLocaleString()} sold
                        </div>
                      </div>

                      <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: 9, color: "#94a3b8", marginBottom: 3 }}>COMPETITION</div>
                        <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px",
                          borderRadius: 5, background: cb.bg, color: cb.color,
                          border: `1px solid ${cb.border}` }}>
                          {cb.label}
                        </span>
                        <div style={{ fontSize: 8, color: "#94a3b8", marginTop: 2 }}>
                          {(row.active_listings || 0).toLocaleString()} active
                        </div>
                      </div>

                      <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: 9, color: "#94a3b8", marginBottom: 2 }}>SELLERS</div>
                        <div className="mono" style={{ fontSize: 13, fontWeight: 700, color: "#334155" }}>
                          {row.unique_sellers || 0}
                        </div>
                        <div style={{ fontSize: 8, color: "#94a3b8" }}>in 50 sold</div>
                      </div>

                      <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: 9, color: "#94a3b8", marginBottom: 2 }}>% NEW</div>
                        <div className="mono" style={{ fontSize: 13, fontWeight: 700,
                          color: (row.new_pct||0) >= 70 ? "#16a34a" : "#d97706" }}>
                          {row.new_pct || 0}%
                        </div>
                      </div>

                      {/* Opportunity score */}
                      <div style={{ textAlign: "center", marginLeft: "auto" }}>
                        <div style={{ fontSize: 9, color: "#94a3b8", marginBottom: 2 }}>OPP SCORE</div>
                        <div style={{ width: 38, height: 38, borderRadius: "50%",
                          background: `conic-gradient(${oppColor(row.opp_score||0)} ${(row.opp_score||0)*3.6}deg, #e2e8f0 0)`,
                          display: "flex", alignItems: "center", justifyContent: "center" }}>
                          <div style={{ width: 28, height: 28, borderRadius: "50%",
                            background: "#fff", display: "flex", alignItems: "center",
                            justifyContent: "center", fontSize: 10, fontWeight: 700,
                            color: oppColor(row.opp_score||0) }}>
                            {row.opp_score || 0}
                          </div>
                        </div>
                      </div>

                      {/* Check Amazon button */}
                      <div style={{ flexShrink: 0 }}>
                        {chk?.result ? (
                          <button onClick={() => setExpandedRow(isExp ? null : key)}
                            className="btn btn-ghost btn-sm"
                            style={{ fontSize: 11, color: chk.result.found
                              ? (chk.result.profitable ? "#16a34a" : "#d97706") : "#dc2626" }}>
                            {chk.result.found
                              ? (chk.result.profitable
                                  ? `✓ +$${chk.result.net_profit?.toFixed(2)} profit`
                                  : "⚠ Not profitable")
                              : "✗ No match"
                            } {isExp ? "▲" : "▼"}
                          </button>
                        ) : (
                          <button className="btn btn-primary btn-sm"
                            onClick={() => checkAmazon(row)}
                            disabled={chk?.loading}
                            style={{ whiteSpace: "nowrap", fontSize: 11 }}>
                            {chk?.loading
                              ? <><span className="spin">⟳</span> Checking...</>
                              : "🛒 Check Amazon $"}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Expanded Amazon result */}
                {isExp && chk?.result?.found && (
                  <div style={{ borderTop: "1px solid #e2e8f0", background: "#f8fafc",
                    padding: "14px 18px 14px 96px" }}>
                    <AmazonResultInline result={chk.result} row={row}
                      importing={importing} onImport={importOpp} />
                  </div>
                )}
                {isExp && chk?.result && !chk.result.found && (
                  <div style={{ borderTop: "1px solid #fee2e2", background: "#fef2f2",
                    padding: "10px 18px 10px 96px", fontSize: 12, color: "#dc2626" }}>
                    No matching Amazon product found. Try searching manually: {" "}
                    <a href={row.amazon_search_url} target="_blank" rel="noreferrer"
                      style={{ color: "#1d4ed8" }}>Open Amazon Search ↗</a>
                  </div>
                )}
                {isExp && chk?.error && (
                  <div style={{ borderTop: "1px solid #fee2e2", background: "#fef2f2",
                    padding: "10px 18px 10px 96px", fontSize: 12, color: "#dc2626" }}>
                    Error: {chk.error}
                  </div>
                )}
              </div>
            );
          })}

          {/* Footnote */}
          <div style={{ fontSize: 10, color: "#94a3b8", textAlign: "center", padding: "4px 0 12px" }}>
            * Est. Profit is a rough range assuming Amazon costs 55–72% of your eBay sell price.
            Use "Check Amazon $" for the real number.
          </div>
        </div>
      )}

      {/* ── FULL SCAN CARDS ── */}
      {results.length > 0 && scanState.mode === "full" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {sortedResults.map((opp, i) => (
            <FullScanCard key={i} opp={opp} importing={importing} onImport={importOpp} />
          ))}
        </div>
      )}

      {/* ── Empty state ── */}
      {!isRunning && results.length === 0 && (
        <div className="card" style={{ padding: "60px 40px", textAlign: "center" }}>
          <div style={{ fontSize: 40, marginBottom: 14 }}>{mode === "scout" ? "⚡" : "🔍"}</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: "#334155", marginBottom: 8 }}>
            {mode === "scout" ? "eBay Scout" : "Full Profit Scan"} ready
          </div>
          <div style={{ fontSize: 13, color: "#94a3b8", maxWidth: 420, margin: "0 auto" }}>
            {mode === "scout"
              ? "Scout scans eBay sold + active listings simultaneously. Each result shows real demand data, competition level, seller count and an estimated profit range — all from eBay's API, no Amazon needed."
              : "Full Scan cross-references eBay listings with Amazon pricing. Works best with Rainforest API. Try 1–2 categories only with the current scraper."}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Inline Amazon result (Scout expand) ──────────────────────

function AmazonResultInline({ result, row, importing, onImport }) {
  const mb  = matchBadge(result.match_score || 0);
  const key = result.amazon_asin || row.ebay_title;
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}>
      {result.image_urls?.[0] && (
        <img src={result.image_urls[0]} alt="" style={{ width: 52, height: 52,
          objectFit: "cover", borderRadius: 7, border: "1px solid #e2e8f0", flexShrink: 0 }}/>
      )}
      <div style={{ flex: 1, minWidth: 200 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: "#1e293b", marginBottom: 5,
          maxWidth: 420, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {result.amazon_title}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: 10, background: mb.bg, color: mb.color,
            border: `1px solid ${mb.border}`, borderRadius: 5, padding: "2px 7px", fontWeight: 700 }}>
            {mb.icon} {mb.label} {result.match_score}%
          </span>
          {result.amazon_rating > 0 &&
            <span style={{ fontSize: 10, color: "#d97706" }}>★ {result.amazon_rating}</span>}
          <a href={result.amazon_url} target="_blank" rel="noreferrer"
            style={{ fontSize: 10, color: "#1d4ed8", textDecoration: "none" }}>View on Amazon ↗</a>
        </div>
      </div>
      <div style={{ display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
        <MetricBlock label="Amazon Cost" val={`$${result.amazon_cost?.toFixed(2)}`} color="#dc2626" />
        <MetricBlock label="Fees (16%)"  val={`$${result.fees?.toFixed(2)}`}        color="#64748b" />
        <MetricBlock label="Net Profit"  val={`+$${result.net_profit?.toFixed(2)}`} color="#16a34a" large />
        <MetricBlock label="ROI"
          val={`${result.roi_pct}%`}
          color={result.roi_pct >= 30 ? "#16a34a" : result.roi_pct >= 15 ? "#d97706" : "#dc2626"}
          large />
        {result.profitable && result.amazon_asin && (
          <button className="btn btn-primary btn-sm" disabled={importing[key]}
            onClick={() => onImport({ ...result, ebay_avg_sold: row.ebay_avg_sold })}>
            {importing[key] ? <span className="spin">⟳</span> : "＋ Import"}
          </button>
        )}
      </div>
    </div>
  );
}

// ── Full scan opportunity card ────────────────────────────────

function FullScanCard({ opp, importing, onImport }) {
  const mb  = matchBadge(opp.match_score || 0);
  const key = opp.amazon_asin || opp.ebay_title;
  return (
    <div style={{ background: "#fff", borderRadius: 10,
      border: "1px solid #e2e8f0", borderLeft: `4px solid ${mb.bar}`,
      padding: "14px 18px", display: "flex", gap: 14, alignItems: "flex-start" }}>
      {opp.image_urls?.[0] && (
        <img src={opp.image_urls[0]} alt="" style={{ width: 64, height: 64,
          objectFit: "cover", borderRadius: 8, border: "1px solid #e2e8f0", flexShrink: 0 }}/>
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", gap: 6, marginBottom: 5, flexWrap: "wrap", alignItems: "center" }}>
          <span style={linkStyle("#fff7ed","#c2410c","#fed7aa")}>eBay</span>
          <span style={{ fontSize: 12, color: "#334155", fontWeight: 500,
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 380 }}>
            {opp.ebay_title}
          </span>
        </div>
        <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap", alignItems: "center" }}>
          <span style={linkStyle("#fffbeb","#92400e","#fde68a")}>Amazon</span>
          <span style={{ fontSize: 12, color: "#334155",
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 380 }}>
            {opp.amazon_title}
          </span>
          <span style={{ fontSize: 10, background: mb.bg, color: mb.color,
            border: `1px solid ${mb.border}`, borderRadius: 5,
            padding: "2px 8px", fontWeight: 700, flexShrink: 0 }}>
            {mb.icon} {mb.label} {opp.match_score}%
          </span>
          {opp.amazon_rating > 0 &&
            <span style={{ fontSize: 10, color: "#d97706", flexShrink: 0 }}>★ {opp.amazon_rating}</span>}
        </div>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
          <MetricBlock label="Amazon Cost" val={`$${opp.amazon_cost?.toFixed(2)}`}      color="#dc2626" />
          <MetricBlock label="eBay Sell"   val={`$${opp.ebay_sell_price?.toFixed(2)}`}  color="#1a54cc" />
          <MetricBlock label="Fees (16%)"  val={`$${opp.fees?.toFixed(2)}`}             color="#64748b" />
          <MetricBlock label="Net Profit"  val={`+$${opp.net_profit?.toFixed(2)}`}      color="#16a34a" large />
          <MetricBlock label="ROI"
            val={`${opp.roi_pct}%`}
            color={opp.roi_pct >= 30 ? "#16a34a" : opp.roi_pct >= 15 ? "#d97706" : "#dc2626"}
            large />
          <div style={{ display: "flex", gap: 5, marginLeft: "auto" }}>
            <a href={opp.amazon_url} target="_blank" rel="noreferrer"
              style={linkStyle("#fffbeb","#92400e","#fde68a")}>Amazon ↗</a>
            <a href={opp.ebay_search_url} target="_blank" rel="noreferrer"
              style={linkStyle("#fff7ed","#c2410c","#fed7aa")}>eBay Sold ↗</a>
            {opp.amazon_asin && (
              <button className="btn btn-primary btn-sm" disabled={importing[key]}
                onClick={() => onImport(opp)} style={{ fontSize: 10, padding: "4px 10px" }}>
                {importing[key] ? <span className="spin">⟳</span> : "＋ Import"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Shared metric block ───────────────────────────────────────

function MetricBlock({ label, val, color, large }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: 9, color: "#94a3b8", marginBottom: 1 }}>{label}</div>
      <div className="mono" style={{ fontSize: large ? 15 : 13, fontWeight: 700, color }}>{val}</div>
    </div>
  );
}

// ── Link pill style helper ────────────────────────────────────

function linkStyle(bg, color, border) {
  return {
    fontSize: 10, background: bg, color, border: `1px solid ${border}`,
    borderRadius: 5, padding: "3px 8px", textDecoration: "none", fontWeight: 600,
    display: "inline-block", whiteSpace: "nowrap", flexShrink: 0,
  };
}
