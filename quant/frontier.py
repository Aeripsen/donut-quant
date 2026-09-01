"""Frontier scanner: every mechanism that adds value to an item, priced. The creativity layer.

The other modules each cover one mechanism (crafting, brewing, villagers, furnaces). This one enumerates
the mechanism CLASSES, including the ones with no recipe anywhere:

  HAND      value added by a click: stripping a log with an axe, clicking a water bottle on dirt,
            dyeing a shulker box. No machine, no recipe file, no build cost.
  CUTTER    the stonecutter converts stone-family blocks at better rates than the crafting table
            (1 block -> 2 slabs instead of 6 -> 6, 1 -> 1 stairs instead of 6 -> 4).
  FURNACE   smelts with a price jump the crafting graph does not show (sandstone -> smooth sandstone).
  MIX       concrete powder: 4 sand + 4 gravel + 1 dye -> 8 powder -> touch water -> 8 concrete.
  TIME      copper oxidation: place, wait days, mine. The only mechanism where the input is literally time.
  RANCH     a mob or plant whose product price justifies the pen: sniffers digging torchflower seeds,
            bees filling bottles, turtles dropping scutes, frogs eating magma cubes.

Pricing discipline (same as engine.py): pay the fresh stack median, sell at min(stack median, p25) so one
optimistic sale cannot inflate a lane, require 3 or more full-stack sales or the row is dropped. Shulker
boxes are the exception: they do not stack, so their single-sale median IS the market (15 sales each).

Every lane carries the market's daily unit flow. The capture rule: assume you can take 20 percent of daily
flow before your own supply moves the price. That number, not the margin, ranks the lanes.

All margins pre-tax; the AH tax rate is still unmeasured (see report section 12).
"""
import csv, os

SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = {r["name"]: r for r in csv.DictReader(open(f"{SP}/quant/price_table.csv", encoding="utf-8"))}
CAPTURE = 0.20


def f(r, k):
    try:
        return float(r.get(k) or 0)
    except (ValueError, AttributeError):
        return 0.0


def cost(name):
    r = P.get(name)
    if not r:
        return None
    if f(r, "n_stack") >= 3 and f(r, "tx_stack_med"):
        return f(r, "tx_stack_med")
    if int(f(r, "stack") or 64) == 1 and f(r, "n_single") >= 5:
        return f(r, "tx_single_med")     # non-stackable items (shulker boxes) trade as singles
    return None


def sell(name, singles_ok=False):
    """Conservative sale price: stack median clamped by p25. Shulker-type items sell as singles."""
    r = P.get(name)
    if not r:
        return None
    if singles_ok and f(r, "n_single") >= 5:
        v = f(r, "tx_single_med")
        p25 = f(r, "tx_p25")
        return min(v, p25) if p25 else v
    if f(r, "n_stack") >= 3 and f(r, "tx_stack_med"):
        v = f(r, "tx_stack_med")
        p25 = f(r, "tx_p25")
        return min(v, p25) if p25 else v
    return None


def flow(name):
    r = P.get(name, {})
    return int(f(r, "ah_d_trades")), int(f(r, "ah_d_vol"))


LANES = []


def lane(mech, label, inputs, output, out_n=1, singles=False, note=""):
    """inputs: list of (item, count). Returns nothing; appends a priced lane if every leg has fresh data."""
    total = 0.0
    for item, n in inputs:
        c = cost(item)
        if c is None:
            return
        total += c * n
    rv = sell(output, singles_ok=singles)
    if rv is None:
        return
    unit_profit = rv - total / out_n
    t, v = flow(output)
    LANES.append(dict(mech=mech, lane=label, cost_unit=round(total / out_n), sell_unit=round(rv),
                      profit_unit=round(unit_profit), margin=round(rv / (total / out_n), 2) if total else 0,
                      out_trades_d=t, out_vol_d=v,
                      capture_day=round(unit_profit * v * CAPTURE), note=note))


FUEL = [("coal", 1 / 8)]     # 1 coal smelts 8 items

