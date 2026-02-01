import dotenv from "dotenv";

dotenv.config();

import { initBot } from "./entryPoints/bot";
import { initCron } from "./entryPoints/cron";
import AppDataSource from "./orm";
import logger from "./utils/logger";

async function main() {
  logger.info("Starting app...");
  await AppDataSource.initialize();
  logger.info("Data Source has been initialized!");

  // IMPORTANT:
  // If EXEC_MODE is not set, we default to running the Telegram bot.
  // Otherwise the app will start, initialize the DB, then exit (so the bot
  // will never answer /start).
  const mode = (process.env.EXEC_MODE || "bot").toLowerCase();

  if (mode === "cron") {
    await initCron();
    return;
  }

  // Default = bot
  await initBot();
}

main();
