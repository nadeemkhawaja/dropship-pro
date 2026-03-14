import sqlite3, json, os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the backend directory (one level up from services/)
load_dotenv(Path(__file__).parent.parent / ".env")

DB = Path("dropship.db")

def get_db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    with get_db() as c:
        # ── Schema (no sensitive data here) ───────────────────────
        c.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id    TEXT NOT NULL,
            supplier     TEXT NOT NULL DEFAULT 'amazon',
            title        TEXT NOT NULL,
            description  TEXT DEFAULT '',
            source_price REAL,
            source_url   TEXT DEFAULT '',
            image_urls   TEXT DEFAULT '[]',
            category     TEXT DEFAULT '',
            brand        TEXT DEFAULT '',
            rating       REAL DEFAULT 0,
            review_count INTEGER DEFAULT 0,
            in_stock     INTEGER DEFAULT 1,
            ebay_avg_sold REAL,
            last_checked  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_id, supplier)
        );

        CREATE TABLE IF NOT EXISTS listings (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id   INTEGER REFERENCES products(id),
            ebay_sku     TEXT DEFAULT '',
            ebay_offer_id  TEXT DEFAULT '',
            ebay_listing_id TEXT DEFAULT '',
            title        TEXT NOT NULL,
            sell_price   REAL NOT NULL,
            source_price REAL NOT NULL,
            markup_pct   REAL DEFAULT 35,
            status       TEXT DEFAULT 'draft',
            views        INTEGER DEFAULT 0,
            watchers     INTEGER DEFAULT 0,
            sales_count  INTEGER DEFAULT 0,
            image_urls   TEXT DEFAULT '[]',
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS orders (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            ebay_order_id     TEXT UNIQUE NOT NULL,
            listing_id        INTEGER REFERENCES listings(id),
            buyer_username    TEXT DEFAULT '',
            ship_name         TEXT DEFAULT '',
            ship_address1     TEXT DEFAULT '',
            ship_city         TEXT DEFAULT '',
            ship_state        TEXT DEFAULT '',
            ship_zip          TEXT DEFAULT '',
            item_title        TEXT DEFAULT '',
            quantity          INTEGER DEFAULT 1,
            sell_price        REAL DEFAULT 0,
            source_cost       REAL DEFAULT 0,
            ebay_fee          REAL DEFAULT 0,
            net_profit        REAL DEFAULT 0,
            status            TEXT DEFAULT 'pending',
            tracking_number   TEXT DEFAULT '',
            notes             TEXT DEFAULT '',
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS price_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id  INTEGER REFERENCES products(id),
            source_price REAL,
            recorded_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS activity_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            type       TEXT,
            title      TEXT,
            detail     TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        """)

        # ── Seed settings — keys come from .env, never hardcoded ──
        # INSERT OR IGNORE means existing values are never overwritten
        defaults = [
            ("ebay_client_id",       os.environ.get("EBAY_CLIENT_ID",       "")),
            ("ebay_client_secret",   os.environ.get("EBAY_CLIENT_SECRET",   "")),
            ("ebay_refresh_token",   os.environ.get("EBAY_REFRESH_TOKEN",   "")),
            ("default_markup_pct",   "35"),
            ("min_profit_usd",       "5.00"),
            ("ebay_fee_pct",         "13.0"),
            ("payment_fee_pct",      "3.0"),
            ("auto_reprice",         "true"),
            ("auto_pause",           "true"),
            ("monitor_interval_min", "120"),
            ("alert_email",          ""),
            ("dry_run",              "true"),
        ]
        c.executemany(
            "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
            defaults
        )

    print("✅ DB initialized")

def get_setting(key, default=""):
    with get_db() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

def set_setting(key, value):
    with get_db() as c:
        c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, str(value)))

def log_activity(type_, title, detail):
    with get_db() as c:
        c.execute("INSERT INTO activity_log(type,title,detail) VALUES(?,?,?)", (type_, title, detail))
