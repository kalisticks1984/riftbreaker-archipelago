"""Generate Archipelago data for The Riftbreaker (open campaign, story campaign, survival).

Usage: python -I gen_data.py <extracted_game_data_dir> <project_dir>
       (extract with tools/extract_data.py)

Outputs:
  <project>/mod/scripts/research/research_tree_open_campaign.rt   } rewards stripped (except free starting nodes),
  <project>/mod/scripts/research/research_tree.rt                 } "hidden" flags cleared,
  <project>/mod/scripts/research/research_tree_survival.rt        } story-critical "locked" flags kept
  <project>/mod/logic/campaigns/open/open_campaign_main.logic     open campaign's automatic biome unlock chain cut
  <project>/mod/scripts/difficulty/difficulties.difficulty        near-instant research
  <project>/mod/gui/archipelago_localizations.csv                 default "[AP]" labels (the client writes per seed)
  <project>/mod/lua/archipelago/ap_data.lua                       id tables for the mod
  <project>/apworld/riftbreaker/data.json                         everything the apworld needs

IDs (keyed by name, so the same research shares one id across modes; open-campaign ids match v0.3):
  research location            first of: open node index, 10000 + story index, 20000 + survival index
  research item                same rule over the item's display name
  biome arrival / biome item   1000 + i / 1100 + i       filler 1200 + i       progressive group 2000 + i
  build check 30000 + i        story mission check 31000 + i      survival time check 32000 + minutes
(all added to BASE_ID)
"""
import glob
import json
import os
import re
import sys

BASE_ID = 7_720_000
PREFIX = "gui/menu/research/name/"
DESC_PREFIX = "gui/menu/research/description/"
BIOMES = ["jungle", "desert", "acid", "magma", "ice", "metallic", "caverns", "swamp"]  # jungle = open/story start
SURVIVAL_MAPS = ["acid", "caverns", "desert", "ice", "jungle", "magma", "metallic", "swamp"]
FILLERS = [("Carbonium Cache", "carbonium", 1500), ("Ironium Cache", "steel", 1500),
           ("Cobalt Cache", "cobalt", 400)]
RESEARCH_TIME_FACTOR = "0.01"
LEVEL_RE = re.compile(r"^(.*?)_lvl_?(\d+)$")
DISPLAY_LEVEL_RE = re.compile(r"\s*[-–—]?\s*(lvl\.?|level)\s*\d+\s*$", re.I)
BIOME_CHAIN_EDGE = re.compile(r'^[ \t]*logic_or_2 "logic_wait_1"[ \t]*\r?\n', re.M)
LOC_HEADER = ";ENGLISH;POLISH;RUSSIAN;FRENCH;GERMAN;SPANISH;BRASILIAN;CHINESE_SP;JAPANESE;KOREAN"

# Story-critical nodes the story campaign enables itself: they keep "locked" in the story tree.
STORY_LOCKED = {
    "resource_handling_uranium", "resource_handling_titanium", "resource_handling_palladium",
    "environmental_shielding_sun", "environmental_shielding_acid", "environmental_shielding_radiation",
    "floor_acid", "floor_desert", "cryo_technology", "quantum_cortex_laboratory", "towers_morphium_lvl1",
}

MODES = {
    # mode: (tree file, location id offset, nodes that keep their "locked" flag)
    "open": ("research_tree_open_campaign.rt", 0, set()),
    "story": ("research_tree.rt", 10000, STORY_LOCKED),
    "survival": ("research_tree_survival.rt", 20000, None),   # None = keep every flag (survival has 1 lock)
}

