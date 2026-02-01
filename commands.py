from __future__ import annotations
import re
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from db import DB
from clients import HttpClient, GeckoTerminal

router = Router()

def _clean_token(s: str) -> str:
    s = (s or "").strip()
    # remove quotes/backticks
    s = s.strip("`'\"")
    return s

def _normalize_pool_id(pid: str) -> str:
    # GeckoTerminal often returns ids like "ton_<address>"
    if not pid:
        return ""
    if "_" in pid:
        # take last segment
        return pid.split("_", 1)[1]
    return pid

def _extract_handle_to_url(handle: str) -> str:
    if not handle:
        return ""
    h = handle.strip()
    if not h:
        return ""
    if h.startswith("http://") or h.startswith("https://"):
        return h
    if h.startswith("@"):
        h = h[1:]
    # basic sanitation
    h = re.sub(r"[^A-Za-z0-9_]", "", h)
    return f"https://t.me/{h}" if h else ""

async def _is_group_admin(msg: Message) -> bool:
    # Works only in groups
    try:
        member = await msg.bot.get_chat_member(msg.chat.id, msg.from_user.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

async def _ensure_group_row(db: DB, chat_id: int, title: str, defaults: dict):
    g = db.get_group(chat_id)
    if g is None:
        db.upsert_group(
            chat_id,
            title=title or "",
            book_trend_url=defaults.get("book_trend_url", ""),
            trending_url=defaults.get("trending_url", ""),
            dtrade_ref=defaults.get("dtrade_ref", ""),
        )
    else:
        # keep title fresh
        db.upsert_group(chat_id, title=title or (g["title"] or ""))

async def _find_best_pool_for_token(gt: GeckoTerminal, network: str, token_address: str) -> tuple[str, dict]:
    # Returns (pool_address, pool_item_dict)
    data = await gt.token_pools(network, token_address)
    pools = (data.get("data") or [])
    best = None
    best_liq = -1.0
    for item in pools:
        attrs = item.get("attributes") or {}
        liq = attrs.get("reserve_in_usd")
        try:
            liq = float(liq) if liq is not None else 0.0
        except Exception:
            liq = 0.0
        if liq > best_liq:
            best_liq = liq
            best = item
    if not best:
        return ("", {})
    pool_id = best.get("id") or ""
    pool_address = _normalize_pool_id(pool_id)
    return (pool_address, best)

@router.message(Command("start"))
async def start_cmd(msg: Message, db: DB, defaults: dict):
    if msg.chat.type in ("group", "supergroup"):
        await _ensure_group_row(db, msg.chat.id, msg.chat.title or "", defaults)
        await msg.reply(
            "✅ BuyBot is active in this group.\n\n"
            "Add your token: /add <token_address>\n"
            "List tokens: /list\n"
            "Remove token: /remove <token_address>\n\n"
            "Group settings (admins):\n"
            "/setlinks <book_trend_url> <trending_url>\n"
            "/setdtrade <ref_code>\n\n"
            "Example: /add EQB...tokenCA"
        )
    else:
        await msg.reply(
            "Add me to your token group, then run:\n"
            "/add <token_address>\n\n"
            "In a group, you can also set buttons:\n"
            "/setlinks <book_trend_url> <trending_url>\n"
            "/setdtrade <ref_code>"
        )

@router.message(Command("add"))
async def add_token(msg: Message, db: DB, network: str, defaults: dict):
    if msg.chat.type not in ("group", "supergroup"):
        await msg.reply("Use /add inside your token group (not in DM).")
        return

    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await msg.reply("Usage: /add <token_address>")
        return

    token_address = _clean_token(parts[1])
    await _ensure_group_row(db, msg.chat.id, msg.chat.title or "", defaults)

    async with HttpClient() as http:
        gt = GeckoTerminal(http)
        try:
            pool_address, _best = await _find_best_pool_for_token(gt, network, token_address)
        except Exception:
            pool_address = ""

        if not pool_address:
            await msg.reply(
                "I couldn't find a GeckoTerminal pool for that token yet.\n"
                "If the token just launched, wait a bit and try again.\n\n"
                "Tip: you can also add manually with /addpool <pool_address> <token_address> (group admin)."
            )
            return

        # Pull pool details to store symbols and links
        try:
            pdata = await gt.pool(network, pool_address)
        except Exception:
            pdata = {}

        # Parse symbols from included tokens (best effort)
        base_symbol = ""
        quote_symbol = ""
        try:
            rel = ((pdata.get("data") or {}).get("relationships") or {})
            base_id = ((rel.get("base_token") or {}).get("data") or {}).get("id")
            quote_id = ((rel.get("quote_token") or {}).get("data") or {}).get("id")
            included = pdata.get("included") or []
            id_to_sym = {}
            id_to_name = {}
            for item in included:
                if (item.get("type") == "token") and item.get("id"):
                    attrs = item.get("attributes") or {}
                    id_to_sym[item["id"]] = attrs.get("symbol") or ""
                    id_to_name[item["id"]] = attrs.get("name") or ""
            base_symbol = id_to_sym.get(base_id, "")
            quote_symbol = id_to_sym.get(quote_id, "")
            token_name = id_to_name.get(base_id, "") or ""
        except Exception:
            token_name = ""

        # token info for telegram handle/url
        telegram_url = ""
        symbol = base_symbol or "TOKEN"
        try:
            tinfo = await gt.token_info(network, token_address)
            attrs = ((tinfo.get("data") or {}).get("attributes") or {})
            symbol = attrs.get("symbol") or symbol
            token_name = attrs.get("name") or token_name
            telegram_url = _extract_handle_to_url(
                attrs.get("telegram_handle") or attrs.get("telegram") or attrs.get("telegram_url") or ""
            )
        except Exception:
            pass

        gt_url = f"https://www.geckoterminal.com/ton/pools/{pool_address}"
        dexs_url = f"https://dexscreener.com/ton/{pool_address}"

        db.upsert_pool(
            pool_address,
            token_ca=token_address,
            symbol=symbol,
            token_name=token_name,
            base_symbol=base_symbol,
            quote_symbol=quote_symbol,
            telegram_url=telegram_url,
            gt_url=gt_url,
            dex_url=dexs_url,
        )
        db.add_group_pool(
            msg.chat.id,
            pool_address,
            token_ca=token_address,
            symbol=symbol,
            added_by=(msg.from_user.id if msg.from_user else None),
        )

    await msg.reply(
        f"✅ Added <b>{symbol}</b>\n"
        f"Pool: <code>{pool_address}</code>\n"
        f"Token: <code>{token_address}</code>\n\n"
        "Buys will now post in this group."
    )

@router.message(Command("addpool"))
async def add_pool_manual(msg: Message, db: DB, defaults: dict):
    if msg.chat.type not in ("group", "supergroup"):
        await msg.reply("Use /addpool inside your group.")
        return
    if not await _is_group_admin(msg):
        await msg.reply("Only group admins can use /addpool.")
        return

    parts = (msg.text or "").split()
    if len(parts) < 2:
        await msg.reply("Usage: /addpool <pool_address> [token_address]")
        return
    pool_address = _clean_token(parts[1])
    token_address = _clean_token(parts[2]) if len(parts) >= 3 else ""

    await _ensure_group_row(db, msg.chat.id, msg.chat.title or "", defaults)

    # Store minimal pool; watcher will fill stats over time
    db.upsert_pool(
        pool_address,
        token_ca=token_address,
        gt_url=f"https://www.geckoterminal.com/ton/pools/{pool_address}",
        dex_url=f"https://dexscreener.com/ton/{pool_address}",
    )
    db.add_group_pool(
        msg.chat.id,
        pool_address,
        token_ca=token_address,
        added_by=(msg.from_user.id if msg.from_user else None),
    )
    await msg.reply(f"✅ Added pool <code>{pool_address}</code> to this group.")

@router.message(Command("remove"))
async def remove_token(msg: Message, db: DB):
    if msg.chat.type not in ("group", "supergroup"):
        await msg.reply("Use /remove inside your token group.")
        return
    if not await _is_group_admin(msg):
        await msg.reply("Only group admins can remove tracked tokens.")
        return

    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await msg.reply("Usage: /remove <token_address OR pool_address>")
        return
    key = _clean_token(parts[1])

    # try token first
    db.remove_group_pool_by_token(msg.chat.id, key)
    # also try pool address
    db.remove_group_pool_by_pool(msg.chat.id, key)

    await msg.reply("✅ Removed (if it existed).")

@router.message(Command("list"))
async def list_tokens(msg: Message, db: DB):
    if msg.chat.type not in ("group", "supergroup"):
        await msg.reply("Use /list inside your token group.")
        return
    rows = db.list_group_pools(msg.chat.id)
    if not rows:
        await msg.reply("No tokens tracked in this group yet. Add one with /add <token_address>.")
        return

    lines = ["<b>Tracked in this group:</b>"]
    for r in rows[:25]:
        sym = r["symbol"] or "TOKEN"
        ca = r["token_ca"] or ""
        pool = r["pool_address"]
        lines.append(f"• <b>{sym}</b> — <code>{pool}</code>" + (f"\n  <code>{ca}</code>" if ca else ""))
    await msg.reply("\n".join(lines))

@router.message(Command("setlinks"))
async def set_links(msg: Message, db: DB):
    if msg.chat.type not in ("group", "supergroup"):
        await msg.reply("Use /setlinks inside your group.")
        return
    if not await _is_group_admin(msg):
        await msg.reply("Only group admins can change buttons.")
        return
    parts = (msg.text or "").split()
    if len(parts) < 3:
        await msg.reply("Usage: /setlinks <book_trend_url> <trending_url>")
        return
    book_url = parts[1].strip()
    trending_url = parts[2].strip()
    db.set_group_links(msg.chat.id, book_url, trending_url)
    await msg.reply("✅ Updated group buttons (Book Trend + Trending).")

@router.message(Command("setdtrade"))
async def set_dtrade(msg: Message, db: DB):
    if msg.chat.type not in ("group", "supergroup"):
        await msg.reply("Use /setdtrade inside your group.")
        return
    if not await _is_group_admin(msg):
        await msg.reply("Only group admins can change dTrade referral.")
        return
    parts = (msg.text or "").split()
    if len(parts) < 2:
        await msg.reply("Usage: /setdtrade <ref_code>  (example: 11TYq7LInG)")
        return
    ref = parts[1].strip()
    db.set_group_dtrade(msg.chat.id, ref)
    await msg.reply("✅ Updated dTrade referral for this group.")
