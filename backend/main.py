"""DropShip Pro — eBay Developer API Edition"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
from contextlib import asynccontextmanager
import json, asyncio, uuid, logging, os, hmac, hashlib, base64, time, urllib.parse
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from services.database      import get_db, get_setting, set_setting, log_activity, init_db
from services.ebay_api      import eBayClient
from services.amazon_scraper import fetch_product as amz_fetch, search as amz_search
from services.walmart_scraper import fetch_product as wmt_fetch, search as wmt_search

limiter = Limiter(key_func=get_remote_address)

log = logging.getLogger("DropShip")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

# ── AUTH ───────────────────────────────────────────────────────

_APP_USER   = os.environ.get("APP_USERNAME", "admin")
_APP_PASS   = os.environ.get("APP_PASSWORD", "changeme")
_APP_SECRET = os.environ.get("APP_SECRET",   "default-secret-change-me")
_TOKEN_DAYS = 30

def _make_token(username: str) -> str:
    exp = int(time.time()) + _TOKEN_DAYS * 86400
    msg = f"{username}:{exp}"
    sig = hmac.new(_APP_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{msg}:{sig}".encode()).decode()

def _verify_token(token: str) -> str:
    try:
        raw      = base64.urlsafe_b64decode(token.encode()).decode()
        parts    = raw.rsplit(":", 2)
        if len(parts) != 3:
            raise ValueError
        username, exp, sig = parts
        msg      = f"{username}:{exp}"
        expected = hmac.new(_APP_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("bad sig")
        if int(exp) < int(time.time()):
            raise ValueError("expired")
        return username
    except Exception:
        raise HTTPException(401, "Invalid or expired session — please log in again")

# Public paths that don't require a token
_PUBLIC = {"/api/auth/login", "/api/health", "/docs", "/openapi.json", "/redoc"}

def get_ebay() -> eBayClient:
    return eBayClient(
        client_id     = get_setting("ebay_client_id"),
        client_secret = get_setting("ebay_client_secret"),
        user_refresh_token = get_setting("ebay_refresh_token"),
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="DropShip Pro", version="4.2 — eBay API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
_CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS", "http://localhost:3000,http://localhost:8000"
).split(",")
app.add_middleware(CORSMiddleware, allow_origins=_CORS_ORIGINS, allow_methods=["*"],
                   allow_headers=["*"], allow_credentials=True)

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if path in _PUBLIC or request.method == "OPTIONS":
        return await call_next(request)
    # Let static files through (Docker SPA serving)
    if not path.startswith("/api/"):
        return await call_next(request)
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)
    try:
        _verify_token(auth[7:])
    except HTTPException as e:
        return JSONResponse({"detail": e.detail}, status_code=401)
    return await call_next(request)

# ── AUTH ENDPOINTS ─────────────────────────────────────────────

class LoginReq(BaseModel):
    username: str
    password: str

@app.post("/api/auth/login")
@limiter.limit("5/minute")
def login(request: Request, data: LoginReq):
    if data.username != _APP_USER or data.password != _APP_PASS:
        raise HTTPException(401, "Invalid username or password")
    token = _make_token(data.username)
    log.info(f"Login: {data.username}")
    return {"token": token, "username": data.username}

@app.post("/api/auth/logout")
def logout():
    # Token is stateless — client just discards it
    return {"success": True}

# ── HEALTH / STATUS ───────────────────────────────────────────

@app.get("/api/health")
async def health():
    ebay = get_ebay()
    ebay_ok = False
    try:
        if ebay.is_configured():
            await ebay._get_app_token()
            ebay_ok = True
    except Exception:
        pass
    return {"status": "ok", "ebay_api": ebay_ok,
            "ebay_configured": ebay.is_configured()}

# ── PRODUCTS ──────────────────────────────────────────────────

class ImportReq(BaseModel):
    source_id: str
    supplier: str = "amazon"

class SearchReq(BaseModel):
    keywords: str
    supplier: str = "amazon"
    max_results: int = 20

@app.get("/api/products")
def products(q: str = "", supplier: str = "", limit: int = 200):
    with get_db() as c:
        sql, p = "SELECT * FROM products WHERE 1=1", []
        if q:        sql += " AND title LIKE ?";  p.append(f"%{q}%")
        if supplier: sql += " AND supplier=?";    p.append(supplier)
        sql += " ORDER BY created_at DESC LIMIT ?"; p.append(limit)
        rows = c.execute(sql, p).fetchall()
        listed = {r[0] for r in c.execute("SELECT product_id FROM listings").fetchall()}

    markup = float(get_setting("default_markup_pct", "35"))
    efee   = float(get_setting("ebay_fee_pct", "13"))
    pfee   = float(get_setting("payment_fee_pct", "3"))
    result = []
    for r in rows:
        d = dict(r)
        d["image_urls"] = json.loads(d.get("image_urls") or "[]")
        d["is_listed"]  = r["id"] in listed
        cost = d["source_price"] or 0
        sell = d["ebay_avg_sold"] or round(cost * (1 + markup/100), 2)
        fees = sell * (efee + pfee) / 100
        d["potential_sell"] = round(sell, 2)
        d["potential_profit"] = round(sell - cost - fees, 2)
        d["roi_pct"] = round((sell - cost - fees) / cost * 100, 1) if cost else 0
        d["price_source"] = "ebay_sold_avg" if d["ebay_avg_sold"] else "markup"
        result.append(d)
    return result

@app.post("/api/products/import")
async def import_product(data: ImportReq):
    with get_db() as c:
        if c.execute("SELECT id FROM products WHERE source_id=? AND supplier=?",
                     (data.source_id, data.supplier)).fetchone():
            raise HTTPException(400, "Already imported")

    p = await (amz_fetch(data.source_id) if data.supplier == "amazon"
               else wmt_fetch(data.source_id))
    if not p:
        raise HTTPException(422, f"Could not scrape {data.source_id} — check ID and try again")
    if not p.get("source_price"):
        raise HTTPException(422, "Price not found for this product")

    ebay = get_ebay()
    ebay_avg = None
    if ebay.is_configured():
        try:
            res = await ebay.search_sold(p["title"][:50], limit=15)
            ebay_avg = res.get("avg_price")
        except Exception:
            pass

    with get_db() as c:
        c.execute("""INSERT INTO products
            (source_id,supplier,title,description,source_price,source_url,
             image_urls,category,brand,rating,review_count,in_stock,ebay_avg_sold)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (p["source_id"], data.supplier, p["title"], p.get("description",""),
             p["source_price"], p.get("source_url",""),
             json.dumps(p.get("image_urls",[])), p.get("category","General"),
             p.get("brand",""), p.get("rating",0), p.get("review_count",0),
             int(p.get("in_stock",True)), ebay_avg))
        pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_activity("import", "Product imported",
                 f"{p['title'][:50]} @ ${p['source_price']}")
    return {"success": True, "product_id": pid, **p, "ebay_avg_sold": ebay_avg}

