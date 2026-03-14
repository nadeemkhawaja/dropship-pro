// ── LISTINGS ─────────────────────────────────────────────────
import { useState } from "react";
import { useApi, PageHeader, Spinner, Empty } from "../components/shared";
import { api } from "../services/api";

export function Listings({ showToast }) {
  const [statusFilter, setStatusFilter] = useState("");
  const { data: listings, loading, refetch } = useApi(
    () => api.getListings({ status: statusFilter }), [statusFilter]
  );

  const toggleStatus = async (l) => {
    const next = l.status === "active" ? "paused" : "active";
    try { await api.updateListing(l.id, { status: next }); refetch(); showToast(`→ ${next}`); }
    catch (e) { showToast(e.message, "error"); }
  };

  const del = async (id) => {
    try { await api.deleteListing(id); refetch(); showToast("Removed"); }
    catch (e) { showToast(e.message, "error"); }
  };

  const STATUSES = ["", "active", "paused", "draft"];

  return (
    <div>
      <PageHeader title="Listings" sub="eBay Inventory API — published via official Sell APIs"/>

      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        {STATUSES.map(s => (
          <button key={s} className="btn btn-ghost btn-sm" onClick={() => setStatusFilter(s)}
            style={{ background: statusFilter===s ? "#dbeafe" : "#f1f5f9",
              color:  statusFilter===s ? "#1d4ed8" : "#475569",
              border: `1px solid ${statusFilter===s ? "#93c5fd" : "#e2e8f0"}` }}>
            {s || "All"}
          </button>
        ))}
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {loading ? (
          <div style={{ padding: 60, textAlign: "center" }}><Spinner/></div>
        ) : (listings || []).length === 0 ? (
          <Empty icon="≡" text="No listings. Go to Products, select items, and click 'List on eBay'."/>
        ) : (
          <table>
            <thead><tr>
              <th>Product</th><th>SKU</th><th>Listing ID</th><th>Sell</th><th>Cost</th><th>Profit</th><th>Status</th><th>Actions</th>
            </tr></thead>
            <tbody>
              {(listings || []).map(l => (
                <tr key={l.id} className="tr-h">
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      {l.image_urls?.[0] && (
                        <img src={l.image_urls[0]} style={{ width: 32, height: 32,
                          objectFit: "cover", borderRadius: 6,
                          border: "1px solid #e2e8f0", flexShrink: 0 }}/>
                      )}
                      <span style={{ fontSize: 12, color: "#334155", maxWidth: 200,
                        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {l.title}
                      </span>
                    </div>
                  </td>
                  <td><span className="mono" style={{ fontSize: 10, color: "#94a3b8" }}>{l.ebay_sku}</span></td>
                  <td>
                    {l.ebay_listing_id
                      ? <a href={`https://www.ebay.com/itm/${l.ebay_listing_id}`}
                          target="_blank" rel="noreferrer"
                          className="mono" style={{ fontSize: 10, color: "#1a54cc", textDecoration: "none" }}>
                          {l.ebay_listing_id} ↗
                        </a>
                      : <span className="mono" style={{ fontSize: 10, color: "#cbd5e1" }}>—</span>
                    }
                  </td>
                  <td><span className="mono" style={{ color: "#16a34a", fontWeight: 700 }}>${l.sell_price}</span></td>
                  <td><span className="mono" style={{ color: "#dc2626" }}>${l.source_price}</span></td>
                  <td><span className="mono" style={{ color: "#7c3aed", fontWeight: 700 }}>+${l.profit?.toFixed(2)}</span></td>
                  <td><span className={`badge s-${l.status}`}>{l.status}</span></td>
                  <td>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button className="btn btn-ghost btn-sm" onClick={() => toggleStatus(l)}>
                        {l.status === "active" ? "⏸" : "▶"}
                      </button>
                      <button className="btn btn-danger btn-sm" onClick={() => del(l.id)}>✕</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card" style={{ padding: "12px 18px", marginTop: 12,
        background: "#fffbeb", border: "1px solid #fde68a" }}>
        <div style={{ fontSize: 12, color: "#92400e" }}>
          💡 <strong>Listing ID</strong> links directly to the live eBay listing.
          Set <strong>Dry Run = OFF</strong> in Settings to publish live.
          Draft listings are queued but not yet published to eBay.
        </div>
      </div>
    </div>
  );
}

// ── ORDERS ────────────────────────────────────────────────────
export function Orders({ showToast }) {
  const [statusFilter, setStatusFilter] = useState("");
  const [syncing,      setSyncing]      = useState(false);
  const { data: orders, loading, refetch } = useApi(
    () => api.getOrders({ status: statusFilter }), [statusFilter]
  );
  const { data: stats } = useApi(api.orderStats);

  const advance = async (o) => {
    const next = { pending:"ordered", ordered:"shipped", shipped:"delivered" }[o.status];
    if (!next) return;
    try { await api.updateOrder(o.id, { status: next }); refetch(); showToast(`→ ${next}`); }
    catch (e) { showToast(e.message, "error"); }
  };

  const syncOrders = async () => {
    setSyncing(true);
    try {
      const r = await api.syncOrders();
      showToast(r.message || `✓ Synced ${r.synced} new orders`);
      refetch();
    } catch (e) { showToast(e.message, "error"); }
    setSyncing(false);
  };

  const s = stats || {};

  return (
    <div>
      <PageHeader title="Orders" sub="eBay Fulfillment API — sync and track all sales">
        <button className="btn btn-ghost" onClick={syncOrders} disabled={syncing}>
          {syncing ? <><span className="spin">⟳</span> Syncing...</> : "🔄 Sync from eBay"}
        </button>
      </PageHeader>

      {/* Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 12, marginBottom: 18 }}>
        {[
          { l: "Revenue",    v: `$${(s.total_revenue||0).toFixed(2)}`, c: "#16a34a" },
          { l: "Net Profit", v: `$${(s.total_profit||0).toFixed(2)}`,  c: "#1a54cc" },
          { l: "Margin",     v: `${s.margin_pct||0}%`,                  c: "#7c3aed" },
          { l: "Pending",    v:  s.pending||0,                           c: "#d97706" },
          { l: "Total",      v:  s.total_orders||0,                      c: "#475569" },
        ].map(k => (
          <div key={k.l} className="card" style={{ padding: "14px 18px" }}>
            <div style={{ fontSize: 10, color: "#94a3b8", marginBottom: 6 }}>{k.l}</div>
            <div className="mono" style={{ fontSize: 18, fontWeight: 700, color: k.c }}>{k.v}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        {["", "pending", "ordered", "shipped", "delivered"].map(s => (
          <button key={s} className="btn btn-ghost btn-sm" onClick={() => setStatusFilter(s)}
            style={{ background: statusFilter===s ? "#dbeafe" : "#f1f5f9",
              color:  statusFilter===s ? "#1d4ed8" : "#475569",
              border: `1px solid ${statusFilter===s ? "#93c5fd" : "#e2e8f0"}` }}>
            {s || "All"}
          </button>
        ))}
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {loading ? (
          <div style={{ padding: 60, textAlign: "center" }}><Spinner/></div>
        ) : (orders || []).length === 0 ? (
          <Empty icon="📦" text="No orders yet. Sync from eBay or they'll appear when sold."/>
        ) : (
          <table>
            <thead><tr>
              <th>Order ID</th><th>Buyer</th><th>Item</th><th>Ship To</th>
              <th>Sold</th><th>Cost</th><th>Profit</th><th>Status</th><th>Action</th>
            </tr></thead>
            <tbody>
              {(orders || []).map(o => (
                <tr key={o.id} className="tr-h">
                  <td><span className="mono" style={{ fontSize: 10, color: "#94a3b8" }}>{o.ebay_order_id}</span></td>
                  <td style={{ fontWeight: 500, color: "#334155" }}>{o.buyer_username}</td>
                  <td style={{ maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 12 }}>
                    {o.item_title}
                  </td>
                  <td style={{ fontSize: 11 }}>{o.ship_city}, {o.ship_state}</td>
                  <td><span className="mono" style={{ color: "#16a34a", fontWeight: 700 }}>${o.sell_price}</span></td>
                  <td><span className="mono" style={{ color: "#dc2626" }}>${o.source_cost}</span></td>
                  <td><span className="mono" style={{ color: "#7c3aed", fontWeight: 700 }}>+${o.net_profit?.toFixed(2)}</span></td>
                  <td><span className={`badge s-${o.status}`}>{o.status}</span></td>
                  <td>
                    {o.status !== "delivered"
                      ? <button className="btn btn-ghost btn-sm" onClick={() => advance(o)}>
                          {o.status==="pending" ? "🛒 Mark Ordered"
                           : o.status==="ordered" ? "Mark Shipped"
                           : "Mark Delivered"}
                        </button>
                      : <span style={{ fontSize: 11, color: "#16a34a" }}>✓ Done</span>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ── SETTINGS ──────────────────────────────────────────────────
export function Settings({ showToast }) {
  const { data: settings } = useApi(api.getSettings);
  const [form,   setForm]  = useState({});
  const [saving, setSaving]= useState(false);
  const [tab,    setTab]   = useState("ebay");

  const get = k => form[k] ?? settings?.[k] ?? "";
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const save = async () => {
    setSaving(true);
    try { await api.saveSettings(form); showToast("✓ Settings saved"); }
    catch (e) { showToast(e.message, "error"); }
    setSaving(false);
  };

  const F = ({ label, k, type = "text", help, mono }) => (
    <div style={{ marginBottom: 14 }}>
      <label style={{ fontSize: 11, color: "#64748b", display: "block", marginBottom: 5, fontWeight: 600 }}>
        {label}
      </label>
      <input className={`input ${mono?"mono":""}`} type={type === "password" ? "password" : "text"}
        value={get(k)} onChange={e => set(k, e.target.value)} placeholder={help || ""}/>
    </div>
  );

  const Toggle = ({ label, desc, k }) => (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "11px 0", borderBottom: "1px solid #f0f4f8" }}>
      <div>
        <div style={{ fontWeight: 500, fontSize: 13, color: "#334155" }}>{label}</div>
        {desc && <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 1 }}>{desc}</div>}
      </div>
      <label className="toggle">
        <input type="checkbox" checked={get(k) === "true"}
          onChange={e => set(k, e.target.checked ? "true" : "false")}/>
        <span className="tslider"/>
      </label>
    </div>
  );

  const TABS = [
    { id: "ebay",    label: "eBay API" },
    { id: "profit",  label: "Profit Rules" },
    { id: "auto",    label: "Automation" },
    { id: "alerts",  label: "Email Alerts" },
  ];

  return (
    <div style={{ maxWidth: 680 }}>
      <PageHeader title="Settings" sub="Configure eBay API keys, profit rules, and automation">
        <button className="btn btn-primary" onClick={save} disabled={saving}>
          {saving ? <><span className="spin">⟳</span> Saving...</> : "Save Settings"}
        </button>
      </PageHeader>

      {/* Tab nav */}
      <div style={{ display: "flex", gap: 6, marginBottom: 18 }}>
        {TABS.map(t => (
          <button key={t.id} className="btn btn-ghost btn-sm" onClick={() => setTab(t.id)}
            style={{ background: tab===t.id ? "#dbeafe" : "#f1f5f9",
              color:  tab===t.id ? "#1d4ed8" : "#475569",
              border: `1px solid ${tab===t.id ? "#93c5fd" : "#e2e8f0"}` }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* eBay API tab */}
      {tab === "ebay" && (
        <div>
          <div className="card" style={{ padding: "18px 24px", marginBottom: 14,
            background: "#eff6ff", border: "1px solid #bfdbfe" }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#1d4ed8", marginBottom: 12 }}>
              🔑 eBay Developer Keys — Already Configured
            </div>
            {[
              "Go to developer.ebay.com → Register (NOT your seller account)",
              "Create a new App → copy App ID (Client ID) + Cert ID (Client Secret)",
              "Go to Application Keys → User Tokens → Generate User Token",
              "Complete OAuth consent, copy the Refresh Token (long-lived)",
              "Paste all 3 values below and Save",
            ].map((s, i) => (
              <div key={i} style={{ display: "flex", gap: 8, marginBottom: 7, alignItems: "flex-start" }}>
                <div style={{ width: 20, height: 20, borderRadius: "50%", background: "#dbeafe",
                  color: "#1d4ed8", fontSize: 10, fontWeight: 700, flexShrink: 0,
                  display: "flex", alignItems: "center", justifyContent: "center" }}>{i+1}</div>
                <span style={{ fontSize: 12, color: "#475569" }}>{s}</span>
              </div>
            ))}
            <a href="https://developer.ebay.com" target="_blank" rel="noreferrer"
              className="btn btn-ghost btn-sm" style={{ marginTop: 8, textDecoration: "none" }}>
              Open eBay Developer Portal ↗
            </a>
          </div>

          <div className="card" style={{ padding: "18px 24px" }}>
            <F label="Client ID (App ID)" k="ebay_client_id" help="e.g. YourApp-12345-abc-PROD-abc123" mono/>
            <F label="Client Secret (Cert ID)" k="ebay_client_secret" type="password" help="Your eBay cert ID" mono/>
            <F label="User Refresh Token" k="ebay_refresh_token" type="password"
              help="Long-lived token from User Tokens page (starts with v^1.1...)" mono/>
          </div>
        </div>
      )}

      {/* Profit Rules tab */}
      {tab === "profit" && (
        <div className="card" style={{ padding: "18px 24px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {[
              { l: "Default Markup %",        k: "default_markup_pct", h: "35" },
              { l: "Min Profit (USD)",         k: "min_profit_usd",     h: "5.00" },
              { l: "eBay Final Value Fee %",   k: "ebay_fee_pct",       h: "13.0" },
              { l: "Payment Processing Fee %", k: "payment_fee_pct",    h: "3.0" },
            ].map(f => (
              <div key={f.k}>
                <label style={{ fontSize: 11, color: "#64748b", display: "block", marginBottom: 5, fontWeight: 600 }}>
                  {f.l}
                </label>
                <input className="input mono" value={get(f.k)} placeholder={f.h}
                  onChange={e => set(f.k, e.target.value)}/>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Automation tab */}
      {tab === "auto" && (
        <div className="card" style={{ padding: "18px 24px" }}>
          <Toggle k="dry_run"      label="Dry Run Mode"  desc="Log all actions without publishing to eBay or making changes"/>
          <Toggle k="auto_reprice" label="Auto-Reprice"  desc="Monitor source prices and update eBay listings when they change"/>
          <Toggle k="auto_pause"   label="Auto-Pause"    desc="Pause listings when item goes OOS on Amazon/Walmart"/>
          <div style={{ marginTop: 16 }}>
            <label style={{ fontSize: 11, color: "#64748b", display: "block", marginBottom: 5, fontWeight: 600 }}>
              Monitor Interval (minutes)
            </label>
            <input className="input mono" style={{ maxWidth: 110 }} value={get("monitor_interval_min")}
              onChange={e => set("monitor_interval_min", e.target.value)} placeholder="120"/>
          </div>
          <div style={{ marginTop: 12, padding: "10px 14px", background: "#fffbeb",
            border: "1px solid #fde68a", borderRadius: 8, fontSize: 11, color: "#92400e" }}>
            ⚠️ Keep Dry Run ON while testing. Turn it OFF only when you have valid eBay tokens
            and are ready to publish live listings.
          </div>
        </div>
      )}

      {/* Email alerts tab */}
      {tab === "alerts" && (
        <div className="card" style={{ padding: "18px 24px" }}>
          <F label="Gmail Address"       k="smtp_user"   help="your@gmail.com"/>
          <F label="Gmail App Password"  k="smtp_pass"   type="password" help="Google Account → Security → App Passwords"/>
          <F label="Alert Email"         k="alert_email" help="Where to send order/price alerts"/>
        </div>
      )}
    </div>
  );
}

export default { Listings, Orders, Settings };
