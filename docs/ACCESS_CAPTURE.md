# Access, inventory capture and private evidence

The account's client logs and public market data do **not** expose full authoritative multiplayer storage. Inventory and Ender Chest are server-held state, not copied into a normal single-player `level.dat` under Modrinth. A screenshot of a **past** inventory is historical evidence, not proof of current possessions.

## Capture order

1. In game: note balance and shard count; open `/ah my` and record active auctions, item counts, exact contents and prices. Record completed/expired items and money claimable if the GUI provides it.
2. Open `/orders`, navigate to **your** orders. Record item, exact variant, bid, quantity ordered, delivered, remaining, refunds, pending claims, and timestamp. Use the game's own history screens if offered.
3. Open main inventory (including armor/offhand), Ender Chest and every economically relevant Shulker Box and chest. Save dated screenshots with `F2` while hovering details; use Java advanced tooltips (`F3+H`) if useful. Capture Shulker Box contents explicitly rather than valuing the shell.
4. Open `/sellhistory` and `/worth` for candidate farm outputs. Take dated screenshots before buying a time-limited Sell Axe.
5. Never publish base coordinates, secrets, account/session tokens, raw player chat or private screenshots.

For a reproducible inventory record, make a private CSV with columns:

`observed_at_local,source,storage_type,container_id,slot,item_id,variant,quantity,notes`

One row per item stack **at an instant**. `container_id` is an arbitrary private local label, not a coordinate. Example header only:

```csv
observed_at_local,source,storage_type,container_id,slot,item_id,variant,quantity,notes
```

Place it at `private/inventory.csv`, already excluded from Git. Every snapshot needs timestamp and completeness notes. Partial screenshots are partial observations, not zero balances for unseen slots.

## API access, not game account access

DonutStats offers a **separate read-only API key**, not a Minecraft login credential. Set `DONUTSTATS_API_KEY` in your local shell session and run:

```powershell
cd "$HOME\donut-quant"
$env:DONUTSTATS_API_KEY = Read-Host 'DonutStats read-only key'
python quant/donutstats_snapshot.py --player YOUR_IGN --item elytra --item dried_kelp_block --include-global --max-requests 12
python quant/import_market.py
Remove-Item Env:DONUTSTATS_API_KEY
```

The optional collector stores JSON only in gitignored `private/market/`; never paste a key into ChatGPT or commit it. On the free tier, the 20 requests/hour limit applies across runs and applications, not just one process.

Useful endpoints:
- `/v1/players/{username}/listings`: active listings, full contents in `details.contents` for listed Shulker Boxes.
- `/v1/players/{username}/orders`: the player's currently observed open orders and collected state.
- `/v1/auction/history?seller=...`: closed listings, **not guaranteed sales**.
- `/v1/orders/fills`: public order fills, product, paid, time, order id. Does not disclose the supplier.
- `/v1/players/{username}/history`: time series of publicly recorded stats.
- `/v1/items/{key}/history`: variant-specific market history.
- `/v1/economy/history`: public economy samples.
- `/v1/leaderboards/{board}/snapshots`: recorded ranking snapshots.

Without a key, the public web pages show limited market snapshots. An official DonutSMP key from `/api` is a different service; `quant/fetch_official.py` supports it separately, and it cannot obtain your private Ender Chest or all order matches.

## Why no client mod is installed automatically

The main Modrinth profile uses performance mods and voice chat. A second profile has non-standard mods. This project neither installs instrumentation nor controls the Minecraft client. Any client-side inventory exporter must be permitted by the specific server rules, and user-approved, before installation. The documented process above works without prohibited automation or a client session token.

Reference:
- https://api.donutstats.io/docs/reference/player-listings/
- https://api.donutstats.io/docs/reference/player-orders/
- https://api.donutstats.io/docs/
