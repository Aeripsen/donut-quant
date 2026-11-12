# Donut Quant Market Terminal

An **interactive, static, public-safe market-exit calculator**, not another
list of estimated "billions per hour".

## What is useful today

- Compare six curated historical settled AH prices against Nov 11-12, 2026
  public asking prices and buy orders. Each item has its original source and
  caveat about item variants, lot sizes and time.
- Simulate an item quantity consuming visible bids in descending price order.
  **Unfilled items are not counted as money.**
- Switch to the hypothetical Sell Axe path: buyers bidding strictly above
  entered server /worth get priority, then the remaining quantity falls back
  to /worth. This routing is a scenario until re-verified in-game.
- Enter real costs, tool cost and assumed fees for a net result. Missing
  costs cause "unknown profit", never a fabricated margin.
- Paste your own current `price,remaining_units` bid levels, no login or
  shared API key required. Custom bids never leave your browser.
- Generate a shareable PNG card showing the math and source caveats.
- Model the physical 24-hour cap with farm production/hour and chest
  clearing rate/hour, instead of multiplying a top order by infinite volume.

This is an intentionally **narrow research instrument** for a genuine
market-microstructure question, not a live full-market tracker.

## Run locally

From the repository root:

```powershell
python -m http.server 8787 --directory docs
```

Open `http://127.0.0.1:8787/`. Directly opening `index.html` as a file
will block `fetch('assets/snapshot.json')` in most browsers.

## Test

```powershell
node --test tests/test_market_engine.mjs
python -m unittest discover -s tests -v
```

To run end-to-end browser tests with Playwright and installed Edge:

```powershell
python tests/browser_smoke.py
```

The browser test screenshots and exported cards are saved only under
gitignored `private/site_qa/`.

## Publishing

This folder can be served as GitHub Pages using `main /docs`. All page
assets are relative URLs so they work at a project path such as
`/donut-quant/`. The full repo keeps historical research and local
private tools separate from the website.

## How to refresh market data correctly

The static, browser-visible file `assets/snapshot.json` is a **curated,
dated and small demonstration**, not a live API feed. Never embed a
DonutStats key in JavaScript or GitHub Pages.

The existing Python collectors `quant/donutstats_snapshot.py` and
`quant/import_market.py` allow a user to collect authorized raw JSON
locally into gitignored `private/`. A future server-side producer can
publish updated derived aggregates after validating schema, source terms,
rate limits, exact variants and unit meaning. Keep private orders and
inventories out of public snapshots.

Read the mathematical and privacy notes in
[System Model](SYSTEM_MODEL.md),
[Market Audit](MARKET_AUDIT_2026-11-12.md) and
[Data Notice](../DATA_NOTICE.md).

## What a public user cannot infer

- Current buy orders are **not guaranteed** available at a later time.
- Quoted asking price is **not** completed sale or liquidation value.
- Historical medians often combine different stack sizes/variants.
- The sell-axe route, fixed server /worth, 2% charge settlement and
  effective multiplier need current in-game verification.
- The project does not claim that unobserved costs are zero.

## A clear roadmap

1. API-key-authorized *server-side* scheduled snapshot and schema checks.
2. Verified exact-variant execution depth for more items.
3. Farm/recipe DAG with physical throughput and market clearing.
4. User-owned inventory and cost-basis import from permitted screenshots.
5. Backtests using realized fills, with honest observation coverage.

## Contribution

Report reproductions and edge cases in GitHub Issues. Especially valuable:
exact order-variant screenshots, Sell Axe versus ordinary /sell differences,
recent /worth screenshots and mismatches between displayed and actual fees.
Do not upload keys, login credentials or private player inventory.
