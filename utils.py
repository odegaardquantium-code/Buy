import re

def short_addr(addr: str, head: int = 4, tail: int = 4) -> str:
    if not addr:
        return ""
    if len(addr) <= head + tail + 3:
        return addr
    return f"{addr[:head]}…{addr[-tail:]}"

def fmt_money(x):
    try:
        x = float(x)
    except Exception:
        return "N/A"
    if x >= 1_000_000_000:
        return f"${x/1_000_000_000:.2f}B"
    if x >= 1_000_000:
        return f"${x/1_000_000:.2f}M"
    if x >= 1_000:
        return f"${x/1_000:.2f}K"
    return f"${x:,.2f}"

def fmt_price(x):
    try:
        x = float(x)
    except Exception:
        return "N/A"
    if x >= 1:
        return f"${x:.4f}"
    if x >= 0.01:
        return f"${x:.6f}"
    return f"${x:.8f}"

def gem_bar(ton_amount: float) -> str:
    # simple strength mapping
    n = 1
    if ton_amount >= 25: n = 5
    elif ton_amount >= 10: n = 4
    elif ton_amount >= 5: n = 3
    elif ton_amount >= 1: n = 2
    return "💎" * n