@app.post("/api/products/search")
async def search_products(data: SearchReq):
    results = await (amz_search(data.keywords, data.max_results)
                     if data.supplier == "amazon"
                     else wmt_search(data.keywords, data.max_results))
    return {"results": results, "count": len(results)}

@app.delete("/api/products/{pid}")
def delete_product(pid: int):
    with get_db() as c:
        c.execute("DELETE FROM products WHERE id=?", (pid,))
    return {"success": True}

# ── EBAY RESEARCH (official API) ──────────────────────────────

@app.get("/api/research/sold")
async def research_sold(keywords: str, limit: int = 20):
    ebay = get_ebay()
    if not ebay.is_configured():
        raise HTTPException(400, "eBay API not configured — add keys in Settings")
    result = await ebay.search_sold(keywords, limit)
    return result

@app.get("/api/research/active")
async def research_active(keywords: str, limit: int = 20):
    ebay = get_ebay()
    if not ebay.is_configured():
        raise HTTPException(400, "eBay API not configured — add keys in Settings")
    result = await ebay.search_active(keywords, limit)
    return result

# ── LISTINGS ──────────────────────────────────────────────────

class ListReq(BaseModel):
    product_id: int
    markup_pct: Optional[float] = None
    title: Optional[str] = None
    publish: bool = False

class BulkListReq(BaseModel):
    product_ids: List[int]
    markup_pct: Optional[float] = None
    publish: bool = False

class ListingUpdate(BaseModel):
    status: Optional[str] = None
    sell_price: Optional[float] = None
    title: Optional[str] = None

