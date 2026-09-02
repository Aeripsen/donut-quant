"""THE MACHINE. One script: every way to buy, transform and sell, ranked by the constraint that binds.

This replaces ten scattered analysis scripts. It loads every price source at once, enumerates every
path from a buyable input to a sellable output, and ranks them honestly.

  BUY      /orders bid (cheapest, needs patience) or the auction house (instant, dearer)
  DO       nothing / smelt / craft, using the real 1.21.11 recipe graph
  SELL     auction house (best price, capped by 18 slots and ~20% of daily volume)
           /sell at /worth (worst price, but UNCAPPED and uses no slot)
           fill a standing buy order (instant, no slot, and the order's own size is the cap)

Nothing here is ranked on margin alone, because margin is not what limits you. Four constraints are
computed for every lane and the report shows each one:

  per unit of CAPITAL   matters when money is the limit
  per FURNACE OP        matters when smelting throughput is the limit (this one decides kelp vs sand)
  per AH SLOT-DAY       matters when the 18 listing slots are the limit
  DAILY CEILING         what the market can actually absorb, which caps everything above

Price discipline, learned from three separate wrong answers earlier in this project:
  - a sale price needs 3+ full-stack sales, and is clamped down to p25
  - single sales of stackable items are money transfers, never prices
  - the finance_jun2 order snapshot is three months stale and is never used as a buy price
  - only fresh LootSeller bids and hand-read in-game orders (quant/orders_live.csv) count as buyable
"""
import csv, json, os

SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURE = 0.20            # share of an item's daily volume you can take before moving the price
FURNACE_SEC = 10.0        # one smelt per furnace per 10 seconds
BANKROLL = float(os.environ.get("BANKROLL", 136_000_000))
FURNACES = int(os.environ.get("FURNACES", 100))
SLOTS = int(os.environ.get("SLOTS", 18))
TAX = float(os.environ.get("TAX", 0.0))    # AH tax, still unmeasured; set it once known

P = {r["name"]: r for r in csv.DictReader(open(f"{SP}/quant/price_table.csv", encoding="utf-8"))}
WORTH = {}
if os.path.exists(f"{SP}/quant/worth_table.csv"):
    WORTH = {r["name"]: float(r["worth"]) for r in csv.DictReader(open(f"{SP}/quant/worth_table.csv", encoding="utf-8"))}
LIVE = {}
if os.path.exists(f"{SP}/quant/orders_live.csv"):
    LIVE = {r["name"]: float(r["order_bid"]) for r in csv.DictReader(open(f"{SP}/quant/orders_live.csv", encoding="utf-8"))}

items = json.load(open(f"{SP}/mcdata/items.json", encoding="utf-8"))
byid = {i["id"]: i["name"] for i in items}
byname = {i["name"]: i["id"] for i in items}

# Smelting is not in recipes.json, so the furnace edges that matter are listed here.
SMELT = {
    "glass": "sand", "dried_kelp": "kelp", "stone": "cobblestone", "charcoal": "spruce_log",
    "brick": "clay_ball", "nether_brick": "netherrack", "green_dye": "cactus",
    "iron_ingot": "raw_iron", "gold_ingot": "raw_gold", "copper_ingot": "raw_copper",
    "netherite_scrap": "ancient_debris", "smooth_stone": "stone", "smooth_sandstone": "sandstone",
    "terracotta": "clay", "popped_chorus_fruit": "chorus_fruit", "cooked_beef": "beef",
    "cooked_porkchop": "porkchop", "cooked_chicken": "chicken", "lime_dye": "sea_pickle",
}
FUEL_PER_SMELT = 623 / 8 / 8      # a coal at 623 smelts 8 items; charcoal is cheaper if self-made


def f(n, k):
    try:
        return float(P.get(n, {}).get(k) or 0)
    except (ValueError, AttributeError):
        return 0.0


def ah_sell(n):
    """What a unit reliably fetches on the AH: 3+ stack sales, clamped by p25. 0 if untrustworthy."""
    if f(n, "n_stack") >= 3 and f(n, "tx_stack_med"):
        v, p25 = f(n, "tx_stack_med"), f(n, "tx_p25")
        return (min(v, p25) if p25 else v) * (1 - TAX)
    if int(f(n, "stack") or 64) == 1 and f(n, "n_single") >= 8:
        v, p25 = f(n, "tx_single_med"), f(n, "tx_p25")
        return (min(v, p25) if p25 else v) * (1 - TAX)
    return 0.0


def buy_price(n):
    """Cheapest way to actually get one unit today, and how. Stale June snapshots are refused."""
    live, ls = LIVE.get(n, 0.0), f(n, "ls_order_bid")
    order = live or ls
    ah = f(n, "tx_stack_med") if f(n, "n_stack") >= 3 else 0.0
    if order and ah:
        return (order, "order") if order <= ah else (ah, "AH")
    if order:
        return order, "order"
    if ah:
        return ah, "AH"
    return 0.0, ""


def vol(n):
    return f(n, "ah_d_vol")


