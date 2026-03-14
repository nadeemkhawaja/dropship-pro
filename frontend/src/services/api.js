const getToken = () => localStorage.getItem("ds_token") || "";

const call = async (path, opts = {}) => {
  const r = await fetch("/api" + path, {
    headers: {
      "Content-Type": "application/json",
      ...(getToken() ? { "Authorization": `Bearer ${getToken()}` } : {}),
    },
    ...opts,
  });
  if (r.status === 401) {
    // Token expired or invalid — force re-login
    localStorage.removeItem("ds_token");
    localStorage.removeItem("ds_user");
    window.location.reload();
    throw new Error("Session expired");
  }
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(e.detail || r.statusText);
  }
  return r.json();
};

export const api = {
  // ── Auth ──────────────────────────────────────────────────
  login:  (username, password) =>
    fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    }).then(async r => {
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "Login failed");
      return d;
    }),

  logout: () => call("/auth/logout", { method: "POST" }),

  // ── Core ──────────────────────────────────────────────────
  health:         ()      => call("/health"),
  dashboard:      ()      => call("/analytics/dashboard"),
  topProducts:    ()      => call("/analytics/top-products"),

  getProducts:    (p={})  => call("/products?" + new URLSearchParams(p)),
  importProduct:  (d)     => call("/products/import",  { method:"POST", body:JSON.stringify(d) }),
  searchProducts: (d)     => call("/products/search",  { method:"POST", body:JSON.stringify(d) }),
  deleteProduct:  (id)    => call(`/products/${id}`,   { method:"DELETE" }),

  researchSold:   (kw,n)  => call(`/research/sold?keywords=${encodeURIComponent(kw)}&limit=${n||20}`),
  researchActive: (kw,n)  => call(`/research/active?keywords=${encodeURIComponent(kw)}&limit=${n||20}`),

  getListings:    (p={})  => call("/listings?" + new URLSearchParams(p)),
  listingStats:   ()      => call("/listings/stats"),
  createListing:  (d)     => call("/listings",         { method:"POST",   body:JSON.stringify(d) }),
  bulkList:       (d)     => call("/listings/bulk",    { method:"POST",   body:JSON.stringify(d) }),
  updateListing:  (id,d)  => call(`/listings/${id}`,   { method:"PATCH",  body:JSON.stringify(d) }),
  deleteListing:  (id)    => call(`/listings/${id}`,   { method:"DELETE" }),

  getOrders:      (p={})  => call("/orders?" + new URLSearchParams(p)),
  orderStats:     ()      => call("/orders/stats"),
  syncOrders:     ()      => call("/orders/sync",      { method:"POST" }),
  updateOrder:    (id,d)  => call(`/orders/${id}`,     { method:"PATCH",  body:JSON.stringify(d) }),

  getSettings:    ()      => call("/settings"),
  saveSettings:   (s)     => call("/settings",         { method:"POST",   body:JSON.stringify({ settings:s }) }),

  getActivity:    (n=50)  => call(`/activity?limit=${n}`),

  // ── Auto Scanner ──────────────────────────────────────────
  scanCategories: ()      => call("/scan/categories"),
  startScan:      (d)     => call("/scan/start",       { method:"POST", body:JSON.stringify(d) }),
  scanStatus:     (id)    => call(`/scan/status/${id}`),
  cancelScan:     (id)    => call(`/scan/cancel/${id}`, { method:"POST" }),
  checkAmazon:    (d)     => call("/scan/check-amazon", { method:"POST", body:JSON.stringify(d) }),
  importOpportunity: (d)  => call("/scan/import-opportunity", { method:"POST", body:JSON.stringify(d) }),
};
