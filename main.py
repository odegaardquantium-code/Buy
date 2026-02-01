import os
import re
import asyncio
import sqlite3
from typing import Optional, Dict, Any, List, Tuple

import httpx
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ChatMemberUpdated
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder

load_dotenv()

# -------------------------
# ENV
# -------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB_PATH = os.getenv("DB_PATH", "buybot.db").strip()

BOOK_TREND_URL = os.getenv("BOOK_TREND_URL", "https://t.me/SpyTONTrndBot").strip()
TRENDING_URL = os.getenv("TRENDING_URL", "https://t.me/SpyTonTrending").strip()

# DTrade referral start code
DTRADE_REF = os.getenv("DTRADE_REF", "11TYq7LInG").strip()

STON_BASE = os.getenv("STON_BASE", "https://api.ston.fi").strip()
DEDUST_BASE = os.getenv("DEDUST_BASE", "https://api.dedust.io").strip()

STON_BLOCK_CHUNK = int(os.getenv("STON_BLOCK_CHUNK", "200"))
LOOP_SLEEP = float(os.getenv("LOOP_SLEEP", "3.0"))

if not BOT_TOKEN:
    raise RuntimeError("Missing BOT_TOKEN in environment variables.")

# -------------------------
# Regex / helpers
# -------------------------
TON_ADDR_RE = re.compile(r"\b(EQ[A-Za-z0-9\-_]{30,80})\b")  # loose match for TON base64url addresses

def short_addr(addr: str, head: int = 4, tail: int = 4) -> str:
    if not addr or len(addr) <= head + tail + 3:
        return addr
    return f"{addr[:head]}…{addr[-tail:]}"

def fmt_num(x: float, decimals: int = 2) -> str:
    try:
        if x >= 1_000_000_000:
            return f"{x/1_000_000_000:.2f}B"
        if x >= 1_000_000:
            return f"{x/1_000_000:.2f}M"
        if x >= 1_000:
            return f"{x/1_000:.2f}K"
        return f"{x:.{decimals}f}"
    except Exception:
        return str(x)

def safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

def dots_for_usd(usd: float) -> str:
    # Buy strength dots (tweak if you want)
    if usd < 25: n = 6
    elif usd < 50: n = 10
    elif usd < 100: n = 16
    elif usd < 250: n = 22
    elif usd < 500: n = 28
    elif usd < 1000: n = 34
    else: n = 40

    dots = "🟢" * n
    if n > 20:
        return dots[:20] + "\n" + dots[20:]
    return dots

def tonviewer_tx_link(tx_hash: str) -> str:
    return f"https://tonviewer.com/transaction/{tx_hash}"

def geckoterminal_pool_link(pool_addr: str) -> str:
    # GeckoTerminal pool page
    return f"https://www.geckoterminal.com/ton/pools/{pool_addr}"

def dexscreener_pool_link(chain: str, pool_addr: str) -> str:
    return f"https://dexscreener.com/{chain}/{pool_addr}"

def build_dtrade_link(token_ca: str) -> str:
    # attach CA with referral
    return f"https://t.me/dtrade?start={DTRADE_REF}_{token_ca}"

def kb_for_post(token_symbol: str, token_ca: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="📌 Book Trend", url=BOOK_TREND_URL)
    kb.button(text="🔥 Trending", url=TRENDING_URL)
    kb.adjust(2)
    kb.button(text=f"🛒 Buy {token_symbol}", url=build_dtrade_link(token_ca))
    kb.adjust(1)
    return kb.as_markup()

def links_row(tx: str, gt: str, dexs: str, telegram: str, trending: str) -> str:
    parts = []
    if tx: parts.append(f"[Tx]({tx})")
    if gt: parts.append(f"[GT]({gt})")
    if dexs: parts.append(f"[DexS]({dexs})")
    if telegram: parts.append(f"[Telegram]({telegram})")
    if trending: parts.append(f"[Trending]({trending})")
    return " | ".join(parts)

