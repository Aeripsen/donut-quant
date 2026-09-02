"""Whale desk: the capital plays. Production earns wages; this is where the multiples are.

Every farm and craft lane is absorption-capped: the market only swallows so much supply per day, so
labor-backed income flattens out around a couple hundred million a day no matter how good the build is.
Capital does not have that cap. Four plays, sized against a real bankroll:

  ACCUMULATE  the ghast tear trade at full size: an order bid is rising and the AH floor has not
              followed. Buy the floor, wait for the reprice, sell into it. Position sized to a few
              days of the item's dollar flow so the exit does not crush the price.
  MARKETMAKE  the standing gap between the order bid and the AH floor on the deepest books. Post bids
              a tick over the current bid, relist fills a tick under the floor. Each round trip earns
              the spread; the books are deep enough that a small share of flow is real money.
  OWNBOOK     thin markets (a few dozen trades a day) where the whole visible floor costs less than a
              day of farm income. Buy every listing, relist 2 to 3x. You are not predicting the price,
              you are setting it. Works while demand tolerates the uplift; watch sell-through.
  OUTSOURCE   buy orders as a labor market. Post orders for INPUTS above what farmers get from their
              own listings but far below what your transformation returns. The server farms for you;
              your throughput becomes their grind rate, not your click rate.

Sizing rules: no position above 40 percent of bankroll; accumulation positions capped at 3 days of the
item's dollar flow; book takeovers capped at thin books only (flow under 30M a day). Pre-tax.
"""
import csv, os

SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = {r["name"]: r for r in csv.DictReader(open(f"{SP}/quant/price_table.csv", encoding="utf-8"))}
BANKROLL = float(os.environ.get("BANKROLL", 80_000_000))


def f(r, k):
    try:
        return float(r.get(k) or 0)
    except (ValueError, AttributeError):
        return 0.0


# ---------------- ACCUMULATE: from the accumulation scanner's own table ----------------
print("=" * 106)
print(f"1. ACCUMULATE (bankroll {BANKROLL:,.0f}): rising bid, lagging AH. Buy the floor before it reprices.")
print("   target = historical peak bid, discounted 40 percent for humility. Position = 3 days of flow, max.")
print("=" * 106)
rows = list(csv.DictReader(open(f"{SP}/quant/accumulation.csv", encoding="utf-8")))
print("%-22s %10s %10s %8s %9s %12s %12s %12s" % (
    "item", "buy at", "target", "upside", "trades/d", "position", "profit", "days flow"))
total_acc = 0.0
for r in rows:
    bid_t, lag, hr = float(r["bid_trend"]), float(r["ah_lag"]), float(r["headroom"])
    ah, peak, tr = float(r["ah_now"]), float(r["peak_bid"]), float(r["trades_day"])
    units = float(r["units_day"]) or tr
    if not (bid_t >= 1.15 and lag <= 1.25 and tr >= 300 and hr >= 1.5 and ah > 0):
        continue
    target = peak * 0.6
    if target <= ah:
        continue
    flow_dollars = ah * units
    pos = min(BANKROLL * 0.4, flow_dollars * 3)
    profit = pos * (target / ah - 1)
    total_acc += profit
    print("%-22s %10s %10s %7.1fx %9s %12s %12s %12s" % (
        r["item"], f"{ah:,.0f}", f"{target:,.0f}", target / ah, f"{tr:,.0f}",
        f"{pos:,.0f}", f"{profit:,.0f}", f"{flow_dollars:,.0f}"))
print("These are trades, not income: entry to exit is days to weeks, and the stop is the bid turning down.")

# ---------------- MARKETMAKE: bid/floor gaps on the deepest books ----------------
print()
print("=" * 106)
print("2. MARKET MAKE: post a bid one tick over the standing bid, relist fills one tick under the floor.")
print("   Assumes you capture 5 percent of daily trades as round trips. Runs from the orders screen, AFK.")
print("=" * 106)
mm = []
for name, r in P.items():
    bid, floor, tr = f(r, "ls_order_bid"), f(r, "ls_ah_floor"), f(r, "ah_d_trades")
    if bid <= 0 or floor <= 0 or tr < 2000:
        continue
    if name in ("filled_map", "map"):
        continue                      # the money-transfer rail, not a market
    smed = f(r, "tx_stack_med")
    if smed > 0 and floor > 4 * smed:
        continue                      # floor is one polluted listing, not where trades clear
    if smed > 0:
        floor = min(floor, smed * 1.5)   # clear against where sales actually happen, not the ask
    spread = floor - bid
    if spread <= 0 or spread / floor < 0.15:
        continue
    daily = spread * tr * 0.05
    mm.append((name, bid, floor, spread, tr, daily))
