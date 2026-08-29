"""Merge every price source into one per-item table: quant/price_table.csv

Sources (see ../SOURCES.md):
  SMP500 snapshot (AH settled sales, 1h/1d), jpsoftware (last AH sale), LootSeller (AH floor + top buy-order bid),
  donutsmp.finance (order book snapshot, June 25 2026 - stale), the player's own chat log, known /sell base prices.
"""
import json, csv, os, statistics
SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
items = json.load(open(f"{SP}/mcdata/items.json", encoding="utf-8"))
byid = {i["id"]: i for i in items}
byname = {i["name"]: i for i in items}
bydisp = {i["displayName"].lower(): i for i in items}
T = {}

def row(i):
    if i not in T:
        T[i] = {"id": i, "name": byid[i]["name"], "display": byid[i]["displayName"], "stack": byid[i]["stackSize"]}
    return T[i]

def num(x):
    try:
        return float(x) if x not in (None, "") else 0.0
    except ValueError:
        return 0.0

# 1) SMP500 settled AH sales
for ln in open(f"{SP}/api/smp500_snapshot.tsv", encoding="utf-8").read().split("\n")[1:]:
    if not ln.strip():
        continue
    p = ln.split()   # tabs were flattened to spaces when the snapshot passed through the browser
    if len(p) < 5:
        continue
    i = int(p[0]); r = row(i)
    d = [num(x) for x in p[2].split(",")]
    ds = [num(x) for x in p[3].split(",")]
    h = [num(x) for x in p[4].split(",")]
    r.update(ah_d_price=d[0], ah_d_vol=d[1], ah_d_trades=d[2], ah_d_min=d[3], ah_d_max=d[4],
             ah_ds_price=ds[0], ah_ds_vol=ds[1], ah_ds_trades=ds[2], ah_h_price=h[0], ah_h_vol=h[1], ah_h_trades=h[2])
    st = r["stack"]
    r["ah_stack_unit"] = round(ds[0] / st, 2) if ds[0] and st else None

# 1b) SMP500 last-15 settled sales per item -> robust medians (tabs flattened; empty fields dropped, so parse by counts)
p2 = f"{SP}/api/smp500_txmed.tsv"
if os.path.exists(p2):
    for ln in open(p2, encoding="utf-8").read().split("\n")[1:]:
        p = ln.split()
        if len(p) < 8 or not p[0].isdigit():
            continue
        try:
            i = int(p[0]); r = row(i)
            n_tx = int(p[2]); k = 3
            r["n_tx"] = n_tx
            r["tx_med"] = num(p[k]); r["tx_p25"] = num(p[k + 1]); r["tx_p75"] = num(p[k + 2]); r["tx_min"] = num(p[k + 3]); k += 4
            n_stack = int(p[k]); k += 1; r["n_stack"] = n_stack
            if n_stack > 0:
                r["tx_stack_med"] = num(p[k]); k += 1
            n_single = int(p[k]); k += 1; r["n_single"] = n_single
            if n_single > 0:
                r["tx_single_med"] = num(p[k]); k += 1
            if k < len(p):
                r["tx_newest_ms"] = p[k]
        except (ValueError, IndexError):
            continue
for i in byid:
    if i in T:
        T[i]["enchantable"] = 1 if byid[i].get("enchantCategories") else 0

# 2) jpsoftware last sale
for x in json.load(open(f"{SP}/api/jpsoftware_items.json", encoding="utf-8")):
    n = x["item_id"].replace("minecraft:", "")
    if n in byname:
        r = row(byname[n]["id"]); c = x.get("latest_count") or 1
        r["jp_last_unit"] = round((x.get("latest_price") or 0) / c, 2)
        r["jp_last_count"] = c
        r["jp_volume"] = x.get("trading_volume")

# 3) LootSeller floor + order bid
lsp = f"{SP}/api/lootseller_summary.json"
ls = json.load(open(lsp, encoding="utf-8")) if os.path.exists(lsp) else {}
for n, v in ls.items():
    if n in byname:
        r = row(byname[n]["id"])
        r["ls_ah_floor"] = v.get("ah_floor_close")
        r["ls_order_bid"] = v.get("order_bid_close")
        r["ls_order_bid_high"] = v.get("order_bid_high")
        r["ls_updated"] = v.get("lastUpdated")
        r["ls_order_t"] = v.get("order_bid_t")

# 4) donutsmp.finance order book (June 25 2026 snapshot)
for x in json.load(open(f"{SP}/api/finance_items.json", encoding="utf-8")):
    n = x["name"]
    if n in byname:
        r = row(byname[n]["id"]); vol = x.get("volume") or {}
        r["fin_order_realistic"] = vol.get("realisticSellPrice")
        r["fin_order_instant"] = vol.get("instantSellPrice")
        r["fin_order_top5"] = x.get("top5Avg")
        r["fin_order_median"] = x.get("median")
        r["fin_order_count"] = x.get("count")
        r["fin_fill_rate"] = vol.get("fillRate")
        r["fin_liq"] = vol.get("liquidityScore")
        r["fin_ah_last"] = x.get("ahLast")