def build_caption(
    token_name: str,
    dex_name: str,
    usd_value: float,
    base_amount: Optional[float],
    base_symbol: str,
    token_amount: Optional[float],
    token_symbol: str,
    price_usd: Optional[float],
    mcap_usd: Optional[float],
    liq_usd: Optional[float],
    trader: Optional[str],
    tx_hash: Optional[str],
    pool_addr: str,
    token_ca: str,
    token_tg: Optional[str],
) -> str:
    title = f"🟩 | {token_name}\n\n{token_name} Buy! — {dex_name}\n"
    dots = dots_for_usd(usd_value)

    lines = [title, dots, ""]
    if base_amount is not None:
        lines.append(f"💎 {fmt_num(base_amount, 2)} {base_symbol} (${fmt_num(usd_value, 2)})")
    else:
        lines.append(f"💎 ${fmt_num(usd_value, 2)}")

    if token_amount is not None:
        lines.append(f"🪙 {fmt_num(token_amount, 2)} {token_symbol}")

    if trader:
        lines.append(f"👤 {short_addr(trader)} | Tx")

    if price_usd is not None:
        lines.append(f"🏷️ Price: ${fmt_num(price_usd, 6)}")
    if mcap_usd is not None:
        lines.append(f"🏦 Market Cap ${fmt_num(mcap_usd, 2)}")
    if liq_usd is not None:
        lines.append(f"💧 Liquidity ${fmt_num(liq_usd, 2)}")

    lines.append(f"🔎 {short_addr(token_ca, 6, 4)}")

    pos = None
    if liq_usd and liq_usd > 0:
        pos = (usd_value / liq_usd) * 100.0
    if pos is not None:
        lines.append(f"⬆️ Position: {pos:.2f} %!")

    tx_link = tonviewer_tx_link(tx_hash) if tx_hash else ""
    gt_link = geckoterminal_pool_link(pool_addr) if pool_addr else ""
    dexs_link = dexscreener_pool_link("ton", pool_addr) if pool_addr else ""
    telegram_link = token_tg or ""
    trending_link = TRENDING_URL

    lines.append("")
    lines.append(links_row(tx_link, gt_link, dexs_link, telegram_link, trending_link))

    return "\n".join(lines).strip()

# -------------------------
# DB
# -------------------------
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db():
    conn = db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_pools (
        chat_id INTEGER NOT NULL,
        dex TEXT NOT NULL,
        pool_addr TEXT NOT NULL,
        token_addr TEXT,
        token_symbol TEXT,
        token_name TEXT,
        token_telegram TEXT,
        token_website TEXT,
        last_cursor TEXT,
        PRIMARY KEY (chat_id, dex, pool_addr)
    );
    """)
    conn.commit()
    conn.close()

def upsert_pool(chat_id: int, dex: str, pool_addr: str, meta: Dict[str, Any]):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO chat_pools (chat_id, dex, pool_addr, token_addr, token_symbol, token_name, token_telegram, token_website, last_cursor)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(chat_id, dex, pool_addr)
    DO UPDATE SET
        token_addr=excluded.token_addr,
        token_symbol=excluded.token_symbol,
        token_name=excluded.token_name,
        token_telegram=excluded.token_telegram,
        token_website=excluded.token_website;
    """, (
        chat_id, dex, pool_addr,
        meta.get("token_addr"), meta.get("token_symbol"), meta.get("token_name"),
        meta.get("token_telegram"), meta.get("token_website"),
        meta.get("last_cursor")
    ))
    conn.commit()
    conn.close()

def set_cursor(chat_id: int, dex: str, pool_addr: str, cursor_val: str):
    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE chat_pools SET last_cursor=? WHERE chat_id=? AND dex=? AND pool_addr=?;",
                (cursor_val, chat_id, dex, pool_addr))
    conn.commit()
    conn.close()

def list_pools(dex: str) -> List[Tuple]:
    conn = db()
    cur = conn.cursor()
    cur.execute("""
    SELECT chat_id, pool_addr, token_addr, token_symbol, token_name, token_telegram, token_website, last_cursor
    FROM chat_pools WHERE dex=?;
    """, (dex,))
    rows = cur.fetchall()
    conn.close()
    return rows

# -------------------------
# API helpers
# -------------------------
async def http_get_json(client: httpx.AsyncClient, url: str, params: Optional[dict] = None) -> Optional[dict]:
    try:
        r = await client.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None

