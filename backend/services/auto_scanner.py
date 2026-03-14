"""
Auto Scanner — finds profitable dropship products automatically.
Scout Mode  : eBay-only, fast — returns eBay sold data for selected categories
Full Mode   : eBay + Amazon — cross-checks price, similarity, profit margin

Filter pipeline (both modes):
  1. Blocks branded / prohibited / refurbished items
  2. Uses avg_sold × 0.95 as the consistent sell price
Full mode extras:
  3. Amazon title similarity (Jaccard, min 28 %)
  4. Conflicting product-type rejection
  5. Profit threshold gate
  6. Returns match confidence score
"""
import asyncio, re, logging, json, urllib.parse
from typing import Optional
from services.ebay_api import eBayClient
from services.amazon_scraper import search as amz_search, fetch_product as amz_fetch
from services.database import get_setting

log = logging.getLogger("AutoScanner")

# ── Blocked brands ─────────────────────────────────────────────
BLOCKED_BRANDS = {
    "apple","iphone","ipad","macbook","airpods","samsung","galaxy",
    "google","pixel","sony","bose","anker","govee","philips","hue",
    "amazon","echo","alexa","kindle","ring","nest","dyson","shark",
    "ninja","instant pot","keurig","nespresso","dewalt","milwaukee",
    "makita","bosch","lg","dell","hp","lenovo","asus","acer","microsoft",
    "surface","xbox","playstation","nintendo","switch","lego","barbie",
    "disney","nike","adidas","under armour","north face","yeti","stanley",
    "hydro flask","cuisinart","kitchenaid","roomba","irobot","fitbit",
    "garmin","logitech","razer","corsair","western digital","seagate",
    "iottie","belkin","mophie","otterbox","spigen","ugreen","baseus",
    "aukey","ravpower","jackery","bluetti","olight","streamlight",
    "gerber","leatherman","victorinox","benchmade","spyderco",
}

# ── Prohibited keywords ────────────────────────────────────────
PROHIBITED_KEYWORDS = {
    "wine","beer","whiskey","bourbon","vodka","tequila","rum","gin",
    "alcohol","liquor","tobacco","cigarette","cigar","vape","e-cig",
    "adult","xxx","sexual","erotic",
    "gun","firearm","pistol","rifle","ammunition","ammo","silencer",
    "switchblade","brass knuckle","taser","stun gun",
    "cbd","thc","marijuana","cannabis","kratom","supplement claim",
    "cure","treat disease","fda approved",
    "explosive","firework","aerosol spray can",
    "live animal","fresh food","raw meat","perishable",
    "replica","counterfeit","fake","knockoff","unauthorized",
}

