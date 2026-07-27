import logging
import httpx
import re

logger = logging.getLogger(__name__)

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
UA = "VOYAGER-App/1.0 (India Transit Navigator)"

class ImageService:
    async def _wikipedia_image(self, name: str, client: httpx.AsyncClient) -> str | None:
        """Try to fetch image from Wikipedia."""
        for search_name in (f"{name} Bengaluru", f"{name}, Bengaluru", f"{name}, Bangalore", name):
            params = {
                "action": "query", "format": "json",
                "generator": "search" if "Bengaluru" in search_name or "Bangalore" in search_name else None,
                "prop": "pageimages",
                "pithumbsize": 400, "redirects": 1,
            }
            if params["generator"]:
                params["gsrsearch"] = search_name
                params["gsrlimit"] = 3
            else:
                params["titles"] = search_name
                del params["generator"]
            try:
                resp = await client.get(WIKIPEDIA_API, params=params)
                if resp.status_code == 200:
                    for pid, page in resp.json().get("query", {}).get("pages", {}).items():
                        if pid != "-1" and "thumbnail" in page:
                            return page["thumbnail"]["source"]
            except Exception:
                continue
        return None

    async def _ddg_image(self, name: str, client: httpx.AsyncClient) -> str | None:
        """DuckDuckGo image search fallback."""
        try:
            ddg_url = f"https://duckduckgo.com/i.js?q={name.replace(' ', '%20')}%20Bengaluru&o=json&p=1"
            resp = await client.get(ddg_url, headers={"User-Agent": UA})
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                if results and results[0].get("image"):
                    return results[0]["image"]
        except Exception as e:
            logger.debug(f"DuckDuckGo image fallback failed for {name}: {e}")
        return None

    async def get_place_image(self, name: str, place_type: str = None) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
                img = await self._wikipedia_image(name, client)
                if img:
                    return img
                img = await self._ddg_image(name, client)
                if img:
                    return img
        except Exception as e:
            logger.warning(f"Image fetch failed for {name}: {e}")
        return None

image_service = ImageService()
