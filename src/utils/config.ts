let dexConfig: Map<string, string> | null = null;
/**
 * @returns {Map<string, string>} interface_name => display_name
 */
export function getDexConfig(): Map<string, string> {
  if (dexConfig === null) {
    const rawData =
      process.env.DEX_CONFIG ?? "stonfi_router:STON.fi,dedust_vault:DeDust";
    dexConfig = new Map<string, string>();

    for (const line of rawData.split(",")) {
      const [interfaceName, displayName] = line.split(":");
      dexConfig.set(interfaceName.trim(), displayName.trim());
    }
  }
  return dexConfig;
}

export function getTrendingUrl(): string {
  return process.env.TRENDING_URL ?? "https://t.me/SpyTonTrending";
}

export function getBookTrendingBotUrl(): string {
  return process.env.BOOK_TRENDING_BOT_URL ?? "https://t.me/SpyTONTrndBot";
}

export function getDtradeReferralBase(): string {
  // User provided default; can override in Railway Variables
  return process.env.DTRADE_REFERRAL ?? "https://t.me/dtrade?start=11TYq7LInG";
}