@app.get("/api/listings")
def listings(status: str = ""):
    with get_db() as c:
        sql = "SELECT l.*,p.source_id,p.supplier FROM listings l LEFT JOIN products p ON l.product_id=p.id WHERE 1=1"
        p = []
        if status: sql += " AND l.status=?"; p.append(status)
        sql += " ORDER BY l.created_at DESC"
        rows = c.execute(sql, p).fetchall()
    efee = float(get_setting("ebay_fee_pct","13"))
    pfee = float(get_setting("payment_fee_pct","3"))
    result = []
    for r in rows:
        d = dict(r)
        d["image_urls"] = json.loads(d.get("image_urls") or "[]")
        d["profit"] = round(d["sell_price"] - d["source_price"]
                            - d["sell_price"] * (efee+pfee)/100, 2)
        result.append(d)
    return result

@app.get("/api/listings/stats")
def listing_stats():
    with get_db() as c:
        rows = c.execute("SELECT status, COUNT(*) as n FROM listings GROUP BY status").fetchall()
    return {r["status"]: r["n"] for r in rows}

@app.post("/api/listings")
async def create_listing(data: ListReq):
    markup = data.markup_pct or float(get_setting("default_markup_pct","35"))
    dry    = get_setting("dry_run","true") == "true"

    with get_db() as c:
        prod = c.execute("SELECT * FROM products WHERE id=?", (data.product_id,)).fetchone()
        if not prod: raise HTTPException(404, "Product not found")
        if c.execute("SELECT id FROM listings WHERE product_id=?", (prod["id"],)).fetchone():
            raise HTTPException(400, "Product already listed")

    sell  = prod["ebay_avg_sold"] or round(prod["source_price"] * (1 + markup/100), 2)
    title = (data.title or prod["title"])[:80]
    sku   = f"DS-{uuid.uuid4().hex[:8].upper()}"
    imgs  = json.loads(prod["image_urls"] or "[]")

    ebay_sku, offer_id, listing_id, status = sku, "", "", "draft"

    if data.publish and not dry:
        ebay = get_ebay()
        if not ebay.is_configured():
            raise HTTPException(400, "eBay API keys not configured")
        try:
            ok = await ebay.create_inventory_item(sku, {
                "title": title, "description": prod["description"] or title,
                "brand": prod["brand"] or "Unbranded", "image_urls": imgs,
            })
            if ok:
                policies = await ebay.get_seller_policies()
                offer_id = await ebay.create_offer(sku, sell, policy_ids=policies) or ""
                if offer_id:
                    listing_id = await ebay.publish_offer(offer_id) or ""
                    status = "active" if listing_id else "draft"
        except Exception as e:
            log.error(f"eBay publish error: {e}")
            status = "draft"
    elif data.publish and dry:
        status = "draft"
        log_activity("dry_run", "Dry Run — listing skipped", f"{title} @ ${sell}")

    with get_db() as c:
        c.execute("""INSERT INTO listings
            (product_id,ebay_sku,ebay_offer_id,ebay_listing_id,title,
             sell_price,source_price,markup_pct,image_urls,status)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (prod["id"], ebay_sku, offer_id, listing_id, title,
             sell, prod["source_price"], markup, prod["image_urls"], status))
        lid = c.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_activity("listing", f"Listing {'published' if status=='active' else 'drafted'}",
                 f"{title} @ ${sell}")
    return {"success": True, "listing_id": lid, "status": status,
            "sell_price": sell, "ebay_listing_id": listing_id, "dry_run": dry}

@app.post("/api/listings/bulk")
async def bulk_list(data: BulkListReq):
    ok, fail = 0, []
    for pid in data.product_ids:
        try:
            await create_listing(ListReq(product_id=pid,
                                         markup_pct=data.markup_pct,
                                         publish=data.publish))
            ok += 1
        except HTTPException as e:
            fail.append({"product_id": pid, "error": e.detail})
        await asyncio.sleep(0.5)
    return {"success_count": ok, "failed": fail}

@app.patch("/api/listings/{lid}")
def update_listing(lid: int, data: ListingUpdate):
    with get_db() as c:
        updates, vals = ["updated_at=CURRENT_TIMESTAMP"], []
        if data.status:     updates.append("status=?");     vals.append(data.status)
        if data.sell_price: updates.append("sell_price=?"); vals.append(data.sell_price)
        if data.title:      updates.append("title=?");      vals.append(data.title)
        c.execute(f"UPDATE listings SET {','.join(updates)} WHERE id=?", vals+[lid])
    return {"success": True}

@app.delete("/api/listings/{lid}")
def delete_listing(lid: int):
    with get_db() as c:
        c.execute("DELETE FROM listings WHERE id=?", (lid,))
    return {"success": True}

# ── ORDERS ────────────────────────────────────────────────────

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    tracking_number: Optional[str] = None
    notes: Optional[str] = None

@app.get("/api/orders")
def orders(status: str = ""):
    with get_db() as c:
        sql = "SELECT * FROM orders WHERE 1=1"
        p = []
        if status: sql += " AND status=?"; p.append(status)
        sql += " ORDER BY created_at DESC"
        return [dict(r) for r in c.execute(sql, p).fetchall()]

@app.get("/api/orders/stats")
def order_stats():
    with get_db() as c:
        rows = c.execute("SELECT * FROM orders").fetchall()
    rev    = sum(r["sell_price"] or 0 for r in rows)
    profit = sum(r["net_profit"] or 0 for r in rows)
    return {
        "total_orders":  len(rows),
        "total_revenue": round(rev, 2),
        "total_profit":  round(profit, 2),
        "margin_pct":    round(profit/rev*100, 1) if rev else 0,
        "pending":       sum(1 for r in rows if r["status"]=="pending"),
        "by_status":     {s: sum(1 for r in rows if r["status"]==s)
                          for s in ["pending","ordered","shipped","delivered"]},
    }

@app.post("/api/orders/sync")
async def sync_orders():
    ebay = get_ebay()
    if not ebay.is_configured():
        raise HTTPException(400, "eBay API not configured")
    dry = get_setting("dry_run","true") == "true"
    if dry:
        return {"synced": 0, "message": "Dry run — no sync performed"}
    try:
        orders = await ebay.get_my_orders(limit=50)
        new = 0
        with get_db() as c:
            for o in orders:
                if not c.execute("SELECT id FROM orders WHERE ebay_order_id=?",
                                 (o["order_id"],)).fetchone():
                    efee = float(get_setting("ebay_fee_pct","13"))
                    pfee = float(get_setting("payment_fee_pct","3"))
                    sell = o["sell_price"]
                    fees = sell * (efee+pfee)/100
                    c.execute("""INSERT INTO orders
                        (ebay_order_id,buyer_username,ship_name,ship_address1,
                         ship_city,ship_state,ship_zip,item_title,quantity,
                         sell_price,ebay_fee,net_profit,status)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (o["order_id"], o["buyer"], o["ship_name"], o["ship_addr1"],
                         o["ship_city"], o["ship_state"], o["ship_zip"],
                         o["item_title"], o["quantity"],
                         sell, round(fees,2), round(sell-fees,2), "pending"))
                    new += 1
        log_activity("sync", "Orders synced", f"{new} new orders from eBay")
        return {"synced": new}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.patch("/api/orders/{oid}")
