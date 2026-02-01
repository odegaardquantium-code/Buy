import { fromNano } from "@ton/core";

export type NotificationArgs = {
  tokenSymbol: string;
  tokenAddress: string;
  dexName?: string;
  transactionId: string;
  buyerAddress: string;
  jettonAmountNano: string;
  holdersCount?: number | null;
  tokenPriceUsd?: number | null;
  liquidityUsd?: number | null;
  marketCapUsd?: number | null;
  tonUsd?: number | null;
  telegramUrl?: string | null;
  trendingUrl: string;
  gtUrl: string;
  dexScreenerUrl: string;
  txUrl: string;
};

function shortAddr(addr: string): string {
  if (!addr) return "";
  if (addr.length <= 12) return addr;
  return `${addr.slice(0, 4)}...${addr.slice(-4)}`;
}

function fmtUsd(v?: number | null): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (v >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (v >= 1) return v.toLocaleString(undefined, { maximumFractionDigits: 4 });
  return v.toLocaleString(undefined, { maximumFractionDigits: 8 });
}

function fmtNum(v?: number | null): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

export function getNotification(args: NotificationArgs): string {
  const jettonAmount = Number(fromNano(args.jettonAmountNano));
  const priceUsd = args.tokenPriceUsd ?? null;
  const usdValue = priceUsd ? jettonAmount * priceUsd : null;
  const tonUsd = args.tonUsd ?? null;
  const tonValue = usdValue && tonUsd ? usdValue / tonUsd : null;

  const header = `${args.tokenSymbol} Buy! — ${args.dexName ?? "DEX"}`;

  const lines: string[] = [];
  lines.push(header);
  lines.push("");

  if (tonValue !== null && usdValue !== null) {
    lines.push(`💎 ${tonValue.toFixed(2)} TON ($${fmtUsd(usdValue)})`);
  } else {
    lines.push(`💎 — TON ($${usdValue !== null ? fmtUsd(usdValue) : "—"})`);
  }

  lines.push(`🪙 ${jettonAmount.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${args.tokenSymbol}`);
  lines.push(`👤 ${shortAddr(args.buyerAddress)}`);
  lines.push("");

  lines.push(`Price: $${fmtUsd(args.tokenPriceUsd)}`);
  lines.push(`Liquidity: $${fmtUsd(args.liquidityUsd)}`);
  lines.push(`MCap: $${fmtUsd(args.marketCapUsd)}`);
  lines.push(`Holders: ${fmtNum(args.holdersCount ?? null)}`);
  lines.push("");

  const parts: string[] = [];
  parts.push(`[TX](${args.txUrl})`);
  parts.push(`[GT](${args.gtUrl})`);
  parts.push(`[DexS](${args.dexScreenerUrl})`);
  if (args.telegramUrl) parts.push(`[Telegram](${args.telegramUrl})`);
  parts.push(`[Trending](${args.trendingUrl})`);
  lines.push(parts.join(" | "));

  return lines.join("\n");
}
