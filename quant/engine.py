"""DECISION ENGINE. One machine: every way to make money, scored on one scale, allocated across the slots you have.

It enumerates every candidate action available on the server, prices each one from the same data, converts them all
into the same unit ($ per slot-hour), then fills the 18 auction slots with the best mix that capital and market
depth actually allow.

WHY $ PER SLOT-HOUR IS THE UNIT
An auction slot is the scarce resource, not money and not time. A default account has 18. One listing occupies one
slot until it sells. So the value of any plan is (profit per listing) x (how many times that slot turns per hour),
and everything -- flipping, crafting, brewing, farming, holding -- has to be quoted that way to be comparable.

ACTION TYPES ENUMERATED
  FLIP   buy on /orders at the top bid, resell as a stack on /ah
  CRAFT  buy inputs (orders or AH, whichever is cheaper), craft, sell the output
  BREW   potion recipes, priced off realized sales because the market data has no potion type
  HOLD   no slot used; return comes from price appreciation, so it is scored separately and never
         competes for slots. Driven by the accumulation signal and by supply class.
  FARM   produce the input yourself instead of buying it; scored as the flip/craft minus input cost

CYCLE TIME
Estimated from real liquidity: an item with T settled trades/day gets an expected time-to-sell of
1440/T minutes, floored at 3 minutes (his own log: floor-priced listings cleared in a median of 1.4 min)
and capped at 24h. Listing at the floor is assumed.

DEPTH LIMIT
You cannot sell more than the market absorbs. Each action is capped at 10% of the item's daily traded units;
past that you are the market and the price you priced against stops existing.

CONFIDENCE
Every number carries a data-quality grade, and low-confidence actions are discounted rather than hidden:
  A  fresh order bid + >=5 stack sales + >=300 trades/day
  B  one of those missing
  C  stale June order price, or thin sale history (<5 obs), or <100 trades/day
Anything graded C is shown but its score is halved, because that is roughly how often stale inputs turn out wrong.
"""
import csv, glob, json, os

SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLOTS = int(os.environ.get("SLOTS", "18"))
BANKROLL = float(os.environ.get("BANKROLL", "80000000"))
TAX = float(os.environ.get("TAX", "0"))            # set 0.10 once measured in game
ACTIVE_HOURS = float(os.environ.get("HOURS", "3"))

items = json.load(open(f"{SP}/mcdata/items.json", encoding="utf-8"))
byid = {i["id"]: i for i in items}
byname = {i["name"]: i for i in items}
P = {r["name"]: r for r in csv.DictReader(open(f"{SP}/quant/price_table.csv", encoding="utf-8"))}


def f(r, k):
    try:
        return float((r or {}).get(k) or 0)
    except (ValueError, AttributeError):
        return 0.0


# ---------- market model -------------------------------------------------
def sell_unit(name):
    """Conservative price one unit clears at, selling in stacks, plus the confidence grade."""
    r = P.get(name)
    if not r or r.get("enchantable") == "1":
        return 0.0, "X"
    ns, nt = f(r, "n_stack"), f(r, "n_tx")
    stack_med, med, p25 = f(r, "tx_stack_med"), f(r, "tx_med"), f(r, "tx_p25")
    stackable = int(r.get("stack") or 1) > 1
    if stackable:
        # only full-stack sales count. No stack sales -> no trustworthy bulk price, full stop.
        if ns >= 3 and stack_med:
            return (min(stack_med, p25) if p25 else stack_med), ("A" if nt >= 10 else "B")
        return 0.0, "X"
    if nt >= 5 and med:
        return (min(med, p25) if p25 else med), "B"
    return 0.0, "X"


def buy_unit(name):
    """Cheapest realistic acquisition, and whether that price is fresh."""
    r = P.get(name)
    if not r:
        return 0.0, "X"
    ob, src = f(r, "order_buy"), r.get("order_buy_src", "")
    ah = f(r, "ah_buy_unit")
    cands = [(ob, "A" if src == "lootseller" else "C")] if ob else []
    if ah:
        cands.append((ah, "B"))
    if not cands:
        return 0.0, "X"
    return min(cands, key=lambda x: x[0])


def cycle_minutes(name, units=1):
    """Expected minutes for one listing to sell, at the floor, behind a queue of other sellers."""
    r = P.get(name)
    t, v = f(r, "ah_d_trades"), f(r, "ah_d_vol")
    if t <= 0 or v <= 0:
        return 1440.0
    # your listing is `units` out of `v` units traded per day; assume ~5 comparable listings ahead of you
    share_of_day = max(units / v, 1.0 / max(t, 1))
    return max(5.0, min(1440.0, 1440.0 * share_of_day * 5))


