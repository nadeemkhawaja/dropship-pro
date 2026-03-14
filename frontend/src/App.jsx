import { useState, useEffect } from "react";
import { G, Toast } from "./components/shared";
import { api } from "./services/api";

import Login     from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import AutoScan  from "./pages/AutoScan";
import Research  from "./pages/Research";
import Products  from "./pages/Products";
import Listings  from "./pages/Listings";
import Orders    from "./pages/Orders";
import Settings  from "./pages/Settings";

const NAV = [
  { id: "dashboard", label: "Dashboard",  icon: "◈" },
  { id: "autoscan",  label: "Auto Scan",  icon: "⚡" },
  { id: "research",  label: "Research",   icon: "⌕" },
  { id: "products",  label: "Products",   icon: "⬡" },
  { id: "listings",  label: "Listings",   icon: "≡" },
  { id: "orders",    label: "Orders",     icon: "📦" },
  { id: "settings",  label: "Settings",   icon: "⚙" },
];
const PAGES = { dashboard: Dashboard, autoscan: AutoScan, research: Research, products: Products,
                listings: Listings, orders: Orders, settings: Settings };

const SCAN_INIT = {
  scanId:      null,
  active:      false,
  mode:        "scout",
  selectedCats: ["electronics", "home_garden", "pets"],
  results:     [],
  progress:    0,
  total:       0,
  totalFound:  0,
  done:        false,
};