# ---- STON.fi (DexScreener export) ----
async def ston_latest_block(client: httpx.AsyncClient) -> Optional[int]:
    # Common STON endpoint used by DexScreener export
    j = await http_get_json(client, f"{STON_BASE}/export/dexscreener/v1/latest-block")
    if j and isinstance(j.get("block"), dict) and "blockNumber" in j["block"]:
        return int(j["block"]["blockNumber"])

    # Fallback older path (some examples use /v1/screener/latest-block)
    j2 = await http_get_json(client, f"{STON_BASE}/v1/screener/latest-block")
    if j2 and isinstance(j2.get("block"), dict) and "blockNumber" in j2["block"]:
        return int(j2["block"]["blockNumber"])

    return None

async def ston_pair_info(client: httpx.AsyncClient, pool_addr: str) -> Optional[dict]:
    return await http_get_json(client, f"{STON_BASE}/export/dexscreener/v1/pair/{pool_addr}")

async def ston_asset_info(client: httpx.AsyncClient, asset_addr: str) -> Optional[dict]:
    return await http_get_json(client, f"{STON_BASE}/v1/assets/{asset_addr}")

async def ston_events(client: httpx.AsyncClient, from_block: int, to_block: int) -> Optional[dict]:
    return await http_get_json(
        client,
        f"{STON_BASE}/export/dexscreener/v1/events",
        params={"fromBlock": from_block, "toBlock": to_block}
    )

# ---- DeDust ----
async def dedust_pool_trades(client: httpx.AsyncClient, pool_addr: str, limit: int = 25) -> Optional[dict]:
    return await http_get_json(client, f"{DEDUST_BASE}/v2/pools/{pool_addr}/trades", params={"limit": limit})

# -------------------------
# Detect DEX from address
# -------------------------
async def detect_pool_dex(client: httpx.AsyncClient, pool_addr: str) -> Tuple[Optional[str], Dict[str, Any]]:
    # Try STON pair
    j = await ston_pair_info(client, pool_addr)
    if j and isinstance(j.get("pool"), dict):
        pool = j["pool"]
        asset0 = pool.get("asset0Id") or pool.get("asset0_id") or pool.get("asset0")
        asset1 = pool.get("asset1Id") or pool.get("asset1_id") or pool.get("asset1")

        token_asset = None
        # heuristic: prefer non-TON asset if possible (TON uses special representation sometimes)
        for a in (asset0, asset1):
            if isinstance(a, str) and a.startswith("EQ"):
                token_asset = a
                break

        symbol = None
        name = None
        tg = None
        web = None
        if token_asset:
            ainfo = await ston_asset_info(client, token_asset)
            if ainfo and isinstance(ainfo.get("asset"), dict):
                asset = ainfo["asset"]
                symbol = asset.get("symbol") or asset.get("ticker")
                name = asset.get("name") or symbol
                tg = asset.get("telegram") or asset.get("telegram_url")
                web = asset.get("website") or asset.get("website_url")

        meta = {
            "token_addr": token_asset,
            "token_symbol": symbol or "TOKEN",
            "token_name": name or (symbol or "Token"),
            "token_telegram": tg,
            "token_website": web,
        }
        return "ston", meta

    # Try DeDust trades endpoint (if responds, treat as DeDust pool)
    j2 = await dedust_pool_trades(client, pool_addr, limit=1)
    if j2 is not None:
        meta = {"token_addr": pool_addr, "token_symbol": "TOKEN", "token_name": "Token"}
        return "dedust", meta

    return None, {}

# -------------------------
# Telegram
# -------------------------
dp = Dispatcher()

@dp.message(CommandStart())
async def start_cmd(message: Message):
    await message.reply(
        "Send me a *STON.fi* or *DeDust* **pool address** (starts with `EQ...`) here.\n\n"
        "✅ No command needed: just paste the pool address once.\n"
        "Then I will start posting buy alerts here.",
        parse_mode=ParseMode.MARKDOWN
    )

