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

Note on tools, post-June-2026 update: the shard Sell Axe and 3x3 Shard Pickaxe are real-money purchases
that self-destruct 24 hours after the ORIGINAL purchase, so they are a cost, not a free multiplier.
The plain `/sell` command needs no tool at all, so ordinary farm output can be routed through this
channel for free. The tool only automates the breaking.
"""
import csv, os

SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = {r["name"]: r for r in csv.DictReader(open(f"{SP}/quant/price_table.csv", encoding="utf-8"))}

# confirmed /worth values. Everything else is unknown: run `/worth <item>` in game and add it here.
WORTH = {
    "spruce_slab": 12,          # confirmed, from the slab-selling video's own numbers
    "dried_kelp_block": 300,    # confirmed earlier in this project
}

# AFK breaking throughput, blocks per hour. An efficiency pick with haste instamines; the water circle
# plus toggle-sprint keeps the character mining unattended. 20 blocks/second is a competent setup.
RATES = {"hand-ish 5/s": 18_000, "steady 10/s": 36_000, "fast 20/s": 72_000, "3x3 drill 40/s": 144_000}
AFK_HOURS = 20
CAPTURE = 0.20

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
print("\nAlso confirm, because the June update changed the shard economy:")
print("   - does the Sell Axe / 3x3 Shard Pickaxe still exist, what does it cost, does it still")
print("     self-destruct 24h after the original purchase")
print("   - does `/sell all` work from inventory with no tool (if yes, farm output routes here free)")
print("   - is there a sell chest or sell wand (a chest under a farm's hoppers is the fully AFK version)")
print("   - the AH tax rate, from any sale receipt (every AH number in this repo is still pre-tax)")
