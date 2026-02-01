# TON Telegram BuyBot (Group-based)

This bot watches **DEX trades** on TON pools using **GeckoTerminal Public API** and posts **BUY** alerts.

✅ **Group-based workflow (like your screenshot):**
1. Add the bot to your token group
2. Run: `/add <token_address>` inside the group
3. The bot automatically finds the best pool and starts posting buys **in that group**
4. (Optional) It can also forward every buy to your main trending channel if `TRENDING_POST_CHAT_ID` is set.

## Buy message style
- Title: `TOKEN Buy!`
- Strength gems (💎)
- Amounts + price/liquidity/mcap/holders
- Links line: **TX | GT | DexS | Telegram | Trending**
- Buttons: **Book Trend**, **Trending**, **Buy with dTrade**  
  dTrade deep-link is built as: `https://t.me/dtrade?start=<REF>_<TOKEN_CA>`

## Deploy on Railway
1. Upload this folder to GitHub (or upload the ZIP).
2. Create a new Railway project → Deploy from repo.
3. Add Environment Variables (see `.env.example`).
4. Start Command: `python main.py` (Railway also reads Procfile)

## Commands (run inside your token group)
### Users
- `/add <token_address>` — auto-detect best pool and start tracking it in the group
- `/list` — show tracked tokens in the group

### Group admins
- `/remove <token_address OR pool_address>` — stop tracking in the group
- `/setlinks <book_trend_url> <trending_url>` — change group buttons
- `/setdtrade <ref_code>` — change group dTrade referral

### Manual add (group admins)
- `/addpool <pool_address> [token_address]` — use if auto-detect can’t find the token yet

## Notes
- GeckoTerminal API is cached and can be ~seconds to ~1 minute behind in some cases.
- Keep tracked tokens per group reasonable to stay within rate limits.
