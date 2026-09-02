"""The /sell channel: the only uncapped way to turn production into money.

Every other module in this repo ranks lanes that end at the auction house, and every one of those
numbers is squeezed by two hard caps:

    18 AH slots            you can only have 18 things for sale at once
    ~20% of daily volume   dump more than that and you are moving the price against yourself

The /sell channel has neither. The server buys unlimited quantity at a fixed /worth price, instantly,
with no listing, no buyer, and no slot. That means a farm routed through /sell is limited only by how
fast it produces, which is the definition of scalable.

The catch: /worth prices are set low on purpose, so the server does not compete with player trade.
The question is therefore never "is /sell cheaper per unit" (it always is). The question is:

    does (production rate x /worth) beat (AH price x 20% of daily volume)?

This module computes that break-even. For each item it prints the /worth price at which an AFK
sell-tool run matches the item's ENTIRE AH route. Those numbers turn out to be low, which is why
this channel deserves a real answer instead of a guess.

WORTH holds the confirmed /worth values. Only two are known. Fill in the rest from `/worth <item>`
in game and rerun; that single checklist is worth more than every other number in this repo, because
it decides whether the ceiling is ~100M a day (AH) or ~500M a day (uncapped throughput).

THE SHARD SELL AXE, confirmed from the player's own Shard Shop screen on 2026-09-02. This is primary
source and it overrides an earlier web-research pass that wrongly concluded the axe did not exist
because both wikis omit it. The wikis are incomplete; the game is the authority.

    Shard Sell Axe -- "Instantly Sells All Items in A Chest"
    Efficiency V, Unbreaking III, Mending
    1.5K Shards in the Shard Shop, Self Destruct: 24h
    AH resale scales with time remaining: one with 10 minutes left was listed at 2.9M

The axe does not sell mined blocks. It empties a CHEST at /worth, so the unit of account is one chest,
and a chest is 27 stacks = 1,728 items:

    chest value = 1,728 x /worth of whatever is inside

At known values that is 518,400 for a chest of dried kelp blocks against 20,736 for a chest of spruce
slabs. Same swing, 25x the money. Choosing what goes in the chest IS the strategy.

CRAFTING MULTIPLIES /worth, which is the mechanic behind the whole kelp meta. /worth is set per item
rather than derived from ingredients, so a crafted item can be worth far more than what went into it:

    cobblestone 6 -> 2 cobble slabs at 3      conserved, no gain, not worth the step
    spruce log -> 4 planks -> 8 slabs at 12   96 a log, which is why slab farms exist
    kelp -> dried kelp -> 9:1 block at 300    the server's best known chain

Every 9:1 block recipe is a candidate: where a block's /worth beats nine times its component's, the
crafting step is free money, and it compounds with the sell axe because denser value per slot means
more money per chest. RECIPE_CHAINS below is the checklist for finding the rest.
"""
import csv, os

SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = {r["name"]: r for r in csv.DictReader(open(f"{SP}/quant/price_table.csv", encoding="utf-8"))}

# confirmed /worth values. Everything else is unknown: run `/worth <item>` in game and add it here.
WORTH = {
    # CONFIRMED, each traced to a player reading the value on screen or to the wiki
    "dried_kelp_block": 300,   # Fandom Dried Kelp Farm: "sold on /sell for $300 each with a 1.0x multiplier"
    "basalt": 15,              # ArcticzMC 2026-06-29; a shulker of basalt sells 27k, and 1728 x 15 = 25.9k
    "cobblestone": 6,          # same video, same sentence
    "cobblestone_slab": 3,     # same video: "one shulker of slabs sells for 5K" -> 5000/1728
    "spruce_slab": 12,         # Bubsy 2026-08-28: a stack sells 768, and 768/64 = 12
    "sand": 1,                 # Crazzington: "a singular piece of sand is worth $1" while orders paid 50
    "gunpowder": 1,            # same: "43 pieces of gunpowder worth $43"
}

# Read live by DrDonut on stream in Aug 2024, so two years stale and quoted as indicative only.
# He says on the same stream that values changed repeatedly afterwards. Never size a position on these.
WORTH_STALE_2024 = {
    "respawn_anchor": 400, "enchanting_table": 250, "obsidian": 50, "soul_sand": 50, "bread": 16,
    "amethyst_block": 15, "copper_ingot": 10, "sweet_berries": 4, "pointed_dripstone": 3,
    "sugar_cane": 3, "terracotta": 2, "nether_wart": 2, "white_wool": 1,
}

# AFK breaking throughput, blocks per hour. An efficiency pick with haste instamines; the water circle
# plus toggle-sprint keeps the character mining unattended. 20 blocks/second is a competent setup.
RATES = {"hand-ish 5/s": 18_000, "steady 10/s": 36_000, "fast 20/s": 72_000, "3x3 drill 40/s": 144_000}
AFK_HOURS = 20
CAPTURE = 0.20

