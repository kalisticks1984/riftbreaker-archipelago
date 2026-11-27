"""Generate Archipelago data for The Riftbreaker OPEN campaign.

Usage: python -I gen_open.py <extracted_game_data_dir> <project_dir>

Inputs (from the game's packs, extracted):
  scripts/research/research_tree_open_campaign.rt
  logic/campaigns/open/open_campaign_main.logic
  gui/*_localizations.csv

Outputs:
  <project>/mod/scripts/research/research_tree_open_campaign.rt   rewards stripped (except free starting nodes)
  <project>/mod/logic/campaigns/open/open_campaign_main.logic     automatic biome unlock chain disconnected
  <project>/mod/gui/archipelago_localizations.csv                 "[AP]" names/descriptions for randomized research
  <project>/mod/lua/archipelago/ap_data.lua                       id tables for the mod
  <project>/apworld/riftbreaker/data.json                         node data for the apworld

IDs (stable for a given game version):
  research location id      = BASE_ID + node index in the tree file
  research item id          = same as its location id (non-progressive nodes)
  progressive item id       = BASE_ID + 2000 + group index
  biome item id             = BASE_ID + 1100 + biome index
  filler item id            = BASE_ID + 1200 + filler index
"""
import glob
import json
import os
import re
import sys

BASE_ID = 7_720_000
PREFIX = "gui/menu/research/name/"
DESC_PREFIX = "gui/menu/research/description/"
BIOMES = ["jungle", "desert", "acid", "magma", "ice", "metallic", "caverns", "swamp"]  # jungle = start
FILLERS = [("Carbonium Cache", "carbonium", 1500), ("Ironium Cache", "steel", 1500)]
RESEARCH_TIME_FACTOR = "0.01"
LEVEL_RE = re.compile(r"^(.*?)_lvl_?(\d+)$")
DISPLAY_LEVEL_RE = re.compile(r"\s*[-–—]?\s*(lvl\.?|level)\s*\d+\s*$", re.I)

# The single edge that starts the automatic "unlock every biome" chain after a Planetary Scanner is built.
BIOME_CHAIN_EDGE = re.compile(r'^[ \t]*logic_or_2 "logic_wait_1"[ \t]*\r?\n', re.M)
LOC_HEADER = ";ENGLISH;POLISH;RUSSIAN;FRENCH;GERMAN;SPANISH;BRASILIAN;CHINESE_SP;JAPANESE;KOREAN"


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


def load_strings(data_dir):
    names = {}
    for path in sorted(glob.glob(os.path.join(data_dir, "gui", "*_localizations.csv"))):
        with open(path, encoding="utf-8", errors="replace") as fh:   # unbalanced quotes: split manually
            for line in fh:
                row = line.rstrip("\r\n").split(";")
                if len(row) > 1 and row[0].startswith(("gui/menu/research/name/", DESC_PREFIX)) and row[1]:
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


def clean(s):
    return " ".join(s.split())


def build_groups(nodes):
    """Progressive groups: <base>_lvl<N> families (plus a bare <base> node as level 0), randomized members only."""
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
        display = clean(DISPLAY_LEVEL_RE.sub("", first["display"])) or clean(first["display"])
        groups.append({"key": base, "display": "Progressive " + display, "members": members,
                       "id": BASE_ID + 2000 + len(groups)})
    return groups


