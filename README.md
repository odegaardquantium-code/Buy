# SpyTON BuyBot (Railway-ready)

A Telegram buy alert bot that posts **STON.fi** and **DeDust** buys into any group/channel in a clean “buybot” style:
- Green strength dots
- Price / Market Cap / Liquidity (when available)
- Links row: Tx | GT | DexS | Telegram | Trending
- Buttons: Book Trend, Trending, Buy (DTrade referral + CA)

## What works now
- ✅ STON.fi live swaps via STON DexScreener export events (block-range polling)
- ✅ DeDust pool latest trades polling
- ✅ No setup commands needed: paste the **pool address** (starts with EQ...) in the chat once

**Sources**
- STON DexScreener export events approach (fromBlock/toBlock): see example write-up.  
- DeDust pool trades endpoint: `GET /v2/pools/{pool}/trades`.

## Deploy on Railway
1) Create a GitHub repo and upload these files.  
2) In Railway: **New Project → Deploy from GitHub Repo**  
3) Add environment variables (Railway → Variables):
- `BOT_TOKEN`
- `BOOK_TREND_URL`
- `TRENDING_URL`
- `DTRADE_REF`

4) Deploy. Railway will run `python main.py`.

## Use in Telegram
- Add the bot to your **group** or make it **admin** in your **channel**.
- Paste a pool address like: `EQ....`
- Bot replies “tracking” and starts posting buys automatically.

## Notes
- “All DEX / Blum / GasPump” requires a dedicated public trades feed per DEX (or a paid/partner onchain-trade provider).
  This repo is structured so new watchers can be plugged in cleanly.
