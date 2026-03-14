import { useState } from "react";
import { useApi, PageHeader, Spinner, Empty } from "../components/shared";
import { api } from "../services/api";

export default function Products({ showToast }) {
  const [q,        setQ]        = useState("");
  const [supplier, setSupplier] = useState("");
  const [asin,     setAsin]     = useState("");
  const [sup,      setSup]      = useState("amazon");
  const [markup,   setMarkup]   = useState(35);
  const [publish,  setPublish]  = useState(false);
  const [selected, setSelected] = useState([]);
  const [importing,setImporting]= useState(false);
  const [bulking,  setBulking]  = useState(false);
  const [showImport, setShowImport] = useState(false);

  const { data: products, loading, refetch } = useApi(
    () => api.getProducts({ q, supplier }), [q, supplier]
  );

  const handleImport = async () => {
    if (!asin.trim()) return;
    setImporting(true);
    try {
      const r = await api.importProduct({ source_id: asin.trim(), supplier: sup });
      showToast(`✓ Imported: ${r.title?.slice(0, 40)}`);
      setAsin(""); setShowImport(false); refetch();
    } catch (e) { showToast(e.message, "error"); }
    setImporting(false);
  };

  const bulkList = async () => {
    if (!selected.length) return;
    setBulking(true);
    try {
      const r = await api.bulkList({ product_ids: selected, markup_pct: markup, publish });
      showToast(`✓ ${r.success_count} listings created${publish?" and published":" as drafts"}`);
      if (r.failed?.length) showToast(`${r.failed.length} failed`, "error");
      setSelected([]); refetch();
    } catch (e) { showToast(e.message, "error"); }
    setBulking(false);
  };

  const delProd = async (id) => {
    try { await api.deleteProduct(id); refetch(); showToast("Removed"); }
    catch (e) { showToast(e.message, "error"); }
  };

  const toggle = (id) => setSelected(s =>
    s.includes(id) ? s.filter(x => x !== id) : [...s, id]
  );
  const toggleAll = () => {
    const eligible = (products||[]).filter(p => !p.is_listed).map(p => p.id);
    setSelected(s => s.length === eligible.length ? [] : eligible);
  };

  return (
    <div>
      <PageHeader title="Products" sub={`${products?.length || 0} imported · Select to list on eBay`}>
        {selected.length > 0 && (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <input type="number" value={markup} onChange={e => setMarkup(+e.target.value)}
                className="input" style={{ width: 60 }} min={1} max={200}/>
              <span style={{ fontSize: 12, color: "#64748b" }}>% markup</span>
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#475569", cursor: "pointer" }}>
              <label className="toggle" style={{ flexShrink: 0 }}>
                <input type="checkbox" checked={publish} onChange={e => setPublish(e.target.checked)}/>
                <span className="tslider"/>
              </label>
              Publish live
            </label>
            <button className="btn btn-primary" onClick={bulkList} disabled={bulking}>
              {bulking ? <><span className="spin">⟳</span> Listing...</> : `⚡ List ${selected.length} on eBay`}
            </button>
          </>
        )}
        <button className="btn btn-ghost" onClick={() => setShowImport(v => !v)}>
          {showImport ? "✕ Close" : "+ Import"}
        </button>
      </PageHeader>

      {/* Import panel */}
      {showImport && (
        <div className="card" style={{ padding: "18px 22px", marginBottom: 14 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#334155", marginBottom: 12 }}>
            Import by ASIN / Walmart Item ID
          </div>
          <div style={{ display: "flex", gap: 9 }}>
            <input className="input" style={{ flex: 1 }} value={asin}
              onChange={e => setAsin(e.target.value)}
              placeholder="e.g. B09X4K9CK2 (Amazon ASIN) or 634596001 (Walmart ID)"
              onKeyDown={e => e.key === "Enter" && handleImport()}/>
            <select className="input" style={{ width: 130 }} value={sup}
              onChange={e => setSup(e.target.value)}>
              <option value="amazon">Amazon</option>
              <option value="walmart">Walmart</option>
            </select>
            <button className="btn btn-primary" onClick={handleImport}
              disabled={importing || !asin.trim()}>
              {importing ? <><span className="spin">⟳</span> Scraping...</> : "Scrape & Import"}
            </button>
          </div>
          <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 8 }}>
            💡 Find ASINs in the Research tab. Import also fetches eBay sold avg for accurate pricing.
          </div>
        </div>
      )}

      {/* Filters */}
      <div style={{ display: "flex", gap: 9, marginBottom: 14 }}>
        <input className="input" style={{ maxWidth: 240 }} placeholder="Search products..."
          value={q} onChange={e => setQ(e.target.value)}/>
        <select className="input" style={{ width: 140 }} value={supplier}
          onChange={e => setSupplier(e.target.value)}>
          <option value="">All Suppliers</option>
          <option value="amazon">Amazon</option>
          <option value="walmart">Walmart</option>
        </select>
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {loading ? (
          <div style={{ padding: 60, textAlign: "center" }}><Spinner/></div>
        ) : (products || []).length === 0 ? (
          <Empty icon="⬡" text="No products yet. Use Auto Scan tab or import by ASIN above."/>
        ) : (
          <table>
            <thead>
              <tr>
                <th style={{ width: 36 }}>
                  <div onClick={toggleAll} style={{
                    width: 16, height: 16, borderRadius: 4, cursor: "pointer",
                    border: `1.5px solid #1a54cc`, background: "#ffffff",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 9, color: "#1a54cc",
                  }}>
                    {selected.length > 0 ? "✓" : ""}
                  </div>
                </th>
                <th>Product</th>
                <th>Supplier</th>
                <th>Cost</th>
                <th>Sell Price</th>
                <th>Profit</th>
                <th>ROI</th>
                <th>Rating</th>
                <th>Stock</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(products || []).map(p => {
                const chk = selected.includes(p.id);
                return (
                  <tr key={p.id} className="tr-h"
                    style={{ background: chk ? "rgba(26,84,204,.04)" : "transparent" }}
                    onClick={() => !p.is_listed && toggle(p.id)}>
                    <td>
                      {!p.is_listed && (
                        <div style={{
                          width: 16, height: 16, borderRadius: 4, cursor: "pointer",
                          border: `1.5px solid ${chk ? "#1a54cc" : "#d1d9e6"}`,
                          background: chk ? "#1a54cc" : "transparent",
                          display: "flex", alignItems: "center", justifyContent: "center",
                          fontSize: 9, color: "#fff",
                        }}>
                          {chk ? "✓" : ""}
                        </div>
                      )}
                    </td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        {p.image_urls?.[0] && (
                          <img src={p.image_urls[0]} style={{ width: 36, height: 36,
                            objectFit: "cover", borderRadius: 7, border: "1px solid #e2e8f0", flexShrink: 0 }}/>
                        )}
                        <div>
                          <div style={{ fontSize: 12, color: "#334155", fontWeight: 500,
                            maxWidth: 210, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {p.title}
                          </div>
                          <div className="mono" style={{ fontSize: 9, color: "#94a3b8" }}>{p.source_id}</div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className="badge" style={{
                        background: p.supplier==="amazon" ? "#fffbeb" : "#eff6ff",
                        color:      p.supplier==="amazon" ? "#d97706" : "#1d4ed8",
                        border:     p.supplier==="amazon" ? "1px solid #fde68a" : "1px solid #bfdbfe",
                      }}>
                        {p.supplier}
                      </span>
                    </td>
                    <td><span className="mono" style={{ color: "#dc2626", fontWeight: 600 }}>${p.source_price}</span></td>
                    <td>
                      <div>
                        <span className="mono" style={{ color: "#16a34a", fontWeight: 700 }}>${p.potential_sell}</span>
                        {p.price_source === "ebay_sold_avg" && (
                          <div style={{ fontSize: 9, color: "#1a54cc" }}>eBay API avg ✓</div>
                        )}
                      </div>
                    </td>
                    <td><span className="mono" style={{ color: "#7c3aed", fontWeight: 700 }}>+${p.potential_profit?.toFixed(2)}</span></td>
                    <td>
                      <span className="mono" style={{ fontSize: 12, fontWeight: 700,
                        color: p.roi_pct >= 30 ? "#16a34a" : p.roi_pct >= 20 ? "#d97706" : "#dc2626" }}>
                        {p.roi_pct}%
                      </span>
                    </td>
                    <td><span style={{ fontSize: 11, color: "#d97706" }}>★ {p.rating}</span></td>
                    <td>
                      <span className="badge" style={{
                        background: p.in_stock ? "#dcfce7" : "#fee2e2",
                        color:      p.in_stock ? "#16a34a" : "#dc2626",
                        border:     p.in_stock ? "1px solid #86efac" : "1px solid #fca5a5",
                      }}>
                        {p.in_stock ? "In Stock" : "OOS"}
                      </span>
                    </td>
                    <td onClick={e => e.stopPropagation()}>
                      {p.is_listed
                        ? <span className="badge s-active">Listed ✓</span>
                        : <button className="btn btn-danger btn-sm" onClick={() => delProd(p.id)}>✕</button>
                      }
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
