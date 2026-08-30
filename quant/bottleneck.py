"""Bottleneck scanner: find the scarce ingredient that a valuable thing needs, before the market prices it in.

This is the Ghast Tear pattern, generalised. A bottleneck is an item where ALL of these hold:
  1. Real demand flows THROUGH it: it is an input to outputs that people actually buy in volume.
  2. Supply is thin: few units trade per day relative to that downstream demand.
  3. It is still cheap: the price has not yet caught up with the value it unlocks.
  4. One player can move it: a day of supply costs less than his bankroll.

Scores, per item X:
  pull        = sum over recipes using X of (output unit value x output units sold per day) / (units of X per craft)
                i.e. how many dollars of finished-goods demand flow through one unit of X per day.
  capture     = pull / price   -> dollars of downstream demand each dollar of X unlocks. High = underpriced input.
  thinness    = pull / (X units sold per day)  -> demand per available unit. High = supply cannot meet the pull.
  corner_cost = price x X units sold per day   -> cash to absorb one day of supply.
  momentum    = order-bid change over the LootSeller candle window (someone already accumulating?).

Deliberately NOT a buy list on its own: an item can score high because its only output is illiquid junk.
Read `top_outputs` on each row to see what the pull is actually made of.
"""
import csv, glob, json, os

SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
items = json.load(open(f"{SP}/mcdata/items.json", encoding="utf-8"))
byid = {i["id"]: i for i in items}
byname = {i["name"]: i for i in items}
P = {int(r["id"]): r for r in csv.DictReader(open(f"{SP}/quant/price_table.csv", encoding="utf-8"))}


def f(r, k):
    try:
        return float(r.get(k) or 0)
    except (ValueError, AttributeError):
        return 0.0


def sell_price(i):
    """Conservative unit value of an item on the AH."""
    r = P.get(i)
    if not r:
        return 0.0
    if r.get("enchantable") == "1":
        return 0.0                      # enchanted copies dominate; unusable as a value signal
    st = f(r, "n_stack")
    if st >= 3 and f(r, "tx_stack_med"):
        return f(r, "tx_stack_med")
    if f(r, "n_tx") >= 5 and f(r, "tx_med"):
        return f(r, "tx_med")
    return 0.0


def acquire_price(i):
    """Cheapest realistic way to get one unit."""
    r = P.get(i)
    if not r:
        return 0.0
    return f(r, "best_buy") or sell_price(i)


