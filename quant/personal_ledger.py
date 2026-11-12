"""Read-only, source-traceable DonutSMP local client ledger.

Only chat-confirmed events are classified. Open listings are NOT sales; auction
earnings summaries are NOT added again to individual sale proceeds. Private
outputs belong in private/ (ignored by Git).
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import csv
import gzip
import hashlib
import json
import os
import re

CASH = r"([0-9][0-9,]*(?:\\.[0-9]+)?[KMBT]?)"
# This pattern deliberately accepts only well-formed amounts, never chat guesses.
MONEY = re.compile(r"^([0-9][0-9,]*(?:\.[0-9]+)?)([KMBT]?)$", re.I)
MUL = {"":1,"K":1_000,"M":1_000_000,"B":1_000_000_000,"T":1_000_000_000_000}
CHAT = re.compile(r"^\[(\d\d:\d\d:\d\d)\].*?\[CHAT\] (.*)$")
DATE = re.compile(r"^(20\d{2}-\d\d-\d\d)")
BUY = re.compile(r"^You bought (\d+) (.+?) for \$\s*([0-9,.]+[KMBT]?)$", re.I)
LIST = re.compile(r"^You listed (\d+) (.+?) for \$\s*([0-9,.]+[KMBT]?)(?: \(\+\$\s*([0-9,.]+[KMBT]?) tax\))?$",re.I)
SOLD = re.compile(r"^(.+?) bought your (.+?) for \$\s*([0-9,.]+[KMBT]?)$",re.I)
EARN = re.compile(r"^You earned \$\s*([0-9,.]+[KMBT]?) from auction(?:.*)?$",re.I)
ORDER_IN = re.compile(r"^(.+?) delivered you (\d+) (.+?)$",re.I)
ORDER_OUT = re.compile(r"^You delivered (\d+) (.+?)(?: to .+)?$",re.I)
ORDER_COMPLETE = re.compile(r"^Your (.+?) order is complete!?$",re.I)
PAY_IN = re.compile(r"^(.+?) paid you \$\s*([0-9,.]+[KMBT]?)$",re.I)
SELL = re.compile(r"^You sold multiple items for \$\s*([0-9,.]+[KMBT]?)$",re.I)


def money(value: str) -> float:
    match = MONEY.fullmatch(value.strip().replace(" ",""))
    if not match:
        raise ValueError("Invalid amount: "+repr(value))
    return float(match[1].replace(",","")) * MUL[match[2].upper()]


def classify(msg: str) -> dict | None:
    m = LIST.fullmatch(msg)
    if m:
        return dict(type="ah_listing", quantity=int(m[1]), item=m[2], amount=money(m[3]),
                    tax_quote=money(m[4]) if m[4] else None, certainty="observed_listing_not_sale")
    m = BUY.fullmatch(msg)
    if m:
        return dict(type="ah_purchase", quantity=int(m[1]), item=m[2], amount=money(m[3]),
                    certainty="observed_cash_outflow")
    m = SOLD.fullmatch(msg)
    if m:
        return dict(type="ah_sale", quantity=None, item=m[2], amount=money(m[3]),
                    counterparty=m[1], certainty="observed_sale_quantity_unknown")
    m = EARN.fullmatch(msg)
    if m:
        return dict(type="ah_earnings_summary", quantity=None, item=None, amount=money(m[1]),
                    certainty="summary_do_not_add_to_sales")
    m = ORDER_IN.fullmatch(msg)
    if m:
        return dict(type="order_delivery_received", quantity=int(m[2]), item=m[3], amount=None,
                    counterparty=m[1],certainty="observed_delivery_price_unknown")
    m = ORDER_OUT.fullmatch(msg)
    if m:
        return dict(type="order_delivery_sent", quantity=int(m[1]), item=m[2], amount=None,
                    certainty="observed_delivery_price_unknown")
    m = ORDER_COMPLETE.fullmatch(msg)
    if m:
        return dict(type="order_completed", quantity=None, item=m[1], amount=None,
                    certainty="observed_order_state_only")
    if msg == "You cancelled the order":
        return dict(type="order_cancelled",quantity=None,item=None,amount=None,
                    certainty="observed_order_state_only")
    m = PAY_IN.fullmatch(msg)
    if m:
        return dict(type="pay_received",quantity=None,item=None,amount=money(m[2]),
                    counterparty=m[1],certainty="observed_transfer")
    m = SELL.fullmatch(msg)
    if m:
        return dict(type="sell_revenue", quantity=None,item=None,amount=money(m[1]),
                    certainty="observed_server_sell_item_unknown")
    return None


def read_observations(profiles: list[Path]) -> tuple[list[dict],dict]:
    """Dedup copied logs conservatively: max multiplicity of identical message
    within one file, instead of summing across overlapping file copies."""
    by_file=[]
    for profile in profiles:
        logdir=profile/"logs"
        if not logdir.exists():
            continue
        for path in sorted(logdir.iterdir()):
            if not (path.name.endswith(".log.gz") or path.name == "latest.log"):
                continue
            dm=DATE.match(path.name)
            day=dm[1] if dm else datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
            try:
                open_file=gzip.open if path.suffix == ".gz" else open
                with open_file(path,"rt",encoding="utf-8",errors="replace") as stream:
                    counts=Counter()
                    for line in stream:
                        m=CHAT.match(line.rstrip("\r\n"))
                        if m:
                            counts[(day,m[1],m[2].strip())]+=1
            except (OSError,EOFError):
                continue
            by_file.append((str(path),counts))
    counts=Counter()
    for _, file_counts in by_file:
        for key, qty in file_counts.items():
            counts[key]=max(counts[key],qty)
    observations=[]
    for (day,time,msg),qty in sorted(counts.items()):
        for occurrence in range(qty):
            payload=classify(msg)
            if payload is None:
                continue
            token=f"{day}|{time}|{msg}|{occurrence}".encode("utf-8")
            observations.append(dict(event_id=hashlib.sha256(token).hexdigest()[:20],date=day,
                                     local_time=time, **payload, message=msg))
    return observations,{"files_read":len(by_file),
        "raw_chat_lines":sum(sum(c.values()) for _,c in by_file),
        "deduplicated_chat_lines":sum(counts.values()),
        "days_with_chat":len({d for d,_,_ in counts}),
        "first_day":min((d for d,_,_ in counts),default=None),
        "last_day":max((d for d,_,_ in counts),default=None),
        "profile_folders":[str(p) for p in profiles]}


def report(events: list[dict],meta: dict) -> dict:
    bytype=Counter(e["type"] for e in events)
    months=defaultdict(lambda:defaultdict(float))
    items=defaultdict(lambda:defaultdict(float))
    for e in events:
        ty=e["type"]
        qty=e.get("quantity") or 0
        amt=e.get("amount") or 0
        months[e["date"][:7]][ty]+=amt
        if e.get("item"):
            items[e["item"]][ty+"_total"]+=amt
            items[e["item"]][ty+"_quantity"]+=qty
    return {
        "scope":"client-visible, source-confirmed; incomplete player ledger",
        "meta":meta,"event_counts":dict(bytype),
        "observed_auction_sales_gross":sum(e["amount"] for e in events if e["type"]=="ah_sale"),
        "observed_ah_purchases_cost":sum(e["amount"] for e in events if e["type"]=="ah_purchase"),
        "sum_of_NONADDITIVE_auction_earnings_notifications":sum(e["amount"] for e in events if e["type"]=="ah_earnings_summary"),
        "tax_quotes_not_proven_paid":sum(e["tax_quote"] or 0 for e in events if e["type"]=="ah_listing"),
        "observed_order_deliveries_received_units":sum(e["quantity"] for e in events if e["type"]=="order_delivery_received"),
        "net_profit":None,
        "reason_no_net_profit":"unknown inventory acquisition costs, unobserved order escrow/fills, unverifiable listing-to-sale matching and gaps",
        "monthly_event_amounts_NOT_cash_flow":{k:dict(v) for k,v in sorted(months.items())},
        "top_items_by_observed_auction_sale_gross":
            sorted(((k,round(v.get("ah_sale_total",0),2),int(v.get("order_delivery_received_quantity",0))) for k,v in items.items()),
                   key=lambda x:-x[1])[:30],
        "top_items_by_observed_ah_purchases":
            sorted(((k,round(v.get("ah_purchase_total",0),2),int(v.get("ah_purchase_quantity",0))) for k,v in items.items()),
                   key=lambda x:-x[1])[:30],
        "top_items_by_order_received_units":
            sorted(((k,int(v.get("order_delivery_received_quantity",0))) for k,v in items.items()),
                   key=lambda x:-x[1])[:30],
        "recent_events":events[-30:],
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--profiles",default=str(Path(os.environ.get("APPDATA",str(Path.home() / "AppData" / "Roaming"))) / "ModrinthApp" / "profiles"))
    parser.add_argument("--out",default=str(Path(__file__).resolve().parent.parent/"private"/"ledger"))
    args=parser.parse_args()
    profiles=[Path(args.profiles)/"DonutSMP",Path(args.profiles)/"DonutSMP (1)"]
    events,meta=read_observations(profiles)
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    columns=["event_id","date","local_time","type","item","quantity","amount","tax_quote","counterparty","certainty","message"]
    with (out/"personal_events.csv").open("w",newline="",encoding="utf-8") as file:
        writer=csv.DictWriter(file,fieldnames=columns,extrasaction="ignore")
        writer.writeheader();writer.writerows(events)
    summary=report(events,meta)
    with (out/"summary.json").open("w",encoding="utf-8") as file:
        json.dump(summary,file,indent=2,ensure_ascii=False)
    concise={k:v for k,v in summary.items() if k not in ("recent_events","monthly_event_amounts_NOT_cash_flow","top_items_by_observed_auction_sale_gross")}
    concise["monthly_event_amounts_NOT_cash_flow"]=summary["monthly_event_amounts_NOT_cash_flow"]
    concise["top_items_by_observed_auction_sale_gross"]=summary["top_items_by_observed_auction_sale_gross"][:12]
    concise["top_items_by_observed_ah_purchases"]=summary["top_items_by_observed_ah_purchases"][:12]
    concise["top_items_by_order_received_units"]=summary["top_items_by_order_received_units"][:12]
    print(json.dumps(concise,indent=2,ensure_ascii=True))
    print("Private files:",out)


if __name__=="__main__":
    main()