# ── 14 product categories with keywords ───────────────────────
CATEGORIES = {
    "electronics": {
        "icon": "📱",
        "label": "Electronics & Gadgets",
        "keywords": [
            "USB C hub multiport adapter",
            "LED strip lights bedroom",
            "monitor light bar desk",
            "blue light glasses computer",
            "phone screen magnifier stand",
            "ring light selfie tripod",
            "cable organizer desk management",
            "keyboard wrist rest pad",
        ],
    },
    "apparel": {
        "icon": "👜",
        "label": "Apparel & Accessories",
        "keywords": [
            "compression socks running women",
            "beanie hat winter knit unisex",
            "silicone watch band replacement",
            "phone wallet card holder case",
            "crossbody bag small women",
            "hair scrunchie velvet set",
            "baseball cap adjustable unstructured",
            "tote bag canvas reusable",
        ],
    },
    "auto": {
        "icon": "🚗",
        "label": "Auto & Car Accessories",
        "keywords": [
            "car phone mount dashboard holder",
            "seat gap filler organizer console",
            "trunk organizer collapsible car",
            "steering wheel cover leather",
            "windshield sun shade foldable",
            "car back seat organizer pocket",
            "LED interior car lights strip",
            "tire pressure gauge digital",
        ],
    },
    "jewelry": {
        "icon": "💎",
        "label": "Jewelry & Watches",
        "keywords": [
            "minimalist ring stainless steel women",
            "crystal stud earrings women silver",
            "layered necklace gold dainty",
            "charm bracelet adjustable women",
            "birthstone pendant necklace",
            "hoop earrings gold plated",
            "anklet gold silver chain",
            "compass pendant necklace",
        ],
    },
    "collectibles": {
        "icon": "🎨",
        "label": "Collectibles & Crafts",
        "keywords": [
            "diamond painting kit landscape adults",
            "paint by number adult canvas set",
            "cross stitch kit beginner flowers",
            "resin mold silicone craft DIY",
            "enamel pin set aesthetic",
            "washi tape set decorative",
            "journaling sticker set aesthetic",
            "calligraphy pen brush lettering set",
        ],
    },
    "health_beauty": {
        "icon": "💊",
        "label": "Health & Beauty",
        "keywords": [
            "jade roller face massager skincare",
            "gua sha stone facial tool",
            "silicone face cleansing brush electric",
            "ice roller face puffiness",
            "nail art kit stamping set",
            "eyebrow stencil shaping kit reusable",
            "sleep mask contoured eye light blocking",
            "electric scalp massager hair growth",
        ],
    },
    "home_garden": {
        "icon": "🏠",
        "label": "Home & Garden",
        "keywords": [
            "wall shelf floating wooden bracket",
            "plant pot succulent ceramic small",
            "shower curtain hooks rust proof",
            "drawer organizer divider kitchen",
            "picture frame set hanging wall",
            "decorative throw pillow cover 18x18",
            "solar garden light stake outdoor",
            "shelf bracket industrial metal",
        ],
    },
    "kitchen": {
        "icon": "🍳",
        "label": "Kitchen & Dining",
        "keywords": [
            "spice rack organizer magnetic wall",
            "silicone kitchen utensil set cooking",
            "reusable beeswax wrap food storage",
            "coffee pod holder organizer rack",
            "garlic press rocker stainless steel",
            "silicone stretch lid set food",
            "egg cooker electric rapid boiler",
            "salad spinner bowl large",
        ],
    },
    "pets": {
        "icon": "🐾",
        "label": "Pet Supplies",
        "keywords": [
            "cat tunnel play interactive toy",
            "dog slow feeder bowl puzzle",
            "pet hair remover roller couch",
            "cat window perch suction cup",
            "dog paw cleaner portable muddy",
            "cat scratch post cardboard lounge",
            "dog treat pouch training bag",
            "aquarium decoration ornament fish",
        ],
    },
    "office": {
        "icon": "💼",
        "label": "Office & Desk",
        "keywords": [
            "desk organizer bamboo wood pen holder",
            "laptop stand adjustable aluminum portable",
            "desk pad mousepad large extended",
            "cable management sleeve wrap desk",
            "monitor riser stand desk organizer",
            "mesh desk organizer file tray",
            "sticky note dispenser acrylic",
            "document tray letter holder stackable",
        ],
    },
    "sports": {
        "icon": "💪",
        "label": "Sports & Fitness",
        "keywords": [
            "resistance bands set loop exercise",
            "foam roller deep tissue muscle",
            "jump rope speed bearing adult",
            "workout gloves grip gym weightlifting",
            "ab wheel roller core exercise",
            "knee compression sleeve support brace",
            "yoga mat thick non-slip exercise",
            "water bottle insulated stainless steel",
        ],
    },
    "toys": {
        "icon": "🧸",
        "label": "Toys & Hobbies",
        "keywords": [
            "fidget toy stress relief sensory",
            "magnetic tiles building blocks kids",
            "slime kit glitter fluffy DIY",
            "card game party family adults",
            "puzzle 1000 piece landscape adults",
            "kinetic sand mold set kids",
            "LED light up toy kids",
            "miniature painting model kit",
        ],
    },
    "baby": {
        "icon": "👶",
        "label": "Baby & Kids",
        "keywords": [
            "silicone teething toy baby",
            "toddler spill proof sippy cup",
            "kids storage bin toy organizer",
            "night light projector stars nursery",
            "diaper bag backpack large",
            "potty training seat insert toddler",
            "baby bath toy floating",
            "kids lunch box insulated bento",
        ],
    },
    "outdoor": {
        "icon": "🌿",
        "label": "Outdoor & Recreation",
        "keywords": [
            "camping lantern LED rechargeable",
            "hiking trekking poles collapsible",
            "hammock portable lightweight nylon",
            "waterproof dry bag backpack",
            "carabiner clip hook set outdoor",
            "tactical flashlight high lumen",
            "garden kneeling pad foam cushion",
            "paracord bracelet survival outdoor",
        ],
    },
}