# Build milestones: (key, location name, blueprints; any of them built counts). Included in a mode only when the
# mode's tree awards the first blueprint (or it is part of the starting kit).
BUILDS = [
    ("hq3", "Upgrade the Headquarters to Level 3", ["buildings/main/headquarters_lvl_%d" % i for i in range(3, 8)]),
    ("hq4", "Upgrade the Headquarters to Level 4", ["buildings/main/headquarters_lvl_%d" % i for i in range(4, 8)]),
    ("hq5", "Upgrade the Headquarters to Level 5", ["buildings/main/headquarters_lvl_%d" % i for i in range(5, 8)]),
    ("hq6", "Upgrade the Headquarters to Level 6", ["buildings/main/headquarters_lvl_%d" % i for i in range(6, 8)]),
    ("hq7", "Upgrade the Headquarters to Level 7", ["buildings/main/headquarters_lvl_7"]),
    ("laboratory", "Build a Laboratory", ["buildings/main/laboratory"] +
     ["buildings/main/laboratory_lvl_%d" % i for i in range(2, 6)]),
    ("planet_scanner", "Build a Planetary Scanner", ["buildings/main/planet_scanner"]),
    ("rare_element_mine", "Build a Rare Element Mine", ["buildings/resources/rare_element_mine",
                                                         "buildings/resources/rare_element_mine_lvl_2",
                                                         "buildings/resources/rare_element_mine_lvl_3"]),
    ("qcl", "Build the Quantum Cortex Laboratory", ["buildings/megastructures/quantum_cortex_laboratory"] +
     ["buildings/megastructures/quantum_cortex_laboratory_lvl_%d" % i for i in range(2, 6)]),
    ("ghl", "Build the Gravitational Hyper Lens", None),
    ("hydroponic", "Build the Hydroponic Lab", None),
    ("nanobot", "Build the Nanobot Center", None),
    ("arcology", "Build the Arcology Workshop", ["buildings/megastructures/arcology_workshop"]),
    ("rift_station", "Build the Prime Rift Station", ["buildings/megastructures/mega_rift_station"]),
]
# Megastructures whose blueprint names are read from their research node's awards.
BUILD_NODES = {"ghl": "gravitational_hyper_lens", "hydroponic": "hydroponic_lab", "nanobot": "nanobot_center"}

# Base story missions (ids as the game uses them, see lua/utils/campaign_patcher.lua).
STORY_MISSIONS = [
    ("desert_scouting", "Complete Desert Scouting"),
    ("desert_find_samples", "Complete Desert: Find Samples"),
    ("desert_find_new_resource", "Complete Desert: New Resource"),
    ("desert_find_rare_resource", "Complete Desert: Rare Resource"),
    ("Desert Resource Outpost", "Complete Desert Resource Outpost"),
    ("acid_scouting", "Complete Acid Fields Scouting"),
    ("acid_find_samples", "Complete Acid Fields: Find Samples"),
    ("acid_find_new_resource", "Complete Acid Fields: New Resource"),
    ("Acid Find Rare Resource", "Complete Acid Fields: Rare Resource"),
    ("acid_resource_outpost", "Complete Acid Fields Resource Outpost"),
    ("magma_scouting", "Complete Magma Scouting"),
    ("magma_find_samples", "Complete Magma: Find Samples"),
    ("magma_find_new_resource", "Complete Magma: New Resource"),
    ("magma_find_rare_resource", "Complete Magma: Rare Resource"),
    ("magma_resource_outpost", "Complete Magma Resource Outpost"),
    ("jungle_find_rare_resource", "Complete Jungle: Rare Resource"),
]
SURVIVAL_MAX_MINUTES = 90


def scan(text):
    for m in re.finditer(r'//[^\n]*|"[^"]*"|[{}]|[^\s{}"]+', text):
        if not m.group().startswith("//"):
            yield m.start(), m.end(), m.group()


def match_brace(toks, i):
    depth = 0
    for j in range(i, len(toks)):
        if toks[j][2] == "{":
            depth += 1
        elif toks[j][2] == "}":
            depth -= 1
            if depth == 0:
                return j
    raise ValueError("unbalanced braces")


def unq(s):
    return s[1:-1] if s.startswith('"') else s


def values(toks, a, b, key):
    return [unq(toks[k + 1][2]) for k in range(a, b) if toks[k][2] == key and toks[k + 1][2].startswith('"')]


def clean(s):
    return " ".join(s.split())


def load_strings(data_dir):
    names = {}
    for path in sorted(glob.glob(os.path.join(data_dir, "gui", "*_localizations.csv"))):
        with open(path, encoding="utf-8", errors="replace") as fh:   # unbalanced quotes: split manually
            for line in fh:
                row = line.rstrip("\r\n").split(";")
                if len(row) > 1 and row[0].startswith((PREFIX, DESC_PREFIX)) and row[1]:
                    names.setdefault(row[0], row[1].strip())
    return names


def parse_scripts(toks, a, b):
    out = []
    k = a
    while k < b:
        if toks[k][2] == "ResearchScript" and toks[k + 1][2] == "{":
            e = match_brace(toks, k + 1)
            name = (values(toks, k, e, "script_name") or [""])[0]
            params = {}
            j = k
            while j < e:
                if toks[j][2] in ("StringData", "IntData", "FloatData") and toks[j + 1][2] == "{":
                    je = match_brace(toks, j + 1)
                    kk, vv = values(toks, j, je, "key"), values(toks, j, je, "value")
                    if kk and vv:
                        params[kk[0]] = vv[0]
                    j = je
                j += 1
            out.append({"script": name.rsplit("/", 1)[-1][:-4], "requirement": "/requirements/" in name,
                        "params": params})
            k = e
        k += 1
    return out


