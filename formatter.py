from __future__ import annotations
from typing import Optional
from utils import fmt_money, fmt_price, short_addr, gem_bar

TON_MASTER = "EQAAA...AM9c"  # displayed only

def build_links_line(tx_url: str, gt_url: str, dexs_url: str, telegram_url: str, trending_url: str) -> str:
    parts = []
    if tx_url: parts.append(f'<a href="{tx_url}">TX</a>')
    if gt_url: parts.append(f'<a href="{gt_url}">GT</a>')
    if dexs_url: parts.append(f'<a href="{dexs_url}">DexS</a>')
    if telegram_url: parts.append(f'<a href="{telegram_url}">Telegram</a>')
    if trending_url: parts.append(f'<a href="{trending_url}">Trending</a>')
    return " | ".join(parts)

def format_buy_message(
    symbol: str,
    ton_amount: float,
    usd_value: float,
    token_amount: float,
    buyer: str,
    price_usd: Optional[float],
    liquidity_usd: Optional[float],
    mcap_usd: Optional[float],
    holders: Optional[int],
    price_change_24h: Optional[float],
    tx_url: str,
    gt_url: str,
    dexs_url: str,
    telegram_url: str,
    trending_url: str,
) -> str:
    gems = gem_bar(ton_amount)
    buyer_short = short_addr(buyer, 4, 4)
    pct = "N/A"
    if price_change_24h is not None:
        pct = f"{price_change_24h:+.1f}%"

    lines = []
    lines.append(f"<b>{symbol} Buy!</b>")
    lines.append("")
    lines.append(gems)
    lines.append("")
    lines.append(f"💎 <b>{ton_amount:,.2f} TON</b> ({fmt_money(usd_value)})")
    lines.append(f"🪙 <b>{token_amount:,.4f}</b> {symbol}")
    lines.append("")
    lines.append(f"<code>{buyer_short}</code>: <b>{pct}</b>")
    if price_usd is not None:
        lines.append(f"Price: {fmt_price(price_usd)}")
    if liquidity_usd is not None:
        lines.append(f"Liquidity: {fmt_money(liquidity_usd)}")
    if mcap_usd is not None:
        lines.append(f"MCap: {fmt_money(mcap_usd)}")
    if holders is not None:
        lines.append(f"Holders: {holders:,}")
    lines.append("")
    lines.append(build_links_line(tx_url, gt_url, dexs_url, telegram_url, trending_url))
    lines.append("--------------------")
    lines.append("<i>You can book an ad here</i>")
    return "\n".join(lines)
