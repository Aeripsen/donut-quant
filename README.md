# donut-quant

I wanted to know where the money actually is on DonutSMP instead of trusting "5 billion a day" thumbnails,
so I pulled the numbers and ran the math over every recipe in the game. This repo is the data, the scripts and the write-up.

Short version: the auction house pays per stack, not per item. A stack of almost any basic block clears for 5-20K,
while `/orders` fill at a fraction of that (spruce logs 72 on orders vs ~330 per log in stack sales, bones 137 vs ~700,
obsidian 601 vs ~1,100, TNT 1,700 vs ~3,900). So for a normal player with 18 slots the game is "how much value can I
put in one slot and how fast does it turn", not "how many blocks per hour does my farm make". Farm-to-`/sell` only pays
at mega scale with a sell axe, and the famous slab farm nets about $22 per log at its own numbers.

The full write-up with 40 methods, each re-priced on live data and scored, is in [`report/analysis.md`](report/analysis.md).
`report/desk.html` is the same thing as a single page with charts.

## What is in here

- `quant/build_prices.py` merges every price source into `quant/price_table.csv`, one row per item:
  SMP500 settled sales (24h aggregates plus the median of the last 15 full-stack sales), LootSeller top order bid and floor,
  the last recorded sale, a June order-book snapshot, my own AH log prices.
- `quant/arbitrage.py` prices every Minecraft 1.21.11 recipe with the cheapest input source and ranks the crafts.
- `quant/orders_to_ah.py` and `quant/report_tables.py` build the order-bid vs auction-sale spread tables with a slot-hour model.
- `quant/conversion.py` answers "which form of this raw input is worth most per unit" (log -> planks -> slabs -> fences...).
- `quant/quant_summary.py` renders the compact market read (`quant/quant_summary.md`).
- `quant/fetch_official.py` talks to the official API (`/api` in game gives you a key) and keeps a local sqlite of sales.
- `api/` raw snapshots pulled 2026-08-29. `mcdata/` is PrismarineJS minecraft-data for 1.21.11; SMP500 item ids equal these ids.
- `sources/` wiki text, method cards mined from videos and blogs, and the list of videos I read.
- `ah_events_anon.csv` my own auction-house events from three days of chat logs, other players pseudonymised.

## Reading the numbers

- Trust `tx_stack_med` (median of the last 15 full-stack sales). The 24h average is polluted by disguised payments
  (people "buy" a stick for 30K to move money) and renamed items.
- Tools, armor and books are excluded from craft math: their AH price is the enchanted copy, not the plain item.
- Order bids marked `(jun)` are from a June snapshot and are stale; read the live bid off `/orders` before acting.
- The AH tax is unknown at the time of writing, every spread is pre-tax.

## Running it

```
python quant/build_prices.py
python quant/report_tables.py
python quant/conversion.py
python quant/quant_summary.py
```

SMP500 sits behind Cloudflare, so the snapshot was pulled through a logged-in browser tab (`/item/{id}/__data.json`).
LootSeller is a free endpoint: `python ls_sweep.py` refreshes it in about 12 minutes.

Not affiliated with DonutSMP. Numbers are in-game dollars.
