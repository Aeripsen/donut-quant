"""Conservative shortlists for the report. Rules:
 - stackable items: price = median of last 15 full-stack sales (n_stack >= 3); conservative = min(that, 25th pct of last 15 sales).
   Single-unit sales of stackable items are ignored (they are mostly disguised payments / renamed items).
 - non-stackable items: price = median of last 15 sales; conservative = min(25th pct, 1-day average). Flag if median > 3x 1-day average.
 - enchantable items (tools, armor, books) are excluded from crafting math (AH price is dominated by enchanted copies).
 - liquidity = settled AH trades in the last 24h (SMP500). Daily cap = profit/unit x units sold per day.
Outputs quant/short_orders_to_ah.csv, quant/short_crafts.csv, quant/short_conversion.csv and prints them.
"""
import json, csv, os
SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
items = json.load(open(f"{SP}/mcdata/items.json", encoding="utf-8")); byid = {i["id"]: i for i in items}; byname = {i["name"]: i for i in items}
P = {int(r["id"]): r for r in csv.DictReader(open(f"{SP}/quant/price_table.csv", encoding="utf-8"))}
rec = json.load(open(f"{SP}/mcdata/recipes.json", encoding="utf-8"))

def f(r, k):
    v = r.get(k) if r else None
    try: return float(v) if v not in (None, "") else None
    except ValueError: return None

def sale(i):
    """returns (median, conservative, trades/day, units/day, flag)"""
    r = P.get(i)
    if not r: return None, None, 0, 0, "no data"
    st = int(r["stack"]); ns = f(r, "n_stack") or 0; nt = f(r, "n_tx") or 0
    med = f(r, "tx_med"); p25 = f(r, "tx_p25"); davg = f(r, "ah_d_price"); smed = f(r, "tx_stack_med")
    tr = f(r, "ah_d_trades") or 0; vol = f(r, "ah_d_vol") or 0
    flag = ""
    jp = f(r, "jp_last_unit")
    if r.get("enchantable") == "1": return None, None, tr, vol, "enchantable"
    if jp and smed and (abs(smed - jp) / jp) > 0.6: flag = "stack-median vs last-sale disagree (%.0f vs %.0f)" % (smed, jp)
    if st > 1:
        if not smed or ns < 3: return None, None, tr, vol, "no stack sales"
        con = min(smed, p25) if p25 else smed
        return smed, con, tr, vol, flag
    if not med or nt < 5: return None, None, tr, vol, "thin"
    if davg and med > 3 * davg: flag = "median>>1d avg (suspect)"
    con = min([x for x in [p25, davg] if x]) if (p25 or davg) else med
    return med, con, tr, vol, flag

def buy(i):
    r = P.get(i)
    return f(r, "best_buy"), (r or {}).get("best_buy_src", ""), (r or {}).get("order_buy_src", "")

# ---- A. orders -> AH (fresh LootSeller bids only)
A = []
for i, r in P.items():
    if r.get("order_buy_src") != "lootseller": continue
    bid = f(r, "order_buy"); med, con, tr, vol, flag = sale(i)
    if not bid or not med: continue
    st = int(r["stack"])
    # slot economics: one /ah slot holds one stack; assume a listing priced at the conservative level sells in
    # max(5 min, 2 x the average gap between settled sales of that item) -> cycles per hour per slot
    gap_min = 1440.0 / tr if tr else 1440.0
    sell_min = max(5.0, 2.0 * gap_min)
    cycles_per_hour = min(6.0, 60.0 / sell_min)
    per_stack = (con - bid) * st
    A.append(dict(item=r["name"], stack=st, order_bid=bid, ah_median=med, ah_conservative=con, spread_con=round(con - bid, 1),
                  spread_con_pct=round(100 * (con - bid) / bid, 1), per_stack_profit_con=round(per_stack), capital_per_stack=round(bid * st),
                  trades_per_day=int(tr), units_per_day=int(vol), day_cap_con=round((con - bid) * vol),
                  est_minutes_to_sell_stack=round(sell_min, 1), profit_per_slot_hour=round(per_stack * cycles_per_hour),
                  profit_per_hour_18_slots=round(per_stack * cycles_per_hour * 18), flag=flag))
A = [x for x in A if x["spread_con"] > 0]
A.sort(key=lambda x: -x["day_cap_con"])