# HAND: one click each, no machine
for wood in ["oak", "spruce", "birch", "dark_oak", "cherry", "mangrove"]:
    lane("HAND", f"axe-strip {wood} log", [(f"{wood}_log", 1)], f"stripped_{wood}_log",
         note="right-click with any axe; no automation exists, so nobody supplies bulk")
lane("HAND", "water bottle on dirt -> mud", [("dirt", 1)], "mud",
     note="bottle is returned empty; refill at a water source")
lane("HAND", "packed mud (mud + wheat)", [("mud", 1), ("wheat", 1)], "packed_mud")
for color in ["black", "blue", "red", "white", "yellow"]:
    lane("HAND", f"recolor shulker box -> {color}", [("shulker_box", 1), (f"{color}_dye", 1)],
         f"{color}_shulker_box", singles=True, note="shulkers sell as singles; that IS their market")
lane("HAND", "dye white wool red", [("white_wool", 1), ("red_dye", 1)], "red_wool",
     note="1 dye does 1 wool in the crafting grid")
lane("HAND", "red + yellow -> 2 orange dye", [("red_dye", 1), ("yellow_dye", 1)], "orange_dye", out_n=2)
lane("HAND", "blue + green -> 2 cyan dye", [("blue_dye", 1), ("green_dye", 1)], "cyan_dye", out_n=2)
lane("HAND", "green + white -> 2 lime dye", [("green_dye", 1), ("white_dye", 1)], "lime_dye", out_n=2)

# CUTTER: stonecutter rates (stone family only; wood cannot be cut)
lane("CUTTER", "stone -> 2 stone slabs", [("stone", 1)], "stone_slab", out_n=2)
lane("CUTTER", "stone -> stone stairs", [("stone", 1)], "stone_stairs")
lane("CUTTER", "cobblestone -> stairs", [("cobblestone", 1)], "cobblestone_stairs")
lane("CUTTER", "cobblestone -> 2 slabs", [("cobblestone", 1)], "cobblestone_slab", out_n=2)
lane("CUTTER", "cobblestone -> wall", [("cobblestone", 1)], "cobblestone_wall")
lane("CUTTER", "cobbled deepslate -> polished", [("cobbled_deepslate", 1)], "polished_deepslate")
lane("CUTTER", "cobbled deepslate -> bricks", [("cobbled_deepslate", 1)], "deepslate_bricks")
lane("CUTTER", "cobbled deepslate -> brick stairs", [("cobbled_deepslate", 1)], "deepslate_brick_stairs")
lane("CUTTER", "tuff -> polished tuff", [("tuff", 1)], "polished_tuff")
lane("CUTTER", "stone -> chiseled stone bricks", [("stone_bricks", 1)], "chiseled_stone_bricks")

# FURNACE: the jumps the recipe graph hides
lane("FURNACE", "sandstone -> smooth sandstone", [("sandstone", 1)] + FUEL, "smooth_sandstone",
     note="a super smelter makes this passive; 15 tight stack sales on the output")
lane("FURNACE", "cobblestone -> stone", [("cobblestone", 1)] + FUEL, "stone",
     note="free input from a cobble generator")
lane("FURNACE", "sand -> glass", [("sand", 1)] + FUEL, "glass")
lane("FURNACE", "spruce log -> charcoal", [("spruce_log", 1)] + FUEL, "charcoal")
lane("FURNACE", "cactus -> green dye", [("cactus", 1)] + FUEL, "green_dye")

# MIX: concrete powder -> concrete (4 sand + 4 gravel + 1 dye -> 8, then touch water)
for color in ["cyan", "red", "purple", "gray", "black", "white", "blue", "lime", "yellow", "light_blue", "green", "orange"]:
    lane("MIX", f"{color} concrete from raw", [("sand", 4), ("gravel", 4), (f"{color}_dye", 1)],
         f"{color}_concrete", out_n=8,
         note="place powder next to water to cure; instamine with an efficiency pick")

