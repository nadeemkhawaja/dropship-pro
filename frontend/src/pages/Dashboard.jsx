import { useApi, StatCard, PageHeader, Spinner, Empty } from "../components/shared";
import { api } from "../services/api";

const ACT = { api_ok:"🟢", import:"⬡", listing:"📋", order_in:"📦", research:"🔍",
              dry_run:"🔵", sync:"🔄", error:"🔴" };

export default function Dashboard({ showToast }) {
  const { data: dash, loading } = useApi(api.dashboard);
  const { data: top  }          = useApi(api.topProducts);
  const s = dash?.stats || {};

  return (
    <div>
      <PageHeader title="Dashboard" sub="eBay API-powered dropshipping — live data"/>

      {loading ? <Spinner/> : (
        <>
          {/* KPIs */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 20 }}>
            <StatCard label="Total Revenue"   value={s.total_revenue}  pre="$" color="#16a34a"/>
            <StatCard label="Net Profit"      value={s.total_profit}   pre="$" color="#1a54cc"/>
            <StatCard label="Active Listings" value={s.active_listings}        color="#7c3aed"/>
            <StatCard label="Pending Orders"  value={s.pending_orders}         color="#d97706"/>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 14 }}>
            {/* Top products */}
            <div className="card" style={{ padding: "18px 22px" }}>
              <h3 style={{ fontSize: 13, fontWeight: 600, color: "#475569", marginBottom: 14 }}>
                Top Products by Profit
              </h3>
              {(top || []).length === 0
                ? <Empty icon="📊" text="No sales data yet — fulfill some orders to see rankings"/>
                : (top || []).map((p, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between",
                    alignItems: "center", padding: "9px 0", borderBottom: "1px solid #f0f4f8" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span className="mono" style={{ fontSize: 10, color: "#cbd5e1", width: 16 }}>{i+1}</span>
                      <span style={{ fontSize: 12, color: "#475569", maxWidth: 260,
                        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {p.item_title}
                      </span>
                    </div>
                    <div style={{ display: "flex", gap: 14, flexShrink: 0 }}>
                      <span className="mono" style={{ fontSize: 11, color: "#94a3b8" }}>{p.sales}x</span>
                      <span className="mono" style={{ fontSize: 12, color: "#16a34a", fontWeight: 700 }}>
                        +${(p.profit || 0).toFixed(2)}
                      </span>
                    </div>
                  </div>
                ))
              }
            </div>

            {/* Activity feed */}
            <div className="card" style={{ padding: "18px 20px" }}>
              <h3 style={{ fontSize: 13, fontWeight: 600, color: "#475569", marginBottom: 14 }}>
                Live Activity
              </h3>
              {(dash?.activity || []).slice(0, 12).map((a, i) => (
                <div key={i} style={{ display: "flex", gap: 9, padding: "7px 0",
                  borderBottom: "1px solid #f8fafc", alignItems: "flex-start" }}>
                  <span style={{ fontSize: 12, flexShrink: 0 }}>{ACT[a.type] || "•"}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, color: "#475569", fontWeight: 500,
                      overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {a.title}
                    </div>
                    <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 1,
                      overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {a.detail}
                    </div>
                  </div>
                </div>
              ))}
              {(dash?.activity || []).length === 0 && (
                <Empty icon="📋" text="No activity yet"/>
              )}
            </div>
          </div>

          {/* Stats row */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12, marginTop: 14 }}>
            <div className="card" style={{ padding: "14px 18px" }}>
              <div style={{ fontSize: 10, color: "#94a3b8", marginBottom: 5 }}>MARGIN</div>
              <div className="mono" style={{ fontSize: 20, fontWeight: 700, color: "#7c3aed" }}>
                {s.margin_pct || 0}%
              </div>
            </div>
            <div className="card" style={{ padding: "14px 18px" }}>
              <div style={{ fontSize: 10, color: "#94a3b8", marginBottom: 5 }}>TOTAL ORDERS</div>
              <div className="mono" style={{ fontSize: 20, fontWeight: 700, color: "#1a54cc" }}>
                {s.total_orders || 0}
              </div>
            </div>
            <div className="card" style={{ padding: "14px 18px" }}>
              <div style={{ fontSize: 10, color: "#94a3b8", marginBottom: 5 }}>PRODUCTS</div>
              <div className="mono" style={{ fontSize: 20, fontWeight: 700, color: "#d97706" }}>
                {s.total_products || 0}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
