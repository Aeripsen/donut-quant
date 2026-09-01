"""Transformation scanner: villager trades, smelting, and every other way to turn item A into item B
that the crafting recipe graph cannot see.

Why this exists: engine.py prices crafts, brews, flips and holds, but a villager is a machine that converts
32 rotten flesh into an emerald and an emerald into 10 bricks, and a furnace turns 155 cobblestone into 547
stone. Those edges never appear in recipes.json, so the engine was blind to them.

The crowding rule, learned from the raid farm video ("The New Meta on Donut SMP is Insane", DrDonut Clips):
once a method is on YouTube everyone runs it and the margin dies. The candles prove it: totem order bid
peaked at 220,000, sits at 103,000 now; respawn anchor bid 60,000 down to 17,700. So every edge here carries
a crowd flag. The money is in edges with no video, or edges where the video sells YOU the inputs cheap
(everyone farming raids dumps emeralds, and emeralds are the input to every villager sell trade).

Villager math (Java 1.21): a trade locks after max_uses, restocks up to twice a day at a workstation, so one
villager runs one trade about 2 x max_uses times a day. That caps every villager lane per head; scale = heads.
Zombie curing discounts what a villager SELLS (emerald cost can fall to 1); it does not reduce the items a
BUY trade demands. Trade rates below are vanilla wiki values; DonutSMP is vanilla-mechanics, but verify one
trade in game before building a hall.
"""
import csv, os

SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = {r["name"]: r for r in csv.DictReader(open(f"{SP}/quant/price_table.csv", encoding="utf-8"))}


def f(r, k):
    try:
        return float(r.get(k) or 0)
    except (ValueError, AttributeError):
        return 0.0


def cost(name):
    """What a unit really costs to BUY today: fresh stack median first, never a June order snapshot."""
    r = P.get(name)
    if not r:
        return None, "?"
    if f(r, "n_stack") >= 3 and f(r, "tx_stack_med"):
        return f(r, "tx_stack_med"), "A"
    if f(r, "n_tx") >= 5 and f(r, "tx_med"):
        return f(r, "tx_med"), "B"
    return None, "?"


def revenue(name):
    """What a unit SELLS for: a fresh order bid fills instantly with no AH slot, else the stack median."""
    r = P.get(name)
    if not r:
        return None, ""
    bid = f(r, "ls_order_bid")
    if bid > 0:
        return bid, "order fill, no slot"
    if f(r, "n_stack") >= 3 and f(r, "tx_stack_med"):
        return f(r, "tx_stack_med"), "AH stack"
    return None, ""


def depth(name):
    r = P.get(name, {})
    return int(f(r, "ah_d_trades")), int(f(r, "ah_d_vol"))


# item -> emerald (villager buy trades): (input, units per emerald, max_uses, profession)
EM_IN = [
    ("rotten_flesh", 32, 16, "cleric"), ("gold_ingot", 3, 12, "cleric"), ("nether_wart", 22, 12, "cleric"),
    ("glass_bottle", 9, 12, "cleric"), ("stick", 32, 16, "fletcher"), ("string", 14, 16, "fletcher"),
    ("flint", 26, 12, "fletcher"), ("feather", 24, 16, "fletcher"), ("tripwire_hook", 8, 12, "fletcher"),
    ("wheat", 20, 16, "farmer"), ("potato", 26, 16, "farmer"), ("carrot", 22, 16, "farmer"),
    ("beetroot", 15, 16, "farmer"), ("pumpkin", 6, 12, "farmer"), ("melon", 4, 12, "farmer"),
    ("paper", 24, 16, "librarian"), ("book", 4, 12, "librarian"), ("ink_sac", 5, 12, "librarian"),
    ("coal", 15, 16, "armorer"), ("iron_ingot", 4, 12, "armorer"), ("diamond", 1, 12, "armorer"),
    ("white_wool", 18, 16, "shepherd"), ("clay_ball", 10, 16, "mason"), ("stone", 20, 12, "mason"),
    ("andesite", 16, 12, "mason"), ("granite", 16, 12, "mason"), ("quartz", 12, 12, "mason"),
    ("dried_kelp_block", 10, 12, "butcher"), ("sweet_berries", 10, 12, "butcher"),
    ("chicken", 14, 16, "butcher"), ("porkchop", 7, 16, "butcher"), ("beef", 10, 16, "butcher"),
    ("leather", 6, 16, "leatherworker"), ("cod", 15, 16, "fisherman"), ("salmon", 13, 16, "fisherman"),
]
# emerald -> item (villager sell trades): (output, emeralds in, units out, max_uses, profession)
EM_OUT = [
    ("brick", 1, 10, 16, "mason"), ("arrow", 1, 16, 12, "fletcher"), ("experience_bottle", 3, 1, 12, "cleric"),
    ("glass", 1, 4, 12, "librarian"), ("lantern", 1, 1, 12, "librarian"), ("name_tag", 20, 1, 12, "librarian"),
    ("golden_carrot", 3, 3, 12, "farmer"), ("lapis_lazuli", 1, 1, 12, "cleric"),
    ("glowstone", 4, 1, 12, "cleric"), ("redstone", 1, 2, 12, "cleric"), ("ender_pearl", 5, 1, 12, "cleric"),
    ("compass", 4, 1, 12, "librarian"), ("clock", 5, 1, 12, "librarian"),
]
# furnace edges, 1 in -> 1 out. Fuel: 1 coal smelts 8 items.
SMELT = [("cobblestone", "stone"), ("sand", "glass"), ("spruce_log", "charcoal"), ("oak_log", "charcoal"),
         ("clay_ball", "brick"), ("netherrack", "nether_brick"), ("kelp", "dried_kelp"),
         ("cactus", "green_dye"), ("raw_iron", "iron_ingot"), ("clay", "terracotta")]

