"""Accumulation detector: catch the buy orders BEFORE the auction price reprices.

The pattern, read off the candle history of trades that already happened:

  ghast tear   bid 2,400 -> 21,000 (8.8x) while the AH floor stayed noisy around 50-90K
  end crystal  bid 2,400 -> 5,900 -> 15,000 -> 24,700 while AH sat at 10,000
               ... then the AH floor went 15,200 -> 22,900 -> 33,000 -> 37,000
  totem        bid spiked to 220,000 against a 61,300 AH floor
               ... then the AH floor hit 224,000 within five days

In every case the ORDER BID moved first and the AH price followed. That is the whole edge: a rising bid is
somebody with capital accumulating, and they place orders before they buy out listings. The AH price is the
lagging indicator; by the time it moves the trade is public and crowded.

Signals computed per item:
  bid_trend    slope of the order bid over the recent window, as a multiple (2.0 = bid doubled)
  bid_vs_ah    today's bid divided by today's AH floor. Above ~0.8 means buyers are bidding near what
               sellers ask, which is aggressive. Above 1.0 means orders are paying MORE than the listings.
  ah_lag       how much the AH floor has moved over the same window. Low while bid_trend is high =
               the repricing has NOT happened yet. This is the window to buy in.
  headroom     historical max bid divided by today's bid: how far it has run before.

Ranks by an entry score that rewards a rising bid the AH has not yet followed, and penalises anything
where the AH already caught up (you are late) or the bid is falling (the trade is unwinding).

Trailing zero bids in the source data mean "no candle", not "no bid"; they are dropped, not read as zero.
"""
import csv, glob, json, os, statistics

SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = {r["name"]: r for r in csv.DictReader(open(f"{SP}/quant/price_table.csv", encoding="utf-8"))}

# supply that cannot regenerate inside the current border. Brushed once, mined once, gone until expansion.
NON_RENEWABLE = {
    "pottery sherd (suspicious sand/gravel, never regenerates)": [n for n in P if n.endswith("_pottery_sherd")],
    "armor trim template (structure chest, one-time)": [n for n in P if n.endswith("_smithing_template")],
    "music disc (structure chest / creeper kill)": [n for n in P if n.startswith("music_disc")],
    "structure block or mob head": ["gilded_blackstone", "deepslate_emerald_ore", "sponge", "wet_sponge", "echo_shard",
                                    "heart_of_the_sea", "elytra", "dragon_head", "dragon_egg", "ancient_debris",
                                    "enchanted_golden_apple", "heavy_core", "mojang_banner_pattern"],
}
finite = {}
for label, names in NON_RENEWABLE.items():
    for n in names:
        finite[n] = label


def series(d, key):
    """closes for a candle list, trailing/leading zeros dropped (zero = missing candle, not a real price)."""
    out = [(c.get("c") or 0) for c in (d.get(key) or [])]
    while out and out[-1] == 0:
        out.pop()
    return [x for x in out if x > 0]


rows = []
for path in glob.glob(f"{SP}/api/lootseller/*.json"):
    try:
        d = json.load(open(path, encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        continue
    name = os.path.basename(path)[:-5]
    bids, ahs = series(d, "orderCandles"), series(d, "candles")
    if len(bids) < 5 or len(ahs) < 5:
        continue
    W = min(6, len(bids) // 2)                 # recent window
    bid_now, bid_then = bids[-1], statistics.median(bids[-2 * W:-W])
    ah_now, ah_then = ahs[-1], statistics.median(ahs[-2 * W:-W])
    if bid_then <= 0 or ah_then <= 0 or ah_now <= 0:
        continue
    bid_trend = bid_now / bid_then
    ah_lag = ah_now / ah_then
    bid_vs_ah = bid_now / ah_now
    headroom = max(bids) / bid_now
    r = P.get(name, {})

    def f(k):
        try:
            return float(r.get(k) or 0)
        except ValueError:
            return 0.0

    # entry score: bid rising, AH not yet followed, room left to run, real liquidity
    score = (bid_trend ** 1.5) * (1.0 / max(ah_lag, 0.4)) * min(headroom, 6) * (1 if f("ah_d_trades") >= 100 else 0.3)
    rows.append(dict(
        item=name, bid_now=round(bid_now), ah_now=round(ah_now), bid_trend=round(bid_trend, 2),
        ah_lag=round(ah_lag, 2), bid_vs_ah=round(bid_vs_ah, 2), headroom=round(headroom, 1),
        peak_bid=round(max(bids)), trades_day=int(f("ah_d_trades")), units_day=int(f("ah_d_vol")),
        finite=finite.get(name, ""), score=round(score, 2)))


def show(title, rs, note="", n=18):
    print(f"\n=== {title} ===")
    if note:
        print(note)
    print("%-26s %11s %11s %7s %7s %8s %8s %11s %9s  %s" % (
        "item", "order bid", "AH floor", "bid x", "AH x", "bid/AH", "headroom", "peak bid", "trades/d", "finite?"))
    for x in rs[:n]:
        print("%-26s %11s %11s %6.2fx %6.2fx %8.2f %7.1fx %11s %9s  %s" % (
            x["item"], f"{x['bid_now']:,}", f"{x['ah_now']:,}", x["bid_trend"], x["ah_lag"], x["bid_vs_ah"],
            x["headroom"], f"{x['peak_bid']:,}", f"{x['trades_day']:,}", x["finite"][:34]))


rows.sort(key=lambda x: -x["score"])
with open(f"{SP}/quant/accumulation.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

show("A. ACCUMULATING NOW: order bid rising, auction price has NOT followed yet",
     [x for x in rows if x["bid_trend"] >= 1.15 and x["ah_lag"] <= 1.25],
     "This is the ghast tear setup. Buy the listings before the AH floor catches up to the bid.")
show("B. BID IS PAYING MORE THAN THE ASK (bid/AH above 0.9) - someone wants size right now",
     sorted([x for x in rows if x["bid_vs_ah"] >= 0.9], key=lambda x: -x["bid_vs_ah"]),
     "Buyers bidding at or above the cheapest listing means the listings are about to be cleared out.")
show("C. TOO LATE: the AH already repriced (hold or sell into it, do not start buying)",
     sorted([x for x in rows if x["ah_lag"] >= 1.4], key=lambda x: -x["ah_lag"]),
     "The move is public. Anything you buy here you are buying from the people who were early.")
show("D. UNWINDING: bid falling from its peak (exit if you hold)",
     sorted([x for x in rows if x["bid_trend"] < 0.8 and x["headroom"] >= 1.5], key=lambda x: x["bid_trend"]),
     "The accumulator stopped. Ghast tear sits here after running 2,400 to 21,000 and back.")
print(f"\n{len(rows)} items with enough candle history. Full table: quant/accumulation.csv")
print("Coverage note: LootSeller tracks about 60 items, so this only sees what it tracks.")
print("Pottery sherds and most trims have NO candle history -> not visible to this scanner. See the note below.")