# Legacy flat list — kept for backward compatibility
SCAN_CATEGORIES = [kw for cat in CATEGORIES.values() for kw in cat["keywords"]]

# ── Stop words ─────────────────────────────────────────────────
STOP_WORDS = {
    "for","the","a","an","in","of","with","and","or","to","on","at","by",
    "from","is","it","its","are","be","this","that","was","as","has","have",
    "had","not","but","so","if","do","did","can","will","may","new","get",
    "use","2pcs","3pcs","4pcs","2pack","3pack","pack","pcs","piece","lot",
    "usa","fast","free","ship","brand","item","great","best","top","high",
    "quality","super","ultra","pro","mini","max","plus","premium","x2","x3",
}

# ── Conflicting product-type pairs ─────────────────────────────
CONFLICTING_PAIRS = [
    ({"strip","strips","bar","bars","tape","ribbon","linear","panel"},
     {"puck","disc","round","circular","dome","bulb","ball","sphere"}),
    ({"wired","corded","3.5mm","aux","cable"},
     {"wireless","bluetooth","wifi","wi-fi","true wireless","tws"}),
    ({"glasses","spectacles","eyewear","frames"},
     {"goggles","visor","shield","mask"}),
    ({"floor","standing","freestanding"},
     {"desk","desktop","tabletop","clamp","clip"}),
]


# ── Filter helpers ─────────────────────────────────────────────

def is_branded(title: str) -> bool:
    title_lower = title.lower()
    for brand in BLOCKED_BRANDS:
        if re.search(r'\b' + re.escape(brand) + r'\b', title_lower):
            return True
    return False


def is_prohibited(title: str) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in PROHIBITED_KEYWORDS)


def is_refurbished(title: str) -> bool:
    bad = ["refurbished","refurb","used","pre-owned","preowned",
           "open box","open-box","parts only","for parts","damaged",
           "broken","as is","as-is","salvage","read description"]
    return any(b in title.lower() for b in bad)


def passes_filters(title: str) -> tuple[bool, str]:
    if not title or len(title) < 5:
        return False, "no title"
    if is_branded(title):
        return False, "branded product"
    if is_prohibited(title):
        return False, "prohibited category"
    if is_refurbished(title):
        return False, "refurbished/used"
    return True, "ok"


# ── Title similarity ───────────────────────────────────────────

def _tokenize(title: str) -> set:
    words = re.findall(r'\b[a-z0-9]+\b', title.lower())
    return {w for w in words if len(w) > 2 and w not in STOP_WORDS}


def title_similarity(ebay_title: str, amazon_title: str) -> int:
    """Jaccard similarity on meaningful words. Returns 0–100."""
    t1 = _tokenize(ebay_title)
    t2 = _tokenize(amazon_title)
    if not t1 or not t2:
        return 0
    union = len(t1 | t2)
    if union == 0:
        return 0
    return round(len(t1 & t2) / union * 100)


def has_conflicting_types(ebay_title: str, amazon_title: str) -> bool:
    e = ebay_title.lower()
    a = amazon_title.lower()
    for group_a, group_b in CONFLICTING_PAIRS:
        e_in_a = any(w in e for w in group_a)
        a_in_b = any(w in a for w in group_b)
        e_in_b = any(w in e for w in group_b)
        a_in_a = any(w in a for w in group_a)
        if e_in_a and a_in_b:
            return True
        if e_in_b and a_in_a:
            return True
    return False


def match_label(score: int) -> str:
    if score >= 60:
        return "great"
    if score >= 40:
        return "good"
    return "weak"


# ── Profit calculator ──────────────────────────────────────────