# ---- momentum from the LootSeller daily candles (order bid = what buyers are willing to pay)
momentum = {}
for path in glob.glob(f"{SP}/api/lootseller/*.json"):
    try:
        d = json.load(open(path, encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        continue
    oc = d.get("orderCandles") or []
    if len(oc) < 3:
        continue
    name = os.path.basename(path)[:-5]
    first, last = oc[0].get("c") or 0, oc[-1].get("c") or 0
    if first > 0:
        momentum[name] = {"bid_change_pct": round(100 * (last - first) / first, 1),
                          "days": len(oc), "bid_now": last, "bid_then": first}

# ---- build the recipe graph: which outputs does each input feed?
rec = json.load(open(f"{SP}/mcdata/recipes.json", encoding="utf-8"))


def ing_id(x):
    if x is None:
        return None
    if isinstance(x, dict):
        return x.get("id")
    if isinstance(x, list):
        return x[0] if x else None
    return x


uses = {}       # input id -> list of (output id, units of input per craft, outputs per craft)
for res_id, variants in rec.items():
    res_id = int(res_id)
    for v in variants:
        counts = {}
        cells = [c for row in v.get("inShape", []) for c in row] if "inShape" in v else v.get("ingredients", [])
        for c in cells:
            i = ing_id(c)
            if i is not None and i >= 0:
                counts[i] = counts.get(i, 0) + 1
        if not counts:
            continue
        out_n = v.get("result", {}).get("count", 1)
        for i, n in counts.items():
            uses.setdefault(i, []).append((res_id, n, out_n))

# ---- non-craft demand sinks the recipe graph cannot see (brewing, and known server uses)
EXTRA_PULL = {
    "ghast_tear":           [("end crystal + regeneration brewing", 15_600)],
    "blaze_powder":         [("brewing fuel for every potion", 859)],
    "nether_wart":          [("base of every potion", 1_703)],
    "glass_bottle":         [("3 per brew, every potion", 1_094)],
    "magma_cream":          [("fire resistance brewing", 3_438)],
    "pufferfish":           [("water breathing brewing", 21_875)],
    "fermented_spider_eye": [("weakness/slowness/invis brewing", 9_375)],
    "glistering_melon_slice": [("healing brewing", 6_219)],
    "golden_carrot":        [("night vision brewing", 2_953)],
    "breeze_rod":           [("wind charges + mace", 27_969)],
    "heavy_core":           [("mace", 3_899_990)],
    "shulker_shell":        [("shulker boxes", 4_688)],
    "crying_obsidian":      [("respawn anchors", 4_375)],
    "glowstone":            [("respawn anchors + potion II", 8_333)],
    "wither_skeleton_skull": [("withers -> nether stars -> beacons", 31_000)],
    "netherite_scrap":      [("netherite gear", 1_941_488)],
}

rows = []
for i, r in P.items():
    name = r["name"]
    price = acquire_price(i)
    if price <= 0:
        continue
    own_vol = f(r, "ah_d_vol")
    own_trades = f(r, "ah_d_trades")
    pull = 0.0
    contributors = []
    for out, n_in, n_out in uses.get(i, []):
        ov = sell_price(out)
        ovol = f(P.get(out, {}), "ah_d_vol")
        if ov <= 0 or ovol <= 0:
            continue
        # dollars of downstream demand per unit of this input, per day
        contrib = (ov * n_out / n_in) * (ovol / max(n_out, 1))
        if contrib > 0:
            pull += contrib
            contributors.append((byid[out]["name"], round(contrib)))
    for label, unit_val in EXTRA_PULL.get(name, []):
        # brewing/server sinks: value one unit at the output's own unit value, times this item's own daily volume
        contrib = unit_val * max(own_vol, 1)
        pull += contrib
        contributors.append((label, round(contrib)))
    if pull <= 0:
        continue
    contributors.sort(key=lambda x: -x[1])
    mom = momentum.get(name, {})
    rows.append(dict(
        item=name,
        price=round(price, 1),
        price_src=r.get("best_buy_src", ""),
        ah_value=round(sell_price(i), 1),
        units_per_day=int(own_vol),
        trades_per_day=int(own_trades),
        pull=round(pull),
        capture=round(pull / price, 1),
        thinness=round(pull / max(own_vol, 1)),
        corner_cost=round(price * own_vol),
        bid_change_pct=mom.get("bid_change_pct", ""),
        bid_now=mom.get("bid_now", ""),
        top_outputs="; ".join(f"{n}({v:,})" for n, v in contributors[:3]),
    ))

rows.sort(key=lambda x: -x["capture"])
with open(f"{SP}/quant/bottlenecks.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)


def show(title, rs, n=22):
    print(f"\n=== {title} ===")
    print("%-24s %10s %8s %14s %10s %9s %14s %7s | %s" % (
        "item", "price", "src", "pull/day", "capture", "thin", "corner cost", "bid%", "what pulls it"))
    for x in rs[:n]:
        print("%-24s %10s %8s %14s %10s %9s %14s %7s | %s" % (
            x["item"], f"{x['price']:,.0f}", x["price_src"][:8], f"{x['pull']:,.0f}", f"{x['capture']:,.0f}",
            f"{x['thinness']:,.0f}", f"{x['corner_cost']:,.0f}", x["bid_change_pct"], x["top_outputs"][:58]))


LIQUID = [x for x in rows if x["trades_per_day"] >= 200]
show("A. UNDERPRICED INPUTS: most downstream demand per dollar spent (liquid)", LIQUID)
show("B. SUPPLY SQUEEZE: most demand per available unit (thin supply, real pull)",
     sorted(LIQUID, key=lambda x: -x["thinness"]))
show("C. CORNERABLE: a whole day of supply costs under $20M",
     sorted([x for x in LIQUID if 0 < x["corner_cost"] <= 20_000_000], key=lambda x: -x["capture"]))
mom_rows = [x for x in rows if x["bid_change_pct"] != "" and x["bid_change_pct"] > 0]
show("D. ALREADY MOVING: buy-order bids rising (someone is accumulating)",
     sorted(mom_rows, key=lambda x: -x["bid_change_pct"]), 18)
falling = [x for x in rows if x["bid_change_pct"] != "" and x["bid_change_pct"] < -20]
show("E. BEATEN DOWN but still load-bearing (bid fell hard, pull intact)",
     sorted(falling, key=lambda x: -x["capture"]), 15)
print(f"\n{len(rows)} items scored. Full table: quant/bottlenecks.csv")
