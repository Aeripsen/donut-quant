# DonutSMP market audit, 2026-11-12

**Evidence model**: older numbers are **2026-08-29 historical AH transactions aggregated by item id** from `quant/price_table.csv` (SMP500 last-15 transaction medians, 15 observations for items below). Current numbers are **2026-11-12 DonutStats asking-price indicators and best standing buy-order quotes**, observed separately. They do NOT have the same execution semantics or necessarily the same variant/stack mix. This table is not a price index or proof of tradeable arbitrage.

| Item | Historical AH transaction median, Aug 29 ($/unit) | Nov 12 ask indicator ($/unit) | Nov 12 best order ($/unit) | Ask relative to historical | Best bid relative to historical |
|---|---:|---:|---:|---:|---:|
| Elytra, historically variant-mixed | 359,000,000 | 692,000,000 | 525,000,000 | +92.8% | +46.2% |
| TNT | 3,906 | 8,300 | 7,000 | +112.5% | +79.2% |
| Dispenser | 4,500 | 5,800 | 3,300 | +28.9% | -26.7% |
| Gravel | 430 (full-stack median) | 835 (small-lot asks) | 500 | +94.2% | +16.3% |
| Dried kelp block | 2,000 (transaction median) | 796.88 | 766 | -60.2% | -61.7% |

The percent differences are `100*(current_quote / historical_transaction_median - 1)`. **They cannot be read as realized investment returns** without exact variant matching, obtainable buy price, sufficient bid depth and fee/sale evidence. Legacy `elytra` series combines exact variants; a current `elytra[mending,unbreaking:3]` is a different product. The $359M historical number is an old approximate sale median, not a preserved tradeable offer.

Source pages, accessed 2026-11-12:
- https://donutstats.io/prices/elytra
- https://donutstats.io/prices/tnt
- https://donutstats.io/prices/dispenser
- https://donutstats.io/prices/gravel
- https://donutstats.io/prices/dried_kelp_block
- Historical inputs: `quant/price_table.csv`, created from 2026-08-29 snapshots (do not refresh in-place).

## Elytra: liquidation is not asking

On Nov 12 the public page reported eight plain-Elytra listings, ask-price indicator $692M, lowest listing $621M and highest standing compatible order $525M. It reported **one delivered order in 24 hours paying $523M**. Thus:
- Ask-based nominal difference from Aug old median: +92.8%; *not executable revenue*.
- Best-bid nominal difference: +46.2%; executable only to **remaining** depth and compatible variant.
- Single observed order fill: $523M (one trade), not proof every other Elytra can exit for that amount.
- August source has no exact enchant identity; cannot strictly claim same-variant appreciation.

## Sell Axe and /sell: conditional market-clearing simulation

Public wiki records the June 9 integration: compatible buy orders strictly above the base /sell value take priority for `/sell`, including the amethyst Sell Axe. June 17 notes a temporary **3x /sell multiplier** until border expansion. The **current effective /worth must be read in game**, since the 3x historical announcement alone does not verify today's multiplier.

`quant/sell_routing.py` computes the following policy *conditionally*, without assuming server order matching or fee treatment remains identical:

`P_net(Q) = sum_i q_i*p_i*(1-t_order) + q_server*W*(1-t_server) - Q*input_unit_cost - axe_cost - other_cost`

With `q_i=min(remaining, order_i_remaining)` for exact matching variant `item_key`, and only bids `p_i>W` consumed before falling back to server `W`. All money in this section is in-game dollars.

### Worked one-chest example, only if the current /worth is still $750

A chest has `27*64=1,728` dried kelp blocks when fully packed. The Sept in-game `worth_table.csv` recorded $750 per dried kelp block.

The Nov 12 public order book **at the time of observation** showed:
- $766: 112 + 25 + 67 = **204** items left across three orders.
- $757.50: **665** items left.
- $757.40: **574** items left.
- $750 or below: do not exceed the assumed server value.

For one full chest, if all higher bids remained available and item matching was identical:
- 204 at $766; 665 at $757.50; 574 at $757.40; remaining **285** at server $750.
- Order routed units: **1,443**, server fallback units: **285**.
- Simulated gross: **$1,308,499.10**, versus **$1,296,000** if all sold for $750.
- Increment from the temporary top order depth: **$12,499.10 (0.96%)**, *not* 1,728 times the highest $766 bid.
- Additional chests mostly hit the $750 floor unless new bids arrive. The first chest already uses the currently visible above-$750 order depth.
- This is **revenue before materials, shard value, processing effort, tax and axe acquisition**.

The unknowns that decide whether this is profitable are actual farm throughput, input prices, effective current `/worth`, order compatibility, tax treatment and the value of the short-lived 1,500-shard axe. Compute per-day capacity as `min(24*production_items_per_hour, 24*axe_chests_per_hour*1728)`, never extrapolate a thin order to an unlimited market.

Source: https://donutstats.io/prices/dried_kelp_block, https://donutsmp.wiki/selling.

## Macro context (not a substitute for per-item flows)

As of the DonutStats economy reading on Nov 12:
- **$253.4T** held by **89,673 ranked players**; **$28.2T (11.1%)** held by the top ten.
- Median ranked balance **$856M**, Gini coefficient **0.73**.
- Ranked aggregate balance was **$186.2T on October 13**, vs **$253.4T on November 12**, reported **+36.1%** over that window.
- Approximately **$1.5T** in serious open buy orders and **$1.5T** paid out by buy orders in the preceding 24h. These are *different stock/flow metrics* and cannot be added to the ranked money total.
- Auction liquid value **$1.1T**, the amount orders would pay for listed goods (not total asking price of all goods).
- A DonutStats 7-day top-50 item-price index showed +16.7%, but that is not a validated matched-basket inflation rate.

Source: https://donutstats.io/economy

## Reliability and next measurement

DonutStats is a third-party observer, not the server's complete immutable ledger. Its `/v1/orders/fills` records confirmed deliveries, but does not expose both counterparties. Closed auction listing history cannot identify sold vs cancelled. Prices are timestamped and can change mid-session. User's private order books/inventories require authorized in-game observation or connected API key.

No API key was present at `quant/donut_api_key.txt` in this checkout. Without a DonutStats API key we could read public web prices, but **did not ingest the historical fill feeds or personal live order endpoints**. `quant/donutstats_snapshot.py` supports authorized snapshot collection when the user configures their own key locally.

Source docs:
- https://api.donutstats.io/docs/
- https://api.donutstats.io/docs/reference/order-fills/
- https://api.donutstats.io/docs/objects/closed-listing/
