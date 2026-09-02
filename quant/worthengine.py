"""The /worth engine: what to craft, what to /sell, what to put in the chest.

This is the module the whole project was missing. With the server's /worth table in hand and the full
1.21.11 recipe graph already on disk, four questions become answerable mechanically:

  1. CRAFT MULTIPLIER  For every recipe: does the output's /worth beat the sum of its inputs' /worth?
                       /worth is set per item, not derived from ingredients, so crafting genuinely
                       creates value in places, and those places are where the money is. This is the
                       reason the kelp meta exists, and it generalises to every recipe in the game.
  2. CHANNEL CHOICE    Per item: /sell (uncapped, no slots, fixed price) or the auction house (higher
                       price, but capped by 18 slots and by roughly a fifth of daily volume)?
  3. FREE MONEY        Any item whose AH price sits BELOW its /worth is risk-free: buy it, /sell it.
                       /worth is a hard floor, so this only appears on panic dumps and mispriced lots.
  4. CHEST VALUE       The Shard Sell Axe empties a chest at /worth, and a chest is 27 stacks = 1,728
                       items, so the unit of account is 1,728 x /worth. Denser value per slot is worth
                       exactly as much as swinging faster.

WORTH_CSV holds values read off the player's own `/worth` GUI screenshots, so it is primary source.
These are server config constants: they do not drift day to day, but admins rebalance them in updates
and they nerf whatever gets popular, so re-read the table after any server update.
"""
import csv, json, os

SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORTH_CSV = f"{SP}/quant/worth_table.csv"
CAPTURE = 0.20
CHEST = 27 * 64          # 1,728 items in a chest, the sell axe's unit of account

P = {r["name"]: r for r in csv.DictReader(open(f"{SP}/quant/price_table.csv", encoding="utf-8"))}
items = json.load(open(f"{SP}/mcdata/items.json", encoding="utf-8"))
byid = {i["id"]: i["name"] for i in items}
byname = {i["name"]: i["id"] for i in items}
display = {i["name"]: i["displayName"] for i in items}

WORTH = {}
if os.path.exists(WORTH_CSV):
    for r in csv.DictReader(open(WORTH_CSV, encoding="utf-8")):
        try:
            WORTH[r["name"]] = float(r["worth"])
        except (ValueError, KeyError):
            pass


def f(n, k):
    try:
        return float(P.get(n, {}).get(k) or 0)
    except (ValueError, AttributeError):
        return 0.0


def ah_unit(n):
    """Conservative AH unit price: stack median clamped by p25, stack sales required."""
    if f(n, "n_stack") >= 3 and f(n, "tx_stack_med"):
        v, p25 = f(n, "tx_stack_med"), f(n, "tx_p25")
        return min(v, p25) if p25 else v
    return 0.0


def show_header(title, sub=""):
    print("=" * 112)
    print(title)
    if sub:
        print(sub)
    print("=" * 112)


if not WORTH:
    print("No /worth data yet. Populate quant/worth_table.csv with columns: name,worth")
    raise SystemExit

print("Loaded %d /worth values (primary source: the player's own /worth GUI).\n" % len(WORTH))

# ---------------------------------------------------------------- 1. craft multiplier
rec = json.load(open(f"{SP}/mcdata/recipes.json", encoding="utf-8"))


def ing_id(x):
    if x is None:
        return None
    if isinstance(x, dict):
        return x.get("id")
    if isinstance(x, list):
        return x[0] if x else None
    return x


chains = []
for res_id, variants in rec.items():
    out_name = byid.get(int(res_id))
    if not out_name or out_name not in WORTH:
        continue
    for v in variants:
        cells = [c for row in v.get("inShape", []) for c in row] if "inShape" in v else v.get("ingredients", [])
        counts = {}
        for c in cells:
            i = ing_id(c)
            if i is not None and i >= 0:
                counts[i] = counts.get(i, 0) + 1
        if not counts:
            continue
        in_cost = 0.0
        ok = True
        parts = []
        for i, n in counts.items():
            nm = byid.get(i)
            if nm not in WORTH:
                ok = False
                break
            in_cost += WORTH[nm] * n
            parts.append("%dx %s" % (n, nm))
        if not ok or in_cost <= 0:
            continue
        out_n = v.get("result", {}).get("count", 1)
        out_val = WORTH[out_name] * out_n
        mult = out_val / in_cost
        chains.append(dict(output=out_name, out_n=out_n, out_worth=WORTH[out_name], inputs=" + ".join(parts),
                           in_cost=in_cost, out_val=out_val, mult=mult, gain=out_val - in_cost))