@dp.chat_member()
async def on_chat_member(update: ChatMemberUpdated, bot: Bot):
    # greet when added
    try:
        me = await bot.me()
        if update.new_chat_member and update.new_chat_member.user and update.new_chat_member.user.is_bot:
            if update.new_chat_member.user.id == me.id:
                await bot.send_message(
                    update.chat.id,
                    "👋 BuyBot added!\n\n"
                    "Paste the *pool address* (STON.fi or DeDust) here and I’ll start posting buys.\n"
                    "Example: `EQD...`",
                    parse_mode=ParseMode.MARKDOWN
                )
    except Exception:
        pass

@dp.message(F.text)
async def handle_text(message: Message):
    text = (message.text or "").strip()
    m = TON_ADDR_RE.search(text)
    if not m:
        return

    pool_addr = m.group(1)
    chat_id = message.chat.id

    async with httpx.AsyncClient() as client:
        dex, meta = await detect_pool_dex(client, pool_addr)

        if not dex:
            await message.reply(
                "I found an address, but I couldn’t confirm if it’s a *STON.fi* or *DeDust* pool.\n\n"
                "✅ Paste the pool address again or send another pool address.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # set initial cursor
        if dex == "ston":
            lb = await ston_latest_block(client)
            meta["last_cursor"] = str(lb or 0)
        else:
            meta["last_cursor"] = ""

    upsert_pool(chat_id, dex, pool_addr, meta)

    await message.reply(
        f"✅ Tracking *{dex.upper()}* pool:\n`{pool_addr}`\n\n"
        "I’ll start posting buys automatically.",
        parse_mode=ParseMode.MARKDOWN
    )

# -------------------------
# Watchers
# -------------------------
async def ston_watcher(bot: Bot):
    async with httpx.AsyncClient() as client:
        while True:
            try:
                pools = list_pools("ston")
                if not pools:
                    await asyncio.sleep(LOOP_SLEEP)
                    continue

                latest = await ston_latest_block(client)
                if latest is None:
                    await asyncio.sleep(LOOP_SLEEP)
                    continue

                for (chat_id, pool_addr, token_addr, token_symbol, token_name, token_tg, token_web, last_cursor) in pools:
                    try:
                        last_block = int(last_cursor or "0")
                        if last_block <= 0:
                            last_block = max(latest - 5, 0)

                        start = last_block + 1
                        while start <= latest:
                            end = min(start + STON_BLOCK_CHUNK, latest)
                            ev = await ston_events(client, start, end)

                            if ev and isinstance(ev.get("events"), list):
                                for item in ev["events"]:
                                    # swaps only, correct pair only
                                    if item.get("eventType") != "swap":
                                        continue
                                    if str(item.get("pairId")) != str(pool_addr):
                                        continue

                                    usd_value = safe_float(item.get("volumeUsd") or item.get("volume_usd")) or 0.0
                                    tx_hash = item.get("txHash") or item.get("tx_hash") or item.get("hash")

                                    trader = item.get("maker") or item.get("trader") or item.get("from")

                                    token_amount = safe_float(item.get("tokenAmount") or item.get("token_amount") or item.get("amount1"))
                                    base_amount = safe_float(item.get("baseAmount") or item.get("base_amount") or item.get("amount0"))
                                    base_symbol = item.get("baseSymbol") or "TON"

                                    # enrich price/liq/mcap from pair endpoint (if available)
                                    price_usd = None
                                    liq_usd = None
                                    mcap_usd = None
                                    pair = await ston_pair_info(client, pool_addr)
                                    if pair and isinstance(pair.get("pool"), dict):
                                        p = pair["pool"]
                                        price_usd = safe_float(p.get("priceUsd") or p.get("price_usd"))
                                        liq_usd = safe_float(p.get("liquidityUsd") or p.get("liquidity_usd"))
                                        mcap_usd = safe_float(p.get("fdv") or p.get("marketCapUsd") or p.get("market_cap_usd"))

                                    caption = build_caption(
                                        token_name=token_name or "Token",
                                        dex_name="STON.fi",
                                        usd_value=usd_value,
                                        base_amount=base_amount,
                                        base_symbol=base_symbol,
                                        token_amount=token_amount,
                                        token_symbol=token_symbol or "TOKEN",
                                        price_usd=price_usd,
                                        mcap_usd=mcap_usd,
                                        liq_usd=liq_usd,
                                        trader=trader,
                                        tx_hash=tx_hash,
                                        pool_addr=pool_addr,
                                        token_ca=token_addr or pool_addr,
                                        token_tg=token_tg,
                                    )

                                    await bot.send_message(
                                        chat_id=chat_id,
                                        text=caption,
                                        parse_mode=ParseMode.MARKDOWN,
                                        disable_web_page_preview=True,
                                        reply_markup=kb_for_post(token_symbol or "TOKEN", token_addr or pool_addr)
                                    )

                            start = end + 1

                        set_cursor(chat_id, "ston", pool_addr, str(latest))

                    except Exception:
                        continue

            except Exception:
                pass

            await asyncio.sleep(LOOP_SLEEP)

async def dedust_watcher(bot: Bot):
    async with httpx.AsyncClient() as client:
        while True:
            try:
                pools = list_pools("dedust")
                if not pools:
                    await asyncio.sleep(LOOP_SLEEP)
                    continue

                for (chat_id, pool_addr, token_addr, token_symbol, token_name, token_tg, token_web, last_cursor) in pools:
                    try:
                        j = await dedust_pool_trades(client, pool_addr, limit=25)
                        if not j:
                            continue

                        trades = None
                        if isinstance(j, list):
                            trades = j
                        elif isinstance(j.get("trades"), list):
                            trades = j["trades"]
                        elif isinstance(j.get("items"), list):
                            trades = j["items"]

                        if not trades:
                            continue

                        # post oldest -> newest
                        pending = []
                        for t in reversed(trades):
                            trade_id = str(t.get("id") or t.get("hash") or t.get("txHash") or t.get("tx_hash") or "")
                            if not trade_id:
                                continue
                            # stop at last seen cursor
                            if last_cursor and trade_id == last_cursor:
                                pending = []
                                continue
                            pending.append((trade_id, t))

                        for trade_id, t in pending:
                            usd_value = safe_float(t.get("volumeUsd") or t.get("amountUsd") or t.get("usd")) or 0.0
                            tx_hash = t.get("txHash") or t.get("hash") or t.get("tx_hash") or trade_id
                            trader = t.get("maker") or t.get("trader") or t.get("from")

                            token_amount = safe_float(t.get("amountOut") or t.get("tokenAmount") or t.get("amount_out"))
                            base_amount = safe_float(t.get("amountIn") or t.get("baseAmount") or t.get("amount_in"))
                            base_symbol = t.get("baseSymbol") or "TON"

                            caption = build_caption(
                                token_name=token_name or "Token",
                                dex_name="DeDust",
                                usd_value=usd_value,
                                base_amount=base_amount,
                                base_symbol=base_symbol,
                                token_amount=token_amount,
                                token_symbol=token_symbol or "TOKEN",
                                price_usd=safe_float(t.get("priceUsd") or t.get("price_usd")),
                                mcap_usd=safe_float(t.get("marketCapUsd") or t.get("fdv")),
                                liq_usd=safe_float(t.get("liquidityUsd") or t.get("liquidity_usd")),
                                trader=trader,
                                tx_hash=tx_hash,
                                pool_addr=pool_addr,
                                token_ca=token_addr or pool_addr,
                                token_tg=token_tg,
                            )

                            await bot.send_message(
                                chat_id=chat_id,
                                text=caption,
                                parse_mode=ParseMode.MARKDOWN,
                                disable_web_page_preview=True,
                                reply_markup=kb_for_post(token_symbol or "TOKEN", token_addr or pool_addr)
                            )
                            set_cursor(chat_id, "dedust", pool_addr, trade_id)

                    except Exception:
                        continue

            except Exception:
                pass

            await asyncio.sleep(LOOP_SLEEP)

# -------------------------
# Main
# -------------------------
async def main():
    init_db()
    bot = Bot(BOT_TOKEN, parse_mode=ParseMode.MARKDOWN)

    # start watchers
    asyncio.create_task(ston_watcher(bot))
    asyncio.create_task(dedust_watcher(bot))

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
