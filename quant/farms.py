"""The farm catalog: every production system in the game, one ranking.

Categories: spawner farms, dark-room and natural mob farms, boss farms, breeding pens, plant farms,
tree farms, block generators, villager halls, raid and event farms, storm farms, and processing lines
(super smelters, autocraft lanes). About a hundred systems, each with inputs, outputs, and rates.

What is data and what is estimate:
  PRICES are data: fresh stack medians clamped by p25, singles medians for items that do not stack
  (5+ recorded sales). Same discipline as engine.py.
  RATES are estimates: conservative per-hour yields for a competent mid-size build of each design,
  labeled with a confidence grade. A "high" grade means the design is standardized (spawner boxes,
  observer cane farms); "low" means it varies a lot with build quality.
  ABSORPTION is data: profit per day is capped at 20 percent of each output's observed daily unit flow.
  A farm that makes 3,000 of something per hour into a market that absorbs 5,000 a day earns the
  capped number, not the fantasy number. The cap is what actually ranks these.

Hours per day by mode: afk 20 (runs while you do other things), active 3, storm 1.5 (thunderstorms),
villager halls use per-day trade caps directly (2 restocks x max uses, 20 heads assumed).

Crowd flags mark methods with major video coverage: expect the margin to decay.
All pre-tax.
"""
import csv, os

SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = {r["name"]: r for r in csv.DictReader(open(f"{SP}/quant/price_table.csv", encoding="utf-8"))}
HOURS = {"afk": 20, "active": 3, "storm": 1.5, "daily": 1}
CAPTURE = 0.20


def f(r, k):
    try:
        return float(r.get(k) or 0)
    except (ValueError, AttributeError):
        return 0.0


def price(name):
    r = P.get(name)
    if not r:
        return 0.0
    p25 = f(r, "tx_p25")
    if int(f(r, "stack") or 64) == 1 and f(r, "n_single") >= 5:
        v = f(r, "tx_single_med")
        return min(v, p25) if p25 else v
    if f(r, "n_stack") >= 3 and f(r, "tx_stack_med"):
        v = f(r, "tx_stack_med")
        return min(v, p25) if p25 else v
    if f(r, "ls_order_bid") > 0:
        return f(r, "ls_order_bid")      # a standing buy order is a real sale price (and uses no AH slot)
    if f(r, "n_single") >= 10:
        return min(f(r, "tx_single_med"), p25) if p25 else f(r, "tx_single_med")
    return 0.0


def vol(name):
    return f(P.get(name, {}), "ah_d_vol")


F = []


def farm(name, cat, mode, conf, out, inp=(), crowd="", note=""):
    """out/inp: ((item, units_per_hour), ...). mode 'daily' means units are already per day."""
    hrs = HOURS[mode]
    rev = cost = 0.0
    capped = False
    for item, per_hr in out:
        p = price(item)
        if p <= 0:
            continue
        units_day = per_hr * hrs
        cap = vol(item) * CAPTURE
        if cap and units_day > cap:
            units_day, capped = cap, True
        rev += p * units_day
    for item, per_hr in inp:
        c = price(item)
        cost += (c if c > 0 else 0) * per_hr * hrs
    if rev <= 0:
        return
    F.append(dict(farm=name, cat=cat, mode=mode, conf=conf, rev_day=round(rev), cost_day=round(cost),
                  profit_day=round(rev - cost), capped="yes" if capped else "", crowd=crowd, note=note))


# ---------- SPAWNER FARMS (spawner block found or bought, boxed) ----------
farm("zombie spawner (flesh, cleric fodder)", "spawner", "afk", "high", [("rotten_flesh", 1500), ("carrot", 8), ("potato", 8)])
farm("skeleton spawner (bones + arrows)", "spawner", "afk", "high", [("bone", 1200), ("arrow", 700)])
farm("spider spawner (string + eyes)", "spawner", "afk", "high", [("string", 700), ("spider_eye", 150)])
farm("cave spider spawner", "spawner", "afk", "high", [("string", 900), ("spider_eye", 200)])
farm("blaze spawner (rods)", "spawner", "afk", "high", [("blaze_rod", 800)])
farm("magma cube spawner (cream)", "spawner", "afk", "med", [("magma_cream", 500)])
farm("bogged spawner, trial chamber (bones)", "spawner", "afk", "med", [("bone", 900), ("arrow", 500)])
farm("breeze spawner, trial chamber (rods)", "spawner", "active", "med", [("breeze_rod", 120)],
     note="your current lane; rods also convert to maces via heavy cores")

