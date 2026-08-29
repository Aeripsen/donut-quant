"""Write quant/quant_summary.md: the compact market read that the verification agents and the final report use."""
import csv, os, json, datetime
SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = {r["name"]: r for r in csv.DictReader(open(f"{SP}/quant/price_table.csv", encoding="utf-8"))}
A = list(csv.DictReader(open(f"{SP}/quant/short_orders_to_ah.csv", encoding="utf-8")))
B = list(csv.DictReader(open(f"{SP}/quant/short_crafts.csv", encoding="utf-8")))
C = list(csv.DictReader(open(f"{SP}/quant/conversion.csv", encoding="utf-8")))

def n(x, d=0):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "-"
    return f"{v:,.{d}f}"

KEY = ["spruce_log", "oak_log", "birch_log", "spruce_planks", "spruce_slab", "stick", "cobblestone", "stone", "deepslate", "cobbled_deepslate", "sand", "gravel",
       "dirt", "netherrack", "blackstone", "polished_blackstone", "basalt", "tuff", "bone", "bone_meal", "bone_block", "kelp", "dried_kelp", "dried_kelp_block",
       "iron_ingot", "iron_block", "gold_ingot", "gold_block", "copper_ingot", "diamond", "diamond_block", "emerald", "emerald_block", "redstone", "redstone_block",
       "lapis_lazuli", "lapis_block", "coal", "coal_block", "quartz", "amethyst_shard", "obsidian", "crying_obsidian", "glowstone", "glowstone_dust", "ender_pearl",
       "ender_eye", "ender_chest", "end_crystal", "respawn_anchor", "ghast_tear", "blaze_rod", "blaze_powder", "nether_wart", "magma_cream", "gunpowder", "tnt",
       "string", "leather", "paper", "book", "bookshelf", "glass", "sugar", "sugar_cane", "bamboo", "wheat", "bread", "apple", "golden_apple", "enchanted_golden_apple",
       "golden_carrot", "cooked_beef", "cooked_porkchop", "totem_of_undying", "experience_bottle", "shulker_shell", "shulker_box", "hopper", "chest", "dropper",
       "dispenser", "observer", "piston", "sticky_piston", "repeater", "comparator", "crafter", "rail", "powered_rail", "minecart", "chest_minecart", "hopper_minecart",
       "torch", "lantern", "campfire", "barrel", "smoker", "furnace", "anvil", "beacon", "nether_star", "wither_skeleton_skull", "skeleton_skull", "zombie_head",
       "creeper_head", "piglin_head", "dragon_head", "elytra", "netherite_ingot", "netherite_block", "netherite_scrap", "ancient_debris", "gilded_blackstone",
       "sponge", "wet_sponge", "heavy_core", "breeze_rod", "wind_charge", "mace", "trident", "trial_key", "ominous_trial_key", "ominous_bottle", "potion",
       "splash_potion", "lingering_potion", "glass_bottle", "dragon_breath", "fire_charge", "firework_rocket", "map", "filled_map", "white_bed", "black_bed",
       "white_wool", "black_wool", "pink_petals", "wildflowers", "water_bucket", "lava_bucket", "bucket", "arrow", "spectral_arrow", "tipped_arrow", "name_tag",
       "saddle", "netherite_pickaxe", "netherite_axe", "diamond_pickaxe", "diamond_sword", "enchanted_book", "netherite_upgrade_smithing_template", "deepslate_emerald_ore"]

