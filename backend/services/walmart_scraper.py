"""Walmart scraper — requests + BeautifulSoup, no paid API."""
import httpx, asyncio, random, re, json, logging
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from typing import Optional

log = logging.getLogger("Walmart")

UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
]

def _hdrs():
    return {
        "User-Agent": random.choice(UAS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    }

async def fetch_product(item_id: str) -> Optional[dict]:
    url = f"https://www.walmart.com/ip/{item_id}"
    await asyncio.sleep(random.uniform(1.0, 2.5))
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
        try:
            r = await c.get(url, headers=_hdrs())
            if r.status_code != 200: return None
            soup = BeautifulSoup(r.text, "lxml")
            script = soup.find("script", {"id": "__NEXT_DATA__"})
            if script:
                data = json.loads(script.string)
                p = (data.get("props",{}).get("pageProps",{})
                     .get("initialData",{}).get("data",{}).get("product",{}))
                if p:
                    imgs = [i.get("url") for i in (p.get("imageInfo",{}).get("allImages") or [])[:3] if i.get("url")]
                    return {
                        "source_id": item_id, "supplier": "walmart",
                        "title": p.get("name",""),
                        "source_price": p.get("priceInfo",{}).get("currentPrice",{}).get("price"),
                        "image_urls": imgs,
                        "category": p.get("category",{}).get("name","General"),
                        "brand": p.get("brand",""),
                        "rating": float(p.get("averageRating",0)),
                        "review_count": int(p.get("numberOfReviews",0)),
                        "in_stock": p.get("availabilityStatus","IN_STOCK") == "IN_STOCK",
                        "source_url": url,
                        "description": p.get("name",""),
                    }
        except Exception as e:
            log.error(f"Walmart scrape {item_id}: {e}")
    return None

async def search(keywords: str, max_results: int = 20) -> list:
    url = f"https://www.walmart.com/search?q={quote_plus(keywords)}"
    await asyncio.sleep(random.uniform(0.8, 2.0))
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
        try:
            r = await c.get(url, headers=_hdrs())
            soup = BeautifulSoup(r.text, "lxml")
            script = soup.find("script", {"id": "__NEXT_DATA__"})
            if not script: return []
            data = json.loads(script.string)
            items = (data.get("props",{}).get("pageProps",{})
                     .get("initialData",{}).get("searchResult",{})
                     .get("itemStacks",[{}])[0].get("items",[]))
            results = []
            for item in items:
                if item.get("__typename") != "Product": continue
                iid   = item.get("usItemId") or item.get("id")
                name  = item.get("name")
                price = item.get("priceInfo",{}).get("currentPrice",{}).get("price")
                thumb = item.get("imageInfo",{}).get("thumbnailUrl")
                if name and price and iid:
                    results.append({
                        "source_id": str(iid), "supplier": "walmart",
                        "title": name, "source_price": float(price),
                        "image_urls": [thumb] if thumb else [],
                        "rating": float(item.get("averageRating",0)),
                        "review_count": int(item.get("numberOfReviews",0)),
                        "in_stock": True,
                    })
                if len(results) >= max_results: break
            return results
        except Exception as e:
            log.error(f"Walmart search: {e}")
            return []
