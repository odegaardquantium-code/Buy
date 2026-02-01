import { Telegraf } from "telegraf";
import { ConfigDao } from "../orm/dao/configDao";
import { Address } from "@ton/core";
import { HttpClient, Api } from "tonapi-sdk-js";
import { TickerDao } from "../orm/dao/tickerDao";
import { waitTONRPSDelay } from "../utils/runtime";
import logger from "../utils/logger";
import { inspect } from "util";

export async function initBot() {
  const httpClient = new HttpClient({
    baseUrl: "https://tonapi.io",
    baseApiParams: {
      headers: {
        Authorization: `Bearer ${process.env.TONAPI_KEY}`,
        "Content-type": "application/json",
      },
    },
  });
  const client = new Api(httpClient);

  const configDao = ConfigDao.getDao();
  const tickerDao = TickerDao.getDao();

  const telegraf = new Telegraf(process.env.BOT_TOKEN as string);

  telegraf.telegram.setMyCommands([{ command: "start", description: "Start" }]);
  telegraf.on("message", async (ctx) => {
    try {
      const [config, created] = await configDao.findOrCreateConfig(
        ctx.chat.id.toString(),
      );

      if (ctx.chat.type !== "private") {
        const chatMember = await ctx.telegram.getChatMember(
          ctx.chat.id,
          ctx.message.from.id,
        );
        if (
          !chatMember ||
          (chatMember.status !== "administrator" &&
            chatMember.status !== "creator")
        ) {
          return;
        }
      }

      // @ts-expect-error message.text is string | undefined
      if (config && !created && ctx.message.text?.startsWith("/start")) {
        await configDao.deleteForChat(ctx.chat.id.toString());
        await ctx.reply("Configuration deleted, I won't disturb you anymore");
        return;
      }

      if (!config.value.tokenRequested) {
        await ctx.reply("Please send me an address of token to track");
        config.value.tokenRequested = true;
        await configDao.updateConfig(config);
        return;
      }
      if (config.value.tokenRequested && config.tokenAddress === null) {
        // @ts-expect-error message.text is string | undefined
        const tokenAddress = ctx.message?.text;
        if (
          !Address.isAddress(tokenAddress) &&
          !Address.isFriendly(tokenAddress) &&
          !Address.isRaw(tokenAddress)
        ) {
          await ctx.reply("Please send me a valid address of token to track");
          return;
        }
        try {
          const tokenData = await client.jettons.getJettonInfo(tokenAddress);
          await waitTONRPSDelay();

          if (tokenData.holders_count === 0) {
            await ctx.reply(`There are no holders for token ${tokenAddress}`);
            return;
          }
          config.tokenAddress = tokenAddress;
          await configDao.updateConfig(config);


    // Store token for this chat (we do NOT require CoinMarketCap listing)
    await tickerDao.getOrCreateTicker(tokenAddress);

    await ctx.reply(
      `✅ Tracking ${tokenInfo.metadata.symbol} (${tokenInfo.holders_count} holders).
` +
        `Now watching buys on DEX and posting alerts.`
    );


}
