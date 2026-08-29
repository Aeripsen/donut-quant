"""Orders -> AH flip scan: buy with a /orders buy order at the current top bid, resell in stacks on /ah.

sell side = robust AH sale price per unit: median of the last 15 settled sales (tx_med) when available,
            else min(stack-avg unit, last sale unit). buy side = LootSeller top order bid (fresh, 2026-08-29)
            or the June-25 donutsmp.finance realistic order price (flagged STALE).
Spread is pre-tax: subtract the AH tax once you have measured it in game.
"""
import csv, os, sys
SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = list(csv.DictReader(open(f"{SP}/quant/price_table.csv", encoding="utf-8")))

def f(r, k):
    v = r.get(k)
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None

rows = []
for r in P:
    buy = f(r, "order_buy"); src = r.get("order_buy_src") or ""
    if not buy:
        continue
    txm = f(r, "tx_med"); stk = f(r, "tx_stack_med"); su = f(r, "ah_stack_unit"); jp = f(r, "jp_last_unit")
    dst = f(r, "ah_ds_trades") or 0; vol = f(r, "ah_d_vol") or 0; trades = f(r, "ah_d_trades") or 0
    cands = [x for x in [stk, txm] if x] or [x for x in [su if dst >= 5 else None, jp] if x]
    if not cands:
        continue
    sell = min(cands)
    spread = sell - buy
    if sell <= 0:
        continue
    rows.append(dict(item=r["name"], stack=r["stack"], order_bid=buy, bid_src=src, ah_sell_unit=round(sell, 1),
                     sell_basis=("tx_median" if (stk or txm) else "stack_avg/last"), spread=round(spread, 1),
                     spread_pct=round(100 * spread / buy, 1), ah_units_per_day=int(vol), ah_trades_per_day=int(trades),
                     spread_x_daily_volume=round(spread * vol), per_stack_profit=round(spread * int(r["stack"]))))
rows.sort(key=lambda x: -x["spread_x_daily_volume"])
with open(f"{SP}/quant/orders_to_ah.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("%-30s %5s %12s %10s %12s %8s %9s %10s %16s %12s" % ("item", "stack", "order_bid", "src", "ah_sell", "spread", "spread%", "trades/d", "spread*vol/day", "$/stack"))
for x in rows[:70]:
    if x["spread"] <= 0:
        continue
    print("%-30s %5s %12s %10s %12s %8s %8s%% %10s %16s %12s" % (x["item"], x["stack"], "{:,.0f}".format(x["order_bid"]), x["bid_src"][:10],
          "{:,.0f}".format(x["ah_sell_unit"]), "{:,.0f}".format(x["spread"]), x["spread_pct"], "{:,}".format(x["ah_trades_per_day"]),
          "{:,.0f}".format(x["spread_x_daily_volume"]), "{:,.0f}".format(x["per_stack_profit"])))