def calc_profit(amazon_cost: float, ebay_sell: float,
                ebay_fee_pct: float = 13.0, payment_fee_pct: float = 3.0,
                min_profit: float = 5.0) -> dict:
    total_fee_pct = ebay_fee_pct + payment_fee_pct
    fees   = round(ebay_sell * total_fee_pct / 100, 2)
    profit = round(ebay_sell - amazon_cost - fees, 2)
    roi    = round(profit / amazon_cost * 100, 1) if amazon_cost > 0 else 0
    return {
        "amazon_cost":  amazon_cost,
        "ebay_sell":    ebay_sell,
        "fees":         fees,
        "net_profit":   profit,
        "roi_pct":      roi,
        "profitable":   profit >= min_profit,
    }


# ── Amazon matcher ─────────────────────────────────────────────

async def find_amazon_match(ebay_title: str, max_cost: float) -> Optional[dict]:
    clean = re.sub(
        r'\b(new|fast|free|ship|usa|lot|pack|set|pcs|pc|brand|'
        r'seller|quality|wholesale|bulk|quantity|listing)\b',
        '', ebay_title, flags=re.I
    ).strip()
    clean = re.sub(r'\s+', ' ', clean).strip()[:60]

    try:
        results = await amz_search(clean, max_results=5)  # 5 is enough; fewer = faster
        await asyncio.sleep(0.3)

        scored = []
        for r in results:
            cost = r.get("source_price")
            if not cost or cost <= 0:
                continue
            if cost >= max_cost:
                continue
            amz_title = r.get("title", "")
            ok, _ = passes_filters(amz_title)
            if not ok:
                continue
            if has_conflicting_types(ebay_title, amz_title):
                log.debug(f"Type conflict: '{ebay_title[:40]}' ≠ '{amz_title[:40]}'")
                continue
            sim = title_similarity(ebay_title, amz_title)
            if sim < 28:
                log.debug(f"Low sim {sim}%: '{ebay_title[:40]}' ≠ '{amz_title[:40]}'")
                continue
            scored.append((sim, cost, r))

        if not scored:
            return None

        scored.sort(key=lambda x: (-x[0], x[1]))
        best_sim, _, best = scored[0]
        best["_match_score"] = best_sim
        return best

    except Exception as e:
        log.error(f"Amazon match error for '{ebay_title[:40]}': {e}")
        return None


# ── eBay Scout (fast, eBay-only) ───────────────────────────────