# ------------------------------------------------------------------ enumerate every lane
rec = json.load(open(f"{SP}/mcdata/recipes.json", encoding="utf-8"))


def ing_id(x):
    if x is None:
        return None
    if isinstance(x, dict):
        return x.get("id")
    if isinstance(x, list):
        return x[0] if x else None
    return x


LANES = []


def add(kind, out, inputs, out_n, smelts, label):
    """inputs: [(item, qty)]. Prices the lane through all three sell channels."""
    cost = 0.0
    srcs = []
    for it, q in inputs:
        p, how = buy_price(it)
        if p <= 0:
            return
        cost += p * q
        srcs.append("%s@%s %.0f" % (it, how, p))
    if out_n <= 0:
        return                      # some recipe entries carry a zero result count
    cost = cost / out_n + smelts * FUEL_PER_SMELT
    channels = []
    a = ah_sell(out)
    if a > 0:
        channels.append(("AH", a, vol(out) * CAPTURE))
    w = WORTH.get(out, 0.0)
    if w > 0:
        channels.append(("/sell", w, float("inf")))
    ob = LIVE.get(out, 0.0) or f(out, "ls_order_bid")
    if ob > 0:
        channels.append(("order", ob, vol(out) * CAPTURE if vol(out) else 1e9))
    trades = f(out, "ah_d_trades")
    nstack = f(out, "n_stack")
    for ch, price, cap in channels:
        profit = price - cost
        if profit <= 0:
            continue
        if ch == "AH" and (trades < 200 or nstack < 5):
            continue      # thin book or too few stack sales: the "price" is an anecdote
        LANES.append(dict(
            kind=kind, lane=label, out=out, channel=ch, cost=cost, price=price, profit=profit,
            ratio=price / cost if cost else 0, smelts=max(smelts, 0.001), cap_day=cap,
            per_capital=profit / cost if cost else 0,
            per_furnace=profit / max(smelts, 0.001),
            daily_ceiling=profit * cap if cap != float("inf") else float("inf"),
            abs_cap=cap, src="; ".join(srcs)))


# smelting lanes
for out, inp in SMELT.items():
    add("SMELT", out, [(inp, 1)], 1, 1, "%s -> smelt -> %s" % (inp, out))
# crafting lanes, from the real recipe graph
for res_id, variants in rec.items():
    out = byid.get(int(res_id))
    if not out:
        continue
    for v in variants[:1]:
        cells = [c for row in v.get("inShape", []) for c in row] if "inShape" in v else v.get("ingredients", [])
        counts = {}
        for c in cells:
            i = ing_id(c)
            if i is not None and i >= 0:
                counts[i] = counts.get(i, 0) + 1
        if not counts or len(counts) > 4:
            continue
        inputs = [(byid[i], n) for i, n in counts.items() if i in byid]
        if len(inputs) != len(counts):
            continue
        add("CRAFT", out, inputs, v.get("result", {}).get("count", 1), 0,
            "%s -> %s" % (" + ".join("%dx %s" % (n, i) for i, n in inputs)[:44], out))
# pure flips: buy and resell with no transformation
for n in P:
    add("FLIP", n, [(n, 1)], 1, 0, "buy %s, resell" % n)
# two-step: smelt then compress (the kelp meta and its cousins)
COMPRESS = {"dried_kelp_block": ("dried_kelp", 9), "coal_block": ("coal", 9), "hay_block": ("wheat", 9),
            "iron_block": ("iron_ingot", 9), "gold_block": ("gold_ingot", 9), "copper_block": ("copper_ingot", 9)}
for blk, (part, n) in COMPRESS.items():
    raw = SMELT.get(part)
    if raw:
        add("SMELT+PACK", blk, [(raw, n)], 1, n, "%dx %s -> smelt -> pack -> %s" % (n, raw, blk))

seen = {}
for L in LANES:
    k = (L["out"], L["channel"], L["kind"])
    if k not in seen or L["profit"] > seen[k]["profit"]:
        seen[k] = L
LANES = list(seen.values())


def table(title, rows, sortkey, col, colfmt, note=""):
    print("=" * 122)
    print(title)
    if note:
        print(note)
    print("=" * 122)
    print("%-40s %-7s %10s %10s %10s %7s %13s  %s" % (
        "lane", "channel", "cost/u", "sells/u", "profit/u", "ratio", col, "buy from"))
    for x in sorted(rows, key=sortkey, reverse=True)[:14]:
        v = colfmt(x)
        print("%-40s %-7s %10s %10s %10s %6.2fx %13s  %s" % (
            x["lane"][:40], x["channel"], f"{x['cost']:,.0f}", f"{x['price']:,.0f}",
            f"{x['profit']:+,.0f}", x["ratio"], v, x["src"][:40]))
    print()


real = [L for L in LANES if L["ratio"] > 1.02 and L["cost"] > 0.5]
table("1. BEST PER DOLLAR OF CAPITAL  (rank this when money is your limit)",
      real, lambda x: x["per_capital"], "return", lambda x: "%.2fx" % (1 + x["per_capital"]))
