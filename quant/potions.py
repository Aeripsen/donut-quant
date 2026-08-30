"""Potion brewing calculator: input cost per brew vs realized AH price, ranked by profit per AH slot.

Why this exists: SMP500 lumps every potion into two rows ("potion", "splash_potion") because the feed carries no
potion type, so the market median (100K / 25K) is a blend of water bottles and Strength II. The player's own log is
the only source of type-level prices. Realized prices below come from his sales on 2026-08-29/30.

One brew = 3 potions (3 water bottles in the stand at once). Fuel: 1 blaze powder per 20 brews.
"""
import csv, os

SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = {r["name"]: r for r in csv.DictReader(open(f"{SP}/quant/price_table.csv", encoding="utf-8"))}


def buy(name):
    r = P.get(name)
    if not r:
        return None
    try:
        return float(r.get("best_buy") or 0) or None
    except ValueError:
        return None


BOTTLE = buy("glass_bottle") or 250
FUEL = (buy("blaze_powder") or 30) / 20.0   # 1 blaze powder fuels 20 brews

# name: (ingredients after the water bottles, realized unit price, source of that price)
RECIPES = {
    "Strength":            (["nether_wart", "blaze_powder"], 333_000, "sold 300K and 333K x2, 2026-08-29/30"),
    "Swiftness":           (["nether_wart", "sugar"], 300_000, "sold 300K, 2026-08-30 00:33"),
    "Water Breathing":     (["nether_wart", "pufferfish"], 333_000, "sold 333K, 2026-08-29"),
    "Fire Resistance":     (["nether_wart", "magma_cream"], 100_000, "his ask 100K, unsold at time of writing"),
    "Healing":             (["nether_wart", "glistering_melon_slice"], 100_000, "no realized sale; market blend"),
    "Regeneration":        (["nether_wart", "ghast_tear"], 100_000, "no realized sale; market blend"),
    "Night Vision":        (["nether_wart", "golden_carrot"], 100_000, "no realized sale; market blend"),
    "Poison":              (["nether_wart", "spider_eye"], 100_000, "no realized sale; lingering sold 90K"),
    "Weakness":            (["fermented_spider_eye"], 100_000, "no realized sale; market blend"),
    "Slowness (splash)":   (["nether_wart", "sugar", "fermented_spider_eye", "gunpowder"], 350_000, "ask 350K x2, 2026-08-30"),
    "Invisibility":        (["nether_wart", "golden_carrot", "fermented_spider_eye"], 100_000, "bought at 15-30K in his log"),
}

MODIFIERS = {
    "+ redstone (extend)": ["redstone"],
    "+ glowstone (level II)": ["glowstone_dust"],
    "+ gunpowder (splash)": ["gunpowder"],
}

rows = []
for name, (ings, price, src) in RECIPES.items():
    cost = 3 * BOTTLE + FUEL
    missing = []
    for i in ings:
        b = buy(i)
        if b is None:
            missing.append(i)
        else:
            cost += b
    if missing:
        continue
    revenue = 3 * price
    rows.append(dict(potion=name, inputs=" + ".join(ings), cost_per_brew=round(cost),
                     cost_per_potion=round(cost / 3), price=price, revenue_per_brew=revenue,
                     profit_per_brew=round(revenue - cost), profit_per_slot=round(price - cost / 3),
                     margin_x=round(price / (cost / 3)), basis=src))
rows.sort(key=lambda r: -r["profit_per_slot"])

print("POTION LANE, per brew of 3 (bottles %.0f each, fuel %.1f per brew)\n" % (BOTTLE, FUEL))
print("%-20s %10s %11s %11s %13s %8s  %s" % ("potion", "cost/brew", "cost/potion", "sells for", "profit/slot", "margin", "price basis"))
for r in rows:
    print("%-20s %10s %11s %11s %13s %7sx  %s" % (
        r["potion"], f"{r['cost_per_brew']:,}", f"{r['cost_per_potion']:,}", f"{r['price']:,}",
        f"{r['profit_per_slot']:,}", r["margin_x"], r["basis"]))

print("\nMODIFIER COSTS (added per brew, applies to all 3 potions)")
for label, ings in MODIFIERS.items():
    c = sum(buy(i) or 0 for i in ings)
    print("  %-24s %7.0f per brew (%.0f per potion)" % (label, c, c / 3))

best = rows[0]
print("\nSLOT MATH at the top recipe (%s)" % best["potion"])
for cycle in (10, 20, 30, 60):
    per_hour = 18 * best["profit_per_slot"] * (60 / cycle)
    print("  if 18 slots clear every %2d min: %13s per hour" % (cycle, f"{per_hour:,.0f}"))
print("\n  Slots are the constraint: potions do not stack, so one potion = one slot.")
print("  Brewing 18 potions = 6 brews = about 9 minutes of stand time (90 s each), unattended.")

with open(f"{SP}/quant/potions.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