# ---- B. crafts (liquid, non-enchantable, stack-priced)
def ing_id(x):
    if x is None: return None
    if isinstance(x, dict): return x.get("id")
    if isinstance(x, list): return x[0] if x else None
    return x
B = []
for res_id, variants in rec.items():
    res_id = int(res_id)
    for v in variants:
        counts = {}
        cells = [c for row in v.get("inShape", []) for c in row] if "inShape" in v else v.get("ingredients", [])
        for c in cells:
            i = ing_id(c)
            if i is not None and i >= 0: counts[i] = counts.get(i, 0) + 1
        if not counts: continue
        out_n = v.get("result", {}).get("count", 1)
        cost = 0.0; ok = True; parts = []; stale = False
        for i, n in counts.items():
            b, src, osrc = buy(i)
            if b is None: ok = False; break
            if src == "orders" and osrc == "finance_jun25": stale = True
            cost += n * b; parts.append(f"{byid[i]['name']}x{n}@{b:.0f}{'o' if src == 'orders' else 'a'}")
        if not ok: continue
        med, con, tr, vol, flag = sale(res_id)
        if not med or tr < 300: continue
        prof = out_n * con - cost
        if prof <= 0: continue
        B.append(dict(output=byid[res_id]["name"], out_n=out_n, inputs=" + ".join(parts), cost=round(cost, 1), ah_median=med, ah_conservative=con,
                      profit_per_craft_con=round(prof, 1), margin_pct=round(100 * prof / cost, 1) if cost else None, trades_per_day=int(tr),
                      units_per_day=int(vol), day_cap_con=round(prof / out_n * vol), input_price_stale=("yes" if stale else ""), flag=flag))
# keep best variant per output
best = {}
for x in B:
    k = x["output"]
    if k not in best or x["profit_per_craft_con"] > best[k]["profit_per_craft_con"]: best[k] = x
B = sorted(best.values(), key=lambda x: -x["day_cap_con"])

for name, rows in [("short_orders_to_ah", A), ("short_crafts", B)]:
    with open(f"{SP}/quant/{name}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

print("=== A. ORDERS -> AH (fresh order bids 2026-08-29, conservative AH sale price) ===")
print("%-24s %5s %11s %11s %11s %9s %7s %12s %12s %9s %14s %8s %12s %14s %s" % ("item", "stack", "order_bid", "ah_med", "ah_cons", "spread", "spr%", "$/stack", "capital/stk", "trades/d", "daycap(cons)", "min/sale", "$/slot-hr", "$/hr 18 slots", "flag"))
for x in sorted(A, key=lambda y: -y["profit_per_hour_18_slots"])[:45]:
    print("%-24s %5d %11s %11s %11s %9s %6s%% %12s %12s %9s %14s %8s %12s %14s %s" % (x["item"], x["stack"], "{:,.0f}".format(x["order_bid"]), "{:,.0f}".format(x["ah_median"]), "{:,.0f}".format(x["ah_conservative"]),
          "{:,.0f}".format(x["spread_con"]), x["spread_con_pct"], "{:,}".format(x["per_stack_profit_con"]), "{:,}".format(x["capital_per_stack"]), "{:,}".format(x["trades_per_day"]), "{:,}".format(x["day_cap_con"]),
          x["est_minutes_to_sell_stack"], "{:,}".format(x["profit_per_slot_hour"]), "{:,}".format(x["profit_per_hour_18_slots"]), x["flag"]))
print("\n=== B. CRAFT ARBITRAGE (>=300 AH trades/day, non-enchantable, conservative AH price; 'o' = orders price, 'a' = AH price; stale = June order price) ===")
print("%-28s %3s %11s %11s %11s %11s %8s %9s %14s %6s | %s" % ("output", "n", "cost", "ah_med", "ah_cons", "profit", "margin%", "trades/d", "daycap(cons)", "stale", "inputs"))
for x in B[:60]:
    print("%-28s %3d %11s %11s %11s %11s %7s%% %9s %14s %6s | %s" % (x["output"], x["out_n"], "{:,.0f}".format(x["cost"]), "{:,.0f}".format(x["ah_median"]), "{:,.0f}".format(x["ah_conservative"]),
          "{:,.0f}".format(x["profit_per_craft_con"]), x["margin_pct"], "{:,}".format(x["trades_per_day"]), "{:,}".format(x["day_cap_con"]), x["input_price_stale"], x["inputs"]))
