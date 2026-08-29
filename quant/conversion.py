"""Conversion optimizer: for a raw input you can buy on /orders, which product form is worth most per input unit on /ah?

Why this matters on DonutSMP: AH buyers think in stacks (a stack of most basic blocks clears for ~5-20K regardless of what
it is), so 1 log (1/64 of a ~20K stack) turned into 8 slabs or 8 sticks (8/64 of a ~10-20K stack) multiplies value.
Prices: median of the last 15 settled full-stack AH sales (tx_stack_med) = 'median'; 25th percentile of the last 15 sales = 'conservative'.
Chains up to depth 2 (raw -> A -> B). Secondary ingredients are costed at their best buy price.
"""
import json, csv, os
SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
items = json.load(open(f"{SP}/mcdata/items.json", encoding="utf-8")); byid = {i["id"]: i for i in items}; byname = {i["name"]: i for i in items}
P = {int(r["id"]): r for r in csv.DictReader(open(f"{SP}/quant/price_table.csv", encoding="utf-8"))}
rec = json.load(open(f"{SP}/mcdata/recipes.json", encoding="utf-8"))

def f(r, k):
    v = r.get(k) if r else None
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None

def ing_id(x):
    if x is None: return None
    if isinstance(x, dict): return x.get("id")
    if isinstance(x, list): return x[0] if x else None
    return x

# recipes as (output_id, out_n, {input_id: count})
R = []
for res_id, variants in rec.items():
    for v in variants:
        counts = {}
        cells = [c for row in v.get("inShape", []) for c in row] if "inShape" in v else v.get("ingredients", [])
        for c in cells:
            i = ing_id(c)
            if i is not None and i >= 0:
                counts[i] = counts.get(i, 0) + 1
        if counts:
            R.append((int(res_id), v.get("result", {}).get("count", 1), counts))
by_input = {}
for out, n, counts in R:
    for i in counts:
        by_input.setdefault(i, []).append((out, n, counts))

def sell(i):
    r = P.get(i)
    if not r: return None, None, 0, 0
    st = int(r["stack"]); ns = f(r, "n_stack") or 0; nt = f(r, "n_tx") or 0
    if r.get("enchantable") == "1": return None, None, 0, 0
    med = f(r, "tx_stack_med") if (st > 1 and ns >= 3) else (f(r, "tx_med") if nt >= 5 else None)
    con = f(r, "tx_p25") if nt >= 5 else None
    if med and con and con > med: con = med
    return med, con, f(r, "ah_d_vol") or 0, f(r, "ah_d_trades") or 0

def cost_other(counts, raw):
    c = 0.0
    for i, n in counts.items():
        if i == raw: continue
        b = f(P.get(i), "best_buy")
        if b is None: return None
        c += n * b
    return c

def options(raw, depth=2):
    """yield (chain_desc, out_id, out_units_per_raw, other_cost_per_raw)"""
    for out, n, counts in by_input.get(raw, []):
        k = counts[raw]; oc = cost_other(counts, raw)
        if oc is None: continue
        yield (f"{byid[raw]['name']} x{k} -> {byid[out]['name']} x{n}", out, n / k, oc / k)
        if depth > 1:
            for out2, n2, counts2 in by_input.get(out, []):
                k2 = counts2[out]; oc2 = cost_other(counts2, out)
                if oc2 is None: continue
                units2 = (n / k) * (n2 / k2)
                yield (f"{byid[raw]['name']} x{k} -> {byid[out]['name']} x{n} -> {byid[out2]['name']} x{n2}", out2, units2, oc / k + (n / k) * oc2 / k2)

RAWS = ["spruce_log", "oak_log", "birch_log", "cobblestone", "cobbled_deepslate", "stone", "bone", "bone_meal", "kelp", "iron_ingot", "gold_ingot",
        "copper_ingot", "diamond", "emerald", "redstone", "coal", "lapis_lazuli", "quartz", "sand", "gunpowder", "obsidian", "crying_obsidian",
        "glowstone_dust", "glowstone", "blaze_rod", "nether_wart", "sugar_cane", "bamboo", "string", "leather", "slime_ball", "ender_pearl",
        "ender_eye", "ghast_tear", "wheat", "pumpkin", "melon_slice", "cactus", "netherrack", "blackstone", "basalt", "tuff", "deepslate", "amethyst_shard",
        "honeycomb", "clay_ball", "dried_kelp", "wool", "white_wool", "paper", "glass", "iron_block", "gold_block", "nether_star", "spruce_planks", "stick"]
out_rows = []
for rn in RAWS:
    if rn not in byname: continue
    raw = byname[rn]["id"]; r = P.get(raw)
    buy = f(r, "best_buy"); src = (r or {}).get("best_buy_src", "")
    own_med, own_con, own_vol, own_tr = sell(raw)
    if buy is None: continue
    best = []
    for desc, out, units, oc in options(raw):
        med, con, vol, tr = sell(out)
        if med is None: continue
        best.append(dict(raw=rn, buy=buy, buy_src=src, chain=desc, out=byid[out]["name"], units_per_raw=round(units, 3),
                         other_cost_per_raw=round(oc, 1), value_med_per_raw=round(units * med, 1), value_con_per_raw=round(units * (con or med), 1),
                         profit_med_per_raw=round(units * med - oc - buy, 1), profit_con_per_raw=round(units * (con or med) - oc - buy, 1),
                         out_vol_day=int(vol), out_trades_day=int(tr), out_med=med, out_con=con))
    best.sort(key=lambda x: -x["profit_con_per_raw"])
    out_rows.append(dict(raw=rn, buy=buy, buy_src=src, chain="(sell raw as-is on AH)", out=rn, units_per_raw=1, other_cost_per_raw=0,
                         value_med_per_raw=own_med, value_con_per_raw=own_con, profit_med_per_raw=round((own_med or 0) - buy, 1),
                         profit_con_per_raw=round((own_con or own_med or 0) - buy, 1), out_vol_day=int(own_vol), out_trades_day=int(own_tr), out_med=own_med, out_con=own_con))
    out_rows.extend(best[:6])
with open(f"{SP}/quant/conversion.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys())); w.writeheader(); w.writerows(out_rows)
cur = None
for x in out_rows:
    if x["raw"] != cur:
        cur = x["raw"]; print(f"\n### {cur}  buy {x['buy']:,.0f} ({x['buy_src']})")
    print(f"  {x['chain']:70s} units/raw {x['units_per_raw']:>7} | value med {x['value_med_per_raw'] or 0:>9,.0f} con {x['value_con_per_raw'] or 0:>9,.0f} | profit/raw med {x['profit_med_per_raw']:>9,.0f} con {x['profit_con_per_raw']:>9,.0f} | out trades/d {x['out_trades_day']:>6,} vol {x['out_vol_day']:>9,}")