# ---------- DARK ROOM / NATURAL MOB FARMS ----------
farm("general dark-room mob farm", "mobfarm", "afk", "high",
     [("gunpowder", 400), ("bone", 400), ("arrow", 250), ("string", 200), ("rotten_flesh", 350)])
farm("creeper-only farm (gunpowder)", "mobfarm", "afk", "high", [("gunpowder", 800)], crowd="video-common")
farm("enderman farm, end (pearls)", "mobfarm", "afk", "high", [("ender_pearl", 1800)], crowd="video-common")
farm("ghast farm (tears + gunpowder)", "mobfarm", "afk", "med", [("ghast_tear", 60), ("gunpowder", 250)])
farm("slime farm (slimeballs)", "mobfarm", "afk", "high", [("slime_ball", 1200)])
farm("witch farm (redstone, glowstone, sugar)", "mobfarm", "afk", "med",
     [("redstone", 350), ("glowstone_dust", 250), ("gunpowder", 200), ("sugar", 180), ("glass_bottle", 120), ("stick", 100)])
farm("guardian farm (prismarine + cod)", "mobfarm", "afk", "med",
     [("prismarine_shard", 3000), ("prismarine_crystals", 600), ("cod", 1200)], crowd="video-common")
farm("wither skeleton farm (skulls + coal)", "mobfarm", "active", "med",
     [("wither_skeleton_skull", 18), ("coal", 250), ("bone", 250)],
     note="skulls have no clean price row; value flows through stars, see wither farm")
farm("gold farm, nether roof (ingots)", "mobfarm", "afk", "high",
     [("gold_ingot", 700), ("gold_nugget", 900), ("rotten_flesh", 400)], crowd="raid video era; sell gold raw, never barter")
farm("hoglin farm (porkchops + leather)", "mobfarm", "afk", "med", [("porkchop", 900), ("leather", 250)],
     note="leather feeds the bundle printer")
farm("shulker farm, end (shells)", "mobfarm", "afk", "med", [("shulker_shell", 120)],
     note="shells are unwinding post-video, but boxes feed the recolor lane")
farm("phantom farm (membranes)", "mobfarm", "afk", "low", [("phantom_membrane", 150)])
farm("drowned farm (tridents, copper, shells)", "mobfarm", "afk", "med",
     [("trident", 1), ("copper_ingot", 50), ("nautilus_shell", 3), ("rotten_flesh", 600)],
     note="ONE trident an hour at 1.79M carries the whole farm")
farm("husk farm (flesh + sand)", "mobfarm", "afk", "low", [("rotten_flesh", 900)])

# ---------- BOSS ----------
farm("automated wither killer (nether stars)", "boss", "active", "med", [("nether_star", 4)],
     inp=[("wither_skeleton_skull", 12), ("soul_sand", 16)],
     note="skull input priced 0 (no clean row): pair with your own wither skeleton farm")
farm("dragon respawn cycle (breath + xp)", "boss", "active", "med", [("dragon_breath", 40)],
     inp=[("end_crystal", 5)])

# ---------- BREEDING PENS ----------
farm("chicken egg pen (eggs)", "breeding", "afk", "high", [("egg", 250)])
farm("chicken cooker (meat + feathers)", "breeding", "afk", "high", [("cooked_chicken", 200), ("feather", 200)])
farm("cow crusher (beef + leather)", "breeding", "afk", "high", [("beef", 250), ("leather", 200)],
     inp=[("wheat", 30)], note="sell beef RAW, it outsells cooked; leather feeds bundles")
farm("auto sheep shearing, white (wool)", "breeding", "afk", "high", [("white_wool", 450)])
farm("auto sheep shearing, dyed colors", "breeding", "afk", "high", [("red_wool", 220), ("black_wool", 220)])
farm("pig cooker (porkchops)", "breeding", "afk", "high", [("porkchop", 250)], inp=[("carrot", 30)],
     note="raw porkchop outsells cooked too")