async def scout_keyword(ebay_client: eBayClient, keywords: str) -> list:
    """
    Enhanced eBay-only scout scan for one keyword set.
    Runs sold + active searches concurrently (same API, no extra cost).
    Returns up to MAX_PER_KW deduplicated listings with full market stats.
    """
    MAX_PER_KW = 3   # max distinct results per keyword set

    results         = []
    kept_token_sets = []

    try:
        # ── Run sold + active searches at the same time ────────────
        sold, active = await asyncio.gather(
            ebay_client.search_sold(keywords, limit=50),
            ebay_client.search_active(keywords, limit=5),   # only need .total
        )

        items      = sold.get("items", [])
        avg_sold   = sold.get("avg_price")
        total_sold = sold.get("total", 0)        # total sold on all of eBay
        active_cnt = active.get("total", 0)      # total active listings on eBay

        if not avg_sold or avg_sold < 8:
            return []

        avg_sell_price = round(avg_sold * 0.95, 2)

        # ── Market stats from 50 sold items ────────────────────────
        prices = [i["price"] for i in items if i.get("price")]
        price_min = round(min(prices), 2) if prices else avg_sold
        price_max = round(max(prices), 2) if prices else avg_sold

        sellers = [i["seller"] for i in items if i.get("seller")]
        unique_sellers = len(set(sellers))

        conds   = [i.get("condition", "").lower() for i in items]
        new_pct = round(sum(1 for c in conds if "new" in c) / len(conds) * 100) if conds else 0

        # ── Estimated profit range (no Amazon price yet) ───────────
        # Assumes Amazon costs 55–72 % of eBay sell price for unbranded generics
        # Fees = 16 % of sell price (13 % eBay + 3 % payment)
        # Pessimistic: cost = 72 % → profit = sell × (1 - 0.72 - 0.16) = sell × 0.12
        # Optimistic : cost = 55 % → profit = sell × (1 - 0.55 - 0.16) = sell × 0.29
        est_profit_low  = round(avg_sell_price * 0.12, 2)
        est_profit_high = round(avg_sell_price * 0.29, 2)
        est_roi_low     = round(est_profit_low  / (avg_sell_price * 0.72) * 100)
        est_roi_high    = round(est_profit_high / (avg_sell_price * 0.55) * 100)

        # ── Demand tier ────────────────────────────────────────────
        if   total_sold >= 500: demand = "hot"
        elif total_sold >= 100: demand = "good"
        elif total_sold >= 20:  demand = "moderate"
        else:                   demand = "low"

        # ── Competition tier ───────────────────────────────────────
        if   active_cnt < 30:  competition = "low"
        elif active_cnt < 150: competition = "medium"
        else:                  competition = "high"

        # ── Opportunity score 0–100 (higher = better) ─────────────
        demand_pts = min(50, round(total_sold / 20))      # up to 50 pts for demand
        comp_pts   = 30 if competition == "low" else 15 if competition == "medium" else 0
        new_pts    = round(new_pct / 5)                   # up to 20 pts for new %
        opp_score  = min(100, demand_pts + comp_pts + new_pts)

        # ── Pick up to MAX_PER_KW unique items ─────────────────────
        for item in items[:50]:
            if len(results) >= MAX_PER_KW:
                break

            title = item.get("title", "")
            if not title:
                continue
            ok, _ = passes_filters(title)
            if not ok:
                continue

            tokens = _tokenize(title)
            too_similar = False
            for existing in kept_token_sets:
                union = len(tokens | existing)
                if union > 0 and len(tokens & existing) / union > 0.50:
                    too_similar = True
                    break
            if too_similar:
                continue

            kept_token_sets.append(tokens)
            results.append({
                # ── Core ───────────────────────────────────────────
                "ebay_title":        title,
                "ebay_item_url":     item.get("item_url", ""),
                "ebay_search_url":   (
                    "https://www.ebay.com/sch/i.html?_nkw="
                    + urllib.parse.quote(title[:80])
                    + "&LH_Sold=1&LH_Complete=1"
                ),
                "amazon_search_url": (
                    "https://www.amazon.com/s?k="
                    + urllib.parse.quote(title[:60])
                ),
                "image":             item.get("image", ""),
                "category":          keywords,
                # ── Pricing ────────────────────────────────────────
                "ebay_avg_sold":     avg_sold,
                "ebay_sell_price":   avg_sell_price,
                "price_min":         price_min,
                "price_max":         price_max,
                # ── Market intel ───────────────────────────────────
                "total_sold":        total_sold,
                "active_listings":   active_cnt,
                "unique_sellers":    unique_sellers,
                "new_pct":           new_pct,
                "demand":            demand,
                "competition":       competition,
                "opp_score":         opp_score,
                # ── Estimated profit (rough — no Amazon data yet) ──
                "est_profit_low":    est_profit_low,
                "est_profit_high":   est_profit_high,
                "est_roi_low":       est_roi_low,
                "est_roi_high":      est_roi_high,
            })

    except Exception as e:
        log.error(f"scout_keyword '{keywords}' error: {e}")
    return results


# ── Full scan (eBay + Amazon) ──────────────────────────────────