def main(data_dir, project):
    src = os.path.join(data_dir, "scripts", "research", "research_tree_open_campaign.rt")
    text = open(src, encoding="utf-8", newline="").read()
    toks = list(scan(text))
    strings = load_strings(data_dir)

    edits, nodes, category = [], [], None
    i = 0
    while i < len(toks):
        tok = toks[i][2]
        if tok == "category" and toks[i + 1][2].startswith('"'):
            category = unq(toks[i + 1][2]).rsplit("/", 1)[-1]
        if tok == "ResearchNode" and toks[i + 1][2] == "{":
            end = match_brace(toks, i + 1)
            node = {"category": category.replace("category_", ""), "requires": [], "costs": {}, "awards": [],
                    "scripts": []}
            award_edit = None
            k = i + 2
            while k < end:
                t, nxt = toks[k][2], toks[k + 1][2]
                if t == "research_name" and nxt.startswith('"') and "name" not in node:
                    node["name"] = unq(nxt)[len(PREFIX):]
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
            node["display"] = clean(strings.get(PREFIX + node["name"], node["name"].replace("_", " ").title()))
            node["description"] = strings.get(DESC_PREFIX + node["name"], "")
            node["id"] = BASE_ID + len(nodes)
            nodes.append(node)
            i = end
        i += 1

    groups = build_groups(nodes)
    for g in groups:
        for idx, name in enumerate(g["members"]):
            n = next(x for x in nodes if x["name"] == name)
            n["group"], n["level"] = g["key"], idx + 1
    randomized = [n for n in nodes if not n["starting"]]

    # --- stripped research tree
    out, last = [], 0
    for s, e, rep in sorted(edits):
        out += [text[last:s], rep]
        last = e
    out.append(text[last:])
    write(os.path.join(project, "mod", "scripts", "research", "research_tree_open_campaign.rt"), "".join(out))

    # --- campaign graph with the automatic biome unlock chain disconnected
    ltext = open(os.path.join(data_dir, "logic", "campaigns", "open", "open_campaign_main.logic"),
                 encoding="utf-8", newline="").read()
    ltext, n = BIOME_CHAIN_EDGE.subn("", ltext)
    assert n == 1, f"biome chain edge found {n} times"
    write(os.path.join(project, "mod", "logic", "campaigns", "open", "open_campaign_main.logic"), ltext)

    # --- "[AP]" research names and descriptions (English column)
    rows = [LOC_HEADER]
    for n in randomized:
        rows.append(f"{PREFIX}{n['name']};{n['display']} [AP];;;;;;;;;")
        desc = "Archipelago check: completing this research sends an item to the multiworld. " + n["description"]
        rows.append(f"{DESC_PREFIX}{n['name']};{desc.replace(';', ',')};;;;;;;;;")
    write(os.path.join(project, "mod", "gui", "archipelago_localizations.csv"), "\r\n".join(rows) + "\r\n")

    # --- near-instant research: DifficultyDef "reserach_science_factor" ("Research time factor" in the custom
    # difficulty menu, default 1) on every difficulty. Material costs are unchanged, so logic still holds.
    dtext = open(os.path.join(data_dir, "scripts", "difficulty", "difficulties.difficulty"),
                 encoding="utf-8", newline="").read()
    dtext = re.sub(r'^[ \t]*reserach_science_factor[^\n]*\n', "", dtext, flags=re.M)
    dtext, nd = re.subn(r'(DifficultyDef\s*\{[ \t]*\r?\n)', r'\1' + f'\treserach_science_factor\t"{RESEARCH_TIME_FACTOR}"\n',
                        dtext)
    assert nd >= 5, f"only {nd} difficulties found"
    write(os.path.join(project, "mod", "scripts", "difficulty", "difficulties.difficulty"), dtext)

    # --- apworld data
    data = {
        "base_id": BASE_ID,
        "biomes": BIOMES,
        "fillers": [{"name": f[0], "resource": f[1], "amount": f[2], "id": BASE_ID + 1200 + i}
                    for i, f in enumerate(FILLERS)],
        "groups": groups,
        "nodes": [{k: v for k, v in n.items() if k != "description"} for n in nodes],
    }
    write(os.path.join(project, "apworld", "riftbreaker", "data.json"), json.dumps(data, indent=1, ensure_ascii=False))

    # --- mod data
    def ls(s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def awards(n):
        return "{ " + ", ".join("{ %s, %s }" % (ls(a["blueprint"]), "true" if a["hidden"] else "false")
                                for a in n["awards"]) + " }"

    by_name = {n["name"]: n for n in nodes}
    lua = ["-- GENERATED by tools/gen_open.py. Do not edit.", "AP_DATA = {", f"  base_id = {BASE_ID},",
           "  locations = {  -- research short name -> location id"]
    lua += [f"    [{ls(n['name'])}] = {n['id']}," for n in randomized]
    lua += ["  },", "  awards = {  -- item id -> { {blueprint, hidden}, ... }"]
    lua += [f"    [{n['id']}] = {awards(n)}," for n in randomized if "group" not in n]
    lua += ["  },", "  progressive = {  -- item id -> awards for copy 1, 2, ..."]
    for g in groups:
        lua.append(f"    [{g['id']}] = {{ " + ", ".join(awards(by_name[m]) for m in g["members"]) + " },")
    lua += ["  },", "  biomes = {  -- item id -> biome name"]
    lua += [f"    [{BASE_ID + 1100 + i}] = {ls(b)}," for i, b in enumerate(BIOMES) if b != "jungle"]
    lua += ["  },", "  fillers = {  -- item id -> { resource, amount }"]
    lua += [f"    [{d['id']}] = {{ {ls(d['resource'])}, {d['amount']} }}," for d in data["fillers"]]
    lua += ["  },", "}", ""]
    write(os.path.join(project, "mod", "lua", "archipelago", "ap_data.lua"), "\n".join(lua))

    print(f"{len(nodes)} nodes, {len(randomized)} randomized, {len(edits)} award blocks stripped, "
          f"{len(groups)} progressive groups covering {sum(len(g['members']) for g in groups)} nodes")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
