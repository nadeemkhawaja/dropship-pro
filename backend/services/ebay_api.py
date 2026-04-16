"""
eBay API Client — Official REST APIs
Uses: Browse API (search/sold research) + Sell Inventory/Listing APIs
Auth: OAuth2 client credentials (app token) + user token with auto-refresh
"""
import httpx, base64, asyncio, logging, json
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger("eBayAPI")

EBAY_PROD = "https://api.ebay.com"
EBAY_AUTH = "https://api.ebay.com/identity/v1/oauth2/token"

BROWSE_SCOPE  = "https://api.ebay.com/oauth/api_scope"
SELL_SCOPES   = " ".join([
    "https://api.ebay.com/oauth/api_scope",
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly",
])


class eBayClient:
    def __init__(self, client_id: str, client_secret: str, user_refresh_token: str = ""):
        self.client_id      = client_id
        self.client_secret  = client_secret
        self.refresh_token  = user_refresh_token   # for sell APIs
        self._app_token     = None
        self._app_exp       = datetime.min
        self._user_token    = None
        self._user_exp      = datetime.min

    def _b64_creds(self):
        return base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()

    def is_configured(self):
        return bool(self.client_id and self.client_secret)

    # ── Token management ──────────────────────────────────────

    async def _get_app_token(self) -> str:
        """Client credentials — for Browse API (search/research)."""
        if self._app_token and datetime.utcnow() < self._app_exp:
            return self._app_token
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(EBAY_AUTH,
                headers={"Authorization": f"Basic {self._b64_creds()}",
                         "Content-Type": "application/x-www-form-urlencoded"},
                data={"grant_type": "client_credentials", "scope": BROWSE_SCOPE})
            data = r.json()
            if "access_token" not in data:
                raise RuntimeError(f"eBay app token error: {data}")
            self._app_token = data["access_token"]
            self._app_exp   = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 7200) - 60)
            log.info("✓ eBay app token refreshed")
            return self._app_token

    async def _get_user_token(self) -> str:
        """Refresh token flow — for Sell APIs (listing, inventory)."""
        if self._user_token and datetime.utcnow() < self._user_exp:
            return self._user_token
        if not self.refresh_token:
            raise RuntimeError("No eBay user refresh token configured. See Settings → eBay Setup Guide.")
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(EBAY_AUTH,
                headers={"Authorization": f"Basic {self._b64_creds()}",
                         "Content-Type": "application/x-www-form-urlencoded"},
                data={"grant_type": "refresh_token",
                      "refresh_token": self.refresh_token,
                      "scope": SELL_SCOPES})
            data = r.json()
            if "access_token" not in data:
                raise RuntimeError(f"eBay user token error: {data}")
            self._user_token = data["access_token"]
            self._user_exp   = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 7200) - 60)
            log.info("✓ eBay user token refreshed")
            return self._user_token

    async def _app_headers(self):
        return {"Authorization": f"Bearer {await self._get_app_token()}",
                "Content-Type": "application/json", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}

    async def _user_headers(self):
        return {"Authorization": f"Bearer {await self._get_user_token()}",
                "Content-Type": "application/json", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}

    # ── Browse API — Search & Research ────────────────────────

    async def search_sold(self, keywords: str, limit: int = 20) -> dict:
        """
        Search eBay sold/completed listings via Browse API.
        Returns average sold price + list of results.
        """
        headers = await self._app_headers()
        params = {
            "q": keywords,
            "limit": limit,
            "filter": "buyingOptions:{FIXED_PRICE},conditionIds:{1000|1500|2000|2500|3000}",
            "sort": "endedDateDesc",
        }
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{EBAY_PROD}/buy/browse/v1/item_summary/search",
                            headers=headers, params=params)
        if r.status_code != 200:
            log.warning(f"eBay search_sold: {r.status_code} {r.text[:200]}")
            return {"items": [], "avg_price": None}

        data   = r.json()
        items  = data.get("itemSummaries", [])
        prices = [float(i["price"]["value"]) for i in items if i.get("price")]
        avg    = round(sum(prices) / len(prices), 2) if prices else None

        return {
            "items": [{
                "title":      i.get("title"),
                "price":      float(i["price"]["value"]) if i.get("price") else None,
                "condition":  i.get("condition"),
                "image":      i.get("image", {}).get("imageUrl"),
                "item_url":   i.get("itemWebUrl"),
                "seller":     i.get("seller", {}).get("username"),
            } for i in items],
            "avg_price":  avg,
            "total":      data.get("total", 0),
        }

    async def search_active(self, keywords: str, limit: int = 20) -> dict:
        """Search active eBay BIN listings."""
        headers = await self._app_headers()
        params  = {"q": keywords, "limit": limit,
                   "filter": "buyingOptions:{FIXED_PRICE}", "sort": "price"}
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{EBAY_PROD}/buy/browse/v1/item_summary/search",
                            headers=headers, params=params)
        data  = r.json() if r.status_code == 200 else {}
        items = data.get("itemSummaries", [])
        return {
            "items": [{
                "title":    i.get("title"),
                "price":    float(i["price"]["value"]) if i.get("price") else None,
                "shipping": i.get("shippingOptions", [{}])[0].get("shippingCost", {}).get("value", "Free"),
                "image":    i.get("image", {}).get("imageUrl"),
                "item_url": i.get("itemWebUrl"),
                "seller":   i.get("seller", {}).get("username"),
                "watchers": i.get("watchCount", 0),
            } for i in items],
            "total": data.get("total", 0),
        }

    async def search_category_best(self, ebay_category_id: str, limit: int = 200,
                                   min_price: float = 5.0, max_price: float = 50.0) -> dict:
        """
        Search top BIN listings in an eBay category sorted by bestMatch.
        bestMatch is weighted by purchase activity — proxy for best-selling products.
        Returns up to 200 results (eBay hard limit per request).
        """
        headers = await self._app_headers()
        params = {
            "category_ids": ebay_category_id,
            "filter": f"buyingOptions:{{FIXED_PRICE}},price:[{min_price}..{max_price}],priceCurrency:USD",
            "sort":   "bestMatch",
            "limit":  min(limit, 200),
        }
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{EBAY_PROD}/buy/browse/v1/item_summary/search",
                            headers=headers, params=params)
        if r.status_code != 200:
            log.warning(f"search_category_best {ebay_category_id}: {r.status_code} {r.text[:200]}")
            return {"items": [], "total": 0}
        data  = r.json()
        items = data.get("itemSummaries", [])
        return {
            "items": [{
                "title":     i.get("title"),
                "price":     float(i["price"]["value"]) if i.get("price") else None,
                "image":     i.get("image", {}).get("imageUrl"),
                "item_url":  i.get("itemWebUrl"),
                "seller":    i.get("seller", {}).get("username"),
                "condition": i.get("condition"),
                "watchers":  i.get("watchCount", 0),
                "sold_qty":  i.get("soldQuantity", 0),
            } for i in items],
            "total": data.get("total", 0),
        }

    async def search_by_seller(self, seller_username: str, limit: int = 60,
                               ebay_category_id: str = None) -> dict:
        """Get a seller's active BIN listings priced $5–$50.
        Uses category_ids=0 (undocumented eBay wildcard) to avoid requiring q.
        """
        headers = await self._app_headers()
        filter_str = (
            f"sellers:{{{seller_username}}},"
            "buyingOptions:{FIXED_PRICE},"
            "price:[5..50],priceCurrency:USD"
        )
        params = {
            "category_ids": ebay_category_id or "0",
            "filter": filter_str,
            "sort":   "bestMatch",
            "limit":  limit,
        }
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{EBAY_PROD}/buy/browse/v1/item_summary/search",
                            headers=headers, params=params)
        if r.status_code != 200:
            log.warning(f"search_by_seller {seller_username}: {r.status_code} {r.text[:200]}")
            return {"items": [], "total": 0}
        data  = r.json()
        items = data.get("itemSummaries", [])
        return {
            "items": [{
                "title":     i.get("title"),
                "price":     float(i["price"]["value"]) if i.get("price") else None,
                "image":     i.get("image", {}).get("imageUrl"),
                "item_url":  i.get("itemWebUrl"),
                "seller":    i.get("seller", {}).get("username"),
                "condition": i.get("condition"),
                "watchers":  i.get("watchCount", 0),
            } for i in items],
            "total": data.get("total", 0),
        }

    async def get_item(self, item_id: str) -> dict:
        """Get single eBay item details."""
        headers = await self._app_headers()
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{EBAY_PROD}/buy/browse/v1/item/{item_id}", headers=headers)
        return r.json() if r.status_code == 200 else {}

    # ── Sell Inventory API — Create Listings ──────────────────

    async def create_inventory_item(self, sku: str, product: dict) -> bool:
        """Create/update an inventory item (product record)."""
        headers = await self._user_headers()
        payload = {
            "availability": {
                "shipToLocationAvailability": {"quantity": 100}
            },
            "condition": "NEW",
            "product": {
                "title":       product["title"][:80],
                "description": product.get("description", product["title"]),
                "aspects":     {"Brand": [product.get("brand", "Unbranded")]},
                "imageUrls":   product.get("image_urls", [])[:12],
            }
        }
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.put(
                f"{EBAY_PROD}/sell/inventory/v1/inventory_item/{sku}",
                headers=headers, json=payload)
        if r.status_code not in (200, 204):
            log.error(f"create_inventory_item {sku}: {r.status_code} {r.text[:300]}")
            return False
        return True

    async def create_offer(self, sku: str, price: float, category_id: str = "175672",
                           policy_ids: dict = None) -> Optional[str]:
        """Create a fixed-price offer for an inventory item. Returns offer_id."""
        headers = await self._user_headers()
        payload = {
            "sku":             sku,
            "marketplaceId":   "EBAY_US",
            "format":          "FIXED_PRICE",
            "availableQuantity": 100,
            "categoryId":      category_id,
            "listingDescription": f"Brand new item — fast US shipping — satisfaction guaranteed",
            "pricingSummary": {
                "price": {"value": str(round(price, 2)), "currency": "USD"}
            },
            "listingDuration": "GTC",
            "merchantLocationKey": "warehouse1",
        }
        if policy_ids:
            payload["listingPolicies"] = {
                "fulfillmentPolicyId": policy_ids.get("fulfillment", ""),
                "paymentPolicyId":     policy_ids.get("payment", ""),
                "returnPolicyId":      policy_ids.get("return", ""),
            }
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{EBAY_PROD}/sell/inventory/v1/offer",
                             headers=headers, json=payload)
        data = r.json()
        if r.status_code not in (200, 201):
            log.error(f"create_offer {sku}: {r.status_code} {data}")
            return None
        return data.get("offerId")

    async def publish_offer(self, offer_id: str) -> Optional[str]:
        """Publish offer → creates live eBay listing. Returns listing_id."""
        headers = await self._user_headers()
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{EBAY_PROD}/sell/inventory/v1/offer/{offer_id}/publish",
                             headers=headers)
        data = r.json()
        if r.status_code not in (200, 201):
            log.error(f"publish_offer {offer_id}: {r.status_code} {data}")
            return None
        return data.get("listingId")

    async def end_listing(self, listing_id: str) -> bool:
        """End/pause an active listing."""
        headers = await self._user_headers()
        # Use the Trading API endpoint for ending items
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.delete(
                f"{EBAY_PROD}/sell/inventory/v1/offer/{listing_id}",
                headers=headers)
        return r.status_code in (200, 204)

    async def get_my_orders(self, limit: int = 50) -> list:
        """Fetch seller's recent orders via Fulfillment API."""
        headers = await self._user_headers()
        params  = {"limit": limit, "ordersFulfillmentStatus": "NOT_STARTED"}
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{EBAY_PROD}/sell/fulfillment/v1/order",
                            headers=headers, params=params)
        if r.status_code != 200:
            return []
        data = r.json()
        orders = []
        for o in data.get("orders", []):
            item = (o.get("lineItems") or [{}])[0]
            addr = o.get("fulfillmentStartInstructions", [{}])[0].get("shippingStep", {}).get("shipTo", {})
            orders.append({
                "order_id":    o.get("orderId"),
                "status":      o.get("orderFulfillmentStatus"),
                "buyer":       o.get("buyer", {}).get("username"),
                "item_title":  item.get("title"),
                "quantity":    item.get("quantity", 1),
                "sell_price":  float(o.get("pricingSummary", {}).get("total", {}).get("value", 0)),
                "ship_name":   addr.get("fullName"),
                "ship_addr1":  addr.get("contactAddress", {}).get("addressLine1"),
                "ship_city":   addr.get("contactAddress", {}).get("city"),
                "ship_state":  addr.get("contactAddress", {}).get("stateOrProvince"),
                "ship_zip":    addr.get("contactAddress", {}).get("postalCode"),
                "created_at":  o.get("creationDate"),
            })
        return orders

    async def get_seller_policies(self) -> dict:
        """Fetch seller's fulfillment/payment/return policy IDs."""
        headers = await self._user_headers()
        result  = {}
        for ptype in ["fulfillment", "payment", "return"]:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"{EBAY_PROD}/sell/account/v1/{ptype}_policy",
                                headers=headers,
                                params={"marketplace_id": "EBAY_US"})
            if r.status_code == 200:
                policies = r.json().get(f"{ptype}Policies", [])
                if policies:
                    result[ptype] = policies[0].get(f"{ptype}PolicyId")
        return result
