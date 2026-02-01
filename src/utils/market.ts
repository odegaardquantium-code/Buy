export type DexMarketData = {
  priceUsd?: number;
  liquidityUsd?: number;
  marketCapUsd?: number;
  dexUrl?: string;
  telegramUrl?: string;
};

let tonUsdCache: { value: number; ts: number } | null = null;
const TON_USD_TTL_MS = 60_000; // 1 min

export async function getTonUsd(): Promise<number | null> {
  const now = Date.now();
  if (tonUsdCache && now - tonUsdCache.ts < TON_USD_TTL_MS) return tonUsdCache.value;

  try {
    const url =
      "https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd";
    const res = await fetch(url, { method: "GET" });
    if (!res.ok) return null;
    const json: any = await res.json();
    const value = Number(json?.["the-open-network"]?.usd);
    if (!Number.isFinite(value)) return null;
    tonUsdCache = { value, ts: now };
    return value;
  } catch {
    return null;
  }
}

let dexCache = new Map<string, { data: DexMarketData; ts: number }>();
const DEX_TTL_MS = 20_000; // 20s

export async function getDexMarketData(tokenAddress: string): Promise<DexMarketData> {
  const now = Date.now();
  const cached = dexCache.get(tokenAddress);
  if (cached && now - cached.ts < DEX_TTL_MS) return cached.data;

  const data: DexMarketData = {};
  try {
    const url = `https://api.dexscreener.com/latest/dex/tokens/${encodeURIComponent(
      tokenAddress,
    )}`;
    const res = await fetch(url, { method: "GET" });
    if (res.ok) {
      const json: any = await res.json();
      const pairs: any[] = Array.isArray(json?.pairs) ? json.pairs : [];
      const tonPairs = pairs.filter((p) => (p?.chainId ?? "").toLowerCase() === "ton");
      const best = (tonPairs.length ? tonPairs : pairs)[0];
      if (best) {
        const priceUsd = Number(best?.priceUsd);
        if (Number.isFinite(priceUsd)) data.priceUsd = priceUsd;

        const liq = Number(best?.liquidity?.usd);
        if (Number.isFinite(liq)) data.liquidityUsd = liq;

        const fdv = Number(best?.fdv);
        if (Number.isFinite(fdv)) data.marketCapUsd = fdv;

        if (typeof best?.url === "string") data.dexUrl = best.url;

        // Socials sometimes live under info.socials
        const socials: any[] = Array.isArray(best?.info?.socials) ? best.info.socials : [];
        const tg = socials.find((s) => (s?.type ?? "").toLowerCase() === "telegram")?.url;
        if (typeof tg === "string") data.telegramUrl = tg;
      }
    }
  } catch {
    // ignore
  }

  dexCache.set(tokenAddress, { data, ts: now });
  return data;
}