# keep the best variant per output
best = {}
for c in chains:
    if c["output"] not in best or c["mult"] > best[c["output"]]["mult"]:
        best[c["output"]] = c
chains = sorted(best.values(), key=lambda x: -x["mult"])

show_header("1. CRAFTING MULTIPLIES /worth: recipes where the output is worth more than its inputs",
            "This is free money: craft, then /sell. Ranked by multiplier. Only recipes where every leg has a known /worth.")
print("%-26s %7s %11s %12s %12s %8s  %s" % ("output", "makes", "out /worth", "inputs cost", "gain", "mult", "recipe"))
for c in chains[:30]:
    if c["mult"] <= 1.001:
        break
    print("%-26s %7d %11s %12s %12s %7.2fx  %s" % (
        c["output"], c["out_n"], f"{c['out_worth']:,.0f}", f"{c['in_cost']:,.0f}",
        f"{c['gain']:+,.0f}", c["mult"], c["inputs"][:52]))
losers = [c for c in chains if c["mult"] < 0.999]
if losers:
    print("\nValue-DESTROYING crafts (never craft these before selling, sell the inputs raw):")
    for c in sorted(losers, key=lambda x: x["mult"])[:8]:
        print("   %-26s %6.2fx   %s" % (c["output"], c["mult"], c["inputs"][:56]))

# ---------------------------------------------------------------- 2. chest value ranking
show_header("2. WHAT GOES IN THE CHEST: /worth x 1,728, the sell axe's unit of account",
            "One swing empties one chest. This is the entire ranking of what to feed the axe.")
rows = sorted(WORTH.items(), key=lambda x: -x[1])
print("%-30s %12s %16s %14s  %s" % ("item", "/worth", "per chest", "AH unit", "channel verdict"))
for n, w in rows[:25]:
    ah = ah_unit(n)
    if ah <= 0:
        verdict = "no AH data, /sell it"
    elif ah > w:
        verdict = "AH pays %.1fx more per unit" % (ah / w)
    else:
        verdict = "/SELL BEATS AH by %.1fx" % (w / ah)
    print("%-30s %12s %16s %14s  %s" % (
        n, f"{w:,.0f}", f"{w * CHEST:,.0f}", f"{ah:,.0f}" if ah else "-", verdict))

# ---------------------------------------------------------------- 3. free money scan
show_header("3. FREE MONEY: items whose AH price is BELOW their /worth",
            "/worth is a hard price floor. Anything listed under it can be bought and /sold risk-free.")
found = []
for n, w in WORTH.items():
    ah = ah_unit(n)
    if 0 < ah < w:
        found.append((n, ah, w, w / ah, f(n, "ah_d_vol")))
if found:
    print("%-30s %12s %12s %8s %14s" % ("item", "AH now", "/worth", "edge", "daily volume"))
    for n, ah, w, r, v in sorted(found, key=lambda x: -x[3]):
        print("%-30s %12s %12s %7.2fx %14s" % (n, f"{ah:,.0f}", f"{w:,.0f}", r, f"{v:,.0f}"))
else:
    print("  Nothing right now: every priced item trades above its /worth floor, which is normal.")
    print("  Re-run after a crash or a big dump; this is where panic sales get harvested.")

# ---------------------------------------------------------------- 4. channel choice
show_header("4. CHANNEL CHOICE per item: does uncapped /sell beat the capped auction house?",
            "AH is capped at ~20%% of daily volume. /sell is unlimited but pays less per unit.")
print("%-28s %10s %11s %15s %17s  %s" % (
    "item", "/worth", "AH unit", "AH capped $/d", "units for /sell tie", "verdict"))
cmp_rows = []
for n, w in WORTH.items():
    ah, vol = ah_unit(n), f(n, "ah_d_vol")
    if ah <= 0 or vol <= 0:
        continue
    cap = ah * vol * CAPTURE
    need = cap / w                      # units/day you must produce for /sell to match the AH route
    cmp_rows.append((n, w, ah, cap, need))
for n, w, ah, cap, need in sorted(cmp_rows, key=lambda x: x[4])[:22]:
    verdict = "/sell if you make >%s/day" % f"{need:,.0f}"
    print("%-28s %10s %11s %15s %17s  %s" % (
        n, f"{w:,.0f}", f"{ah:,.0f}", f"{cap:,.0f}", f"{need:,.0f}", verdict))

print("\nStill missing: the AH tax rate. It is the only money sink on the server (/sell is the faucet),")
print("so it sets the inflation rate and it makes every AH figure above optimistic. Read it off a receipt.")
