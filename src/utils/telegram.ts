import { JettonHolders, JettonInfo, Transaction } from "tonapi-sdk-js";
import { config as dotenvConfig } from "dotenv";
import { Telegraf } from "telegraf";

import { getNotification } from "../content";
import { Config } from "../orm/entities/config";
import { getBookTrendingBotUrl, getDtradeReferralBase, getTrendingUrl, getDexConfig } from "./config";
import { getDexMarketData, getTonUsd } from "./market";

dotenvConfig();

export async function broadcastNotification({
  telegraf,
  configs,
  address,
  tokenInfo,
  isNewHolder,
  tickerValue,
  transaction,
  dex,
  holdersCount,
}: {
  telegraf: Telegraf;
  configs: Config[];
  address: JettonHolders;
  tokenInfo: JettonInfo;
  isNewHolder: boolean;
  tickerValue: string | null;
  transaction: Transaction;
  dex?: string;
  holdersCount?: number | null;
}) {
  const tokenSymbol = tokenInfo.metadata.symbol ?? "TOKEN";
  const tokenAddress = tokenInfo.metadata.address;

  const [tonUsd, market] = await Promise.all([
    getTonUsd(),
    getDexMarketData(tokenAddress),
  ]);

  // We treat tickerValue as a fallback token USD price if we don't have DexScreener data.
  const fallbackPriceUsd = tickerValue ? Number(tickerValue) : null;
  const tokenPriceUsd = market.priceUsd ?? (Number.isFinite(fallbackPriceUsd) ? fallbackPriceUsd : null);

  const dexDisplay = dex ? (getDexConfig().get(dex) ?? dex) : undefined;
  const notificationText = getNotification({
    tokenSymbol,
    tokenAddress,
    dexName: dexDisplay,
    transactionId: transaction.hash,
    buyerAddress: address.address,
    jettonAmountNano: transaction.amount,
    holdersCount: holdersCount ?? null,
    tokenPriceUsd,
    liquidityUsd: market.liquidityUsd ?? null,
    marketCapUsd: market.marketCapUsd ?? null,
    tonUsd,
    telegramUrl: market.telegramUrl ?? null,
    trendingUrl: getTrendingUrl(),
  });

  const bookTrendingUrl = getBookTrendingBotUrl();
  const trendingUrl = getTrendingUrl();
  const dtradeBase = getDtradeReferralBase();
  const dtradeUrl = `${dtradeBase}_${tokenAddress}`;

  const inlineKeyboard = {
    inline_keyboard: [
      [
        { text: "🔥 Book Trending", url: bookTrendingUrl },
        { text: "📈 Trending", url: trendingUrl },
      ],
      [{ text: "⚡️ Buy with DTrade", url: dtradeUrl }],
    ],
  };

  for (const config of configs) {
    try {
      await telegraf.telegram.sendMessage(config.telegramChatId, notificationText, {
        parse_mode: "Markdown",
        reply_markup: inlineKeyboard,
        disable_web_page_preview: true,
      });
    } catch (err) {
      console.error("Failed to send message to chat", config.telegramChatId, err);
    }
  }

  // Optional: also send to a global trending channel chat id.
  const trendingChatId = process.env.TRENDING_CHAT_ID;
  if (trendingChatId) {
    try {
      await telegraf.telegram.sendMessage(trendingChatId, notificationText, {
        parse_mode: "Markdown",
        reply_markup: inlineKeyboard,
        disable_web_page_preview: true,
      });
    } catch (err) {
      console.error("Failed to send message to TRENDING_CHAT_ID", err);
    }
  }
}