def parse_tree(path, strings, keep_locked):
    """Returns (nodes, edited_text). Rewards of non-free nodes are stripped; flags edited per keep_locked."""
    text = open(path, encoding="utf-8", newline="").read()
    toks = list(scan(text))
    edits, nodes, category = [], [], None
    i = 0
    while i < len(toks):
        tok = toks[i][2]
        if tok == "category" and toks[i + 1][2].startswith('"'):
            category = unq(toks[i + 1][2]).rsplit("/", 1)[-1]
        if tok == "ResearchNode" and toks[i + 1][2] == "{":
            end = match_brace(toks, i + 1)
            node = {"category": category.replace("category_", ""), "requires": [], "costs": {}, "awards": [],
                    "scripts": [], "flags": []}
            award_edit = flags_tok = None
            k = i + 2
            while k < end:
                t, nxt = toks[k][2], toks[k + 1][2]
                if t == "research_name" and nxt.startswith('"') and "name" not in node:
                    node["name"] = unq(nxt)[len(PREFIX):]
                elif t == "research_flags":
                    node["flags"] = unq(nxt).split("|") if nxt.startswith('"') else []
                    flags_tok = k if nxt.startswith('"') else None
                elif t in ("requirements", "research_costs", "research_awards", "research_scripts") and nxt == "{":
                    be = match_brace(toks, k + 1)
                    if t == "requirements":
                        node["requires"] = [r[len(PREFIX):] for r in values(toks, k + 1, be, "research_name")]
                    elif t == "research_costs":
                        node["costs"] = {r: int(c) for r, c in zip(values(toks, k + 1, be, "resource"),
                                                                   values(toks, k + 1, be, "count"))}
                    elif t == "research_awards":
                        node["awards"] = [{"blueprint": b, "hidden": v != "1"} for b, v in
                                          zip(values(toks, k + 1, be, "blueprint"),
                                              values(toks, k + 1, be, "is_visible"))]
                        award_edit = (toks[k][0], toks[be][1], "research_awards")
                    else:
                        node["scripts"] = parse_scripts(toks, k + 1, be)
                    k = be
                k += 1
            node["starting"] = not any(node["costs"].values())   # free nodes auto-complete: keep vanilla
            if award_edit and not node["starting"]:
                edits.append(award_edit)
            if flags_tok is not None and keep_locked is not None:
                keep = [f for f in node["flags"] if f == "locked" and node["name"].strip() in keep_locked]
                new = 'research_flags "%s"' % "|".join(keep) if keep else "research_flags"
                edits.append((toks[flags_tok][0], toks[flags_tok + 1][1], new))
                node["locked"] = bool(keep)
            else:
                node["locked"] = "locked" in node["flags"]
            node["display"] = clean(strings.get(PREFIX + node["name"], node["name"].replace("_", " ").title()))
            node["description"] = strings.get(DESC_PREFIX + node["name"], "")
            nodes.append(node)
            i = end
        i += 1
    out, last = [], 0
    for s, e, rep in sorted(edits):
        out += [text[last:s], rep]
        last = e
    out.append(text[last:])
    return nodes, "".join(out)


def build_groups(nodes):
    by_name = {n["name"]: n for n in nodes}
    fams = {}
    for n in nodes:
        m = LEVEL_RE.match(n["name"].strip())
        if m:
            fams.setdefault(m.group(1), []).append((int(m.group(2)), n["name"]))
    groups = []
    for base, members in sorted(fams.items()):
        if base in by_name:
            members.append((0, base))
        members = [name for _, name in sorted(members) if not by_name[name]["starting"]]
        if len(members) < 2:
            continue
        first = by_name[members[0]]
        display = clean(DISPLAY_LEVEL_RE.sub("", first["display"])) or first["display"]
        groups.append({"key": base, "display": "Progressive " + display, "members": members})
    return groups


