import { useState } from "react";
import { PageHeader, Spinner } from "../components/shared";
import { api } from "../services/api";

export default function Research({ showToast }) {
  const [tab,      setTab]      = useState("sold");
  const [keywords, setKeywords] = useState("");
  const [supplier, setSupplier] = useState("amazon");
  const [loading,  setLoading]  = useState(false);
  const [soldRes,  setSoldRes]  = useState(null);
  const [actRes,   setActRes]   = useState(null);
  const [srcRes,   setSrcRes]   = useState(null);
  const [importing,setImporting]= useState(null);

  const go = async () => {
    if (!keywords.trim()) return;
    setLoading(true);
    setSoldRes(null); setActRes(null); setSrcRes(null);
    try {
      if (tab === "sold")   setSoldRes(await api.researchSold(keywords));
      if (tab === "active") setActRes(await api.researchActive(keywords));
      if (tab === "source") setSrcRes(await api.searchProducts({ keywords, supplier }));
    } catch (e) { showToast(e.message, "error"); }
    setLoading(false);
  };

  const importItem = async (item) => {
    setImporting(item.source_id);
    try {
      await api.importProduct({ source_id: item.source_id, supplier });
      showToast(`✓ Imported: ${item.title?.slice(0, 40)}`);
    } catch (e) { showToast(e.message, "error"); }
    setImporting(null);
  };

  const TABS = [
    { id: "sold",   label: "eBay Sold Prices",    badge: "API" },
    { id: "active", label: "eBay Active Listings", badge: "API" },
    { id: "source", label: "Find Products",        badge: "Scraper" },
  ];

  return (
    <div>
      <PageHeader title="Research" sub="Powered by eBay Browse API — reliable real market data"/>

      {/* Tab selector */}
      <div style={{ display: "flex", gap: 8, marginBottom: 18 }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} className="btn btn-ghost"
            style={{ background: tab===t.id ? "#dbeafe" : "#f1f5f9",
              color:      tab===t.id ? "#1d4ed8" : "#475569",
              border:     `1px solid ${tab===t.id ? "#93c5fd" : "#e2e8f0"}` }}>
            {t.label}
            <span style={{ fontSize: 9, background: tab===t.id?"#1d4ed8":"#e2e8f0",
              color: tab===t.id?"#fff":"#64748b", padding:"1px 5px", borderRadius:4, marginLeft:2 }}>
              {t.badge}
            </span>
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="card" style={{ padding: "18px 22px", marginBottom: 18 }}>
        <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
          <div style={{ flex: 1 }}>
            <label style={{ fontSize: 11, color: "#64748b", display: "block", marginBottom: 5, fontWeight: 600 }}>
              Keywords
            </label>
            <input className="input" value={keywords} onChange={e => setKeywords(e.target.value)}
              placeholder={tab==="sold" ? "e.g. USB-C hub 7-in-1" : tab==="active" ? "bluetooth earbuds" : "laptop stand"}
              onKeyDown={e => e.key === "Enter" && go()}/>
          </div>
          {tab === "source" && (
            <div>
              <label style={{ fontSize: 11, color: "#64748b", display: "block", marginBottom: 5, fontWeight: 600 }}>
                Supplier
              </label>
              <select className="input" style={{ width: 130 }} value={supplier}
                onChange={e => setSupplier(e.target.value)}>
                <option value="amazon">Amazon</option>
                <option value="walmart">Walmart</option>
              </select>
            </div>
          )}
          <button className="btn btn-primary" onClick={go} disabled={loading || !keywords.trim()}>
            {loading ? <><span className="spin">⟳</span> Searching...</> : "Search"}
          </button>
        </div>
        <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 8 }}>
          {tab==="sold"   && "🔵 Uses eBay Browse API — returns real completed listings with accurate sold prices"}
          {tab==="active" && "🔵 Uses eBay Browse API — live BIN listings sorted by lowest price"}
          {tab==="source" && "🟡 Web scraper — finds products on Amazon/Walmart to import"}
        </div>
      </div>

      {loading && (
        <div style={{ textAlign: "center", padding: 48, color: "#64748b" }}>
          <Spinner/> <span style={{ marginLeft: 8 }}>Querying eBay API...</span>
        </div>
      )}

      {/* Sold results */}
      {tab==="sold" && soldRes && !loading && (
        <div>
          <div style={{ display: "flex", gap: 12, marginBottom: 14 }}>
            <div className="card" style={{ padding: "14px 20px", display: "flex", gap: 24 }}>
              <div>
                <div style={{ fontSize: 10, color: "#94a3b8", marginBottom: 4 }}>AVG SOLD PRICE</div>
                <div className="mono" style={{ fontSize: 24, fontWeight: 700, color: "#16a34a" }}>
                  ${soldRes.avg_price?.toFixed(2) || "—"}
                </div>
              </div>
              <div style={{ borderLeft: "1px solid #e2e8f0", paddingLeft: 24 }}>
                <div style={{ fontSize: 10, color: "#94a3b8", marginBottom: 4 }}>RESULTS</div>
                <div className="mono" style={{ fontSize: 24, fontWeight: 700, color: "#1a54cc" }}>
                  {soldRes.items?.length || 0}
                </div>
              </div>
              <div style={{ borderLeft: "1px solid #e2e8f0", paddingLeft: 24 }}>
                <div style={{ fontSize: 10, color: "#94a3b8", marginBottom: 4 }}>TOTAL FOUND</div>
                <div className="mono" style={{ fontSize: 24, fontWeight: 700, color: "#7c3aed" }}>
                  {(soldRes.total || 0).toLocaleString()}
                </div>
              </div>
            </div>
          </div>
          <div className="card" style={{ overflow: "hidden" }}>
            <table>
              <thead><tr>
                <th>Title</th><th>Sold Price</th><th>Condition</th><th>Seller</th>
              </tr></thead>
              <tbody>
                {(soldRes.items || []).map((item, i) => (
                  <tr key={i} className="tr-h">
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        {item.image && (
                          <img src={item.image} style={{ width: 32, height: 32, objectFit: "cover",
                            borderRadius: 6, border: "1px solid #e2e8f0", flexShrink: 0 }}/>
                        )}
                        <a href={item.item_url} target="_blank" rel="noreferrer"
                          style={{ fontSize: 12, color: "#334155", textDecoration: "none",
                            maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {item.title}
                        </a>
                      </div>
                    </td>
                    <td>
                      <span className="mono" style={{ color: "#16a34a", fontWeight: 700 }}>
                        ${item.price?.toFixed(2)}
                      </span>
                    </td>
                    <td style={{ fontSize: 11 }}>{item.condition}</td>
                    <td style={{ fontSize: 11, color: "#94a3b8" }}>{item.seller}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Active results */}
      {tab==="active" && actRes && !loading && (
        <div className="card" style={{ overflow: "hidden" }}>
          <table>
            <thead><tr>
              <th>Title</th><th>Price</th><th>Shipping</th><th>Watchers</th><th>Seller</th>
            </tr></thead>
            <tbody>
              {(actRes.items || []).map((item, i) => (
                <tr key={i} className="tr-h">
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      {item.image && (
                        <img src={item.image} style={{ width: 32, height: 32, objectFit: "cover",
                          borderRadius: 6, border: "1px solid #e2e8f0", flexShrink: 0 }}/>
                      )}
                      <a href={item.item_url} target="_blank" rel="noreferrer"
                        style={{ fontSize: 12, color: "#334155", textDecoration: "none",
                          maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {item.title}
                      </a>
                    </div>
                  </td>
                  <td><span className="mono" style={{ color: "#d97706", fontWeight: 700 }}>${item.price?.toFixed(2)}</span></td>
                  <td style={{ fontSize: 11 }}>{item.shipping === "0.00" ? "Free" : `$${item.shipping}`}</td>
                  <td style={{ fontSize: 11 }}>{item.watchers || 0}</td>
                  <td style={{ fontSize: 11, color: "#94a3b8" }}>{item.seller}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Source search results */}
      {tab==="source" && srcRes && !loading && (
        <div>
          <div style={{ marginBottom: 10, fontSize: 13, color: "#475569" }}>
            {srcRes.count} products found on {supplier}
          </div>
          <div className="card" style={{ overflow: "hidden" }}>
            <table>
              <thead><tr>
                <th>Product</th><th>ID</th><th>Price</th><th>Rating</th><th></th>
              </tr></thead>
              <tbody>
                {(srcRes.results || []).map((item, i) => (
                  <tr key={i} className="tr-h">
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        {item.image_urls?.[0] && (
                          <img src={item.image_urls[0]} style={{ width: 34, height: 34,
                            objectFit: "cover", borderRadius: 7,
                            border: "1px solid #e2e8f0", flexShrink: 0 }}/>
                        )}
                        <span style={{ fontSize: 12, color: "#334155", maxWidth: 260,
                          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {item.title}
                        </span>
                      </div>
                    </td>
                    <td><span className="mono" style={{ fontSize: 10, color: "#94a3b8" }}>{item.source_id}</span></td>
                    <td><span className="mono" style={{ color: "#dc2626", fontWeight: 700 }}>${item.source_price?.toFixed(2)}</span></td>
                    <td><span style={{ fontSize: 11, color: "#d97706" }}>★ {item.rating}</span></td>
                    <td>
                      <button className="btn btn-ghost btn-sm" disabled={importing === item.source_id}
                        onClick={() => importItem(item)}>
                        {importing === item.source_id ? <span className="spin">⟳</span> : "+ Import"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