farm("rabbit farm (hide + feet)", "breeding", "afk", "low", [("rabbit_hide", 80), ("rabbit_foot", 25)])
farm("turtle beach (scutes)", "breeding", "afk", "med", [("turtle_scute", 25)])
farm("bee farm (honey blocks)", "breeding", "afk", "med", [("honey_block", 12)])
farm("bee farm (honeycomb)", "breeding", "afk", "med", [("honeycomb", 30)])
farm("froglight farm (ochre)", "breeding", "afk", "med", [("ochre_froglight", 200)])
farm("sniffer ranch (seeds + torchflowers)", "breeding", "afk", "low",
     [("torchflower_seeds", 15), ("torchflower", 8)], note="young market, thin book, price it before scaling")
farm("squid farm (ink)", "breeding", "afk", "med", [("ink_sac", 350)])
farm("glow squid farm (glow ink)", "breeding", "afk", "med", [("glow_ink_sac", 350)])
farm("goat ram station (horns)", "breeding", "active", "low", [("goat_horn", 4)],
     note="horns at 200K as singles; rams charging a block drop them")

# ---------- PLANT FARMS ----------
farm("observer sugar cane farm", "plant", "afk", "high", [("sugar_cane", 900)],
     note="sell the CANE: cane at 1,250 outsells both sugar and paper")
farm("bamboo farm", "plant", "afk", "high", [("bamboo", 1800)])
farm("cactus farm", "plant", "afk", "high", [("cactus", 1200)])
farm("melon farm (blocks)", "plant", "afk", "high", [("melon", 280)])
farm("pumpkin farm", "plant", "afk", "high", [("pumpkin", 280)])
farm("villager wheat farm", "plant", "afk", "high", [("wheat", 280)])
farm("carrot farm", "plant", "afk", "high", [("carrot", 450)])
farm("potato farm", "plant", "afk", "high", [("potato", 450)])
farm("beetroot farm", "plant", "afk", "med", [("beetroot", 300)])
farm("nether wart farm (piston cycle)", "plant", "active", "high", [("nether_wart", 400)])
farm("kelp farm", "plant", "afk", "high", [("kelp", 1800)])
farm("sweet berry farm (fox picked)", "plant", "afk", "med", [("sweet_berries", 350)])
farm("glow berry farm", "plant", "afk", "med", [("glow_berries", 400)])
farm("cocoa farm", "plant", "afk", "med", [("cocoa_beans", 300)])
farm("chorus farm + smelt (popped)", "plant", "afk", "med", [("popped_chorus_fruit", 350)],
     inp=[("coal", 44)], note="popped at 1,406 p25 versus 234 raw; the smelt is the whole margin")
farm("moss bonemeal loop", "plant", "afk", "high", [("moss_block", 2500)],
     note="composter feeds itself; moss is cheap but the volume is huge")
farm("vine wall (shears)", "plant", "active", "low", [("vine", 200)])
farm("glow lichen spread (bone meal)", "plant", "active", "med", [("glow_lichen", 400)])
farm("sea pickle farm", "plant", "afk", "med", [("sea_pickle", 500)])

# ---------- TREE FARMS ----------
farm("oak tree farm + hand-strip", "tree", "active", "high", [("stripped_oak_log", 1200), ("apple", 15), ("stick", 200)])
farm("spruce mega farm + hand-strip", "tree", "active", "high", [("stripped_spruce_log", 1500)])
farm("dark oak farm + hand-strip", "tree", "active", "high", [("stripped_dark_oak_log", 1200)],
     note="312 raw becomes 6,016 stripped; the axe click is the farm")
farm("cherry farm (raw logs)", "tree", "active", "high", [("cherry_log", 1200)])
farm("mangrove propagule farm (raw logs)", "tree", "active", "med", [("mangrove_log", 900)])
farm("pale oak farm -> slab line", "tree", "active", "med", [("pale_oak_slab", 1600)],
     note="1 log = 4 planks = 8 slabs at 3,125 p25; rare-biome wood, young market")