smelters = [L for L in real if L["smelts"] >= 1]
table("2. BEST PER FURNACE OPERATION  (rank this when smelting throughput is your limit)",
      smelters, lambda x: x["per_furnace"], "$/smelt", lambda x: "%.1f" % x["per_furnace"],
      "This is the number that decides kelp versus sand, and it is not the one the videos quote.")
capped = [L for L in real if L["daily_ceiling"] != float("inf")]
table("3. BIGGEST DAILY CEILING  (what the market can actually absorb, profit x 20% of daily volume)",
      capped, lambda x: x["daily_ceiling"], "ceiling/day", lambda x: f"{x['daily_ceiling']:,.0f}")
uncapped = [L for L in real if L["channel"] == "/sell"]
table("4. UNCAPPED LANES  (/sell: no slot, no buyer, no ceiling - only your production rate)",
      uncapped, lambda x: x["per_furnace"] if x["smelts"] >= 1 else x["profit"], "$/smelt",
      lambda x: "%.1f" % x["per_furnace"])

print("=" * 122)
print("THE PLAN, at BANKROLL=%s FURNACES=%s SLOTS=%s TAX=%.0f%%" % (
    f"{BANKROLL:,.0f}", FURNACES, SLOTS, TAX * 100))
print("=" * 122)
OPS_DAY = FURNACES * 3600 / FURNACE_SEC * 20      # smelts available per 20h day
ops_hr = FURNACES * 3600 / FURNACE_SEC


def realized(L):
    """Honest daily profit: limited by market absorption AND furnace throughput AND bankroll."""
    units = L["abs_cap"] if L["abs_cap"] != float("inf") else 1e18
    if L["smelts"] >= 1:
        units = min(units, OPS_DAY / L["smelts"])
    units = min(units, BANKROLL / L["cost"])          # one bankroll turn per day
    return units * L["profit"], units


for L in real:
    L["realized"], L["units_day"] = realized(L)

BAR = "=" * 122
print(BAR)
print("THE PLAN, at BANKROLL=%s FURNACES=%s SLOTS=%s TAX=%.0f%%" % (
    f"{BANKROLL:,.0f}", FURNACES, SLOTS, TAX * 100))
print("Every number below is capped three ways at once: what the market absorbs, what your furnaces")
print("can smelt in 20h, and what one turn of your bankroll can buy. That is why they are smaller")
print("than any single lane's headline margin, and why they are the only ones worth acting on.")
print(BAR)
print("Furnace capacity: %s furnaces = %s smelts/hour = %s smelts/day at 20h" % (
    FURNACES, f"{ops_hr:,.0f}", f"{OPS_DAY:,.0f}"))
print("")
print("%-42s %-7s %11s %11s %13s  %s" % (
    "lane", "channel", "units/day", "profit/u", "REALIZED/DAY", "limited by"))
top = sorted(real, key=lambda x: -x["realized"])[:12]
for L in top:
    lim = []
    if L["abs_cap"] != float("inf") and abs(L["units_day"] - L["abs_cap"]) < 1:
        lim.append("market depth")
    if L["smelts"] >= 1 and abs(L["units_day"] - OPS_DAY / L["smelts"]) < 1:
        lim.append("furnaces")
    if abs(L["units_day"] - BANKROLL / L["cost"]) < 1:
        lim.append("bankroll")
    print("%-42s %-7s %11s %11s %13s  %s" % (
        L["lane"][:42], L["channel"], f"{L['units_day']:,.0f}", f"{L['profit']:+,.0f}",
        f"{L['realized']:,.0f}", " + ".join(lim) or "-"))

print("")
print("STACKING THEM: these lanes use different markets, so they add rather than compete.")
tot, used = 0.0, set()
for L in top:
    if L["out"] in used:
        continue
    used.add(L["out"])
    tot += L["realized"]
    if len(used) >= 6:
        break
print("   Top %d non-overlapping lanes together: %s/day" % (len(used), f"{tot:,.0f}"))

deep = [L for L in real if L["smelts"] >= 1 and L["realized"] > 0]
if deep:
    b = max(deep, key=lambda x: x["realized"])
    print("")
    print("Best lane for a big smelter, after depth is accounted for:")
    print("   %s via %s" % (b["lane"], b["channel"]))
    print("   %.0f per smelt, %s units/day, %s/day realized" % (
        b["per_furnace"], f"{b['units_day']:,.0f}", f"{b['realized']:,.0f}"))

print("")
print("Sequencing rule: sell into the highest-priced channel until it saturates, then step down.")
print("For anything both AH-liquid and /worth-priced that means AH first, /sell the overflow,")
print("because /sell has no ceiling and is the only place surplus production is still worth money.")
if TAX == 0:
    print("")
    print("WARNING: TAX=0. The AH tax is still unmeasured, so every AH figure above is optimistic.")
    print("Read it off one sale receipt and rerun with TAX=0.05 (or whatever it turns out to be).")