# methods with a public video or guide: the crowd is already in, treat the margin as decaying
CROWDED = {
    "totem_of_undying": "raid farm video this month; bid 220K down to 103K",
    "experience_bottle": "XP farm content everywhere; still the deepest market on the server",
    "arrow": "fletcher halls are in every villager video",
    "gold_ingot": "gold farm videos; input side, crowding makes it CHEAPER for us",
    "rotten_flesh": "zombie farm videos; input side, crowding makes it CHEAPER for us",
    "emerald": "raid farms drop emeralds; supply grows while the video runs",
}

EM_COST_DIRECT, _ = cost("emerald")

print("=" * 100)
print("1. MAKING EMERALDS: real cost per emerald by input, at today's fresh AH prices")
print("   (if you FARM the input yourself the emerald is free and this is pure conversion capacity)")
print("=" * 100)
print("%-18s %-13s %10s %12s %11s %13s %11s  %s" % (
    "input", "villager", "in/em", "cost/em", "em/day/vil", "cost basis", "in trades/d", "crowd"))
rows_in = []
for item, n, uses, prof in EM_IN:
    c, g = cost(item)
    if c is None:
        continue
    t, v = depth(item)
    rows_in.append((item, prof, n, c * n, uses * 2, g, t))
for item, prof, n, ce, per_day, g, t in sorted(rows_in, key=lambda x: x[3]):
    print("%-18s %-13s %10d %12s %11d %13s %11s  %s" % (
        item, prof, n, f"{ce:,.0f}", per_day, g, f"{t:,}", CROWDED.get(item, "")[:44]))
print("")
print("Buying emeralds outright: %s each (fresh stack median)." % f"{EM_COST_DIRECT:,.0f}")
print("Any input line above that number is pointless to trade in; sell the input instead.")

print("")
print("=" * 100)
print("2. SPENDING EMERALDS: revenue per emerald by sell trade, and profit per villager per day")
print("=" * 100)
best_in = min(rows_in, key=lambda x: x[3])
EM_CHEAP = min(EM_COST_DIRECT or 9e9, best_in[3])
src = "buying outright" if EM_CHEAP == EM_COST_DIRECT else ("trading in " + best_in[0])
print("cheapest emerald: %s via %s" % (f"{EM_CHEAP:,.0f}", src))
print("")
print("%-19s %-10s %6s %12s %9s %8s %14s %12s %11s  %s" % (
    "output", "villager", "em in", "rev/em", "margin", "uses/d", "profit/vil/d", "out trades/d", "out vol/d", "sell route"))
out_rows = []
for item, em_n, out_n, uses, prof in EM_OUT:
    rv, route = revenue(item)
    if rv is None:
        continue
    rev_per_em = rv * out_n / em_n
    per_day = uses * 2
    profit_day = (rev_per_em - EM_CHEAP) * em_n * per_day
    t, v = depth(item)
    out_rows.append(dict(output=item, prof=prof, em=em_n, rev_per_em=round(rev_per_em),
                         margin=round(rev_per_em / EM_CHEAP, 2), uses=per_day, profit_day=round(profit_day),
                         trades=t, vol=v, route=route, crowd=CROWDED.get(item, "")))
for x in sorted(out_rows, key=lambda r: -r["profit_day"]):
    print("%-19s %-10s %6d %12s %8.2fx %8d %14s %12s %11s  %s" % (
        x["output"], x["prof"], x["em"], f"{x['rev_per_em']:,}", x["margin"], x["uses"],
        f"{x['profit_day']:,}", f"{x['trades']:,}", f"{x['vol']:,}", x["route"]))
    if x["crowd"]:
        print("%19s   CROWDED: %s" % ("", x["crowd"]))
print("")
print("Curing note: a cured villager discounts its SELL trades, floor 1 emerald. The 3 emerald XP bottle")
print("and the 20 emerald name tag are the trades where curing changes the answer most.")

print("")
print("=" * 100)
print("3. FURNACE EDGES: buy input, smelt, sell output (fuel costed at coal/8)")
print("=" * 100)
coal_c, _ = cost("coal")
fuel = (coal_c or 623) / 8
print("fuel cost per item: %.0f" % fuel)
print("")
print("%-16s %12s %-16s %12s %11s %9s %13s  %s" % (
    "input", "cost", "output", "revenue", "profit/u", "margin", "out trades/d", "verdict"))
for a, b in SMELT:
    ca, ga = cost(a)
    rv, route = revenue(b)
    if ca is None or rv is None:
        continue
    pr = rv - ca - fuel
    t, v = depth(b)
    verdict = "smelt" if pr > 0 else "LOSS, sell the input raw"
    print("%-16s %12s %-16s %12s %11s %8.2fx %13s  %s" % (
        a, f"{ca:,.0f}", b, f"{rv:,.0f}", f"{pr:,.0f}", rv / (ca + fuel), f"{t:,}", verdict))
print("")
print("Raw iron trades ABOVE iron ingots (players buy raw to smelt for XP): sell raw, buy ingots, never smelt iron.")

with open(f"{SP}/quant/transform.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
    w.writeheader()
    w.writerows(out_rows)
print("")
print("Sell-trade table written to quant/transform.csv")