mm.sort(key=lambda x: -x[5])
print("%-22s %10s %10s %10s %10s %14s" % ("item", "bid", "AH floor", "spread", "trades/d", "profit/d @5%"))
total_mm = 0.0
for name, bid, floor, spread, tr, daily in mm[:12]:
    total_mm += daily
    print("%-22s %10s %10s %10s %10s %14s" % (
        name, f"{bid:,.0f}", f"{floor:,.0f}", f"{spread:,.0f}", f"{tr:,.0f}", f"{daily:,.0f}"))
print(f"Portfolio at 5 percent of flow on these twelve books: {total_mm:,.0f} a day, slot-light, no farming.")

# ---------------- OWNBOOK: thin books cheap enough to buy outright ----------------
print()
print("=" * 106)
print("3. OWN THE BOOK: thin markets where 2 days of flow costs under 25M. Buy the floor, relist at 2x.")
print("   profit/day = flow x uplift x sell-through 50 percent, while the wall holds.")
print("=" * 106)
ob = []
for name, r in P.items():
    if f(r, "enchantable") == "1":
        continue
    tr, vold = f(r, "ah_d_trades"), f(r, "ah_d_vol")
    stackable = int(f(r, "stack") or 64) > 1
    if stackable:
        pr = f(r, "tx_stack_med") if f(r, "n_stack") >= 5 else 0
    else:
        pr = f(r, "tx_single_med") if f(r, "n_single") >= 10 else 0
    if pr <= 0 or tr < 20 or tr > 800:
        continue
    flow = pr * (vold if stackable else tr)
    cost2d = flow * 2
    if not (1_000_000 < cost2d < 25_000_000):
        continue
    daily = flow * 1.0 * 0.5          # 2x relist = 1.0x uplift, half the old volume still clears
    ob.append((name, pr, tr, cost2d, daily))
ob.sort(key=lambda x: -x[4])
print("%-28s %11s %9s %14s %14s" % ("item", "price now", "trades/d", "cost to own 2d", "profit/d held"))
for name, pr, tr, cost2d, daily in ob[:14]:
    print("%-28s %11s %9s %14s %14s" % (name, f"{pr:,.0f}", f"{tr:,.0f}", f"{cost2d:,.0f}", f"{daily:,.0f}"))
print("Rotate 3 or 4 of these at a time; drop any book where relisted stock stops selling within a day.")

# ---------------- OUTSOURCE: buy orders as a labor pipeline into your transformations ----------------
print()
print("=" * 106)
print("4. OUTSOURCE: post buy orders for inputs ABOVE the farmer's alternative, transform, sell.")
print("   Your margin shrinks per unit but throughput becomes the whole server's grind rate.")
print("=" * 106)
PIPE = [
    ("dark_oak_log", "stripped_dark_oak_log", 1, "strip"),
    ("oak_log", "stripped_oak_log", 1, "strip"),
    ("sandstone", "smooth_sandstone", 1, "smelt"),
    ("stone", "stone_slab", 2, "stonecut"),
    ("string", "bundle", 0.5, "craft w/ leather (order both)"),
    ("dirt", "clay", 1, "mud converter"),
    ("sand", "cyan_concrete", 1.6, "mix w/ gravel+dye (order all)"),
]
print("%-14s %9s %9s %-22s %11s %11s %13s" % (
    "input", "they get", "you pay", "output", "sells", "margin/in", "profit/d capped"))
for a, b, ratio, how in PIPE:
    ra, rb = P.get(a, {}), P.get(b, {})
    pa = f(ra, "tx_stack_med")
    pb = f(rb, "tx_stack_med") if int(f(rb, "stack") or 64) > 1 else f(rb, "tx_single_med")
    p25 = f(rb, "tx_p25")
    if p25:
        pb = min(pb, p25)
    if pa <= 0 or pb <= 0:
        continue
    pay = round(pa * 1.3)              # 30 percent over their own-listing take: your order fills first
    margin = pb * ratio - pay
    # throughput: input flow you can hire, but never more than the OUTPUT market absorbs (20 pct of flow).
    out_vol = f(rb, "ah_d_vol") or f(rb, "ah_d_trades")
    units = min(f(ra, "ah_d_vol") * 0.4, out_vol * 0.2 / max(ratio, 0.01))
    daily = margin * units
    print("%-14s %9s %9s %-22s %11s %11s %13s" % (
        a, f"{pa:,.0f}", f"{pay:,}", how + " -> " + b[:12], f"{pb:,.0f}", f"{margin:,.0f}", f"{daily:,.0f}"))
print("The order book is a hiring hall: a 30 percent overpay makes you every farmer's best customer,")
print("and the transformation margin stays 3 to 10x. This is how a lane beats its own absorption cap:")
print("you stop being the farmer and become the factory.")