# 5) player's own log
PLURAL = {"cooked porkchops": "cooked porkchop", "spruce logs": "spruce log", "ender pearls": "ender pearl",
          "golden carrots": "golden carrot", "gold ingots": "gold ingot", "iron ingots": "iron ingot",
          "chorus fruits": "chorus fruit", "steaks": "steak", "snowballs": "snowball", "ladders": "ladder",
          "vines": "vine", "leather cap": "leather helmet", "leather tunic": "leather chestplate"}

def match(disp):
    d = disp.lower().strip()
    for cand in [d, d[:-1] if d.endswith("s") else d + "s", PLURAL.get(d, "")]:
        if cand in bydisp:
            return bydisp[cand]["id"]
    return None

logp = {}
for e in csv.DictReader(open(f"{SP}/ah_events.csv", encoding="utf-8")):
    if not e["unit"] or e["type"] not in ("listed", "bought"):
        continue
    i = match(e["item"])
    if i is None:
        continue
    logp.setdefault(i, {}).setdefault(e["type"], []).append(float(e["unit"]))
for i, d in logp.items():
    r = row(i)
    if "bought" in d:
        r["log_bought_unit_med"] = round(statistics.median(d["bought"]), 1); r["log_bought_n"] = len(d["bought"])
    if "listed" in d:
        r["log_listed_unit_med"] = round(statistics.median(d["listed"]), 1); r["log_listed_n"] = len(d["listed"])

# 6) known /sell base prices (verify in game with /worth)
BASE = {"spruce_slab": 12, "dried_kelp_block": 300, "bone_meal": 30, "pink_petals": 10, "wildflowers": 10}
for n, v in BASE.items():
    if n in byname:
        row(byname[n]["id"])["base_sell"] = v

# 7) derived fields
for i, r in T.items():
    dp = r.get("ah_d_price") or 0; dsu = r.get("ah_stack_unit") or 0
    dst = r.get("ah_ds_trades") or 0; dt = r.get("ah_d_trades") or 0
    tsm = r.get("tx_stack_med") or 0; tm = r.get("tx_med") or 0; tsg = r.get("tx_single_med") or 0
    ns = r.get("n_stack") or 0; nt = r.get("n_tx") or 0; nsg = r.get("n_single") or 0
    # realistic bulk sell price on AH: median of recent full-stack sales, else median of recent sales, else averages
    if tsm and ns >= 3:
        r["ah_sell_unit"] = tsm; r["sell_basis"] = "tx_stack_med"
    elif tm and nt >= 5:
        r["ah_sell_unit"] = tm; r["sell_basis"] = "tx_med"
    elif dsu and dst >= 5:
        r["ah_sell_unit"] = dsu; r["sell_basis"] = "stack_avg"
    else:
        r["ah_sell_unit"] = dp if dt else None; r["sell_basis"] = "single_avg" if dt else ""
    r["ah_sell_single"] = tsg if (tsg and nsg >= 3) else (dp if dt else None)   # single-item sale price
    cands = [v for v in [tsm if ns >= 3 else None, tm if nt >= 5 else None, dsu if dst >= 5 else None, r.get("jp_last_unit")] if v]
    r["ah_buy_unit"] = min(cands) if cands else None                           # cheapest realistic AH buy
    ob = r.get("ls_order_bid")
    if ob:
        r["order_buy"] = ob; r["order_buy_src"] = "lootseller"
    elif r.get("fin_order_realistic"):
        r["order_buy"] = r["fin_order_realistic"]; r["order_buy_src"] = "finance_jun25"
    else:
        r["order_buy"] = None; r["order_buy_src"] = ""
    opts = [v for v in [r.get("order_buy"), r.get("ah_buy_unit")] if v]
    r["best_buy"] = min(opts) if opts else None
    r["best_buy_src"] = "orders" if (r.get("order_buy") and r["best_buy"] == r.get("order_buy")) else ("ah" if r["best_buy"] else "")

cols = ["id", "name", "display", "stack", "ah_d_price", "ah_d_vol", "ah_d_trades", "ah_d_min", "ah_d_max", "ah_ds_price", "ah_ds_vol",
        "ah_ds_trades", "ah_stack_unit", "ah_h_price", "ah_h_vol", "ah_h_trades", "jp_last_unit", "jp_last_count", "jp_volume",
        "ls_ah_floor", "ls_order_bid", "ls_order_bid_high", "ls_updated", "fin_order_realistic", "fin_order_instant", "fin_order_top5",
        "fin_order_median", "fin_order_count", "fin_fill_rate", "fin_liq", "fin_ah_last", "log_bought_unit_med", "log_bought_n",
        "log_listed_unit_med", "log_listed_n", "base_sell", "n_tx", "tx_med", "tx_p25", "tx_p75", "tx_min", "n_stack", "tx_stack_med",
        "n_single", "tx_single_med", "tx_newest_ms", "enchantable", "ah_sell_unit", "sell_basis", "ah_sell_single", "ah_buy_unit",
        "order_buy", "order_buy_src", "best_buy", "best_buy_src"]
with open(f"{SP}/quant/price_table.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader()
    for i in sorted(T):
        w.writerow(T[i])
print("price_table rows:", len(T), "| with order_buy:", sum(1 for r in T.values() if r.get("order_buy")),
      "| lootseller fresh:", sum(1 for r in T.values() if r.get("ls_order_bid")))
