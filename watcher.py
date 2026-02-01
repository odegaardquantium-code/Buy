from __future__ import annotations
import asyncio
from typing import Any, Optional, Dict, List
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from db import DB
from clients import GeckoTerminal, DexScreener, HttpClient
from formatter import format_buy_message

def build_keyboard(book_trend_url: str, trending_url: str, dtrade_url: str) -> InlineKeyboardMarkup:
    row = []
    if book_trend_url:
        row.append(InlineKeyboardButton(text="Book Trend", url=book_trend_url))
    if trending_url:
        row.append(InlineKeyboardButton(text="Trending", url=trending_url))
    if dtrade_url:
        row.append(InlineKeyboardButton(text="Buy with dTrade", url=dtrade_url))
    return InlineKeyboardMarkup(inline_keyboard=[row]) if row else InlineKeyboardMarkup(inline_keyboard=[])

def _safe_float(x) -> Optional[float]:
    try:
        if x is None: return None
        return float(x)
    except Exception:
        return None

def _safe_int(x) -> Optional[int]:
    try:
        if x is None: return None
        return int(x)
    except Exception:
        return None

def _parse_pool_symbols(pdata: dict):
    try:
        data = pdata.get("data") or {}
        rel = data.get("relationships") or {}
        base_id = ((rel.get("base_token") or {}).get("data") or {}).get("id")
        quote_id = ((rel.get("quote_token") or {}).get("data") or {}).get("id")
        included = pdata.get("included") or []
        id_to_sym = {}
        for item in included:
            if (item.get("type") == "token") and item.get("id"):
                sym = (item.get("attributes") or {}).get("symbol")
                id_to_sym[item["id"]] = sym
        return (id_to_sym.get(base_id) or "", id_to_sym.get(quote_id) or "")
    except Exception:
        return ("", "")