# ---------- BLOCK GENERATORS ----------
farm("cobble generator + super smelter (stone)", "blockgen", "afk", "high", [("stone", 2500)], inp=[("coal", 313)])
farm("obsidian farm (portal cycling)", "blockgen", "active", "med", [("obsidian", 250)],
     crowd="unwinding post-video; sell into strength, do not stockpile")
farm("ice farm (silk touch)", "blockgen", "active", "high", [("ice", 1000)],
     note="sell plain ice; packing to packed or blue ice LOSES money")
farm("snow golem snowball line", "blockgen", "afk", "high", [("snowball", 1500)])
farm("amethyst geode array (shards)", "blockgen", "afk", "med", [("amethyst_shard", 250)])
farm("dripstone farm (pointed)", "blockgen", "afk", "med", [("pointed_dripstone", 150)])
farm("sculk catalyst room (sculk)", "blockgen", "afk", "med", [("sculk", 1500)],
     note="bolt on under any mob farm; XP you were wasting becomes 1,516 a block")
farm("resin farm (creaking heart)", "blockgen", "afk", "low", [("resin_clump", 120)])
farm("mud-to-clay dripstone converter", "blockgen", "afk", "med", [("clay", 280)], inp=[("dirt", 280)],
     note="dirt 570 in, clay 3,125 out, fully automatic; the sleeper build of this whole file")
farm("mud-to-clay + smelt line (bricks)", "blockgen", "afk", "med", [("brick", 1000)],
     inp=[("dirt", 250), ("coal", 125)],
     note="same converter, clay balls smelted: dirt to bricks is about 18x through the chain")

# ---------- VILLAGER HALLS (20 heads, 2 restocks/day, per-day caps) ----------
farm("mason hall x20 (bricks for emeralds)", "villager", "daily", "high", [("brick", 6400)],
     inp=[("emerald", 640)], note="numbers per day, not per hour: 32 trades x 10 bricks x 20 heads")
farm("cleric hall x20 cured (xp bottles)", "villager", "daily", "high", [("experience_bottle", 480)],
     inp=[("emerald", 480)], note="cured to 1 emerald per bottle; fills standing 7,500 buy orders, no AH slot")
farm("fletcher hall x20 (arrows)", "villager", "daily", "high", [("arrow", 7680)], inp=[("emerald", 480)])
farm("farmer hall x20 (golden carrots)", "villager", "daily", "high", [("golden_carrot", 1440)], inp=[("emerald", 1440)])
farm("armorer iron loop x20 (iron to emeralds)", "villager", "daily", "high", [("emerald", 480)],
     inp=[("iron_ingot", 1920)], note="cheapest emerald source at 2,708 each; feeds the other halls")
farm("librarian hall x20 (glass)", "villager", "daily", "high", [("glass", 1920)], inp=[("emerald", 480)])

# ---------- RAID / EVENT ----------
farm("raid farm (totems + emeralds)", "raid", "afk", "high",
     [("totem_of_undying", 12), ("emerald", 180)], crowd="THE video meta; totem bid fell 220K to 103K")
farm("outpost captain farm (ominous bottles)", "raid", "afk", "med", [("ominous_bottle", 18)],
     note="18,773 trades a day; feeds the ominous-trial and mace economy")
farm("trial chamber route (keys + rods)", "raid", "active", "med",
     [("trial_key", 4), ("breeze_rod", 100), ("ominous_bottle", 2)])
farm("ominous trial route (cores + keys)", "raid", "active", "med",
     [("heavy_core", 0.4), ("ominous_trial_key", 1.5), ("enchanted_golden_apple", 0.3)],
     note="your lane; cores at 3.9M make this the best active hourly in the game")
farm("end city raiding (shells + purpur)", "raid", "active", "med",
     [("shulker_shell", 30), ("purpur_block", 400)], crowd="border-bound loot, sell before expansion")
farm("disc farm (skeleton shoots creeper)", "raid", "afk", "med", [("music_disc_mellohi", 1.5)],
     note="EV 121K per disc across 12 discs; priced here via one mid disc as proxy")

# ---------- STORM (thunderstorm windows) ----------
farm("charged creeper head farm", "storm", "storm", "med",
     [("creeper_head", 5), ("zombie_head", 3), ("skeleton_skull", 3), ("piglin_head", 1)],
     note="lightning rod flips creepers, punch mobs into the blast; heads are 200-450K singles")
