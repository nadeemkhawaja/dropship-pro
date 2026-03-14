export const G = `
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#f0f4f8;color:#334155;font-family:'Inter',system-ui,sans-serif}
  ::-webkit-scrollbar{width:5px}
  ::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:4px}
  button,input,select,textarea{font-family:inherit}
  .mono{font-family:'JetBrains Mono','Fira Code',monospace}

  /* Cards */
  .card{background:#ffffff;border:1px solid #e2e8f0;border-radius:12px}
  .card-sm{background:#f8fafc;border:1px solid #edf2f7;border-radius:9px}

  /* Buttons */
  .btn{border:none;border-radius:8px;font-size:13px;font-weight:600;padding:8px 16px;cursor:pointer;transition:all .15s;display:inline-flex;align-items:center;gap:6px}
  .btn-primary{background:linear-gradient(135deg,#1a54cc,#3b44d4);color:#fff}
  .btn-primary:hover{transform:translateY(-1px);box-shadow:0 6px 20px rgba(26,84,204,.3)}
  .btn-primary:disabled{opacity:.45;transform:none;cursor:wait}
  .btn-ghost{background:#f1f5f9;color:#475569;border:1px solid #e2e8f0}
  .btn-ghost:hover{background:#e8edf5;color:#334155}
  .btn-success{background:#f0fdf4;color:#16a34a;border:1px solid #bbf7d0}
  .btn-success:hover{background:#dcfce7}
  .btn-danger{background:#fff5f5;color:#dc2626;border:1px solid #fecaca}
  .btn-danger:hover{background:#fee2e2}
  .btn-warning{background:#fffbeb;color:#d97706;border:1px solid #fde68a}
  .btn-sm{padding:5px 11px;font-size:12px;border-radius:6px}

  /* Inputs */
  .input{background:#ffffff;border:1px solid #d1d9e6;border-radius:8px;color:#334155;font-size:13px;padding:8px 12px;outline:none;width:100%;transition:border-color .15s}
  .input:focus{border-color:#1a54cc;box-shadow:0 0 0 3px rgba(26,84,204,.08)}
  .input::placeholder{color:#94a3b8}
  select.input{cursor:pointer}

  /* Table */
  table{width:100%;border-collapse:collapse}
  th{padding:10px 14px;text-align:left;font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.08em;border-bottom:1px solid #e8edf5;white-space:nowrap;background:#f8fafc}
  td{padding:12px 14px;border-bottom:1px solid #f0f4f8;font-size:13px;color:#475569}
  tr:last-child td{border-bottom:none}
  .tr-h:hover td{background:#f7f9fc}

  /* Badges */
  .badge{display:inline-flex;align-items:center;padding:2px 9px;border-radius:20px;font-size:11px;font-weight:600}

  /* Toggle */
  .toggle{position:relative;display:inline-block;width:38px;height:20px}
  .toggle input{opacity:0;width:0;height:0}
  .tslider{position:absolute;cursor:pointer;inset:0;background:#cbd5e1;border-radius:20px;transition:.2s}
  .tslider:before{content:"";position:absolute;height:14px;width:14px;left:3px;bottom:3px;background:#fff;border-radius:50%;transition:.2s;box-shadow:0 1px 3px rgba(0,0,0,.2)}
  input:checked+.tslider{background:#1a54cc}
  input:checked+.tslider:before{transform:translateX(18px)}

  /* Animations */
  @keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
  .fade-up{animation:fadeUp .22s ease both}
  @keyframes spin{to{transform:rotate(360deg)}}
  .spin{animation:spin 1s linear infinite;display:inline-block}

  /* Status colors */
  .s-active{background:#dcfce7;color:#16a34a;border:1px solid #86efac}
  .s-paused{background:#fef9c3;color:#a16207;border:1px solid #fde047}
  .s-draft{background:#ede9fe;color:#6d28d9;border:1px solid #c4b5fd}
  .s-ended{background:#fee2e2;color:#b91c1c;border:1px solid #fca5a5}
  .s-pending{background:#fef9c3;color:#a16207;border:1px solid #fde047}
  .s-ordered{background:#dbeafe;color:#1d4ed8;border:1px solid #93c5fd}
  .s-shipped{background:#ede9fe;color:#6d28d9;border:1px solid #c4b5fd}
  .s-delivered{background:#dcfce7;color:#16a34a;border:1px solid #86efac}
`;

// Shared stat card
export function StatCard({ label, value, color = "#1a54cc", pre = "" }) {
  return (
    <div className="card" style={{ padding: "16px 20px" }}>
      <div style={{ fontSize: 10, color: "#94a3b8", textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 8 }}>
        {label}
      </div>
      <div className="mono" style={{ fontSize: 22, fontWeight: 700, color }}>
        {pre}{typeof value === "number" ? value.toLocaleString() : (value ?? "—")}
      </div>
    </div>
  );
}

// Shared page header
export function PageHeader({ title, sub, children }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: "#0f172a", marginBottom: 3 }}>{title}</h1>
        {sub && <p style={{ fontSize: 13, color: "#64748b" }}>{sub}</p>}
      </div>
      {children && <div style={{ display: "flex", gap: 8, alignItems: "center" }}>{children}</div>}
    </div>
  );
}

// Toast
export function Toast({ toast }) {
  if (!toast) return null;
  const c = {
    success: { bg: "#f0fdf4", border: "#86efac", color: "#16a34a" },
    error:   { bg: "#fff5f5", border: "#fca5a5", color: "#dc2626" },
    info:    { bg: "#eff6ff", border: "#93c5fd", color: "#1d4ed8" },
  }[toast.type] || { bg: "#f0fdf4", border: "#86efac", color: "#16a34a" };
  return (
    <div style={{
      position: "fixed", bottom: 24, right: 24, padding: "11px 20px",
      borderRadius: 10, fontSize: 13, fontWeight: 600, zIndex: 9999,
      boxShadow: "0 8px 32px rgba(0,0,0,.12)",
      background: c.bg, color: c.color, border: `1px solid ${c.border}`,
      animation: "fadeUp .2s ease",
    }}>
      {toast.msg}
    </div>
  );
}

// Loading spinner
export function Spinner() {
  return <span className="spin" style={{ fontSize: 16, color: "#1a54cc" }}>⟳</span>;
}

// Empty state
export function Empty({ icon, text }) {
  return (
    <div style={{ padding: "60px 24px", textAlign: "center" }}>
      <div style={{ fontSize: 32, marginBottom: 10 }}>{icon}</div>
      <div style={{ color: "#94a3b8", fontSize: 13 }}>{text}</div>
    </div>
  );
}

// useApi hook — must be used inside React components only
import { useState, useEffect, useCallback } from "react";

export function useApi(fn, deps = []) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { setData(await fn()); }
    catch (e) { setError(e.message); }
    setLoading(false);
  }, deps);
  useEffect(() => { load(); }, [load]);
  return { data, loading, error, refetch: load };
}
