"""Optional read-only DonutStats snapshot collector, intentionally rate-bounded.

Requires user's own DONUTSTATS_API_KEY in the environment. Outputs raw
responses only to private/ (gitignored); never prints or stores the key.
Documentation: https://api.donutstats.io/docs/
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.parse import quote,urlencode
from urllib.request import Request,urlopen
import argparse
import hashlib
import json
import re
import os
import sys
import time

BASE="https://api.donutstats.io/v1"
USER_AGENT="donut-quant/2026.11.12"
class APIError(RuntimeError):
    pass

def get_json(endpoint:str, api_key:str, timeout:float=20)->dict:
    """Safe relative GET for a documented endpoint on fixed first-party host."""
    if not endpoint.startswith("/") or endpoint.startswith("//") or ".." in endpoint:
        raise ValueError("Unexpected endpoint")
    req=Request(BASE+endpoint,headers={"x-api-key":api_key,"Accept":"application/json","User-Agent":USER_AGENT})
    try:
        with urlopen(req,timeout=timeout) as response:
            return json.load(response)
    except HTTPError as ex:
        if ex.code==429: raise APIError("DonutStats rate limit reached; stop and retry after reset") from ex
        if ex.code in (401,403): raise APIError("DonutStats key is missing, invalid, or lacks read scope") from ex
        raise APIError(f"DonutStats returned HTTP {ex.code}") from ex
    except URLError as ex:
        raise APIError("Network error communicating with DonutStats") from ex

def plan(username:str,items:list[str],include_global:bool=False)->list[tuple[str,str]]:
    player=quote(username,safe="")
    tasks=[
       ("status","/status"),
       ("player",f"/players/{player}?"+urlencode({"lookup":"none"})),
       ("player_orders",f"/players/{player}/orders?"+urlencode({"refresh":"none","limit":100})),
       ("player_history",f"/players/{player}/history?"+urlencode({"days":120,"detail":"compact"})),
       ("player_listings",f"/players/{player}/listings?"+urlencode({"refresh":"none","limit":100})),
       ("seller_closed_listings","/auction/history?"+urlencode({"seller":username,"limit":500})),
       ("economy","/economy?days=30"),
    ]
    if include_global:
        tasks.extend([
            ("global_order_fills","/orders/fills?limit=1000"),
            ("global_closed_orders","/orders/history?limit=1000"),
            ("global_auction_closures","/auction/history?limit=1000"),
            ("global_economy_history","/economy/history?limit=1000"),
        ])
    for item in items:
        key=quote(item,safe="")
        tasks.append(("item_"+item,f"/items/{key}"))
        tasks.append(("history_"+item,f"/items/{key}/history?interval=day&limit=180"))
        tasks.append(("fills_"+item,"/orders/fills?"+urlencode({"item":item,"limit":500})))
    return tasks

def snapshot(username:str,items:list[str],out_dir:Path,max_requests:int=8,include_global:bool=False)->dict:
    key=os.environ.get("DONUTSTATS_API_KEY","").strip()
    if not key:
        raise APIError("Set DONUTSTATS_API_KEY locally; register at https://api.donutstats.io. Never commit or paste keys.")
    if max_requests<=0 or max_requests>20:
        raise ValueError("max_requests must be between 1 and 20 for free-tier safety")
    out_dir.mkdir(parents=True,exist_ok=True)
    history_file=out_dir/"request_times.json"
    try:
        recent=[float(t) for t in json.loads(history_file.read_text(encoding="utf-8"))]
    except (FileNotFoundError,ValueError,TypeError):
        recent=[]
    recent=[t for t in recent if time.time()-t<3600]
    budget=20-len(recent)
    if budget<=0:
        raise APIError("Local free-tier request budget exhausted for the past hour")
    full_plan=plan(username,items,include_global)
    tasks=full_plan[:min(max_requests,budget)]
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    meta={"fetched_at_utc":stamp,"username":username,"max_requests":max_requests,
          "outputs":[],"unfinished_tasks":max(0,len(full_plan)-len(tasks))}
    for name,url in tasks:
        recent.append(time.time())  # count attempts before sending
        history_file.write_text(json.dumps(recent),encoding="utf-8")
        try:
            body=get_json(url,key)
        except APIError as ex:
            meta["error"]=str(ex)
            break
        safe_name=re.sub(r"[^A-Za-z0-9._-]","_",name)[:72]
        suffix=hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
        dest=out_dir/f"{stamp}_{safe_name}_{suffix}.json"
        with dest.open("w",encoding="utf-8") as fh:
            json.dump(body,fh,ensure_ascii=False,indent=2)
        meta["outputs"].append({"dataset":name,"path":str(dest),
                   "record_count":len(body.get("entries",[])) if isinstance(body,dict) else None,
                   "updatedAt":body.get("updatedAt") if isinstance(body,dict) else None})
        time.sleep(0.2)  # gentle spacing; the file enforces hourly budget in this output folder
    with (out_dir/f"{stamp}_manifest.json").open("w",encoding="utf-8") as fh:
        json.dump(meta,fh,indent=2)
    return meta

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--player",required=True,help="Your Minecraft username; not stored in public code")
    parser.add_argument("--item",action="append",default=[])
    parser.add_argument("--max-requests",type=int,default=8)
    parser.add_argument("--include-global",action="store_true",help="Sample global fills and closure feeds (first page only)")
    parser.add_argument("--out",default=str(Path(__file__).resolve().parent.parent/"private"/"market"))
    args=parser.parse_args()
    try:
        out=snapshot(args.player,args.item,Path(args.out),args.max_requests,args.include_global)
        print(json.dumps(out,indent=2))
    except (APIError,ValueError) as ex:
        print(str(ex),file=sys.stderr);sys.exit(2)

if __name__=="__main__":
    main()
