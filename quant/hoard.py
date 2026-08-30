"""Hoard scanner: what to stockpile, what to dump, and why.

Hoarding only pays when supply shrinks faster than demand. On DonutSMP supply is governed by three forces:

  RENEWABLE   farmable forever by anyone (bones, logs, potions, crops). Hoarding is a losing bet: any price
              rise is met with more farming within days. Only worth holding across a known demand spike.
  STRUCTURE   comes from world generation (trial chambers, temples, ocean ruins, bastions, end cities).
              Finite inside the current border, INFINITE the day the border expands. Hold now, dump before expansion.
  DEAD        the source was removed from the server and cannot come back (/shop items, crate items,
              the sell multiplier era). Supply can only fall as items are consumed or lost on death.
              This is the only category where time is on the holder's side.

Price position: where today's price sits inside its own observed range (0 = at its floor, 100 = at its ceiling),
from the LootSeller daily candles where they exist, otherwise from the last-15 sale spread (p25..p75).
Buy low in range with persistent demand; never buy high in range in a RENEWABLE item.
"""
import csv, glob, json, os

SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = {r["name"]: r for r in csv.DictReader(open(f"{SP}/quant/price_table.csv", encoding="utf-8"))}

# supply class per item family. Anything unlisted defaults to RENEWABLE (the pessimistic assumption).
STRUCTURE = {
    "elytra": "end city", "dragon_head": "end ship", "gilded_blackstone": "bastion",
    "netherite_upgrade_smithing_template": "bastion", "ancient_debris": "nether (mined)",
    "deepslate_emerald_ore": "mountain (silk touch)", "sponge": "ocean monument", "wet_sponge": "ocean monument",
    "echo_shard": "ancient city", "heart_of_the_sea": "buried treasure", "nautilus_shell": "drowned/fishing",
    "music_disc_pigstep": "bastion", "music_disc_relic": "trail ruins", "music_disc_creator": "trial chamber",
    "music_disc_precipice": "trial chamber", "heavy_core": "trial chamber (ominous vault)",
    "ominous_trial_key": "trial chamber (ominous vault)", "trial_key": "trial chamber vault",
    "flow_armor_trim_smithing_template": "trial chamber", "bolt_armor_trim_smithing_template": "trial chamber",
    "flow_pottery_sherd": "trial chamber", "guster_pottery_sherd": "trial chamber", "scrape_pottery_sherd": "trial chamber",
    "flow_banner_pattern": "trial chamber", "guster_banner_pattern": "trial chamber",
    "arms_up_pottery_sherd": "desert well/temple", "brewer_pottery_sherd": "desert temple",
    "skull_pottery_sherd": "desert temple", "danger_pottery_sherd": "desert temple",
    "heart_pottery_sherd": "desert temple/ocean ruin", "heartbreak_pottery_sherd": "ocean ruin",
    "howl_pottery_sherd": "trail ruins", "miner_pottery_sherd": "trail ruins", "shelter_pottery_sherd": "trail ruins",
    "friend_pottery_sherd": "trail ruins", "burn_pottery_sherd": "trail ruins", "plenty_pottery_sherd": "trail ruins",
    "explorer_pottery_sherd": "ocean ruin", "mourner_pottery_sherd": "trail ruins", "prize_pottery_sherd": "trail ruins",
    "sheaf_pottery_sherd": "trail ruins", "snort_pottery_sherd": "trail ruins", "angler_pottery_sherd": "ocean ruin",
    "archer_pottery_sherd": "ocean ruin", "blade_pottery_sherd": "ocean ruin",
    "breeze_rod": "trial chamber (breeze spawner)",
    "wither_skeleton_skull": "nether fortress mob", "skeleton_skull": "charged creeper", "creeper_head": "charged creeper",
    "zombie_head": "charged creeper", "piglin_head": "charged creeper", "dragon_egg": "the end (one per dragon)",
    "sentry_armor_trim_smithing_template": "pillager outpost", "vex_armor_trim_smithing_template": "woodland mansion",
    "ward_armor_trim_smithing_template": "ancient city", "silence_armor_trim_smithing_template": "ancient city",
    "wayfinder_armor_trim_smithing_template": "trail ruins", "raiser_armor_trim_smithing_template": "trail ruins",
    "host_armor_trim_smithing_template": "trail ruins", "shaper_armor_trim_smithing_template": "trail ruins",
    "eye_armor_trim_smithing_template": "stronghold", "spire_armor_trim_smithing_template": "end city",
    "tide_armor_trim_smithing_template": "ocean monument", "snout_armor_trim_smithing_template": "bastion",
    "rib_armor_trim_smithing_template": "nether fortress", "dune_armor_trim_smithing_template": "desert temple",
    "coast_armor_trim_smithing_template": "shipwreck", "wild_armor_trim_smithing_template": "jungle temple",
    "mojang_banner_pattern": "woodland mansion", "globe_banner_pattern": "n/a (crafted)",
    "enchanted_golden_apple": "structure chest only",
}
# sources the June 2026 update deleted: supply is now strictly falling
# Nothing currently qualifies: the June update deleted /shop and the crates, but every item they used to sell is
# still obtainable another way (totems from raid farms, ender chests and anchors from crafting). Kept as a category
# because a future removal would create one, and because "the shop sold it" is NOT by itself a scarcity thesis.
DEAD = {}