async def scan_category(ebay_client: eBayClient, keywords: str,
                        ebay_fee_pct: float, payment_fee_pct: float,
                        min_profit: float) -> list:
    """
    Full scan — eBay sold → Amazon cross-check → profit calc.
    Uses avg_sold × 0.95 as the consistent sell price for all calcs.
    """
    opportunities = []
    try:
        sold = await ebay_client.search_sold(keywords, limit=50)
        items = sold.get("items", [])
        avg_sold = sold.get("avg_price")

        if not avg_sold or avg_sold < 10:
            return []

        avg_sell_price = round(avg_sold * 0.95, 2)

        # ── Full scan: check at most 12 eBay items against Amazon.
        # More than that risks Amazon blocking mid-scan.
        # If Amazon returns nothing 4 times in a row, it's blocked — bail early.
        consecutive_misses = 0
        MISS_LIMIT         = 4   # bail if Amazon blanks 4 items in a row
        ITEM_LIMIT         = 12  # max eBay items to check per keyword

        for item in items[:ITEM_LIMIT]:
            title = item.get("title", "")
            if not title:
                continue

            ok, reason = passes_filters(title)
            if not ok:
                log.debug(f"Filtered '{title[:40]}' — {reason}")
                continue

            amz = await find_amazon_match(title, avg_sell_price)
            if not amz:
                consecutive_misses += 1
                if consecutive_misses >= MISS_LIMIT:
                    log.warning(f"Amazon returning nothing for '{keywords[:30]}' — likely blocked. Stopping early.")
                    break
                continue
            consecutive_misses = 0  # reset on success

            amazon_cost = amz.get("source_price")
            if not amazon_cost:
                continue

            match_score = amz.get("_match_score", 0)

            profit_data = calc_profit(
                amazon_cost, avg_sell_price, ebay_fee_pct, payment_fee_pct, min_profit
            )

            if not profit_data["profitable"]:
                continue

            ebay_search_url = (
                "https://www.ebay.com/sch/i.html?_nkw="
                + urllib.parse.quote(title[:80])
                + "&LH_Sold=1&LH_Complete=1"
            )
            opportunities.append({
                "ebay_title":      title,
                "ebay_item_url":   item.get("item_url", ""),
                "ebay_search_url": ebay_search_url,
                "amazon_title":    amz.get("title", ""),
                "amazon_asin":     amz.get("source_id", ""),
                "amazon_cost":     amazon_cost,
                "amazon_url":      f"https://www.amazon.com/dp/{amz.get('source_id', '')}",
                "amazon_rating":   amz.get("rating", 0),
                "amazon_reviews":  amz.get("review_count", 0),
                "ebay_avg_sold":   avg_sold,
                "ebay_sell_price": avg_sell_price,
                "match_score":     match_score,
                "match_label":     match_label(match_score),
                "image_urls":      amz.get("image_urls", []),
                **profit_data,
                "category":        keywords,
                "filter_passed":   True,
            })
            await asyncio.sleep(0.2)

    except Exception as e:
        log.error(f"scan_category '{keywords}' error: {e}")

    return opportunities


# ── Legacy entry point ─────────────────────────────────────────

async def run_auto_scan(max_categories: int = 5,
                        category_keywords: Optional[list] = None) -> dict:
    """
    Legacy blocking scan — kept for backward compatibility.
    Prefer the background-task approach via main.py.
    """
    ebay_fee  = float(get_setting("ebay_fee_pct", "13"))
    pay_fee   = float(get_setting("payment_fee_pct", "3"))
    min_prof  = float(get_setting("min_profit_usd", "5"))

    ebay = eBayClient(
        client_id          = get_setting("ebay_client_id"),
        client_secret      = get_setting("ebay_client_secret"),
        user_refresh_token = get_setting("ebay_refresh_token"),
    )

    if not ebay.is_configured():
        return {"error": "eBay API not configured. Add keys in Settings.", "results": []}

    keywords = category_keywords or SCAN_CATEGORIES[:max_categories]
    all_opps = []
    scanned  = 0

    for kw in keywords:
        log.info(f"Scanning: {kw}")
        opps = await scan_category(ebay, kw, ebay_fee, pay_fee, min_prof)
        scanned += 1
        all_opps.extend(opps)
        await asyncio.sleep(1.0)

    seen_asins = set()
    unique = []
    for o in all_opps:
        asin = o.get("amazon_asin", "")
        if asin and asin not in seen_asins:
            seen_asins.add(asin)
            unique.append(o)

    unique.sort(key=lambda x: (-x.get("match_score", 0), -x.get("roi_pct", 0)))

    return {
        "results":            unique[:50],
        "total_found":        len(unique),
        "categories_scanned": scanned,
        "scan_complete":      True,
    }