def update_order(oid: int, data: OrderUpdate):
    with get_db() as c:
        updates, vals = ["updated_at=CURRENT_TIMESTAMP"], []
        if data.status:          updates.append("status=?");          vals.append(data.status)
        if data.tracking_number: updates.append("tracking_number=?"); vals.append(data.tracking_number)
        if data.notes:           updates.append("notes=?");           vals.append(data.notes)
        c.execute(f"UPDATE orders SET {','.join(updates)} WHERE id=?", vals+[oid])
    return {"success": True}

# ── ANALYTICS ─────────────────────────────────────────────────

@app.get("/api/analytics/dashboard")
def dashboard():
    with get_db() as c:
        orders   = c.execute("SELECT * FROM orders").fetchall()
        listings = c.execute("SELECT status FROM listings").fetchall()
        products = c.execute("SELECT COUNT(*) as n FROM products").fetchone()
        activity = c.execute("SELECT * FROM activity_log ORDER BY created_at DESC LIMIT 25").fetchall()

    rev    = sum(r["sell_price"] or 0 for r in orders)
    profit = sum(r["net_profit"] or 0 for r in orders)
    return {
        "stats": {
            "total_revenue":   round(rev, 2),
            "total_profit":    round(profit, 2),
            "margin_pct":      round(profit/rev*100, 1) if rev else 0,
            "total_orders":    len(orders),
            "active_listings": sum(1 for l in listings if l["status"]=="active"),
            "total_products":  products["n"],
            "pending_orders":  sum(1 for o in orders if o["status"]=="pending"),
        },
        "activity": [dict(a) for a in activity],
    }