out = []
out.append(f"# DonutSMP market read, generated {datetime.date.today()} from SMP500 (settled AH sales, last 15 per item + 24h aggregates), LootSeller (order bids), jpsoftware (last sale), player log\n")
out.append("Money unit: in-game $. 'stack med' = median unit price of the last 15 full-stack AH sales (best bulk price signal). 'p25' = 25th percentile of last 15 sales (conservative). '1d avg' is polluted by outliers; 'trades/d' and 'units/d' = settled AH liquidity in 24h. 'order bid' = top /orders buy price (LootSeller, fresh 2026-08-29) or the June-25 order snapshot marked (jun). AH tax is NOT subtracted (unknown).\n")
out.append("## Key item prices\n")
out.append("| item | stack | stack med | p25 | single med | 1d avg | trades/d | units/d | last sale (lot) | order bid | floor (LS) | his log buy/list |")
out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
for k in KEY:
    r = P.get(k)
    if not r:
        continue
    ob = r.get("ls_order_bid") or (f"{n(r.get('fin_order_realistic'))} (jun)" if r.get("fin_order_realistic") else "-")
    log = ""
    if r.get("log_bought_unit_med"): log += f"buy {n(r['log_bought_unit_med'])}x{r['log_bought_n']} "
    if r.get("log_listed_unit_med"): log += f"list {n(r['log_listed_unit_med'])}x{r['log_listed_n']}"
    out.append(f"| {k} | {r['stack']} | {n(r.get('tx_stack_med'))} | {n(r.get('tx_p25'))} | {n(r.get('tx_single_med'))} | {n(r.get('ah_d_price'))} | {n(r.get('ah_d_trades'))} | {n(r.get('ah_d_vol'))} | {n(r.get('jp_last_unit'))} (x{r.get('jp_last_count') or '-'}) | {ob if isinstance(ob, str) else n(ob)} | {n(r.get('ls_ah_floor'))} | {log.strip() or '-'} |")
out.append("\n## A. Orders -> AH flips (fresh order bids; conservative AH unit price; pre-tax)\n")
out.append("| item | stack | order bid | AH stack med | AH conservative | spread/unit | spread % | profit/stack | capital/stack | trades/d | units/d | day cap | flag |")
out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for x in A[:40]:
    out.append(f"| {x['item']} | {x['stack']} | {n(x['order_bid'])} | {n(x['ah_median'])} | {n(x['ah_conservative'])} | {n(x['spread_con'])} | {x['spread_con_pct']}% | {n(x['per_stack_profit_con'])} | {n(x['capital_per_stack'])} | {n(x['trades_per_day'])} | {n(x['units_per_day'])} | {n(x['day_cap_con'])} | {x['flag']} |")
out.append("\n## B. Craft arbitrage (non-enchantable outputs, >=300 AH trades/day, conservative AH price; input prices: o = order bid (jun = stale June snapshot), a = AH)\n")
out.append("| output | n | cost/craft | AH stack med | AH conservative | profit/craft | margin | trades/d | day cap | stale input? | inputs | flag |")
out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
for x in B[:70]:
    out.append(f"| {x['output']} | {x['out_n']} | {n(x['cost'])} | {n(x['ah_median'])} | {n(x['ah_conservative'])} | {n(x['profit_per_craft_con'])} | {x['margin_pct']}% | {n(x['trades_per_day'])} | {n(x['day_cap_con'])} | {x['input_price_stale']} | {x['inputs']} | {x['flag']} |")
out.append("\n## C. Conversion optimizer (what form of a raw input is worth most per input unit on AH; conservative)\n")
out.append("| raw | buy | src | chain | units/raw | value/raw (con) | profit/raw (con) | out trades/d |")
out.append("|---|---|---|---|---|---|---|---|")
seen = {}
for x in C:
    k = x["raw"]
    seen.setdefault(k, 0)
    if seen[k] >= 4: continue
    seen[k] += 1
    out.append(f"| {k} | {n(x['buy'])} | {x['buy_src']} | {x['chain']} | {x['units_per_raw']} | {n(x['value_con_per_raw'])} | {n(x['profit_con_per_raw'])} | {n(x['out_trades_day'])} |")
open(f"{SP}/quant/quant_summary.md", "w", encoding="utf-8").write("\n".join(out))
print("wrote quant_summary.md", len("\n".join(out)), "chars")
