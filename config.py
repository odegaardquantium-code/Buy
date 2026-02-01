import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except Exception:
        return default

@dataclass(frozen=True)
class Config:
    bot_token: str
    # Optional: if set, all detected buys will ALSO be posted to this channel (your main trending channel)
    trending_post_chat_id: int = 0

    admin_ids: set[int] = None
    network: str = "ton"
    poll_seconds: int = 12
    stats_refresh_seconds: int = 180

    # Defaults used for new groups (can be overridden per group using /setlinks and /setdtrade inside the group)
    default_book_trend_url: str = ""
    default_trending_url: str = ""
    default_dtrade_ref: str = "11TYq7LInG"

def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is missing")

    # Backward compatible: accept POST_CHAT_ID as alias
    trending_post_chat_id = _get_int("TRENDING_POST_CHAT_ID", 0)
    if not trending_post_chat_id:
        trending_post_chat_id = _get_int("POST_CHAT_ID", 0)

    admin_raw = os.getenv("ADMIN_IDS", "").strip()
    admin_ids = set()
    if admin_raw:
        for part in admin_raw.split(","):
            part = part.strip()
            if part:
                admin_ids.add(int(part))

    return Config(
        bot_token=token,
        trending_post_chat_id=trending_post_chat_id,
        admin_ids=admin_ids,
        network=os.getenv("NETWORK", "ton").strip() or "ton",
        poll_seconds=_get_int("POLL_SECONDS", 12),
        stats_refresh_seconds=_get_int("STATS_REFRESH_SECONDS", 180),
        default_book_trend_url=os.getenv("BOOK_TREND_URL", "").strip(),
        default_trending_url=os.getenv("TRENDING_URL", "").strip(),
        default_dtrade_ref=os.getenv("DTREDE_REF", os.getenv("DTRADE_REF", "11TYq7LInG")).strip() or "11TYq7LInG",
    )