# TIME: copper oxidation (place, wait, mine). Thin markets, p25 clamp is brutal here, shown anyway.
lane("TIME", "copper block, one wait stage", [("copper_block", 1)], "exposed_copper",
     note="thin market, wide spread; treat as a side bet, not a lane")
lane("TIME", "copper block, full oxidation + wax", [("copper_block", 1), ("honeycomb", 1)], "waxed_oxidized_copper")

# RANCH: the pen pays for itself if the product does. Output prices are the hard data;
# the rates in the notes are vanilla estimates to sanity-check scale, not model inputs.
lane("RANCH", "bee farm -> honey blocks", [], "honey_block",
     note="4 bottles per block; ~1 bottle/90s per hive AFK. 20 hives ~ 200 blocks/day")
lane("RANCH", "magma spawner + frogs -> ochre froglight", [], "ochre_froglight",
     note="needs a temperate frog; passive once built")
lane("RANCH", "sniffer ranch -> torchflower seeds", [], "torchflower_seeds",
     note="sniffers dig seeds passively; also breeds more sniffers")
lane("RANCH", "sniffer ranch -> torchflower", [], "torchflower",
     note="grown from the seeds; n=3 stacks only, price less certain")
lane("RANCH", "turtle beach -> scutes", [], "turtle_scute",
     note="babies drop 1 scute on growing up; seagrass speeds it")
lane("RANCH", "sculk catalyst under any mob farm", [], "sculk",
     note="XP becomes sculk blocks; silk touch to harvest")
lane("RANCH", "bone meal spam -> moss", [], "moss_block",
     note="composter loop feeds itself: moss -> bone meal -> moss")
lane("RANCH", "snow golem in a box", [], "snowball", note="infinite snowballs, zero input")
lane("RANCH", "glow squid farm -> glow ink", [], "glow_ink_sac")

LANES.sort(key=lambda x: -x["capture_day"])
with open(f"{SP}/quant/frontier.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(LANES[0].keys()))
    w.writeheader()
    w.writerows(LANES)


def show(title, rows, note=""):
    print("=" * 112)
    print(title)
    if note:
        print(note)
    print("=" * 112)
    print("%-8s %-38s %9s %9s %10s %8s %10s %11s %13s" % (
        "mech", "lane", "cost/u", "sell/u", "profit/u", "margin", "trades/d", "flow u/d", "20pct cap/d"))
    for x in rows:
        print("%-8s %-38s %9s %9s %10s %7sx %10s %11s %13s" % (
            x["mech"], x["lane"], f"{x['cost_unit']:,}", f"{x['sell_unit']:,}", f"{x['profit_unit']:,}",
            x["margin"], f"{x['out_trades_d']:,}", f"{x['out_vol_d']:,}", f"{x['capture_day']:,}"))
        if x["note"]:
            print("%-8s   %s" % ("", x["note"]))
    print("")


paid = [x for x in LANES if x["cost_unit"] > 0 and x["profit_unit"] > 0]
free = [x for x in LANES if x["cost_unit"] == 0]
losers = [x for x in LANES if x["cost_unit"] > 0 and x["profit_unit"] <= 0]
show("A. BUY INPUT, TRANSFORM, SELL: ranked by profit at a 20 percent capture of daily flow", paid,
     "cost and sell are fresh stack medians, sale clamped by p25. Pre-tax.")
show("B. FREE-INPUT PRODUCTION (the pen or machine is the only cost): what the output is worth", free,
     "capture/day here is what 20 percent of the existing market flow pays. Rates in notes are estimates.")
show("C. NEVER DO THESE: the conversion destroys value at today's prices", losers)
print("Also never: smelt raw iron (raw sells above the ingot), compress ice to packed ice or snowballs to")
print("snow blocks (both sell below their inputs), convert concrete powder you could sell raw (white),")
print("barter gold with piglins (a gold ingot sells for 2,813; the barter table EV is a few hundred).")
print("")
print(f"{len(LANES)} lanes priced. Table: quant/frontier.csv")
