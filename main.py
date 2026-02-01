import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import load_config
from db import DB
from commands import router as commands_router
from watcher import BuyWatcher

logging.basicConfig(level=logging.INFO)

async def main():
    cfg = load_config()
    db = DB("buybot.db")

    bot = Bot(token=cfg.bot_token, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=MemoryStorage())

    defaults = {
        "book_trend_url": cfg.default_book_trend_url,
        "trending_url": cfg.default_trending_url,
        "dtrade_ref": cfg.default_dtrade_ref,
    }

    # Dependencies for handlers
    dp["db"] = db
    dp["network"] = cfg.network
    dp["defaults"] = defaults

    dp.include_router(commands_router)

    watcher = BuyWatcher(
        bot=bot,
        db=db,
        network=cfg.network,
        poll_seconds=cfg.poll_seconds,
        stats_refresh_seconds=cfg.stats_refresh_seconds,
        defaults=defaults,
        trending_post_chat_id=cfg.trending_post_chat_id,
    )

    watcher_task = asyncio.create_task(watcher.run())

    try:
        await dp.start_polling(bot)
    finally:
        await watcher.stop()
        watcher_task.cancel()
        try:
            await watcher_task
        except Exception:
            pass
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