export default function App() {
  const [authed,    setAuthed]    = useState(!!localStorage.getItem("ds_token"));
  const [authUser,  setAuthUser]  = useState(localStorage.getItem("ds_user") || "");
  const [page,      setPage]      = useState("dashboard");
  const [toast,     setToast]     = useState(null);
  const [stats,     setStats]     = useState(null);
  const [ebayOk,    setEbayOk]    = useState(null);
  const [scanState, setScanState] = useState(SCAN_INIT);

  const handleLogin = (username) => {
    setAuthUser(username);
    setAuthed(true);
  };

  const handleLogout = async () => {
    try { await api.logout(); } catch {}
    localStorage.removeItem("ds_token");
    localStorage.removeItem("ds_user");
    setAuthed(false);
    setAuthUser("");
  };

  if (!authed) return <Login onLogin={handleLogin} />;

  const showToast = (msg, type = "success") => {
    setToast({ msg, type, id: Date.now() });
    setTimeout(() => setToast(null), 3500);
  };

  useEffect(() => {
    const load = async () => {
      try {
        const [d, h] = await Promise.all([api.dashboard(), api.health()]);
        setStats(d.stats);
        setEbayOk(h.ebay_api);
      } catch {}
    };
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, []);

  const Page = PAGES[page] || Dashboard;
  const scanning = scanState.active && !scanState.done;

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#f0f4f8" }}>
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet"/>
      <style>{G + `
        @keyframes pulse-dot {
          0%,100% { opacity:1; transform:scale(1); }
          50%      { opacity:.5; transform:scale(1.4); }
        }
        @keyframes scan-shimmer {
          0%   { background-position: -200px 0; }
          100% { background-position: calc(200px + 100%) 0; }
        }
      `}</style>

      {/* ── Sidebar ── */}
      <aside style={{ width: 215, background: "#1c2e42", borderRight: "1px solid #253d54",
        display: "flex", flexDirection: "column", padding: "0 8px", flexShrink: 0 }}>

        {/* Logo */}
        <div style={{ padding: "20px 12px 16px", borderBottom: "1px solid #253d54", marginBottom: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, display: "flex",
              alignItems: "center", justifyContent: "center", fontSize: 18,
              background: "linear-gradient(135deg,#1a54cc,#3b44d4)" }}>◈</div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 800, color: "#e2edf8", letterSpacing: "-.2px" }}>DropShip Pro</div>
              <div className="mono" style={{ fontSize: 10, color: "#7ab0f8", fontWeight: 500 }}>v4.0 · eBay API</div>
            </div>
          </div>
        </div>

        {/* Nav items */}
        <nav style={{ flex: 1, paddingTop: 4 }}>
          {NAV.map(n => (
            <button key={n.id} onClick={() => setPage(n.id)} style={{
              width: "100%", display: "flex", alignItems: "center", gap: 9,
              padding: "9px 12px", borderRadius: 8, border: "none", marginBottom: 2,
              fontSize: 13, fontWeight: page === n.id ? 600 : 400,
              background: page === n.id ? "rgba(96,165,250,.15)" : "transparent",
              color: page === n.id ? "#93c5fd" : "#7a9ab5",
              borderLeft: page === n.id ? "2px solid #60a5fa" : "2px solid transparent",
              cursor: "pointer", transition: "all .12s",
            }}>
              <span style={{ fontSize: 14 }}>{n.icon}</span>
              {n.label}
              {/* Orders pending badge */}
              {n.id === "orders" && (stats?.pending_orders > 0) && (
                <span style={{ marginLeft: "auto", background: "#1a54cc", color: "#fff",
                  borderRadius: "50%", width: 18, height: 18, display: "flex",
                  alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700 }}>
                  {stats.pending_orders}
                </span>
              )}
              {/* Scan active badge */}
              {n.id === "autoscan" && scanning && (
                <span style={{ marginLeft: "auto", display: "flex", alignItems: "center",
                  gap: 3, background: "rgba(96,165,250,.2)", borderRadius: 10,
                  padding: "1px 6px", fontSize: 9, color: "#93c5fd", fontWeight: 700 }}>
                  <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#60a5fa",
                    animation: "pulse-dot 1.4s infinite", display: "inline-block" }}/>
                  Live
                </span>
              )}
            </button>
          ))}
        </nav>

        {/* eBay API status */}
        <div style={{ margin: "8px 6px 14px", background: "#162840",
          border: "1px solid #23384f", borderRadius: 9, padding: "10px 12px" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#4a6a85",
            textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 6 }}>
            API Status
          </div>
          {[
            { label: "eBay API", ok: ebayOk },
            { label: "Amazon",   ok: true },
          ].map(s => (
            <div key={s.label} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%",
                background: s.ok === null ? "#4a6a85" : s.ok ? "#4ade80" : "#f87171" }}/>
              <span style={{ fontSize: 11, color: "#7a9ab5" }}>{s.label}</span>
              <span style={{ fontSize: 10, color: s.ok === null ? "#4a6a85" : s.ok ? "#4ade80" : "#f87171",
                marginLeft: "auto" }}>
                {s.ok === null ? "..." : s.ok ? "Live" : "Check Settings"}
              </span>
            </div>
          ))}
        </div>
      </aside>

      {/* ── Main ── */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>

        {/* Topbar */}
        <div style={{ height: 54, background: "#ffffff", borderBottom: "1px solid #e2e8f0",
          display: "flex", alignItems: "center", padding: "0 26px", gap: 16, flexShrink: 0,
          boxShadow: "0 1px 3px rgba(0,0,0,.05)" }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: "#334155" }}>
            {NAV.find(n => n.id === page)?.label}
          </div>
          <div style={{ flex: 1 }}/>

          {/* Scanning indicator in topbar */}
          {scanning && (
            <div onClick={() => setPage("autoscan")}
              style={{ display: "flex", alignItems: "center", gap: 7, cursor: "pointer",
                background: "#eff6ff", border: "1px solid #bfdbfe",
                borderRadius: 20, padding: "5px 13px" }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#1a54cc",
                animation: "pulse-dot 1.4s infinite", display: "inline-block" }}/>
              <span style={{ fontSize: 11, color: "#1d4ed8", fontWeight: 600 }}>
                {scanState.mode === "scout" ? "⚡ Scouting" : "🔍 Full Scan"}
                {" "}· {scanState.totalFound} found
              </span>
              <span style={{ fontSize: 10, color: "#60a5fa" }}>
                {scanState.progress}/{scanState.total}
              </span>
            </div>
          )}

          {stats && (
            <div style={{ display: "flex", gap: 20 }}>
              {[
                { l: "Revenue", v: `$${(stats.total_revenue||0).toFixed(0)}`, c: "#16a34a" },
                { l: "Profit",  v: `$${(stats.total_profit||0).toFixed(0)}`,  c: "#1a54cc" },
                { l: "Pending", v: stats.pending_orders || 0,                  c: "#d97706" },
              ].map(s => (
                <div key={s.l} style={{ textAlign: "center" }}>
                  <div className="mono" style={{ fontSize: 13, fontWeight: 700, color: s.c }}>{s.v}</div>
                  <div style={{ fontSize: 10, color: "#94a3b8" }}>{s.l}</div>
                </div>
              ))}
            </div>
          )}
          <div className="mono" style={{ fontSize: 11, color: "#94a3b8" }}>
            {new Date().toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
          </div>

          {/* User + logout */}
          <div style={{ display: "flex", alignItems: "center", gap: 10,
            paddingLeft: 14, borderLeft: "1px solid #e2e8f0" }}>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#334155" }}>{authUser}</div>
              <div style={{ fontSize: 10, color: "#94a3b8" }}>logged in</div>
            </div>
            <button onClick={handleLogout} style={{
              padding: "5px 12px", borderRadius: 7, border: "1px solid #e2e8f0",
              background: "#fff", color: "#64748b", fontSize: 12, fontWeight: 600,
              cursor: "pointer", transition: "all .12s",
            }}
              onMouseEnter={e => { e.target.style.background="#fee2e2"; e.target.style.color="#dc2626"; e.target.style.borderColor="#fca5a5"; }}
              onMouseLeave={e => { e.target.style.background="#fff"; e.target.style.color="#64748b"; e.target.style.borderColor="#e2e8f0"; }}
            >
              Sign out
            </button>
          </div>
        </div>

        {/* Page content */}
        <div style={{ flex: 1, padding: "24px 28px", overflowY: "auto" }}>
          <div className="fade-up" key={page}>
            <Page showToast={showToast} scanState={scanState} setScanState={setScanState} />
          </div>
        </div>
      </main>

      <Toast toast={toast}/>
    </div>
  );
}
