"""Crafting-arbitrage scan over every Minecraft 1.21.11 recipe using quant/price_table.csv

For each recipe: input cost = sum(count x best_buy) where best_buy = min(order bid, cheapest AH unit).
Output value = realistic AH bulk unit price (stack sales) or the /sell base price if that is higher.
Throughput model: one hopper line feeds 2.5 items/s = 9000 items/h into a crafter.
Market cap: you cannot sell more per day than the AH actually absorbed in the last 24h (SMP500 volume).
"""
import json, csv, os
SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
items = json.load(open(f"{SP}/mcdata/items.json", encoding="utf-8")); byid = {i["id"]: i for i in items}
P = {int(r["id"]): r for r in csv.DictReader(open(f"{SP}/quant/price_table.csv", encoding="utf-8"))}
HOPPER_PER_HR = 9000

def f(r, k):
    v = r.get(k) if r else None
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None

def ing_id(x):
    if x is None:
        return None
    if isinstance(x, dict):
        return x.get("id")
    if isinstance(x, list):
        return x[0] if x else None
    return x

rec = json.load(open(f"{SP}/mcdata/recipes.json", encoding="utf-8"))
rows = []
for res_id, variants in rec.items():
    res_id = int(res_id)
    for v in variants:
        counts = {}
        if "inShape" in v:
            for rowv in v["inShape"]:
                for c in rowv:
                    i = ing_id(c)
                    if i is not None and i >= 0:
                        counts[i] = counts.get(i, 0) + 1
        elif "ingredients" in v:
            for c in v["ingredients"]:
                i = ing_id(c)
                if i is not None and i >= 0:
                    counts[i] = counts.get(i, 0) + 1
        else:
            continue
        if not counts:
            continue
        out_n = v.get("result", {}).get("count", 1)
        cost = 0.0; ok = True; srcs = []
        for i, n in counts.items():
            r = P.get(i); b = f(r, "best_buy")
            if b is None:
                ok = False; break
            cost += n * b
            srcs.append("%s x%d @%.0f%s" % (byid[i]["name"], n, b, "o" if r.get("best_buy_src") == "orders" else "a"))
        if not ok:
            continue
        ro = P.get(res_id)
        sell = f(ro, "ah_sell_unit"); sells = f(ro, "ah_sell_single"); base = f(ro, "base_sell")
        vol = f(ro, "ah_d_vol") or 0; trades = f(ro, "ah_d_trades") or 0
        ench = (ro or {}).get("enchantable") == "1"
        ntx = f(ro, "n_tx") or 0
        if ench and not base:
            continue   # AH prices of tools/armor/books are dominated by enchanted items; plain crafts do not get that price
        if sell is not None and ntx < 5 and not base:
            continue   # too thin to trust
        stale_in = any(s.endswith("o") and P.get(i, {}).get("order_buy_src") == "finance_jun25" for i, s in zip(counts, srcs))
        if sell is None and base is None:
            continue
        best_out = max([x for x in [sell, base] if x])
        rev = out_n * best_out; profit = rev - cost
        items_per_craft = sum(counts.values())
        crafts_hr = HOPPER_PER_HR / items_per_craft
        rows.append(dict(output=byid[res_id]["name"], out_n=out_n, inputs=" + ".join(srcs), cost=round(cost, 1),
                         sell_unit=round(best_out, 1), sell_channel="base" if (base and best_out == base) else "ah",
                         revenue=round(rev, 1), profit_per_craft=round(profit, 1),
                         margin_pct=round(100 * profit / cost, 1) if cost else None,
                         profit_per_input_item=round(profit / items_per_craft, 2),
                         crafts_per_hr_per_line=round(crafts_hr), profit_per_hr_per_line=round(profit * crafts_hr),
                         out_daily_ah_units=int(vol), out_daily_trades=int(trades),
                         max_profit_per_day_by_volume=round(profit / out_n * vol) if vol else 0,
                         ah_single_sell=sells, sell_basis=(ro or {}).get("sell_basis", ""), out_n_tx=int(ntx),
                         stale_order_input=("STALE-JUN25" if stale_in else "")))
rows.sort(key=lambda r: -(r["profit_per_hr_per_line"] or 0))
with open(f"{SP}/quant/crafting_arbitrage.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("recipes priced:", len(rows))

def show(title, rs, n=30):
    print("\n=== %s ===" % title)
    for r in rs[:n]:
        print("%-34s x%-2d cost %10s -> %10s (%s) profit/craft %9s %7s%%  $/hr/line %12s  daycap %13s  vol/d %8s | %s" % (
            r["output"], r["out_n"], "{:,.0f}".format(r["cost"]), "{:,.0f}".format(r["revenue"]), r["sell_channel"],
            "{:,.0f}".format(r["profit_per_craft"]), r["margin_pct"], "{:,.0f}".format(r["profit_per_hr_per_line"]),
            "{:,.0f}".format(r["max_profit_per_day_by_volume"]), "{:,}".format(r["out_daily_ah_units"]), r["inputs"]))

liquid = [r for r in rows if r["out_daily_trades"] >= 50 and r["profit_per_craft"] > 0]
show("TOP by $/hr per crafter line (liquid outputs: >=50 AH trades/day)", liquid, 35)
show("TOP by max profit/day capped by AH volume (liquid)", sorted(liquid, key=lambda r: -r["max_profit_per_day_by_volume"]), 35)
show("TOP by margin pct (liquid, cost>=100)", sorted([r for r in liquid if r["cost"] >= 100], key=lambda r: -(r["margin_pct"] or 0)), 25)