# The real hunt: where does crafting multiply /worth? Read /worth at EVERY step of each chain.
RECIPE_CHAINS = [
    ("kelp", ["dried kelp (smelt)", "dried kelp block 9:1  <- known 300"]),
    ("spruce log", ["4 planks", "8 slabs  <- known 12 each, so 96 a log"]),
    ("cobblestone", ["2 slabs (cutter)  <- known 3, conserved", "stairs", "wall"]),
    ("sand", ["sandstone 4:1", "smooth sandstone (smelt)", "slabs"]),
    ("iron ingot", ["iron block 9:1"]),
    ("gold ingot", ["gold block 9:1"]),
    ("bone", ["3 bone meal", "bone block 9:1"]),
    ("coal", ["coal block 9:1"]),
    ("wheat", ["hay block 9:1"]),
    ("slime ball", ["slime block 9:1"]),
    ("clay ball", ["clay 4:1", "brick (smelt)", "brick block 4:1"]),
    ("amethyst shard", ["amethyst block 4:1"]),
    ("copper ingot", ["copper block 9:1", "cut copper", "cut copper slab"]),
    ("netherrack", ["nether brick (smelt)", "nether brick block 4:1"]),
    ("quartz", ["quartz block 4:1", "quartz slab"]),
]

CANDIDATES = ["cobblestone", "stone", "sand", "glass", "dried_kelp_block", "spruce_slab", "stone_slab",
              "smooth_sandstone", "bone_block", "dirt", "netherrack", "basalt", "obsidian", "sea_lantern",
              "sandstone", "deepslate", "cobbled_deepslate", "smooth_stone", "stone_bricks", "moss_block",
              "packed_ice", "snow_block", "bamboo_planks", "oak_planks", "amethyst_block", "purpur_block"]


def f(r, k):
    try:
        return float(r.get(k) or 0)
    except (ValueError, AttributeError):
        return 0.0


rows = []
for n in CANDIDATES:
    r = P.get(n)
    if not r:
        continue
    unit = f(r, "tx_stack_med") or f(r, "tx_med")
    vol = f(r, "ah_d_vol")
    if unit <= 0 or vol <= 0:
        continue
    ah_capped = unit * vol * CAPTURE
    rows.append((n, unit, vol, ah_capped))
rows.sort(key=lambda x: -x[3])

print("=" * 104)
print("1. BREAK-EVEN: the /worth price at which an AFK sell run matches the item's ENTIRE AH route")
print("=" * 104)
print("%-22s %10s %13s %16s %14s %14s" % (
    "item", "AH unit", "AH absorbs/d", "AH capped $/d", "need @10/s", "need @20/s"))
for n, unit, vol, cap in rows:
    print("%-22s %10s %13s %16s %14s %14s" % (
        n, f"{unit:,.0f}", f"{vol:,.0f}", f"{cap:,.0f}",
        f"{cap / (36_000 * AFK_HOURS):,.1f}", f"{cap / (72_000 * AFK_HOURS):,.1f}"))
print("\nRead this as: if /worth on that row beats the last column, the sell channel alone out-earns")
print("everything the auction house can absorb for that item, using zero slots.")

print()
print("=" * 104)
print("2. WHAT THE CHANNEL PAYS, by /worth price and breaking speed (20h AFK, no slots, no cap)")
print("=" * 104)
print("%-14s" % "/worth" + "".join("%18s" % k for k in RATES))
for w in (5, 12, 25, 50, 100, 200, 300, 500, 1000):
    line = "%-14s" % f"{w:,}"
    for k, rate in RATES.items():
        line += "%18s" % f"{w * rate * AFK_HOURS:,.0f}"
    print(line)
print("\nFor scale, the best single farm in quant/farms.py earns about 76M a day, and it is AH-capped.")

print()
print("=" * 104)
print("3. CONFIRMED /worth VALUES AND WHAT THEY IMPLY")
print("=" * 104)
if not WORTH:
    print("  none recorded yet")
print("  (%d confirmed values; %d more from a 2024 stream, too stale to size on)\n"
      % (len(WORTH), len(WORTH_STALE_2024)))
for item, w in sorted(WORTH.items(), key=lambda x: -x[1]):
    r = P.get(item, {})
    unit = f(r, "tx_stack_med") or f(r, "tx_med")
    cap = unit * f(r, "ah_d_vol") * CAPTURE
    best = w * 72_000 * AFK_HOURS
    verdict = "SELL CHANNEL WINS" if best > cap else "auction house wins"
    print("  %-20s /worth %-6s AH-capped %14s   /sell @20blk/s %15s   -> %s" % (
        item, f"{w:,}", f"{cap:,.0f}", f"{best:,.0f}", verdict))

print()
print("=" * 104)
print("4. THE CHECKLIST (5 minutes in game, decides the whole strategy)")
print("=" * 104)
print("Run `/worth <item>` on each and add the numbers to WORTH at the top of this file:")
for i in range(0, len(CANDIDATES), 4):
    print("   " + "  ".join("%-20s" % c for c in CANDIDATES[i:i + 4]))
print("\nBUT THE BIGGER CHECK IS THE CHAINS. Read /worth at EVERY step and find where crafting")
print("multiplies. One chest of the winner pays 1,728 x that number, per swing of the sell axe:")
for raw, steps in RECIPE_CHAINS:
    print("   %-16s -> %s" % (raw, " -> ".join(steps)))
print("\nStill unmeasured:")
print("   - the AH tax rate, from any sale receipt (every AH number in this repo is still pre-tax)")
print("   - what a FRESH 24h Sell Axe resells for (a 10-minute one was listed at 2.9M)")
print("   - whether /sell all works from inventory with no tool at all")