CONSUMED = {"end_crystal", "ominous_bottle", "ominous_trial_key", "trial_key", "experience_bottle", "firework_rocket",
            "ender_pearl", "tnt", "wind_charge", "splash_potion", "lingering_potion", "potion", "enchanted_golden_apple",
            "golden_apple", "totem_of_undying", "respawn_anchor", "end_crystal", "arrow", "spectral_arrow", "tipped_arrow"}


def f(r, k):
    try:
        return float(r.get(k) or 0)
    except (ValueError, AttributeError):
        return 0.0


ranges = {}
for path in glob.glob(f"{SP}/api/lootseller/*.json"):
    try:
        d = json.load(open(path, encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        continue
    c = d.get("candles") or []
    if len(c) < 4:
        continue
    lows = [x.get("l") or 0 for x in c if x.get("l")]
    highs = [x.get("h") or 0 for x in c if x.get("h")]
    if not lows or not highs:
        continue
    now = c[-1].get("c") or 0
    lo, hi = min(lows), max(highs)
    peak_recent = max(highs[-5:]) if len(highs) >= 5 else hi
    ranges[os.path.basename(path)[:-5]] = {
        "lo": lo, "hi": hi, "now": now, "peak5": peak_recent, "days": len(c),
        "pos": round(100 * (now - lo) / (hi - lo)) if hi > lo else 50,
        "off_peak": round(100 * (now - peak_recent) / peak_recent) if peak_recent else 0,
    }

rows = []
for name, r in P.items():
    med = f(r, "tx_med") or f(r, "tx_stack_med")
    if med <= 0:
        continue
    trades = f(r, "ah_d_trades")
    p25, p75 = f(r, "tx_p25"), f(r, "tx_p75")
    rg = ranges.get(name)
    if rg:
        pos, basis, lo, hi = rg["pos"], f"{rg['days']}d candles", rg["lo"], rg["hi"]
    elif p75 > p25 > 0:
        pos, basis, lo, hi = round(100 * (med - p25) / (p75 - p25)), "last-15 spread", p25, p75
    else:
        continue
    if name in DEAD:
        cls, src = "DEAD", DEAD[name]
    elif name in STRUCTURE:
        cls, src = "STRUCTURE", STRUCTURE[name]
    else:
        cls, src = "RENEWABLE", "farmable"
    rows.append(dict(item=name, cls=cls, source=src, price=round(med), lo=round(lo), hi=round(hi),
                     pos_in_range=max(0, min(100, pos)), consumed="yes" if name in CONSUMED else "",
                     trades_per_day=int(trades), units_per_day=int(f(r, "ah_d_vol")), basis=basis))

with open(f"{SP}/quant/hoard.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)


def show(title, rs, n=20, note=""):
    print(f"\n=== {title} ===")
    if note:
        print(note)
    print("%-38s %-10s %11s %11s %11s %5s %6s %9s  %s" % (
        "item", "class", "price", "range lo", "range hi", "pos", "used?", "trades/d", "source"))
    for x in rs[:n]:
        print("%-38s %-10s %11s %11s %11s %4d%% %6s %9s  %s" % (
            x["item"], x["cls"], f"{x['price']:,}", f"{x['lo']:,}", f"{x['hi']:,}", x["pos_in_range"],
            x["consumed"], f"{x['trades_per_day']:,}", x["source"][:30]))


liquid = [x for x in rows if x["trades_per_day"] >= 300]
show("A. HOARD: liquid, consumed on use, and currently in the bottom third of its own range",
     sorted([x for x in liquid if x["pos_in_range"] <= 33 and x["consumed"]], key=lambda x: x["pos_in_range"]),
     18, "These get burned, so supply leaves the market permanently. Cheap now relative to where they have traded.")
show("B. DUMP BEFORE THE BORDER EXPANSION: structure loot at the top of its range",
     sorted([x for x in rows if x["cls"] == "STRUCTURE" and x["pos_in_range"] >= 50 and x["trades_per_day"] >= 50],
            key=lambda x: -x["pos_in_range"]),
     18, "Expansion generates unlimited fresh structures. Every one of these is a sell, not a hold.")
show("C. STRUCTURE loot that is CHEAP right now (buy the dip, but still sell before expansion)",
     sorted([x for x in rows if x["cls"] == "STRUCTURE" and x["pos_in_range"] <= 30 and x["trades_per_day"] >= 30],
            key=lambda x: x["pos_in_range"]), 15)
show("D. ILLIQUID TRAPS: high headline price, almost nobody trades them",
     sorted([x for x in rows if x["trades_per_day"] < 15 and x["price"] >= 50_000], key=lambda x: -x["price"]),
     15, "A 500K median on 2 sales a day is not a price, it is an anecdote. Do not stockpile these.")
print(f"\n{len(rows)} items classified. Full table: quant/hoard.csv")