def survival_maps(data_dir):
    out = {}
    for b in SURVIVAL_MAPS:
        t = open(os.path.join(data_dir, "missions", "survival", b + ".mission"), encoding="utf-8",
                 errors="replace").read()
        i = t.find("random_resources")
        veins = sorted(set(re.findall(r'resource\s+"([a-z_]+)"', t[i:]))) if i >= 0 else []
        out[b] = {"veins": veins,
                  "shards": sorted(set(re.findall(r'shard_([a-z_]+)_item', t))),
                  "creatures": sorted(set(re.findall(r'creature_species\s+"([a-z_0-9]+)"', t)))}
    return out


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def main(data_dir, project):
    strings = load_strings(data_dir)
    modes = {}
    for mode, (tree, offset, keep_locked) in MODES.items():
        nodes, edited = parse_tree(os.path.join(data_dir, "scripts", "research", tree), strings, keep_locked)
        write(os.path.join(project, "mod", "scripts", "research", tree), edited)
        groups = build_groups(nodes)
        for idx, n in enumerate(nodes):
            n["index_id"] = BASE_ID + offset + idx
        modes[mode] = {"nodes": nodes, "groups": groups}

    # --- name-keyed ids (open first, so open-campaign ids are unchanged)
    location_ids, item_ids, group_ids = {}, {}, {}
    for mode in MODES:
        for n in modes[mode]["nodes"]:
            if n["starting"]:
                continue
            location_ids.setdefault("Research: " + n["display"], n["index_id"])
        member_of = {m: g for g in modes[mode]["groups"] for m in g["members"]}
        for n in modes[mode]["nodes"]:
            if n["starting"]:
                continue
            g = member_of.get(n["name"])
            if g:
                n["group"], n["level"] = g["display"], g["members"].index(n["name"]) + 1
            else:
                item_ids.setdefault(n["display"], n["index_id"])
        for g in modes[mode]["groups"]:
            group_ids.setdefault(g["display"], None)
    for i, name in enumerate(group_ids):
        group_ids[name] = BASE_ID + 2000 + i
    for mode in MODES:
        for n in modes[mode]["nodes"]:
            if not n["starting"]:
                n["location_id"] = location_ids["Research: " + n["display"]]
                n["item_id"] = group_ids[n["group"]] if "group" in n else item_ids[n["display"]]

    # --- build checks (per mode availability from the tree's awards)
    builds = []
    for i, (key, name, bps) in enumerate(BUILDS):
        entry = {"key": key, "name": name, "id": BASE_ID + 30000 + i, "modes": {}}
        for mode in MODES:
            nodes = modes[mode]["nodes"]
            bp_node = {a["blueprint"]: n for n in nodes for a in n["awards"]}
            blueprints = bps
            if blueprints is None:
                src = next((n for n in nodes if n["name"] == BUILD_NODES[key]), None)
                if not src:
                    continue
                stem = next((a["blueprint"] for a in src["awards"] if a["blueprint"].startswith("buildings/")), None)
                if not stem:
                    continue
                blueprints = [stem] + [stem + "_lvl_%d" % j for j in range(2, 6)]
            node = bp_node.get(blueprints[0])
            if node is None:
                continue
            entry["modes"][mode] = {"blueprints": blueprints, "node": node["name"]}
        builds.append(entry)

    missions = [{"mission": mid, "name": name, "id": BASE_ID + 31000 + i} for i, (mid, name) in enumerate(STORY_MISSIONS)]

    # --- campaign graph with the open campaign's automatic biome unlock chain disconnected
    ltext = open(os.path.join(data_dir, "logic", "campaigns", "open", "open_campaign_main.logic"),
                 encoding="utf-8", newline="").read()
    ltext, n = BIOME_CHAIN_EDGE.subn("", ltext)
    assert n == 1, f"biome chain edge found {n} times"
    write(os.path.join(project, "mod", "logic", "campaigns", "open", "open_campaign_main.logic"), ltext)

    # --- near-instant research on every difficulty (material costs unchanged)
    dtext = open(os.path.join(data_dir, "scripts", "difficulty", "difficulties.difficulty"),
                 encoding="utf-8", newline="").read()
    dtext = re.sub(r'^[ \t]*reserach_science_factor[^\n]*\n', "", dtext, flags=re.M)
    dtext, nd = re.subn(r'(DifficultyDef\s*\{[ \t]*\r?\n)',
                        r'\1' + f'\treserach_science_factor\t"{RESEARCH_TIME_FACTOR}"\n', dtext)
    assert nd >= 5, f"only {nd} difficulties found"
    write(os.path.join(project, "mod", "scripts", "difficulty", "difficulties.difficulty"), dtext)

    # --- default "[AP]" labels for every randomized research in any mode (the client overwrites per seed)
    rows, seen = [LOC_HEADER], set()
    for mode in MODES:
        for n in modes[mode]["nodes"]:
            if n["starting"] or n["name"] in seen:
                continue
            seen.add(n["name"])
            rows.append(f"{PREFIX}{n['name']};{n['display']} [AP];;;;;;;;;")
            desc = "Archipelago check: completing this research sends an item to the multiworld. " + n["description"]
            rows.append(f"{DESC_PREFIX}{n['name']};{desc.replace(';', ',')};;;;;;;;;")
    write(os.path.join(project, "mod", "gui", "archipelago_localizations.csv"), "\r\n".join(rows) + "\r\n")

    # --- apworld data
    data = {
        "base_id": BASE_ID,
        "biomes": BIOMES,
        "survival_maps": survival_maps(data_dir),
        "fillers": [{"name": f[0], "resource": f[1], "amount": f[2], "id": BASE_ID + 1200 + i}
                    for i, f in enumerate(FILLERS)],
        "groups": group_ids,
        "builds": builds,
        "missions": missions,
        "survival_time_base": BASE_ID + 32000,
        "survival_max_minutes": SURVIVAL_MAX_MINUTES,
        "modes": {mode: {"groups": modes[mode]["groups"],
                         "nodes": [{k: v for k, v in n.items() if k not in ("description", "index_id")}
                                   for n in modes[mode]["nodes"]]} for mode in MODES},
    }
    write(os.path.join(project, "apworld", "riftbreaker", "data.json"), json.dumps(data, indent=1, ensure_ascii=False))

    # --- mod data
    def ls(s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def awards(n):
        return "{ " + ", ".join("{ %s, %s }" % (ls(a["blueprint"]), "true" if a["hidden"] else "false")
                                for a in n["awards"]) + " }"

    lua = ["-- GENERATED by tools/gen_data.py. Do not edit.", "AP_DATA = {", f"  base_id = {BASE_ID},", "  modes = {"]
    for mode in MODES:
        nodes = modes[mode]["nodes"]
        by_name = {n["name"]: n for n in nodes}
        rnd = [n for n in nodes if not n["starting"]]
        lua.append(f"    {mode} = {{")
        lua.append("      locations = {")
        lua += [f"        [{ls(PREFIX + n['name'])}] = {n['location_id']}," for n in rnd]
        lua.append("      },")
        lua.append("      awards = {")
        lua += [f"        [{n['item_id']}] = {awards(n)}," for n in rnd if "group" not in n]
        lua.append("      },")
        lua.append("      progressive = {")
        for g in modes[mode]["groups"]:
            lua.append(f"        [{group_ids[g['display']]}] = {{ " +
                       ", ".join(awards(by_name[m]) for m in g["members"]) + " },")
        lua.append("      },")
        lua.append("      builds = {")
        for b in builds:
            if mode in b["modes"]:
                bl = ", ".join(ls(x) for x in b["modes"][mode]["blueprints"])
                lua.append(f"        {{ id = {b['id']}, blueprints = {{ {bl} }} }},")
        lua.append("      },")
        lua.append("    },")
    lua.append("  },")
    lua.append("  missions = {")
    lua += [f"    {{ id = {m['id']}, mission = {ls(m['mission'])} }}," for m in missions]
    lua.append("  },")
    lua.append("  biomes = {  -- item id -> biome name (open campaign)")
    lua += [f"    [{BASE_ID + 1100 + i}] = {ls(b)}," for i, b in enumerate(BIOMES) if b != "jungle"]
    lua.append("  },")
    lua.append("  fillers = {  -- item id -> { resource, amount }")
    lua += [f"    [{d['id']}] = {{ {ls(d['resource'])}, {d['amount']} }}," for d in data["fillers"]]
    lua += ["  },", "}", ""]
    write(os.path.join(project, "mod", "lua", "archipelago", "ap_data.lua"), "\n".join(lua))

    for mode in MODES:
        nodes = modes[mode]["nodes"]
        rnd = [n for n in nodes if not n["starting"]]
        print(f"{mode:9} {len(nodes)} nodes, {len(rnd)} randomized, {len(modes[mode]['groups'])} progressive groups, "
              f"{sum(1 for b in builds if mode in b['modes'])} build checks")
    print(f"{len(location_ids)} research locations, {len(item_ids)} research items, {len(group_ids)} progressive items")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
