"""Build the local, source-preserving economy SQLite evidence store.

Private by design: raw account events and API snapshots never enter git.
This database distinguishes observations from transactions and is safe
to rebuild idempotently from the parser's private event CSV.
"""
from __future__ import annotations
from pathlib import Path
import argparse
import csv
import hashlib
import json
import sqlite3
from datetime import datetime,timezone

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS source (
  source_id TEXT PRIMARY KEY,
  source_kind TEXT NOT NULL,
  file_path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  imported_utc TEXT NOT NULL,
  UNIQUE(file_path,sha256)
);
CREATE TABLE IF NOT EXISTS personal_event (
  event_id TEXT PRIMARY KEY,
  source_id TEXT REFERENCES source(source_id),
  local_date TEXT NOT NULL,
  local_clock TEXT NOT NULL,
  event_type TEXT NOT NULL,
  item_label TEXT,
  product_key TEXT,
  quantity INTEGER CHECK (quantity IS NULL OR quantity >= 0),
  amount REAL CHECK (amount IS NULL OR amount >= 0),
  tax_quote REAL CHECK (tax_quote IS NULL OR tax_quote >= 0),
  counterparty TEXT,
  certainty TEXT NOT NULL,
  raw_message TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_personal_time ON personal_event(local_date,local_clock);
CREATE INDEX IF NOT EXISTS ix_personal_item ON personal_event(item_label,event_type);
CREATE TABLE IF NOT EXISTS product (
  product_key TEXT PRIMARY KEY,
  item_id TEXT NOT NULL,
  variant TEXT NOT NULL DEFAULT '',
  details_json TEXT,
  last_verified_utc TEXT
);
CREATE TABLE IF NOT EXISTS quote_observation (
  quote_id TEXT PRIMARY KEY,
  product_key TEXT NOT NULL REFERENCES product(product_key),
  observed_utc TEXT NOT NULL,
  quote_kind TEXT NOT NULL CHECK(quote_kind IN
       ('best_bid','lowest_ask','median_ask','historical_sale','order_fill_price','server_worth')),
  unit_price REAL NOT NULL CHECK(unit_price>=0),
  max_units INTEGER CHECK(max_units IS NULL OR max_units>=0),
  source_id TEXT NOT NULL REFERENCES source(source_id)
);
CREATE INDEX IF NOT EXISTS ix_quote_time ON quote_observation(product_key,observed_utc);
CREATE TABLE IF NOT EXISTS order_observation (
  order_id TEXT NOT NULL,
  observed_utc TEXT NOT NULL,
  product_key TEXT NOT NULL REFERENCES product(product_key),
  bid REAL NOT NULL CHECK(bid>=0),
  ordered INTEGER NOT NULL CHECK(ordered>=0),
  delivered INTEGER NOT NULL CHECK(delivered>=0),
  remaining INTEGER NOT NULL CHECK(remaining>=0),
  buyer TEXT,
  source_id TEXT REFERENCES source(source_id),
  PRIMARY KEY(order_id,observed_utc),
  CHECK(ordered = delivered + remaining)
);
CREATE TABLE IF NOT EXISTS order_fill (
  fill_key TEXT PRIMARY KEY,
  order_id TEXT,
  product_key TEXT NOT NULL REFERENCES product(product_key),
  at_utc TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK(quantity>0),
  paid REAL NOT NULL CHECK(paid>=0),
  supplier TEXT,
  source_id TEXT REFERENCES source(source_id)
);
CREATE TABLE IF NOT EXISTS auction_listing_observation (
  listing_id TEXT NOT NULL,
  observed_utc TEXT NOT NULL,
  product_key TEXT NOT NULL REFERENCES product(product_key),
  seller TEXT,
  quantity INTEGER NOT NULL CHECK(quantity>0),
  price REAL NOT NULL CHECK(price>=0),
  lifecycle TEXT NOT NULL CHECK(lifecycle IN('open','closed_unknown')),
  source_id TEXT REFERENCES source(source_id),
  PRIMARY KEY(listing_id,observed_utc)
);
CREATE TABLE IF NOT EXISTS inventory_stack (
  snapshot_id TEXT NOT NULL,
  observed_local TEXT NOT NULL,
  storage TEXT NOT NULL,
  container_id TEXT NOT NULL,
  slot_label TEXT NOT NULL,
  product_key TEXT NOT NULL REFERENCES product(product_key),
  quantity INTEGER NOT NULL CHECK(quantity>0),
  source_id TEXT REFERENCES source(source_id),
  PRIMARY KEY(snapshot_id,container_id,slot_label)
);
CREATE TABLE IF NOT EXISTS raw_api_snapshot (
  source_id TEXT PRIMARY KEY REFERENCES source(source_id),
  dataset TEXT NOT NULL,
  observed_utc TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
"""

def connect(path:Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SCHEMA)
    return con

def import_ledger(con:sqlite3.Connection, csv_file:Path) -> tuple[int,str]:
    if not csv_file.exists():
        raise FileNotFoundError(csv_file)
    payload=csv_file.read_bytes()
    digest=hashlib.sha256(payload).hexdigest()
    source_id="local_csv:"+digest[:24]
    now=datetime.now(timezone.utc).isoformat()
    with con:
        con.execute("""INSERT OR IGNORE INTO source
                    (source_id,source_kind,file_path,sha256,imported_utc)
                    VALUES(?,?,?,?,?)""",
                    (source_id,"modrinth_local_events",str(csv_file),digest,now))
        for e in csv.DictReader(payload.decode("utf-8-sig").splitlines()):
            def num(k):
                raw=e.get(k,"").strip()
                return float(raw) if raw else None
            def qty():
                raw=e.get("quantity","").strip()
                return int(raw) if raw else None
            con.execute("""INSERT OR REPLACE INTO personal_event
                (event_id,source_id,local_date,local_clock,event_type,
                 item_label,quantity,amount,tax_quote,counterparty,certainty,raw_message)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (e["event_id"],source_id,e["date"],e["local_time"],e["type"],
                 e.get("item") or None,qty(),num("amount"),num("tax_quote"),
                 e.get("counterparty") or None,e["certainty"],e["message"]))
    count=con.execute("SELECT COUNT(*) FROM personal_event").fetchone()[0]
    return count,source_id

def audit(con:sqlite3.Connection) -> dict:
    data=con.execute("""SELECT event_type,COUNT(*),SUM(COALESCE(amount,0))
                          FROM personal_event GROUP BY event_type ORDER BY event_type""").fetchall()
    return {"event_classes":[dict(type=t,count=n,observed_event_amount=v) for t,n,v in data],
            "net_profit":None,
            "warning":"AH listings are not revenue; auction summary notifications overlap sale events; unknown cost basis."}

def main():
    parser=argparse.ArgumentParser()
    parent=Path(__file__).resolve().parent.parent
    parser.add_argument("--ledger",type=Path,default=parent/"private"/"ledger"/"personal_events.csv")
    parser.add_argument("--database",type=Path,default=parent/"private"/"economy.sqlite")
    args=parser.parse_args()
    with connect(args.database) as con:
        n,source=import_ledger(con,args.ledger)
        print(json.dumps({"database":str(args.database),"personal_events":n,
                         "source_hash_id":source,"audit":audit(con)},indent=2))

if __name__=="__main__":
    main()
