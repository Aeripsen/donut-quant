"""Autocrafter lanes: the server does the buying, the crafters do the work, you press nothing.

This is the shape of every genuinely scalable lane found so far, and it has three parts:

  1. /orders buys the input.   You post a buy order slightly over the standing bid. Every farmer on the
     server delivers to you while you are offline. No clicking, no slots consumed while it fills.
  2. Crafters do the labour.   A bank of vanilla crafters converts input to output continuously. One
     video's build turned "half a million planks in 25 seconds" through 256 crafters, which cost about
     1.3M to buy.
  3. The output market absorbs it. The lane only works if the finished item has a deep book, because
     depth, not craft speed, is the ceiling.

The reference lane is the chest crafter (Tomax's design, popularised by Melton): 2 logs -> 8 planks ->
1 chest. Logs are among the cheapest things on the order book and chests trade over 700,000 units a
day. The video claims 300-750M an hour; the honest figure at 20 percent of daily chest volume is about
91M a day, which is still the best AFK lane in this repo.

PRICE DISCIPLINE, learned the hard way: only fresh LootSeller order bids count. The finance_jun2
snapshot is three months stale and quoting it produced fantasy numbers twice before (see engine.py).
Any lane whose input has no fresh bid is printed in a separate UNVERIFIED section, never mixed in.
"""
import csv, os

SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = {r["name"]: r for r in csv.DictReader(open(f"{SP}/quant/price_table.csv", encoding="utf-8"))}
CAPTURE = 0.20


def f(n, k):
    try:
        return float(P.get(n, {}).get(k) or 0)
    except (ValueError, AttributeError):
        return 0.0


def fresh_bid(n):
    """Only a LootSeller order bid is trusted; finance_jun2 is a stale June snapshot."""
    return f(n, "ls_order_bid")


def sale(n):
    """Clamped sale price: stack median held down by p25."""
    sm, p25 = f(n, "tx_stack_med"), f(n, "tx_p25")
    if sm <= 0:
        return 0.0
    return min(sm, p25) if p25 else sm


# (label, [(input, units per output)], output, note)
LANES = [
    ("chest crafter", [("spruce_log", 2)], "chest",
     "2 logs -> 8 planks -> 1 chest. THE lane: deepest output book on the board"),
    ("TNT autocraft", [("gunpowder", 5), ("sand", 4)], "tnt",
     "871,838 units/day of market; needs a creeper farm or a big gunpowder order"),
    ("hopper line", [("iron_ingot", 5), ("chest", 1)], "hopper", "check: hopper bid is unwinding"),
    ("bone meal", [("bone", 1)], "bone_meal", "1 bone -> 3 meal; uncraft, not craft"),
    ("planks only", [("spruce_log", 1)], "spruce_planks", "1 log -> 4 planks, the half-step"),
    ("stone slabs", [("stone", 1)], "stone_slab", "stonecutter: 1 -> 2 slabs"),
    ("crafting tables", [("spruce_log", 1)], "crafting_table", "1 log -> 4 planks -> 1 table"),
    ("barrels", [("spruce_log", 2)], "barrel", "6 planks + 2 slabs; the wiki's starter method"),
    ("ladders", [("spruce_log", 1)], "ladder", "7 sticks -> 3 ladders"),
    ("boats", [("spruce_log", 2)], "spruce_boat", "5 planks per boat"),
]

OUT_N = {"bone_meal": 3, "spruce_planks": 4, "stone_slab": 2}

verified, unverified = [], []
for label, inputs, out, note in LANES:
    osell = sale(out)
    if osell <= 0:
        continue
    n_out = OUT_N.get(out, 1)
    cost = 0.0
    stale = False
    for item, qty in inputs:
        b = fresh_bid(item)
        if b <= 0:
            b = sale(item)          # fall back to what it costs on the AH
            if b <= 0:
                cost = -1
                break
            stale = True
        cost += b * qty
    if cost < 0:
        continue
    cost /= n_out
    margin = osell - cost
    vol = f(out, "ah_d_vol")
    ns = int(f(out, "n_stack"))
    row = dict(lane=label, cost=round(cost), sells=round(osell), margin=round(margin),
               mult=round(osell / cost, 2) if cost else 0, trades=int(f(out, "ah_d_trades")),
               vol=int(vol), capture=round(margin * vol * CAPTURE), n_stack=ns,
               conf="solid" if ns >= 7 else ("THIN" if ns >= 3 else "no data"), note=note)
    (unverified if stale else verified).append(row)

verified.sort(key=lambda x: -x["capture"])
unverified.sort(key=lambda x: -x["capture"])


def show(title, rows, note):
    print("=" * 108)
    print(title)
    print(note)
    print("=" * 108)
    print("%-18s %9s %9s %9s %7s %10s %12s %14s %8s %s" % (
        "lane", "cost/u", "sells/u", "margin", "mult", "trades/d", "market u/d", "20% capture/d",
        "n stacks", "confidence"))
    for x in rows:
        print("%-18s %9s %9s %9s %6sx %10s %12s %14s %8s %s" % (
            x["lane"], f"{x['cost']:,}", f"{x['sells']:,}", f"{x['margin']:+,}", x["mult"],
            f"{x['trades']:,}", f"{x['vol']:,}", f"{x['capture']:+,}", x["n_stack"], x["conf"]))
        if x["note"]:
            print("      %s" % x["note"])
    print()


show("VERIFIED: every input priced off a FRESH order bid", verified,
     "These are safe to size up. The input is something you can actually buy at that price today.")
show("UNVERIFIED: input has no fresh order bid, priced at AH cost instead", unverified,
     "Directionally interesting, but confirm the real order price before committing capital.")

# rank the headline lane by confidence first, then money: a 27x on three sales is a rumour
solid = [x for x in verified if x["conf"] == "solid"]
if solid:
    b = solid[0]
    print("SCALE-UP on the best SOLID lane (%s, %d confirmed stack sales):" % (b["lane"], b["n_stack"]))
    for pct in (0.05, 0.10, 0.20, 0.35, 0.50):
        units = b["vol"] * pct
        print("   %4.0f%% of daily volume = %9s units/day x %s margin = %15s /day" % (
            pct * 100, f"{units:,.0f}", f"{b['margin']:,}", f"{units * b['margin']:,.0f}"))
    thin = [x for x in verified if x["conf"] == "THIN"]
    if thin:
        print("\n   Thin-data lanes worth ONE test stack before believing: " +
              ", ".join("%s (%sx on %d stack sales)" % (x["lane"], x["mult"], x["n_stack"]) for x in thin))
    print("\n   Build cost: 256 crafters at %s each = %s, plus shulker boxes at %s." % (
        f"{f('crafter','tx_stack_med'):,.0f}", f"{256 * f('crafter','tx_stack_med'):,.0f}",
        f"{fresh_bid('shulker_box'):,.0f}"))
    print("   Input draw at 20%% capture: %s logs/day. Post the order well above the %s bid to pull that." % (
        f"{b['vol'] * 0.2 * 2:,.0f}", f"{fresh_bid('spruce_log'):,.0f}"))
