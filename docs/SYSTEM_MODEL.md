# DonutSMP as a dynamic economic system (2026-11-12)

This is a **typed, time-dependent network**, not an inventory of unrelated topics.

## 1. Objects, relations and state

At time `t`, write `G(t)=(V(t), E(t), X(t), O(t))`:
- **Entities** `V`: player/account, item kind, exact item variant, item instance, inventory/container, auction listing, buy order, order fill, AH sale, currency account, farm, recipe, server price rule, tax rule.
- **Relations** `E`: owns(player,item), contains(container,item), places(player,order), lists(player,listing), bids(order,variant), matches(fill,order), delivered(fill,variant), makes(recipe,outputs), consumes(recipe,inputs), restricts(rule,action), receives(player,currency).
- **States** `X`: per-player available cash, money committed to orders, claimable goods, item quantities by variant/location, order remaining quantity, active listings, facility throughput, server-configured /worth and fees.
- **Observations** `O`: evidence with source, scope, timestamp, exact unit, provenance and status. A log line, API response and price chart are distinct observations, not independent proof of an event.

The model is a relational event graph with balance sheets at selected times. Events change many related states simultaneously.

## 2. State transitions and conservation

For each verified event, reconcile **what changed**, not just its label:

| Event | Asset and cash transitions | Important uncertainty |
|---|---|---|
| Buy order created | Available funds may be reserved in escrow; quantity bid is not a purchase | Exact server reservation/refund mechanics |
| Order filled | Buyer receives claimable goods, order remaining quantity decreases, seller receives payment | Supplier identity not in public DonutStats fill object |
| AH listing created | Goods become listed; listing price is *not* revenue; a quoted listing tax may arise | Whether/when tax actually debits the account |
| AH listing closes | Listed goods disappear from market | DonutStats cannot distinguish sale from cancellation/expiry |
| Confirmed sale in player log | Seller receives value and goods leave portfolio | Quantity/contents and cost basis may be missing |
| /sell or Sell Axe | Eligible goods leave inventory; compatible orders may absorb first, otherwise server pays /worth | Current routing, multiplier, fees and order book must be checked |
| Craft/farm operation | Inputs/resources consumed or transformed into exact output variants | Throughput, server restrictions and losses |

At the item level: `initial_stock + acquired + produced - sold - consumed - transferred = final_stock`.
At the account level: `opening_cash + verified_cash_in - verified_cash_out +/- transfers = closing_cash`.
Unobserved transfers, incomplete capture and overlapping summaries should appear as an explicit residual; never force equality by inventing trades.

Order fills conserve quantity: `initial_order_amount = delivered + remaining` unless the order expires/cancels. **Do not** sum AH proceeds with a separate aggregate `You earned from auction` notification, which can report the same underlying sales.

## 3. Observability / epistemic limits

| Dataset | Observable from | What cannot be concluded |
|---|---|---|
| Account balances and history | DonutStats player profile/history; old public leaderboards | Balances alone do not imply earnings or net worth |
| Active personal listings/orders | DonutStats player endpoints with API key and recent check | Private equipment, Ender Chest and base storage |
| Closed AH listings | DonutStats auction history, filtered by seller | Whether each listing sold, expired or was cancelled |
| Actual order deliveries | DonutStats `/v1/orders/fills`: orderId, variant, timestamp, qty, paid | Seller/receiver identity unless separately observed |
| Open orders | DonutStats order book: exact variant, price, amount, delivered, remaining | Future fills or guaranteed executable depth |
| Item prices/history | DonutStats products, historical points | Guaranteed liquidation at asking price |
| Local account activity | Client logs from Modrinth, own screenshots | Events during missing sessions or other devices |
| /worth | Historical in-game screenshots, in-game /worth | Current value until refreshed |
| Private inventory | Screenshots/export explicitly authorized in-game | A server-authoritative copy from multiplayer client save files |
| Market size | DonutStats economy/leaderboard samples | Exact total currency across unranked/non-observed accounts |
| All player-to-player trades | Partial public AH/order history | Complete global transaction graph, full counterparties or /pay ledger |

Observed history begins when a third-party provider began recording. “Keeps everything” means its **observed records**, not all server transactions since server launch. The public market is **not a blockchain**: many transfers and identities are non-public.

## 4. Price and identifiability discipline

The exact product key matters: `elytra` differs from `elytra[mending,unbreaking:3]`; a filled shulker's value depends on `details.contents` even if both have `item=shulker_box`. Quantities and lot sizes matter: single-unit asks are not equivalent to realized 64-stack prices.

Use separate measures:
- `ask`: cheapest executable offered listing *if still active*, not a past sale.
- `bid`: highest compatible order price, limited by its **remaining quantity**, not the aggregate of all orders.
- `order_fill_price`: `paid / quantity` on a recorded delivery, which is realized trade evidence.
- `historical_AH_listing_close`: closure, **not** a confirmed sale.
- `realized_P&L`: confirmed proceeds less traced acquisition/production costs, fees and taxes. Unknown cost basis => unknown realized P&L.

Uncertainty is propagated: if fill likelihood, acquisition cost or sale identity is unknown, no precise expected profit may be asserted.

## 5. Optimization follows the state constraints

A prospective action `a` has `E[net_profit(a)]`, active time, required capital, physical throughput, inventory, slot capacity, risk and absorption limits. Choose actions `x_a` to maximize sustainable expected net returns subject to:

`sum capital_a*x_a <= available_cash`

`sum active_minutes_a*x_a <= available_minutes`

`sum slot_hours_a*x_a <= AH_slot_hours`

`sum sold_units_(variant,a)*x_a <= executable_demand_variant + valid_server_sell_capacity`

`production_a <= min(input_supply, farm_capacity, processing_capacity)`

Include transaction tax/fees, delayed fills, holding risk and correlated prices. In a recursive market, selling more can change order depth and therefore later marginal revenue. Re-optimize with refreshed data; do not multiply today's best bid by an unlimited output rate.

## 6. Data collection architecture

- `quant/personal_ledger.py`: read-only, de-duplicated parsing of two Modrinth profiles, producing **private** event CSV and summary. Source timestamps are local clock times; raw logs are not a complete ledger.
- `quant/donutstats_snapshot.py`: optional API-key-authenticated, bounded snapshot collection to **private/**.
- `quant/linked_db.py`: typed relational evidence schema (products, order states, verified fills, unknown-closure AH listings, quotes, inventory snapshots) and private chat import.
- `quant/import_market.py`: normalize authenticated DonutStats JSON into the private linked database with source hashes; it does not label closed listings as sales.
- `quant/sell_routing.py`: pure value-conservation and exact-variant order routing model with limited depth, explicit tax parameters, Sell Axe cost.
- `tests/test_quant_v2.py`: reproducible unit tests.

Public code must never contain the player's raw chat, friends, current inventory, credentials, or live private datasets. They remain under gitignored `private/`.

## 7. Questions requiring new evidence

1. Exact 2026-11 in-game Sell Axe and /sell routing preview and fee treatment; check `/sellhistory`.
2. Latest actual 2026-11 `/worth` for candidate outputs, whether temporary 3x rate still applies.
3. Inventory / Ender Chest / filled-shulker quantities via explicitly shared screenshots or permitted export.
4. DonutStats API key installed **locally** by account owner for current private and public snapshots.
5. Current remaining buy orders and order prices, including filled/claimable order deliveries and refunds.

References:
- https://api.donutstats.io/docs/reference/
- https://api.donutstats.io/docs/objects/closed-listing/
- https://api.donutstats.io/docs/objects/fill/
- https://donutsmp.wiki/selling
- https://donutsmp.wiki/orders
