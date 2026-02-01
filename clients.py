import aiohttp
from typing import Any, Optional

class HttpClient:
    def __init__(self, timeout: int = 20):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=self.timeout, headers={
            "User-Agent": "TON-BuyBot/1.0 (Telegram)"
        })
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()

    async def get_json(self, url: str, params: Optional[dict[str, Any]] = None) -> Any:
        assert self.session is not None
        async with self.session.get(url, params=params) as r:
            r.raise_for_status()
            return await r.json()

class GeckoTerminal:
    BASE = "https://api.geckoterminal.com/api/v2"

    def __init__(self, http: HttpClient):
        self.http = http

    async def pool(self, network: str, pool_address: str) -> Any:
        url = f"{self.BASE}/networks/{network}/pools/{pool_address}"
        return await self.http.get_json(url, params={"include": "base_token,quote_token,dex"})

    async def trades(self, network: str, pool_address: str, limit: int = 20) -> Any:
        url = f"{self.BASE}/networks/{network}/pools/{pool_address}/trades"
        return await self.http.get_json(url, params={"limit": str(limit)})


    async def token_pools(self, network: str, token_address: str) -> Any:
        # Returns pools for a token; we pick the best (highest liquidity) when auto-adding from groups.
        url = f"{self.BASE}/networks/{network}/tokens/{token_address}/pools"
        return await self.http.get_json(url, params={"include": "dex"})

    async def token_info(self, network: str, token_address: str) -> Any:
        url = f"{self.BASE}/networks/{network}/tokens/{token_address}/info"
        return await self.http.get_json(url)

    async def pool_info(self, network: str, pool_address: str) -> Any:
        url = f"{self.BASE}/networks/{network}/pools/{pool_address}/info"
        return await self.http.get_json(url)

class DexScreener:
    # Not officially documented fully, but widely used.
    BASE = "https://api.dexscreener.com/latest/dex"

    def __init__(self, http: HttpClient):
        self.http = http

    async def pair(self, chain: str, pair_address: str) -> Any:
        url = f"{self.BASE}/pairs/{chain}/{pair_address}"
        return await self.http.get_json(url)

    async def token_pairs(self, chain: str, token_address: str) -> Any:
        # common endpoint used by many bots
        url = f"https://api.dexscreener.com/token-pairs/v1/{chain}/{token_address}"
        return await self.http.get_json(url)