def depth_units(name):
    return f(P.get(name), "ah_d_vol") * 0.10


def grade(*gs):
    order = {"A": 0, "B": 1, "C": 2, "X": 3}
    worst = max(gs, key=lambda g: order.get(g, 3))
    return worst


def discount(g):
    return {"A": 1.0, "B": 0.85, "C": 0.5}.get(g, 0.0)


# ---------- accumulation signal (bid leads the AH price) -----------------
signal = {}
for path in glob.glob(f"{SP}/api/lootseller/*.json"):
    try:
        d = json.load(open(path, encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        continue
    def ser(k):
        v = [(c.get("c") or 0) for c in (d.get(k) or [])]
        while v and v[-1] == 0:
            v.pop()
        return [x for x in v if x > 0]
    b, a = ser("orderCandles"), ser("candles")
    if len(b) >= 5 and len(a) >= 5:
        w = min(6, len(b) // 2)
        prev_b = sorted(b[-2 * w:-w])[len(b[-2 * w:-w]) // 2] if b[-2 * w:-w] else b[0]
        prev_a = sorted(a[-2 * w:-w])[len(a[-2 * w:-w]) // 2] if a[-2 * w:-w] else a[0]
        signal[os.path.basename(path)[:-5]] = {
            "bid_trend": b[-1] / prev_b if prev_b else 1.0,
            "ah_lag": a[-1] / prev_a if prev_a else 1.0,
            "bid_vs_ah": b[-1] / a[-1] if a[-1] else 0.0,
            "headroom": max(b) / b[-1] if b[-1] else 1.0,
            "bid": b[-1], "ah": a[-1],
        }

STRUCTURE = set()
for n in P:
    if n.endswith(("_pottery_sherd", "_smithing_template")) or n.startswith("music_disc"):
        STRUCTURE.add(n)
STRUCTURE |= {"elytra", "dragon_head", "gilded_blackstone", "deepslate_emerald_ore", "sponge", "wet_sponge",
              "echo_shard", "heart_of_the_sea", "ancient_debris", "enchanted_golden_apple", "heavy_core",
              "ominous_trial_key", "trial_key", "breeze_rod", "mojang_banner_pattern"}

actions = []


def add(kind, label, item, unit_cost, unit_value, units_per_listing, g, note="", inputs="", extra_min=0.0):
    if unit_value <= 0 or units_per_listing <= 0:
        return
    revenue = unit_value * units_per_listing * (1 - TAX)
    cost = unit_cost * units_per_listing
    profit = revenue - cost
    if profit <= 0:
        return
    cyc = cycle_minutes(item, units_per_listing) + extra_min
    turns = 60.0 / cyc
    per_slot_hour = profit * turns
    daily_value = f(P.get(item), "ah_d_vol") * unit_value
    if daily_value > 0 and profit > 0.05 * daily_value:
        return            # one listing cannot be a twentieth of the whole day's turnover
    cap_units = depth_units(item)
    max_listings_day = (cap_units / units_per_listing) if units_per_listing else 0
    # what the market can absorb, per hour, in dollars of profit -- independent of how many slots you own
    ceiling_per_hour = max_listings_day * profit / 24.0
    turns_per_day = 1440.0 / cyc
    # slots that can actually stay busy on this item before you are oversupplying it
    useful_slots = max_listings_day / turns_per_day if turns_per_day else 0
    actions.append(dict(
        kind=kind, action=label, item=item, inputs=inputs,
        unit_cost=round(unit_cost, 1), unit_value=round(unit_value, 1), per_listing=units_per_listing,
        capital_per_listing=round(cost), profit_per_listing=round(profit),
        cycle_min=round(cyc, 1), profit_per_slot_hour=round(per_slot_hour * discount(g)),
        raw_slot_hour=round(per_slot_hour), grade=g, depth_listings_per_day=round(max_listings_day, 1),
        ceiling_per_hour=round(ceiling_per_hour * discount(g)), useful_slots=round(useful_slots, 2),
        note=note))


# ---------- 1. FLIP: orders -> AH ---------------------------------------
for name, r in P.items():
    sv, sg = sell_unit(name)
    if r.get("order_buy_src") != "lootseller":
        continue          # stale June bid: that order price no longer exists, an order there never fills
    bc, bg = f(r, "order_buy"), "A"
    if not bc or not sv:
        continue
    stack = int(r["stack"])
    vol = f(r, "ah_d_vol")
    if vol <= 0:
        continue
    # hours to fill one stack: your order competes for the same flow the AH is selling into
    fill_min = max(30.0, 1440.0 * (stack / vol) * 3)
    add("FLIP", f"buy {name} on /orders at {bc:,.0f}, relist a stack", name, bc, sv, stack,
        grade(bg, sg), inputs=f"{stack} x {name}", extra_min=fill_min,
        note=f"order needs ~{fill_min/60:.1f}h to fill")

# ---------- 2. CRAFT ----------------------------------------------------
rec = json.load(open(f"{SP}/mcdata/recipes.json", encoding="utf-8"))


def ing_id(x):
    if x is None:
        return None
    if isinstance(x, dict):
        return x.get("id")
    if isinstance(x, list):
        return x[0] if x else None
    return x


best_craft = {}
for res_id, variants in rec.items():
    res_id = int(res_id)
    out_name = byid[res_id]["name"]
    sv, sg = sell_unit(out_name)
    if not sv:
        continue
    for v in variants:
        counts = {}
        cells = [c for row in v.get("inShape", []) for c in row] if "inShape" in v else v.get("ingredients", [])
        for c in cells:
            i = ing_id(c)
            if i is not None and i >= 0:
                counts[i] = counts.get(i, 0) + 1
        if not counts:
            continue
        out_n = v.get("result", {}).get("count", 1)
        cost = 0.0
        gs = [sg]
        parts = []
        ok = True
        for i, n in counts.items():
            nm = byid[i]["name"]
            bc, bg = buy_unit(nm)
            if not bc:
                ok = False
                break
            cost += n * bc
            gs.append(bg)
            parts.append(f"{n}x {nm}")
        if not ok:
            continue
        unit_cost = cost / out_n
        if unit_cost >= sv:
            continue
        cur = best_craft.get(out_name)
        if cur is None or unit_cost < cur[0]:
            best_craft[out_name] = (unit_cost, grade(*gs), " + ".join(parts))
for out_name, (uc, g, parts) in best_craft.items():
    sv, _ = sell_unit(out_name)
    stack = int(P[out_name]["stack"])
    add("CRAFT", f"craft {out_name} and sell a stack", out_name, uc, sv, stack, g,
        inputs=parts, extra_min=1.0)

# ---------- 3. BREW -----------------------------------------------------
BOTTLE = buy_unit("glass_bottle")[0] or 250
BREW = {
    "Strength":          (["nether_wart", "blaze_powder"], 333_000),
    "Swiftness":         (["nether_wart", "sugar"], 300_000),
    "Water Breathing":   (["nether_wart", "pufferfish"], 333_000),
    "Slowness (splash)": (["nether_wart", "sugar", "fermented_spider_eye", "gunpowder"], 350_000),
    "Fire Resistance":   (["nether_wart", "magma_cream"], 100_000),
    "Healing":           (["nether_wart", "glistering_melon_slice"], 100_000),
}
for nm, (ings, realized) in BREW.items():
    cost = 3 * BOTTLE + (buy_unit("blaze_powder")[0] or 30) / 20.0
    gs = []
    ok = True
    for i in ings:
        b, g = buy_unit(i)
        if not b:
            ok = False
            break
        cost += b
        gs.append(g)
    if not ok:
        continue
    # potions do not stack: one potion is one listing. Cycle uses the "potion" row's liquidity.
    add("BREW", f"brew {nm}, one potion per slot", "potion", cost / 3, realized, 1,
        grade(*gs) if gs else "B", inputs=" + ".join(ings) + " + 3 bottles",
        note="price from his own realized sales, not market median", extra_min=2.0)

# ---------- 4. HOLD (no slot consumed) ----------------------------------
holds = []
for name, s in signal.items():
    r = P.get(name)
    if not r:
        continue
    trades = f(r, "ah_d_trades")
    if trades < 100:
        continue
    if s["bid_trend"] >= 1.15 and s["ah_lag"] <= 1.25:
        upside = s["headroom"]
        holds.append(dict(item=name, why="bid rising, AH has not followed", bid=round(s["bid"]),
                          ah=round(s["ah"]), bid_trend=round(s["bid_trend"], 2), ah_lag=round(s["ah_lag"], 2),
                          headroom=round(upside, 1), trades_day=int(trades),
                          structure="yes" if name in STRUCTURE else ""))
holds.sort(key=lambda x: -x["bid_trend"])

exits = []
for name, s in signal.items():
    r = P.get(name)
    if not r or f(r, "ah_d_trades") < 100:
        continue
    if s["bid_trend"] < 0.8 and s["headroom"] >= 1.5:
        exits.append(dict(item=name, why="bid falling from peak", bid=round(s["bid"]),
                          peak=round(s["bid"] * s["headroom"]), bid_trend=round(s["bid_trend"], 2),
                          trades_day=int(f(r, "ah_d_trades"))))
exits.sort(key=lambda x: x["bid_trend"])

# ---------- rank and allocate -------------------------------------------
actions.sort(key=lambda a: -a["profit_per_slot_hour"])
with open(f"{SP}/quant/engine_actions.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(actions[0].keys()))
    w.writeheader()
    w.writerows(actions)

print("=" * 118)
print(f"DECISION ENGINE  |  {SLOTS} slots  |  bankroll ${BANKROLL:,.0f}  |  tax {TAX:.0%}  |  {ACTIVE_HOURS:.0f} active hours/day")
print("=" * 118)
print("\nTOP ACTIONS BY $/SLOT-HOUR (grade C is halved for stale or thin data)\n")
print("%-6s %-44s %11s %13s %9s %6s %6s %14s" % (
    "type", "action", "capital", "profit/list", "cycle", "grade", "depth", "$/slot-hour"))
seen = set()
shown = 0
for a in actions:
    k = (a["kind"], a["item"])
    if k in seen:
        continue
    seen.add(k)
    if a["capital_per_listing"] > BANKROLL:
        continue
    print("%-6s %-44s %11s %13s %6.0fm %6s %6.0f %14s" % (
        a["kind"], a["action"][:44], f"{a['capital_per_listing']:,}", f"{a['profit_per_listing']:,}",
        a["cycle_min"], a["grade"], a["depth_listings_per_day"], f"{a['profit_per_slot_hour']:,}"))
    shown += 1
    if shown >= 22:
        break

# greedy allocation across slots, respecting capital and market depth
print(f"\n\nSLOT ALLOCATION: how to fill your {SLOTS} slots right now\n")
cap_left = BANKROLL
used = 0
plan = []
per_item_slots = {}
for a in actions:
    if used >= SLOTS:
        break
    if a["grade"] == "C":
        continue          # stale or thin data: never allocate real slots against it
    if a["item"] in per_item_slots:
        continue
    take = min(SLOTS - used, max(1, round(a["useful_slots"])), 6)
    if a["capital_per_listing"] * take > cap_left:
        take = int(cap_left // max(a["capital_per_listing"], 1))
    if take < 1:
        continue
    cap_left -= a["capital_per_listing"] * take
    used += take
    per_item_slots[a["item"]] = take
    # earnings are capped by what the market absorbs, not by slots x rate
    plan.append((take, a, min(take * a["profit_per_slot_hour"], a["ceiling_per_hour"])))
print("%-5s %-44s %13s %14s %15s" % ("slots", "what to list", "capital", "mkt ceiling", "$/hour realistic"))
tot = 0
for take, a, real in plan:
    tot += real
    print("%-5d %-44s %13s %14s %15s" % (
        take, a["action"][:44], f"{a['capital_per_listing']*take:,}",
        f"{a['ceiling_per_hour']:,}", f"{real:,.0f}"))
print("%-5d %-44s %13s %14s %15s" % (used, "TOTAL", f"{BANKROLL-cap_left:,.0f}", "", f"{tot:,.0f}"))
print("")
print("  Realistic daily take at %.0f active hours plus overnight fills: $%s" % (
    ACTIVE_HOURS, f"{tot*ACTIVE_HOURS + tot*0.4*(24-ACTIVE_HOURS):,.0f}"))
print(f"\n  Capital left over: ${cap_left:,.0f}   ->  put it into the HOLD list below, which uses no slots.")

print("\n\nHOLD (no slot used; bid is rising and the auction price has not caught up)\n")
print("%-24s %11s %11s %8s %8s %9s %10s  %s" % ("item", "bid", "AH floor", "bid x", "AH x", "headroom", "trades/d", "finite?"))
for h in holds[:12]:
    print("%-24s %11s %11s %7.2fx %7.2fx %8.1fx %10s  %s" % (
        h["item"], f"{h['bid']:,}", f"{h['ah']:,}", h["bid_trend"], h["ah_lag"], h["headroom"],
        f"{h['trades_day']:,}", h["structure"]))

print("\n\nEXIT (bid falling from its peak; sell what you hold)\n")
print("%-24s %11s %11s %8s %10s" % ("item", "bid now", "peak bid", "bid x", "trades/d"))
for e in exits[:12]:
    print("%-24s %11s %11s %7.2fx %10s" % (e["item"], f"{e['bid']:,}", f"{e['peak']:,}", e["bid_trend"], f"{e['trades_day']:,}"))

print(f"\n\n{len(actions)} priced actions. Full table: quant/engine_actions.csv")
print("Re-run with different constraints:  SLOTS=45 BANKROLL=200000000 TAX=0.10 python quant/engine.py")
