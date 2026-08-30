# DonutSMP money-method research: source index (built 2026-08-29)

All paths relative to this scratchpad folder:
C:\Users\sepeh\AppData\Local\Temp\claude\C--Users-sepeh-AppData-Roaming-ModrinthApp\a55c25d7-7947-4549-bd84-8663350dc136\scratchpad

## Player context
- Player: the player (Java, DonutSMP, region "DonutFolia"). Balance ~$72M on 2026-08-29, 5.3K shards, 3d7h playtime.
- Default rank: 18 AH slots + 18 order slots. 3 homes.
- Proven trades for him: Ghast Tear lowball orders -> AH, torch/redstone-component crafting arbitrage, Dragon's Breath, trial chamber loot (Ominous Trial Keys sold at 440K), Flow armor trims.

## Local data (from his Minecraft logs)
- logs/all_chat.txt : all chat lines 2026-08-26 .. 08-29
- ah_events.csv : parsed AH events (listed / bought / sold_to / sold_multi / earned / balance). Actors: "You" = the player; flipper_D and flipper_M are other players whose AH activity is broadcast in his chat (team/friend feed). flipper_D is a high-volume flipper (buys diamond pickaxes ~110-115K, lists 150K; lists totems 110-111K in bulk; lists golden apples 20K; end crystals 38K; respawn anchors 29-30K; crying obsidian 9.9K; wind charges 10-59K).
- parse_chat.py : the parser.

## Server mechanics (verified from wiki sources)
- Three sell channels: /ah (player listings), /orders (buy orders, cheap bulk, open ~24h, 90h to claim), /sell (server fixed "base price"; /worth <item> shows it; /sellhistory).
- June 2-3 2026 update: /shop removed, sell multiplier removed, AFK shards removed, teams removed, crates removed. Default AH+orders slots 18 (was 25). Donut+ 45 slots ($5.49/mo), Donut++/+++ 90 slots.
- Shards: only from real-money store now (+ trickle "You earned 1 Shard for playing the server"). Shard shop (inside /ah or /orders GUI): Shard Pickaxe ("drill", breaks 3x3 = 9 blocks) 3,000 shards; Shard Axe 3,000; Shard Shovel 3,000; Shard Potion of Haste 6,000; spawners 1,500 each; maxed netherite gear 500-2,000. ALL shard tools self-destruct 24h after purchase; players resell them on /ah (drill seen at ~195M, sell axe ~24M for 18h left, per Bubsy 2026-08-28).
- Sell Axe: right-click/break a chest, barrel, trapped chest or hopper while holding it -> sells contents at /sell base price. Used to AFK-sell farm output (stand in water stream, toggle sneak/attack/use in vanilla controls, golden carrots offhand, no armor).
- Block limits: 20,000 per type per... (hoppers, dispensers, barrels); chests unlimited.
- Rules: no macros/scripts, no autoclicker, no freecam, no inventory mods, no crafting mods, no ESP/xray, max 5 accounts. Anti-cheat detects Freecam/Meteor via translation exploit.
- World border 225K; expansion to 30M expected within ~2 years (W1zox, July 2026). Wiki advice: sell finite valuables before expansion; farm heads now.
- AH tax: UNKNOWN (not found in any source). Needs an in-game check.
- /worth base prices known so far: spruce slab $12; dried kelp block $300; bone meal ~$30; wildflower/pink petal ~$10 each. Everything else UNKNOWN -> needs in-game /worth.

## Official API (api.donutsmp.net, Swagger at /v1/player/index.html, spec api/v1_doc.json)
- Auth: Authorization: Bearer <key>; key from in-game /api (revoke with /api revoke). 250 req/min.
- GET /v1/auction/list/{page} (body {search, sort: lowest_price|highest_price|recently_listed|last_listed}) -> result[{item{id,count,display_name,enchants,lore,contents}, price, seller{name,uuid}, time_left}]
- GET /v1/auction/transactions/{page} -> settled sales [{item, price, seller, unixMillisDateSold}]
- GET /v1/stats/{user}, /v1/lookup/{user}, /v1/leaderboards/{money|sell|shop|shards|playtime|kills|deaths|brokenblocks|placedblocks|mobskilled}/{page}
- NO orders endpoint. No enchant/potion detail in transactions (per SMP500 limitations).

