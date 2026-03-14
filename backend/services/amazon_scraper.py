"""Amazon product scraper — requests + BeautifulSoup, no paid API."""
import httpx, asyncio, random, re, json, logging
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from typing import Optional

log = logging.getLogger("Amazon")

UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

def _hdrs():
    return {
        "User-Agent":                random.choice(UAS),
        "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language":           "en-US,en;q=0.9",
        "Accept-Encoding":           "gzip, deflate, br",
        "Referer":                   "https://www.google.com/",
        "DNT":                       "1",
        "Connection":                "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest":            "document",
        "Sec-Fetch-Mode":            "navigate",
        "Sec-Fetch-Site":            "none",
        "Sec-Fetch-User":            "?1",
        "Cache-Control":             "max-age=0",
    }

# ── CAPTCHA / block detection ──────────────────────────────────

def _is_blocked(soup: BeautifulSoup, text: str) -> bool:
    """Returns True if Amazon returned a CAPTCHA or bot-block page."""
    if soup.find("form", {"action": "/errors/validateCaptcha"}):
        return True
    if soup.find("input", {"id": "captchacharacters"}):
        return True
    title = soup.find("title")
    if title:
        t = title.get_text().lower()
        if "robot" in t or "captcha" in t or "sorry" in t or "blocked" in t:
            return True
    # Suspiciously short response with no products = likely blocked
    if len(text) < 2000:
        return True
    return False


# ── Single product fetch (by ASIN) ────────────────────────────

async def fetch_product(asin: str) -> Optional[dict]:
    url = f"https://www.amazon.com/dp/{asin}"
    await asyncio.sleep(random.uniform(1.0, 2.5))
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
        try:
            r = await c.get(url, headers=_hdrs())
            if r.status_code != 200:
                log.debug(f"Amazon {asin} HTTP {r.status_code}")
                return None

            soup = BeautifulSoup(r.text, "lxml")
            if _is_blocked(soup, r.text):
                log.warning(f"Amazon blocked/CAPTCHA for ASIN {asin}")
                return None

            title_el = soup.select_one("#productTitle")
            title = title_el.get_text(strip=True) if title_el else None
            if not title:
                return None

            price = None
            for sel in ["span.a-offscreen", "#priceblock_ourprice",
                        "#priceblock_dealprice", ".a-price .a-offscreen"]:
                el = soup.select_one(sel)
                if el:
                    m = re.search(r"[\d.]+", el.get_text().replace(",", ""))
                    if m:
                        price = float(m.group())
                        break

            image = None
            img_el = soup.select_one("#landingImage")
            if img_el:
                image = img_el.get("data-old-hires") or img_el.get("src")

            rating, reviews = 0.0, 0
            rat_el = soup.select_one("#acrPopover")
            if rat_el:
                m = re.search(r"([\d.]+)\s+out", rat_el.get("title", ""))
                if m: rating = float(m.group(1))
            rev_el = soup.select_one("#acrCustomerReviewText")
            if rev_el:
                m = re.search(r"([\d,]+)", rev_el.get_text())
                if m: reviews = int(m.group(1).replace(",", ""))

            brand = ""
            brand_el = soup.select_one("#bylineInfo")
            if brand_el:
                brand = re.sub(r"^(Brand:|Visit the|Store)", "",
                               brand_el.get_text(strip=True)).strip()

            category = "General"
            bc = soup.select("#wayfinding-breadcrumbs_container li")
            if bc: category = bc[-1].get_text(strip=True)

            avail_el = soup.select_one("#availability span")
            in_stock = True
            if avail_el:
                txt = avail_el.get_text().lower()
                in_stock = "in stock" in txt or "only" in txt

            return {
                "source_id":    asin,
                "supplier":     "amazon",
                "title":        title,
                "source_price": price,
                "image_urls":   [image] if image else [],
                "category":     category,
                "brand":        brand,
                "rating":       rating,
                "review_count": reviews,
                "in_stock":     in_stock,
                "source_url":   url,
                "description":  f"{brand} {title}".strip(),
            }
        except httpx.TimeoutException:
            log.warning(f"Amazon fetch timeout for {asin}")
            return None
        except Exception as e:
            log.error(f"Amazon scrape {asin}: {e}")
            return None


# ── Search (used by auto-scanner) ─────────────────────────────

async def search(keywords: str, max_results: int = 10) -> list:
    """
    Search Amazon for keywords. Returns up to max_results products.
    Timeout: 8s — fails fast if Amazon is blocking rather than hanging.
    """
    url = f"https://www.amazon.com/s?k={quote_plus(keywords)}"
    await asyncio.sleep(random.uniform(0.6, 1.4))   # shorter delay, still looks human

    async with httpx.AsyncClient(timeout=8, follow_redirects=True) as c:
        try:
            r = await c.get(url, headers=_hdrs())

            if r.status_code != 200:
                log.debug(f"Amazon search HTTP {r.status_code} for '{keywords[:40]}'")
                return []

            soup = BeautifulSoup(r.text, "lxml")

            if _is_blocked(soup, r.text):
                log.warning(f"Amazon blocked/CAPTCHA on search '{keywords[:40]}'")
                return []

            results = []
            for item in soup.select("[data-asin]"):
                asin = item.get("data-asin", "").strip()
                if not asin or len(asin) != 10:
                    continue

                title_el = item.select_one("h2 span")
                price_el = item.select_one("span.a-offscreen")
                img_el   = item.select_one("img.s-image")
                rat_el   = item.select_one("span.a-icon-alt")

                title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    continue

                price = None
                if price_el:
                    m = re.search(r"[\d.]+", price_el.get_text().replace(",", ""))
                    if m: price = float(m.group())

                rating = 0.0
                if rat_el:
                    m = re.search(r"([\d.]+)\s+out", rat_el.get_text())
                    if m: rating = float(m.group(1))

                if asin and title and price:
                    results.append({
                        "source_id":    asin,
                        "supplier":     "amazon",
                        "title":        title,
                        "source_price": price,
                        "image_urls":   [img_el.get("src")] if img_el else [],
                        "rating":       rating,
                        "review_count": 0,
                        "in_stock":     True,
                    })

                if len(results) >= max_results:
                    break

            log.debug(f"Amazon search '{keywords[:40]}' → {len(results)} results")
            return results

        except httpx.TimeoutException:
            log.warning(f"Amazon search timeout for '{keywords[:40]}'")
            return []
        except Exception as e:
            log.error(f"Amazon search error '{keywords[:40]}': {e}")
            return []
