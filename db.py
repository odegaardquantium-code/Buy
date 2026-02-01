import sqlite3
from typing import Optional, Any

SCHEMA = '''
CREATE TABLE IF NOT EXISTS pools (
  pool_address TEXT PRIMARY KEY,
  token_ca TEXT,
  symbol TEXT,
  token_name TEXT,
  base_symbol TEXT,
  quote_symbol TEXT,
  last_trade_id TEXT,
  telegram_url TEXT,
  dex_url TEXT,
  gt_url TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pool_stats (
  pool_address TEXT PRIMARY KEY,
  price_usd REAL,
  liquidity_usd REAL,
  market_cap_usd REAL,
  fdv_usd REAL,
  holders INTEGER,
  price_change_24h REAL,
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS groups (
  chat_id INTEGER PRIMARY KEY,
  title TEXT,
  book_trend_url TEXT,
  trending_url TEXT,
  dtrade_ref TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS group_pools (
  chat_id INTEGER NOT NULL,
  pool_address TEXT NOT NULL,
  token_ca TEXT,
  symbol TEXT,
  enabled INTEGER DEFAULT 1,
  added_by INTEGER,
  created_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (chat_id, pool_address),
  FOREIGN KEY (pool_address) REFERENCES pools(pool_address)
);

CREATE INDEX IF NOT EXISTS idx_group_pools_pool ON group_pools(pool_address);
'''

class DB:
    def __init__(self, path: str = "buybot.db"):
        self.path = path
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self):
        self._conn.close()

    # ---------- Pools ----------
    def upsert_pool(self, pool_address: str, **fields: Any):
        cols = ["pool_address"] + list(fields.keys())
        vals = [pool_address] + list(fields.values())
        placeholders = ",".join(["?"] * len(cols))
        updates = ",".join([f"{k}=excluded.{k}" for k in fields.keys()])

        sql = f"INSERT INTO pools ({','.join(cols)}) VALUES ({placeholders})"
        if fields:
            sql += f" ON CONFLICT(pool_address) DO UPDATE SET {updates}"
        self._conn.execute(sql, vals)
        self._conn.commit()

    def list_pools(self):
        cur = self._conn.execute("SELECT * FROM pools ORDER BY created_at DESC")
        return cur.fetchall()

    def get_pool(self, pool_address: str):
        cur = self._conn.execute("SELECT * FROM pools WHERE pool_address=?", (pool_address,))
        return cur.fetchone()

    def set_last_trade(self, pool_address: str, last_trade_id: str):
        self._conn.execute("UPDATE pools SET last_trade_id=? WHERE pool_address=?", (last_trade_id, pool_address))
        self._conn.commit()

    # ---------- Stats ----------
    def upsert_stats(self, pool_address: str, **fields: Any):
        cols = ["pool_address"] + list(fields.keys())
        vals = [pool_address] + list(fields.values())
        placeholders = ",".join(["?"] * len(cols))
        updates = ",".join([f"{k}=excluded.{k}" for k in fields.keys()])

        sql = f"INSERT INTO pool_stats ({','.join(cols)}) VALUES ({placeholders})"
        if fields:
            sql += f" ON CONFLICT(pool_address) DO UPDATE SET {updates}, updated_at=datetime('now')"
        self._conn.execute(sql, vals)
        self._conn.commit()

    def get_stats(self, pool_address: str):
        cur = self._conn.execute("SELECT * FROM pool_stats WHERE pool_address=?", (pool_address,))
        return cur.fetchone()

    # ---------- Groups ----------
    def upsert_group(self, chat_id: int, **fields: Any):
        cols = ["chat_id"] + list(fields.keys())
        vals = [chat_id] + list(fields.values())
        placeholders = ",".join(["?"] * len(cols))
        updates = ",".join([f"{k}=excluded.{k}" for k in fields.keys()])

        sql = f"INSERT INTO groups ({','.join(cols)}) VALUES ({placeholders})"
        if fields:
            sql += f" ON CONFLICT(chat_id) DO UPDATE SET {updates}"
        self._conn.execute(sql, vals)
        self._conn.commit()

    def get_group(self, chat_id: int):
        cur = self._conn.execute("SELECT * FROM groups WHERE chat_id=?", (chat_id,))
        return cur.fetchone()

    def set_group_links(self, chat_id: int, book_trend_url: str, trending_url: str):
        self.upsert_group(chat_id, book_trend_url=book_trend_url, trending_url=trending_url)

    def set_group_dtrade(self, chat_id: int, dtrade_ref: str):
        self.upsert_group(chat_id, dtrade_ref=dtrade_ref)

    # ---------- Group pools ----------
    def add_group_pool(self, chat_id: int, pool_address: str, token_ca: str = "", symbol: str = "", added_by: Optional[int] = None):
        self._conn.execute(
            "INSERT OR REPLACE INTO group_pools (chat_id, pool_address, token_ca, symbol, enabled, added_by) VALUES (?,?,?,?,1,?)",
            (chat_id, pool_address, token_ca, symbol, added_by)
        )
        self._conn.commit()

    def remove_group_pool_by_pool(self, chat_id: int, pool_address: str):
        self._conn.execute("DELETE FROM group_pools WHERE chat_id=? AND pool_address=?", (chat_id, pool_address))
        self._conn.commit()

    def remove_group_pool_by_token(self, chat_id: int, token_ca: str):
        self._conn.execute("DELETE FROM group_pools WHERE chat_id=? AND token_ca=?", (chat_id, token_ca))
        self._conn.commit()

    def list_group_pools(self, chat_id: int):
        cur = self._conn.execute(
            "SELECT gp.*, p.gt_url, p.dex_url, p.telegram_url FROM group_pools gp "
            "LEFT JOIN pools p ON p.pool_address=gp.pool_address "
            "WHERE gp.chat_id=? ORDER BY gp.created_at DESC",
            (chat_id,)
        )
        return cur.fetchall()


def list_active_pools(self):
    cur = self._conn.execute(
        "SELECT DISTINCT p.* FROM pools p JOIN group_pools gp ON gp.pool_address=p.pool_address WHERE gp.enabled=1"
    )
    return cur.fetchall()

    def group_targets_for_pool(self, pool_address: str):
        cur = self._conn.execute(
            "SELECT g.chat_id, g.book_trend_url, g.trending_url, g.dtrade_ref, g.title, gp.token_ca, gp.symbol "
            "FROM group_pools gp "
            "JOIN groups g ON g.chat_id=gp.chat_id "
            "WHERE gp.pool_address=? AND gp.enabled=1",
            (pool_address,)
        )
        return cur.fetchall()
