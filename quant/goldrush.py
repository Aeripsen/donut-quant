"""Goldrush scanner: the immature markets. New content, singles markets, and drop-farm EV.

The thesis, straight from the ghast tear and pottery sherd playbook: mispricing lives where the market is
young. Items added to the game in the last year (pale garden, happy ghast harnesses, copper golems and
chests, bundles, shelves) have thin, chaotic order books; nobody has computed their input cost yet.
This module does, with verified 1.21.11 recipes and today's fresh prices.

Three market types priced here:
  CRAFT     a verified recipe whose inputs trade liquid and whose output trades young.
  EV        a drop table: the creeper-killed-by-skeleton disc farm pays a random disc; price the average.
  SINGLES   items that legitimately trade one at a time (harnesses, discs, maces, keys, bundles do not
            stack or trade as collectibles). For these the single-sale median IS the market. For
            stackable items, single sales are contaminated by disguised money transfers, so the retail
            scan at the bottom is a list of candidates to verify in /ah, not a signal.

Sale prices clamped to p25 of the last 15 sales where a p25 exists. Pre-tax.
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
    r = P.get(name)
    if not r:
        return None
    if f(r, "n_stack") >= 3 and f(r, "tx_stack_med"):
        return f(r, "tx_stack_med")
    if int(f(r, "stack") or 64) == 1 and f(r, "n_single") >= 5:
        return f(r, "tx_single_med")
    if f(r, "n_tx") >= 5 and f(r, "tx_med"):
        return f(r, "tx_med")
    return None


def sell(name):
    """Clamped: singles median for non-stackers, stack median for stackers, p25 floor on both."""
    r = P.get(name)
    if not r:
        return None
    p25 = f(r, "tx_p25")
    if int(f(r, "stack") or 64) == 1 and f(r, "n_single") >= 5:
        v = f(r, "tx_single_med")
        return min(v, p25) if p25 else v
    if f(r, "n_stack") >= 3 and f(r, "tx_stack_med"):
        v = f(r, "tx_stack_med")
        return min(v, p25) if p25 else v
    return None


def trades(name):
    return int(f(P.get(name, {}), "ah_d_trades"))


LANES = []


def lane(label, inputs, output, out_n=1, note=""):
    total = 0.0
    for item, n in inputs:
        c = cost(item)
        if c is None:
            return
        total += c * n
    rv = sell(output)
    if rv is None:
        return
    LANES.append(dict(lane=label, cost=round(total / out_n), sells=round(rv),
                      profit=round(rv - total / out_n), margin=round(rv / (total / out_n), 1),
                      out_trades_d=trades(output), note=note))


# ---- A. new-content assembly, recipes verified against mcdata/recipes.json
lane("bundle = 1 string + 1 leather", [("string", 1), ("leather", 1)], "bundle",
     note="does not stack; 15 single sales at 99K. The recipe is two of the cheapest mob drops in the game")
lane("mace = heavy core + breeze rod", [("heavy_core", 1), ("breeze_rod", 1)], "mace",
     note="THE PvP weapon. You already hold the rods; a core turns one into a mace")
lane("copper chest = 8 copper + chest", [("copper_ingot", 8), ("chest", 1)], "copper_chest")
lane("copper bars x16 = 6 copper", [("copper_ingot", 6)], "copper_bars", out_n=16)
lane("lantern = 8 iron nuggets + torch", [("iron_nugget", 8), ("torch", 1)], "lantern")
lane("firework x3 = gunpowder + paper", [("gunpowder", 1), ("paper", 1)], "firework_rocket", out_n=3,
     note="elytra fuel, burned constantly; 532K units of daily flow. A creeper farm makes the input free")
lane("pale oak log -> 4 planks", [("pale_oak_log", 1)], "pale_oak_planks", out_n=4,
     note="pale gardens are rare, the wood market is young")
lane("3 pale planks -> 6 slabs", [("pale_oak_planks", 3)], "pale_oak_slab", out_n=6)
lane("6 pale planks -> 4 stairs", [("pale_oak_planks", 6)], "pale_oak_stairs", out_n=4)
lane("resin clump -> smelt -> brick", [("resin_clump", 1), ("coal", 1 / 8)], "resin_brick")
lane("6 stripped spruce -> 6 shelves", [("stripped_spruce_log", 1)], "spruce_shelf",
     note="for most woods the STRIPPED LOG outsells the shelf; spruce is the exception. Check before crafting")
for c in ["blue", "black", "red", "lime", "purple", "magenta"]:
    lane(f"harness recolor: yellow + {c} dye", [("yellow_harness", 1), (f"{c}_dye", 1)], f"{c}_harness",
         note="")
lane("harness from scratch (white)", [("leather", 3), ("glass", 2), ("white_wool", 1)], "white_harness",
     note="happy ghast saddle, 16 colors, every color has 15 single sales. Craft any color, recolor to the priciest")
lane("copper golem statue: block + carved pumpkin, wait", [("copper_block", 1), ("carved_pumpkin", 1)],
     "oxidized_copper_golem_statue",
     note="spawn the golem, let it oxidize into the statue. Time does the work")

LANES.sort(key=lambda x: -x["profit"] * max(x["out_trades_d"], 1))
print("=" * 108)
print("A. NEW-CONTENT ASSEMBLY: verified recipes into young markets (ranked by profit x liquidity)")
print("=" * 108)
print("%-46s %10s %11s %11s %8s %9s" % ("lane", "cost", "sells", "profit", "margin", "trades/d"))
for x in LANES:
    print("%-46s %10s %11s %11s %7sx %9s" % (
        x["lane"], f"{x['cost']:,}", f"{x['sells']:,}", f"{x['profit']:,}", x["margin"], f"{x['out_trades_d']:,}"))
    if x["note"]:
        print("      %s" % x["note"])

# ---- B. the disc farm: a skeleton killing a creeper drops one random disc from the classic set
DISCS = ["music_disc_13", "music_disc_cat", "music_disc_blocks", "music_disc_chirp", "music_disc_far",
         "music_disc_mall", "music_disc_mellohi", "music_disc_stal", "music_disc_strad", "music_disc_ward",
         "music_disc_wait", "music_disc_11"]
print()
print("=" * 108)
print("B. THE DISC FARM: creeper killed by a skeleton arrow drops one of the 12 classic discs, uniform odds")
print("=" * 108)
vals = []
for d in DISCS:
    v = sell(d)
    if v:
        vals.append(v)
        print("  %-24s %11s  (%s single sales, %s trades/d)" %
              (d.replace("music_disc_", ""), f"{v:,.0f}", int(f(P[d], "n_single")), trades(d)))
ev = sum(vals) / len(vals)
print("  EV per disc: %s across %d priced discs. Each disc is one AH slot, but at this EV the slot" % (f"{ev:,.0f}", len(vals)))
print("  earns like a top craft lane, and the farm runs itself. Nobody on the server builds these.")

# ---- C. retail split candidates: singles trading far above the stack unit price
print()
print("=" * 108)
print("C. RETAIL SPLIT CANDIDATES: single sales far above stack price. For stackables this can be disguised")
print("   money transfers, so these are leads to VERIFY in /ah, not signals. Non-stackers excluded (see A).")
print("=" * 108)
rows = []
for name, r in P.items():
    if int(f(r, "stack") or 64) == 1:
        continue
    st, si = f(r, "tx_stack_med"), f(r, "tx_single_med")
    if f(r, "n_stack") >= 5 and f(r, "n_single") >= 8 and st > 0 and si > 2 * st:
        rows.append((name, st, si, si / st, int(f(r, "n_single")), trades(name)))
rows.sort(key=lambda x: -x[3] * x[5])
print("%-28s %11s %11s %8s %10s %9s" % ("item", "stack unit", "single med", "ratio", "n singles", "trades/d"))
for name, st, si, ratio, ns, t in rows[:14]:
    print("%-28s %11s %11s %7.1fx %10d %9s" % (name, f"{st:,.0f}", f"{si:,.0f}", ratio, ns, f"{t:,}"))

with open(f"{SP}/quant/goldrush.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(LANES[0].keys()))
    w.writeheader()
    w.writerows(LANES)
print()
print("Your stockpile, priced: lingering potions sell 50,000 each as singles (15 sales), trial keys 53,950,")
print("ominous trial keys 544,999, breeze rods 27,969 in stacks. A heavy core turns one rod into 1.5M profit.")
print("Lanes written to quant/goldrush.csv")