## Third-party data (fetched)
- api/smp500_snapshot.tsv : SMP500 per-item AH settled-sale stats (1h/1d single+stack: avg price, volume, trades, min, max). IDs = Minecraft 1.21.11 item registry ids (mcdata/items.json). Source: smp500.org (Cloudflare-protected; pulled via browser). Snapshot 2026-08-29 ~13:50 local.
- api/jpsoftware_items.json : api.donutsmp.jpsoftware.nl/api/items, 1384 items, latest AH sale price+count (stack) and trading_volume. Fresh (used by the "Loot Liquidity" CurseForge mod).
- api/finance_items.json : donutsmp.finance/api/items, 472 items, FULL ORDER BOOK snapshot (orders[{price,amount,filled}], volume{instantSellPrice, quickSellPrice, realisticSellPrice, patientSellPrice, fillRate, liquidityScore, tiers}, ahMin, ahLast). WARNING: snapshot timestamps are 2026-06-25 (two months old). Use as structure/level indicator only.
- api/lootseller/*.json + api/lootseller_summary.json : lootseller.io/api/prices?item=<Display Name>&tf=1d -> daily candles of AH floor (cheapest listing) and orderCandles (top buy-order bid). Fresh for popular items (lastUpdated). Free public endpoint.
- api/v1_doc.json : official swagger.
- mcdata/items.json, mcdata/recipes.json : PrismarineJS minecraft-data 1.21.11 (ids match SMP500).

## Text sources
- fandom/*.json : DonutSMP Fandom wiki wikitext (Economy, Money, Money_Making_Tutorial, Shop (old shop prices), Shards, Shard_Pickaxe, Shard_Axe, Amethyst_Items, Spawner, Sell_Multiplier, Border_Expansion, Investment_items, Dried_Kelp_Farm, Block_Limits, Anti-Cheat, Ranks, June_2nd_update, DonutSMP_Memberships, Auction_House, Money_Making_Methods).
- wiki_repo/wiki/Wikitext/** : donutpedia (donutdb/donutsmp-wiki) sgw pages: Guide/Making money, General/Server rules, General/Spawner (spawner drop table + rate function), General/Donut+, Updates/Shop removal update, Commands/commands.toml.
- web/p1..p6.txt : ggwtb.com guides (cobblestone wall farm meta 40-60M/h; auto-crafter flips: bookshelves; bonemeal farm 9M/h vs chest autocrafter -26M loss; post-update farms: piglin bartering, wildflower, chest minecart to orders ~$900/item up to 60M/h; shulker/TNT/anvil/concrete flips; update notes: pearls crashed $1000->$80, shulker shells $850->$350).
- web/p9.txt : donutpedia shop removal update. web/p10.txt : lootseller.io page.
- videos/meta_all.json + videos/<id>.txt : YouTube transcripts (see meta for channel/date/views). Key: Bubsy L5oVTgYM4Zg (2026-08-28, spruce log -> slabs mega farm, "5B/day" gross), Bubsy jfmqSLQgAeg (2026-08-13, compact slab farm, /worth spruce slab = 12), Bubsy 8p26PQQR-00 (IKEA V1 kelp), DrSteve zJSfjgfi5Vo + _rCCyUBze1Q (order diamonds/leggings+books -> enchant -> AH, 23M/39min), KingOostin zJp6Fn4N5K4 (order KB1 netherite swords 4M -> AH 6M), SadBonker l2ZmBRfjPPQ (flower bunker V2, bones $90, bone meal $30, petals 60-70/bone meal, 50-60M/h gross), Melton oDqWI0oNPtE (750M/h chest farm claim), Letokosa 0BqJTW0Firw (300M/h), Voidrik ESm94gshRJY (doubling to 150M/h), Logix ahFclI9zgcg (4 no-farm methods, 10B), TierBlue qeuCBTQwsH4 (100M in 1h orders only), numen qK_7ByDtBbM (predicting the AH), Camel27 Z-V5gXSVTG0 (100M selling potions), iditity obXJdP_OEVA (shards), Smurfi mKvcLvXaPQE (selling bases 40M), SlaySlasher g5XTRRrMFvs, Jestica y0VK5q-ze78 (5 strange methods), iditity vc8btPwcCA8 (safest base, 10k skeleton spawners).