farm("thunder trident overdrive (drowned)", "storm", "storm", "low", [("trident", 2), ("copper_ingot", 60)])

# ---------- PROCESSING LINES ----------
farm("super smelter: sandstone -> smooth", "process", "afk", "high", [("smooth_sandstone", 2500)],
     inp=[("sandstone", 2500), ("coal", 313)])
farm("TNT autocraft (sand + gunpowder)", "process", "afk", "high", [("tnt", 800)],
     inp=[("sand", 3200), ("gunpowder", 4000)],
     note="871K units a day of flow, the deepest craft market on the server")
farm("firework autocraft", "process", "afk", "high", [("firework_rocket", 2400)],
     inp=[("gunpowder", 800), ("paper", 800)])
farm("fire charge craft", "process", "active", "high", [("fire_charge", 900)],
     inp=[("blaze_rod", 150), ("charcoal", 300), ("gunpowder", 300)])
farm("bundle line (string + leather)", "process", "active", "high", [("bundle", 120)],
     inp=[("string", 120), ("leather", 120)])
farm("concrete line, mixed colors", "process", "active", "high",
     [("black_concrete", 500), ("cyan_concrete", 250), ("red_concrete", 250)],
     inp=[("sand", 500), ("gravel", 500), ("black_dye", 63), ("cyan_dye", 31), ("red_dye", 31)])
farm("bone to bone meal uncraft", "process", "active", "high", [("bone_meal", 3000)], inp=[("bone", 1000)])
farm("iron to nuggets uncraft", "process", "active", "med", [("iron_nugget", 1800)], inp=[("iron_ingot", 200)],
     note="nuggets at 522 p25 versus ingot 677: 7x, thin book, test first")
farm("tool bench: flint and steel", "process", "active", "med", [("flint_and_steel", 60)],
     inp=[("iron_ingot", 60), ("flint", 60)],
     note="55K p25 on 14,523 trades a day; check enchant pollution with one test sale")
farm("tool bench: shears", "process", "active", "med", [("shears", 60)], inp=[("iron_ingot", 120)])
farm("stonecutter line: stone slabs", "process", "active", "high", [("stone_slab", 4000)], inp=[("stone", 2000)])
farm("strip station (buy dark oak, click, sell)", "process", "active", "high",
     [("stripped_dark_oak_log", 2500)], inp=[("dark_oak_log", 2500)])
farm("mace bench (core + rod)", "process", "active", "med", [("mace", 2)],
     inp=[("heavy_core", 2), ("breeze_rod", 2)])
farm("harness bench (craft + recolor)", "process", "active", "med",
     [("black_harness", 3), ("blue_harness", 1)],
     inp=[("leather", 12), ("glass", 8), ("white_wool", 4), ("black_dye", 3), ("blue_dye", 1)])

F.sort(key=lambda x: -x["profit_day"])
with open(f"{SP}/quant/farms.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(F[0].keys()))
    w.writeheader()
    w.writerows(F)

print(f"{len(F)} systems priced. Ranked by absorption-capped profit per day (pre-tax).\n")
print("%-46s %-9s %-6s %-4s %12s %12s %12s %-4s %s" % (
    "farm", "category", "mode", "conf", "revenue/d", "cost/d", "PROFIT/D", "cap", "crowd"))
for x in F:
    print("%-46s %-9s %-6s %-4s %12s %12s %12s %-4s %s" % (
        x["farm"][:46], x["cat"], x["mode"], x["conf"], f"{x['rev_day']:,}", f"{x['cost_day']:,}",
        f"{x['profit_day']:,}", x["capped"], x["crowd"][:30]))
print("\nBest per category:")
seen = set()
for x in F:
    if x["cat"] not in seen and x["profit_day"] > 0:
        seen.add(x["cat"])
        print("  %-10s %-46s %12s /day" % (x["cat"], x["farm"][:46], f"{x['profit_day']:,}"))
print("\n'cap' means the 20 percent absorption ceiling binds: build it smaller than the design allows.")
print("Full table with notes: quant/farms.csv")