class BuyWatcher:
    def __init__(
        self,
        bot: Bot,
        db: DB,
        network: str,
        poll_seconds: int,
        stats_refresh_seconds: int,
        defaults: Dict[str, str],
        trending_post_chat_id: int = 0,
    ):
        self.bot = bot
        self.db = db
        self.network = network
        self.poll_seconds = max(5, poll_seconds)
        self.stats_refresh_seconds = max(60, stats_refresh_seconds)
        self.defaults = defaults
        self.trending_post_chat_id = trending_post_chat_id
        self._stop = asyncio.Event()

    async def stop(self):
        self._stop.set()

    async def run(self):
        async with HttpClient() as http:
            gt = GeckoTerminal(http)
            ds = DexScreener(http)

            last_stats_refresh = 0.0

            while not self._stop.is_set():
                pools = self.db.list_active_pools()

                if not pools:
                    await asyncio.sleep(self.poll_seconds)
                    continue

                # refresh cached stats periodically (one pool per loop to limit rate)
                now = asyncio.get_event_loop().time()
                do_stats = (now - last_stats_refresh) >= self.stats_refresh_seconds

                for p in pools:
                    pool_address = p["pool_address"]

                    # Stats refresh (best-effort)
                    if do_stats:
                        try:
                            pdata = await gt.pool(self.network, pool_address)
                            attrs = (pdata.get("data") or {}).get("attributes") or {}
                            bsym, qsym = _parse_pool_symbols(pdata)
                            if bsym or qsym:
                                self.db.upsert_pool(pool_address, base_symbol=bsym or (p["base_symbol"] or ""), quote_symbol=qsym or (p["quote_symbol"] or ""))
                            price_usd = _safe_float(attrs.get("base_token_price_usd"))
                            liquidity = _safe_float(attrs.get("reserve_in_usd"))
                            mcap = _safe_float(attrs.get("market_cap_usd")) or _safe_float(attrs.get("fdv_usd"))
                            fdv = _safe_float(attrs.get("fdv_usd"))
                            holders = _safe_int(attrs.get("holders"))
                            pchg = None
                            try:
                                pchg = _safe_float((attrs.get("price_change_percentage") or {}).get("h24"))
                            except Exception:
                                pchg = None
                            self.db.upsert_stats(pool_address,
                                                 price_usd=price_usd,
                                                 liquidity_usd=liquidity,
                                                 market_cap_usd=mcap,
                                                 fdv_usd=fdv,
                                                 holders=holders,
                                                 price_change_24h=pchg)
                        except Exception:
                            pass
                        last_stats_refresh = now
                        do_stats = False  # only 1 pool stats per cycle

                    # Trades polling
                    try:
                        tdata = await gt.trades(self.network, pool_address, limit=12)
                        trades = tdata.get("data") or []
                    except Exception:
                        trades = []

                    # trades are usually newest first; process oldest->newest excluding already seen
                    last_seen = p["last_trade_id"]
                    new_trades = []
                    for tr in trades:
                        tid = tr.get("id") or ""
                        if not tid:
                            continue
                        if last_seen and tid == last_seen:
                            break
                        new_trades.append(tr)
                    new_trades.reverse()

                    for tr in new_trades:
                        sent = await self._handle_trade(tr, p, ds)
                        # store last trade id regardless (prevents spam)
                        tid = tr.get("id")
                        if tid:
                            self.db.set_last_trade(pool_address, tid)

                await asyncio.sleep(self.poll_seconds)

    async def _handle_trade(self, tr: Any, pool_row: Any, ds: DexScreener) -> bool:
        attrs = tr.get("attributes") or {}

        # Only BUY trades (GeckoTerminal usually includes kind="buy"/"sell")
        kind = (attrs.get("kind") or attrs.get("trade_type") or "").lower()
        if kind and kind != "buy":
            return False

        tx_hash = attrs.get("tx_hash") or attrs.get("transaction_hash") or ""
        maker = attrs.get("from_address") or attrs.get("trader_address") or attrs.get("maker") or ""
        volume_usd = _safe_float(attrs.get("volume_in_usd") or attrs.get("trade_volume_in_usd") or attrs.get("amount_usd")) or 0.0

        base_amt = _safe_float(attrs.get("base_token_amount")) or 0.0
        quote_amt = _safe_float(attrs.get("quote_token_amount")) or 0.0

        base_symbol = (pool_row["base_symbol"] or "")
        quote_symbol = (pool_row["quote_symbol"] or "")
        symbol = (pool_row["symbol"] or base_symbol or "TOKEN")

        ton_amount = 0.0
        token_amount = 0.0
        if quote_symbol.upper() == "TON":
            ton_amount = abs(quote_amt)
            token_amount = abs(base_amt)
        elif base_symbol.upper() == "TON":
            ton_amount = abs(base_amt)
            token_amount = abs(quote_amt)
        else:
            ton_amount = abs(quote_amt)
            token_amount = abs(base_amt)

        pool_address = pool_row["pool_address"]
        gt_url = pool_row["gt_url"] or f"https://www.geckoterminal.com/ton/pools/{pool_address}"
        dexs_url = pool_row["dex_url"] or f"https://dexscreener.com/ton/{pool_address}"
        tx_url = f"https://tonviewer.com/transaction/{tx_hash}" if tx_hash else ""
        telegram_url = pool_row["telegram_url"] or ""

        token_ca = (pool_row["token_ca"] or "").strip()

        stats = self.db.get_stats(pool_address)
        price_usd = stats["price_usd"] if stats else None
        liquidity = stats["liquidity_usd"] if stats else None
        mcap = stats["market_cap_usd"] if stats else None
        holders = stats["holders"] if stats else None
        pchg = stats["price_change_24h"] if stats else None

        # Send to every group tracking this pool (with that group's button links)
        targets = self.db.group_targets_for_pool(pool_address)

        for t in targets:
            book_url = (t["book_trend_url"] or "") or self.defaults.get("book_trend_url", "")
            trending_url = (t["trending_url"] or "") or self.defaults.get("trending_url", "")
            dtrade_ref = (t["dtrade_ref"] or "") or self.defaults.get("dtrade_ref", "")

            dtrade_url = ""
            if token_ca and dtrade_ref:
                dtrade_url = f"https://t.me/dtrade?start={dtrade_ref}_{token_ca}"

            msg = format_buy_message(
                symbol=symbol,
                ton_amount=ton_amount,
                usd_value=volume_usd,
                token_amount=token_amount,
                buyer=maker or "",
                price_usd=price_usd,
                liquidity_usd=liquidity,
                mcap_usd=mcap,
                holders=holders,
                price_change_24h=pchg,
                tx_url=tx_url,
                gt_url=gt_url,
                dexs_url=dexs_url,
                telegram_url=telegram_url,
                trending_url=trending_url,
            )
            kb = build_keyboard(book_url, trending_url, dtrade_url)

            try:
                await self.bot.send_message(
                    chat_id=int(t["chat_id"]),
                    text=msg,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=kb
                )
            except Exception:
                # ignore per-chat send errors
                pass

        # Optional: also post to your main trending channel (global), if configured
        if self.trending_post_chat_id:
            dtrade_url = ""
            if token_ca and self.defaults.get("dtrade_ref"):
                dtrade_url = f"https://t.me/dtrade?start={self.defaults.get('dtrade_ref')}_{token_ca}"
            msg = format_buy_message(
                symbol=symbol,
                ton_amount=ton_amount,
                usd_value=volume_usd,
                token_amount=token_amount,
                buyer=maker or "",
                price_usd=price_usd,
                liquidity_usd=liquidity,
                mcap_usd=mcap,
                holders=holders,
                price_change_24h=pchg,
                tx_url=tx_url,
                gt_url=gt_url,
                dexs_url=dexs_url,
                telegram_url=telegram_url,
                trending_url=self.defaults.get("trending_url", ""),
            )
            kb = build_keyboard(self.defaults.get("book_trend_url", ""), self.defaults.get("trending_url", ""), dtrade_url)
            try:
                await self.bot.send_message(
                    chat_id=self.trending_post_chat_id,
                    text=msg,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=kb
                )
            except Exception:
                pass

        return True
