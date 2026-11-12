"""Import authenticated DonutStats snapshot JSON into the private linked database.

Imports market evidence by exact product key and order ID. A CLOSED auction
listing is never promoted to a sale. Only ORDER FILLS are observed trades.
All raw source payloads remain private, traceable by source SHA256.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import sqlite3
from linked_db import connect


def iso(ms:int|float|None)->str:
    if ms is None:
        return datetime.now(timezone.utc).isoformat()
    return datetime.fromtimestamp(float(ms)/1000,timezone.utc).isoformat()

def fingerprint(*parts:Any)->str:
    raw=json.dumps(parts,sort_keys=True,ensure_ascii=False,separators=(",",":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

def source(con:sqlite3.Connection,path:Path,dataset:str,fetched_utc:str,payload:Any)->str:
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    sid="donutstats:"+digest[:24]
    con.execute("""INSERT OR IGNORE INTO source
      (source_id,source_kind,file_path,sha256,imported_utc) VALUES(?,?,?,?,?)""",
      (sid,"donutstats_"+dataset,str(path),digest,fetched_utc))
    con.execute("""INSERT OR IGNORE INTO raw_api_snapshot
      (source_id,dataset,observed_utc,payload_json) VALUES(?,?,?,?)""",
      (sid,dataset,fetched_utc,json.dumps(payload,ensure_ascii=False)))
    return sid

def upsert_product(con:sqlite3.Connection,product:dict|None,observed_utc:str)->str|None:
    if not isinstance(product,dict):
        return None
    key=product.get("key")
    item=product.get("item")
    if not isinstance(key,str) or not key or not isinstance(item,str) or not item:
        return None
    variant=product.get("variant") or ""
    details=product.get("details")
    con.execute("""INSERT INTO product(product_key,item_id,variant,details_json,last_verified_utc)
      VALUES(?,?,?,?,?) ON CONFLICT(product_key) DO UPDATE SET
      item_id=excluded.item_id,variant=excluded.variant,
      details_json=COALESCE(excluded.details_json,product.details_json),
      last_verified_utc=excluded.last_verified_utc""",
      (key,item,variant,json.dumps(details,ensure_ascii=False) if details is not None else None,observed_utc))
    return key

def ingest_payload(con:sqlite3.Connection,dataset:str,payload:dict,source_id:str,at:str)->dict:
    counts={"products":0,"order_observations":0,"fills":0,"listings":0,"quotes":0,"invalid":0}
    if not isinstance(payload,dict):
        return counts
    entries=payload.get("entries",[])
    if not isinstance(entries,list):
        entries=[]
    if dataset in ("player_orders","global_closed_orders"):
        for x in entries:
            if not isinstance(x,dict):continue
            key=upsert_product(con,x.get("product"),at)
            ordered=x.get("amount");delivered=x.get("delivered");remaining=x.get("remaining")
            if ordered is not None and delivered is not None and remaining is None:
                remaining=ordered-delivered
            if key is None or x.get("id") is None or any(v is None for v in (ordered,delivered,remaining,x.get("unitPrice"))):
                counts["invalid"]+=1;continue
            try:
                con.execute("""INSERT OR REPLACE INTO order_observation
                  (order_id,observed_utc,product_key,bid,ordered,delivered,remaining,buyer,source_id)
                  VALUES(?,?,?,?,?,?,?,?,?)""",
                  (str(x["id"]),at,key,float(x["unitPrice"]),int(ordered),
                   int(delivered),int(remaining),x.get("buyer"),source_id))
                counts["order_observations"]+=1
            except (ValueError,sqlite3.IntegrityError,TypeError):
                counts["invalid"]+=1
    if dataset in ("global_order_fills",) or dataset.startswith("fills_"):
        for x in entries:
            if not isinstance(x,dict):continue
            key=upsert_product(con,x.get("product"),at)
            if key is None or any(x.get(k) is None for k in ("orderId","quantity","paid","at")):
                counts["invalid"]+=1;continue
            event_id=fingerprint(x["orderId"],key,x["at"],x["quantity"],x["paid"])
            try:
                con.execute("""INSERT OR IGNORE INTO order_fill
                   (fill_key,order_id,product_key,at_utc,quantity,paid,source_id)
                   VALUES(?,?,?,?,?,?,?)""",
                   (event_id,str(x["orderId"]),key,iso(x["at"]),int(x["quantity"]),float(x["paid"]),source_id))
                counts["fills"]+=1
            except (ValueError,sqlite3.IntegrityError,TypeError):
                counts["invalid"]+=1
    if dataset in ("player_listings","seller_closed_listings","global_auction_closures"):
        status="open" if dataset=="player_listings" else "closed_unknown"
        for x in entries:
            if not isinstance(x,dict):continue
            key=upsert_product(con,x.get("product"),at)
            if key is None or any(x.get(k) is None for k in ("id","price")):
                counts["invalid"]+=1;continue
            qty=x.get("count") or 1
            try:
                con.execute("""INSERT OR REPLACE INTO auction_listing_observation
                  (listing_id,observed_utc,product_key,seller,quantity,price,lifecycle,source_id)
                  VALUES(?,?,?,?,?,?,?,?)""",
                  (str(x["id"]),at,key,x.get("seller"),int(qty),float(x["price"]),status,source_id))
                counts["listings"]+=1
            except (ValueError,sqlite3.IntegrityError,TypeError):
                counts["invalid"]+=1
    if dataset.startswith("item_") or dataset.startswith("history_"):
        body=payload.get("item") if dataset.startswith("item_") else None
        if isinstance(body,dict):
            key=upsert_product(con,body,at)
            series=[(body.get("prices",{}),iso(body.get("prices",{}).get("updatedAt")))]
        else:
            # Exact identifier from normalized filename, only when the provider
            # response declares its own key and the local name agrees.
            key=payload.get("key")
            if isinstance(key,str) and key:
                upsert_product(con,{"key":key,"item":key.split("[",1)[0],
                                   "variant":key.partition("[")[2].rstrip("]")},at)
            series=[(row,iso(row.get("t"))) for row in entries if isinstance(row,dict)]
        if key:
            for q,t in series:
                if not isinstance(q,dict): continue
                for field,kind in (("low","lowest_ask"),("median","median_ask"),("bid","best_bid")):
                    value=q.get(field)
                    if value is None:continue
                    try:
                        con.execute("""INSERT OR IGNORE INTO quote_observation
                           (quote_id,product_key,observed_utc,quote_kind,unit_price,max_units,source_id)
                           VALUES(?,?,?,?,?,?,?)""",
                           (fingerprint(key,t,kind,source_id),key,t,kind,float(value),None,source_id))
                        counts["quotes"]+=1
                    except (ValueError,TypeError,sqlite3.IntegrityError):
                        counts["invalid"]+=1
    return counts

def import_snapshots(con:sqlite3.Connection,market_dir:Path)->dict:
    market_dir=market_dir.resolve()
    total={"manifests":0,"sources":0,"products":0,"order_observations":0,
           "fills":0,"listings":0,"quotes":0,"invalid":0}
    for manifest_path in sorted(market_dir.glob("*_manifest.json")):
        manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
        t=manifest.get("fetched_at_utc","")
        if not t:continue
        total["manifests"]+=1
        for entry in manifest.get("outputs",[]):
            dataset=entry.get("dataset","")
            path=Path(entry.get("path","")).resolve()
            if not path.is_relative_to(market_dir) or not path.is_file():
                total["invalid"]+=1;continue
            payload=json.loads(path.read_text(encoding="utf-8"))
            with con:
                sid=source(con,path,dataset,t,payload)
                result=ingest_payload(con,dataset,payload,sid,t)
            total["sources"]+=1
            for k,v in result.items():total[k]+=v
    return total

if __name__=="__main__":
    import argparse
    cli=argparse.ArgumentParser()
    root=Path(__file__).resolve().parent.parent
    cli.add_argument("--market-dir",type=Path,default=root/"private"/"market")
    cli.add_argument("--database",type=Path,default=root/"private"/"economy.sqlite")
    args=cli.parse_args()
    if not args.market_dir.is_dir():
        raise SystemExit("No private market snapshots yet. Run donutstats_snapshot.py after obtaining your own key.")
    with connect(args.database) as con:
        print(json.dumps(import_snapshots(con,args.market_dir),indent=2))