@app.get("/api/analytics/top-products")
def top_products():
    with get_db() as c:
        rows = c.execute("""SELECT item_title, COUNT(*) as sales, SUM(net_profit) as profit
            FROM orders GROUP BY item_title ORDER BY profit DESC LIMIT 10""").fetchall()
    return [dict(r) for r in rows]

# ── SETTINGS ──────────────────────────────────────────────────

class SettingsSave(BaseModel):
    settings: dict

@app.get("/api/settings")
def get_settings_all():
    with get_db() as c:
        rows = c.execute("SELECT key,value FROM settings").fetchall()
    d = {r["key"]: r["value"] for r in rows}
    for k in ["ebay_client_secret", "ebay_refresh_token"]:
        if d.get(k): d[k] = d[k][:6] + "•" * 12
    return d

@app.post("/api/settings")
def save_settings(data: SettingsSave):
    with get_db() as c:
        for k, v in data.settings.items():
            if "•" not in str(v):
                c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (k, str(v)))
    return {"success": True}

@app.get("/api/settings/raw/{key}")
def get_raw_setting(key: str):
    return {"value": get_setting(key)}

@app.get("/api/activity")
def activity(limit: int = 100):
    with get_db() as c:
        rows = c.execute("SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]

# ── AUTO SCANNER ──────────────────────────────────────────────

from services.auto_scanner import (
    run_auto_scan, CATEGORIES, SCAN_CATEGORIES,
    scout_keyword, scan_category, find_amazon_match,
    calc_profit, match_label,
    top_sellers_scan,
)

# In-memory scan state (survives for lifetime of process)
active_scans: dict = {}


# ── Background task runners ────────────────────────────────────

async def _bg_scout(scan_id: str, keywords_list: list):
    """Background eBay-only scout scan."""
    state = active_scans[scan_id]
    ebay  = get_ebay()
    for i, kw in enumerate(keywords_list):
        if state.get("cancelled"):
            break
        try:
            results = await scout_keyword(ebay, kw)
            state["results"].extend(results)
            state["progress"]   = i + 1
            state["total_found"] = len(state["results"])
            log.info(f"[Scout {scan_id}] {i+1}/{len(keywords_list)} '{kw[:30]}' → {len(results)} items")
        except Exception as e:
            log.error(f"[Scout {scan_id}] Error on '{kw}': {e}")
        await asyncio.sleep(0.4)
    state["done"]   = True
    state["status"] = "complete"
    log_activity("scan", "eBay Scout complete",
                 f"Found {state['total_found']} listings across {len(keywords_list)} keyword sets")


async def _bg_full(scan_id: str, keywords_list: list):
    """Background full eBay + Amazon profit scan."""
    state    = active_scans[scan_id]
    ebay     = get_ebay()
    ebay_fee = float(get_setting("ebay_fee_pct", "13"))
    pay_fee  = float(get_setting("payment_fee_pct", "3"))
    min_prof = float(get_setting("min_profit_usd", "5"))
    seen_asins: set = set()

    for i, kw in enumerate(keywords_list):
        if state.get("cancelled"):
            break
        try:
            opps = await scan_category(ebay, kw, ebay_fee, pay_fee, min_prof)
            for o in opps:
                asin = o.get("amazon_asin", "")
                if asin and asin not in seen_asins:
                    seen_asins.add(asin)
                    state["results"].append(o)
            state["progress"]    = i + 1
            state["total_found"] = len(state["results"])
            log.info(f"[Full {scan_id}] {i+1}/{len(keywords_list)} '{kw[:30]}' → {len(opps)} opps")
        except Exception as e:
            log.error(f"[Full {scan_id}] Error on '{kw}': {e}")
        await asyncio.sleep(1.0)

    state["done"]   = True
    state["status"] = "complete"
    log_activity("scan", "Full Profit Scan complete",
                 f"Found {state['total_found']} opportunities")


async def _bg_topsellers(scan_id: str, category_ids: list):
    """
    Background task — finds top BIN products per category using eBay bestMatch sort.
    bestMatch is eBay's purchase-activity-weighted ranking = proxy for top sellers.
    """
    state = active_scans[scan_id]
    ebay  = get_ebay()

    for cat_id in category_ids:
        if state.get("cancelled"):
            break
        cat       = CATEGORIES.get(cat_id, {})
        cat_label = cat.get("label", cat_id)
        cat_icon  = cat.get("icon", "📦")

        try:
            products = await top_sellers_scan(ebay, cat_id, max_products=200)

            for p in products:
                if state.get("cancelled"):
                    break
                title = p.get("title", "")
                q = urllib.parse.quote(title[:80])
                p["category_id"]    = cat_id
                p["category_label"] = cat_label
                p["category_icon"]  = cat_icon
                p["amazon_search_url"] = f"https://www.amazon.com/s?k={q}"
                state["results"].append(p)
                state["total_found"] += 1

        except Exception as e:
            log.error(f"Top sellers scan ({cat_id}): {e}")

        state["progress"] += 1

    state["done"]   = True
    state["status"] = "done"
    log_activity("scan", "Top Sellers scan complete",
                 f"Found {state['total_found']} products across {len(category_ids)} categories")


# ── Scan endpoints ─────────────────────────────────────────────

class ScanStartReq(BaseModel):
    mode: str               # "scout", "full", or "topsellers"
    category_ids: List[str]

@app.get("/api/scan/categories")
def scan_categories():
    return {
        cid: {"icon": c["icon"], "label": c["label"], "keyword_count": len(c["keywords"])}
        for cid, c in CATEGORIES.items()
    }

@app.post("/api/scan/start")
async def start_scan(data: ScanStartReq):
    if not data.category_ids:
        raise HTTPException(400, "Select at least one category")

    ebay = get_ebay()
    if not ebay.is_configured():
        raise HTTPException(400, "eBay API not configured — add keys in Settings")

    # Top Sellers mode — no keyword list needed
    if data.mode == "topsellers":
        total = len(data.category_ids) * 10  # 10 sellers per category
        scan_id = uuid.uuid4().hex[:8]
        active_scans[scan_id] = {
            "scan_id": scan_id, "status": "running", "mode": "topsellers",
            "results": [], "progress": 0, "total": total,
            "total_found": 0, "done": False, "cancelled": False,
        }
        asyncio.create_task(_bg_topsellers(scan_id, data.category_ids))
        log_activity("scan", "Top Sellers scan started",
                     f"{len(data.category_ids)} categories, up to {total} sellers")
        return {"scan_id": scan_id, "total": total, "mode": data.mode}

    # Scout / Full — build keyword list
    keywords_list = []
    for cat_id in data.category_ids:
        if cat_id in CATEGORIES:
            keywords_list.extend(CATEGORIES[cat_id]["keywords"])

    if not keywords_list:
        raise HTTPException(400, "No keywords found for selected categories")

    scan_id = uuid.uuid4().hex[:8]
    active_scans[scan_id] = {
        "scan_id":    scan_id,
        "status":     "running",
        "mode":       data.mode,
        "results":    [],
        "progress":   0,
        "total":      len(keywords_list),
        "total_found": 0,
        "done":       False,
        "cancelled":  False,
    }

    if data.mode == "scout":
        asyncio.create_task(_bg_scout(scan_id, keywords_list))
    else:
        asyncio.create_task(_bg_full(scan_id, keywords_list))

    log_activity("scan",
                 f"{'eBay Scout' if data.mode=='scout' else 'Full Profit Scan'} started",
                 f"{len(data.category_ids)} categories, {len(keywords_list)} keyword sets")
    return {"scan_id": scan_id, "total": len(keywords_list), "mode": data.mode}


@app.get("/api/scan/status/{scan_id}")
def get_scan_status(scan_id: str):
    if scan_id not in active_scans:
        raise HTTPException(404, "Scan not found")
    s = active_scans[scan_id]
    return {
        "scan_id":    scan_id,
        "status":     s["status"],
        "mode":       s["mode"],
        "results":    s["results"],
        "progress":   s["progress"],
        "total":      s["total"],
        "total_found": s["total_found"],
        "done":       s["done"],
    }


@app.post("/api/scan/cancel/{scan_id}")
def cancel_scan(scan_id: str):
    if scan_id in active_scans:
        active_scans[scan_id]["cancelled"] = True
        active_scans[scan_id]["status"]    = "cancelled"
        active_scans[scan_id]["done"]      = True
    return {"success": True}


class CheckAmazonReq(BaseModel):
    ebay_title: str
    ebay_sell_price: float

@app.post("/api/scan/check-amazon")
async def check_amazon_price(data: CheckAmazonReq):
    """Check a single eBay listing against Amazon — used by Scout mode inline button."""
    ebay_fee = float(get_setting("ebay_fee_pct", "13"))
    pay_fee  = float(get_setting("payment_fee_pct", "3"))
    min_prof = float(get_setting("min_profit_usd", "5"))

    amz = await find_amazon_match(data.ebay_title, data.ebay_sell_price)
    if not amz:
        return {"found": False, "message": "No matching Amazon product found"}

    amazon_cost = amz.get("source_price")
    match_score = amz.get("_match_score", 0)
    profit_data = calc_profit(amazon_cost, data.ebay_sell_price, ebay_fee, pay_fee, min_prof)

    return {
        "found":        True,
        "amazon_title": amz.get("title", ""),
        "amazon_asin":  amz.get("source_id", ""),
        "amazon_cost":  amazon_cost,
        "amazon_url":   f"https://www.amazon.com/dp/{amz.get('source_id', '')}",
        "amazon_rating": amz.get("rating", 0),
        "amazon_reviews": amz.get("review_count", 0),
        "match_score":  match_score,
        "match_label":  match_label(match_score),
        "image_urls":   amz.get("image_urls", []),
        **profit_data,
    }


@app.post("/api/scan/import-opportunity")
async def import_opportunity(data: dict):
    asin = data.get("amazon_asin")
    if not asin:
        raise HTTPException(400, "No ASIN provided")
    with get_db() as c:
        existing = c.execute("SELECT id FROM products WHERE source_id=? AND supplier='amazon'",
                             (asin,)).fetchone()
        if existing:
            pid = existing["id"]
        else:
            from services.amazon_scraper import fetch_product as amz_fetch2
            p = await amz_fetch2(asin)
            if not p:
                raise HTTPException(422, f"Could not scrape ASIN {asin}")
            ebay_avg = data.get("ebay_avg_sold")
            c.execute("""INSERT INTO products
                (source_id,supplier,title,description,source_price,source_url,
                 image_urls,category,brand,rating,review_count,in_stock,ebay_avg_sold)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (asin, "amazon", p["title"], p.get("description",""),
                 p["source_price"], p.get("source_url",""),
                 json.dumps(p.get("image_urls",[])), p.get("category","General"),
                 p.get("brand",""), p.get("rating",0), p.get("review_count",0),
                 1, ebay_avg))
            pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    try:
        await create_listing(ListReq(product_id=pid, publish=False))
    except HTTPException:
        pass
    log_activity("import", "Opportunity imported", f"ASIN {asin}")
    return {"success": True, "product_id": pid}


# ── Legacy blocking scan (kept for compatibility) ──────────────

@app.post("/api/scan/run")
async def auto_scan_legacy(max_categories: int = 5):
    log_activity("scan", "Legacy auto scan started", f"Scanning {max_categories} categories")
    try:
        result = await run_auto_scan(max_categories=max_categories)
        count = len(result.get("results", []))
        log_activity("scan", "Legacy auto scan complete", f"Found {count} opportunities")
        return result
    except Exception as e:
        log.error(f"Auto scan error: {e}")
        raise HTTPException(500, str(e))


# ── Static File Serving (Docker / Production) ─────────────────
# When `npm run build` output is copied to backend/static/, serve the SPA
_static_dir = Path(__file__).parent / "static"
if _static_dir.exists() and (_static_dir / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the React SPA — all non-API routes get index.html."""
        file = _static_dir / full_path
        if file.is_file() and ".." not in full_path:
            return FileResponse(file)
        return FileResponse(_static_dir / "index.html")
