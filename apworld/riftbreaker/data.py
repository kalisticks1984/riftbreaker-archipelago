"""Static data for The Riftbreaker (open campaign).

data.json is generated from the game files by tools/gen_open.py. Everything else here was read from the game's
data packs (biome mission files, resource definitions, research tree scripts); see the comments for sources.
"""
import json
import pkgutil
from typing import Dict, FrozenSet, List, Set, Tuple

GAME = "The Riftbreaker"
PROTOCOL = 2

_RAW = json.loads(pkgutil.get_data(__name__, "data.json").decode("utf-8"))
BASE_ID: int = _RAW["base_id"]
BIOMES: List[str] = _RAW["biomes"]
START_BIOME = "jungle"
OFFWORLD_BIOMES = [b for b in BIOMES if b != START_BIOME]
NODES: List[dict] = _RAW["nodes"]
NODE_BY_NAME: Dict[str, dict] = {n["name"]: n for n in NODES}
FILLERS: List[dict] = _RAW["fillers"]
GROUPS: List[dict] = _RAW["groups"]
GROUP_BY_KEY: Dict[str, dict] = {g["key"]: g for g in GROUPS}

BIOME_DISPLAY = {"jungle": "Jungle", "desert": "Desert", "acid": "Acid Fields", "magma": "Magma",
                 "ice": "Cryo Fields", "metallic": "Metallic Valley", "caverns": "Caverns", "swamp": "Swamp"}

# ---------------------------------------------------------------- resources
# Where each research-cost resource can be obtained in the open campaign.
# Source: missions/campaigns/open/headquarters_<biome>.mission  (random_resources volumes and resource shard loot).
RESOURCE_BIOMES: Dict[str, FrozenSet[str]] = {
    "cobalt":    frozenset(BIOMES),
    "palladium": frozenset({"acid", "ice", "swamp"}),
    "titanium":  frozenset({"magma", "swamp"}),
    "uranium":   frozenset({"desert", "swamp"}),
    "rhodonite": frozenset({"acid", "swamp"}),
    "tanzanite": frozenset({"desert", "ice", "swamp"}),
    "hazenite":  frozenset({"jungle", "metallic", "swamp"}),
    "ferdonite": frozenset({"magma", "swamp"}),
}
RARE_RESOURCES = {"rhodonite", "tanzanite", "hazenite", "ferdonite"}
FREE_RESOURCES = {"carbonium", "steel", "download"}   # starting kit: carbonium/ironium factories, comms hub
RESOURCE_HANDLING = {r: f"resource_handling_{r}" for r in RESOURCE_BIOMES}
ANALYSIS_NODE = "alien_research"        # Laboratory produces "analysis"
RARE_MINE_NODE = "rare_element_mining_lvl1"
SCANNER_NODE = "orbital_scanning"       # Planetary Scanner: needed to travel to other biomes

# ---------------------------------------------------------------- creatures / flora for familiarity requirements
# Source: creature_species in missions/campaigns/open/headquarters_<biome>.mission and units in
# lua/missions/campaigns/open/headquarters/dom_waves_<biome>_*.lua (exact name or <name>_<biome>/_alpha variants);
# flora from logic/campaigns/story/discover_<biome>_rare_resource.logic and biomes/<biome>/ tiles.
# Species not listed here could not be placed reliably and require access to every biome (always sufficient).
SPECIES_BIOMES: Dict[str, FrozenSet[str]] = {k: frozenset(v) for k, v in {
    "flurian": {"metallic"},
    "crawlog": {"caverns"},
    "gulgor": {"caverns"},
    "stregaros_crystal": {"caverns"},
    "baxmoth": {"jungle", "acid", "swamp"},
    "krocoon": {"jungle", "acid", "magma", "ice", "metallic"},
    "geotrupex": {"desert"},
    "mushbit": {"desert"},
    "spawner_canoptrix": {"jungle"},
    "kermon": {"jungle", "desert", "ice", "metallic"},
    "gnerot": {"jungle", "desert", "magma", "caverns"},
    "cryo_plant": {"desert", "magma"},
    "morirot": {"magma"},
    "lesigian": {"desert", "metallic"},
    "granan": {"acid", "ice"},
    "stregaros": {"desert"},
    "bomogan": {"jungle", "acid", "magma", "ice"},
    "bradron": {"metallic"},
    "wingmite": {"metallic"},
    "nurglax": {"acid", "swamp"},
    "necrodon": {"caverns"},
    "magmoth": {"magma", "ice"},
    "plutrodon": {"ice", "swamp"},
    "carnicinth": {"swamp"},
    "phirian": {"jungle", "acid", "magma", "swamp"},
    "artigian": {"swamp"},
    "drexolian": {"magma", "swamp"},
    "stickrid": {"swamp"},
    "fungor": {"swamp"},
    "drillgor": {"caverns"},   # logic/missions/survival/caverns/attack_drillgor.logic
    "prop_name/crystal_pure_red": {"acid"},
    "prop_name/cactus_pear_purple": {"desert"},
    "prop_name/mushroom_spiky_bulb_red": {"jungle"},
    "prop_name/crystal_entwined_blue": {"magma"},
    "prop_name/cryo_plant": {"desert", "magma"},
}.items()}


def species_key(params: dict) -> str:
    return params.get("sub_species_name") or params.get("species_name", "")


# ---------------------------------------------------------------- goal
GOAL_NODES = {
    # Arcology assembly needs the workshop and the three megastructures it assembles.
    "arcology": ["arcology_workshop", "gravitational_hyper_lens", "hydroponic_lab", "nanobot_center"],
    "prime_rift": ["arcology_workshop", "gravitational_hyper_lens", "hydroponic_lab", "nanobot_center",
                   "prime_rift_station"],
}

# ---------------------------------------------------------------- names and ids
RANDOMIZED = [n for n in NODES if not n["starting"]]


def research_location_name(node: dict) -> str:
    return f"Research: {node['display']}"


def node_item(node: dict) -> Tuple[str, int]:
    """(item name, copies needed) that grants this node's reward."""
    if "group" in node:
        return GROUP_BY_KEY[node["group"]]["display"], node["level"]
    return node["display"], 1


def biome_item_name(biome: str) -> str:
    return f"Biome: {BIOME_DISPLAY[biome]}"


ITEM_NAME_TO_ID: Dict[str, int] = {}
LOCATION_NAME_TO_ID: Dict[str, int] = {}
for _n in RANDOMIZED:
    LOCATION_NAME_TO_ID[research_location_name(_n)] = _n["id"]
    if "group" not in _n:
        ITEM_NAME_TO_ID[_n["display"]] = _n["id"]
for _g in GROUPS:
    ITEM_NAME_TO_ID[_g["display"]] = _g["id"]
for _i, _b in enumerate(BIOMES):
    if _b != START_BIOME:
        ITEM_NAME_TO_ID[biome_item_name(_b)] = BASE_ID + 1100 + _i
for _f in FILLERS:
    ITEM_NAME_TO_ID[_f["name"]] = _f["id"]
assert len(set(ITEM_NAME_TO_ID.values())) == len(ITEM_NAME_TO_ID), "duplicate item ids"

# Item pool: one copy per randomized node (progressive items once per level), plus biome items.
POOL: List[str] = [node_item(n)[0] for n in RANDOMIZED] + [biome_item_name(b) for b in OFFWORLD_BIOMES]

# ---------------------------------------------------------------- requirements
# A requirement is (items, biome_groups): items is a frozenset of (item name, count); biome_groups is a frozenset of
# biome sets, each needing access to at least one of its biomes.
Req = Tuple[FrozenSet[Tuple[str, int]], FrozenSet[FrozenSet[str]]]
EMPTY: Req = (frozenset(), frozenset())

BLUEPRINT_NODE: Dict[str, str] = {}
for _n in NODES:
    for _a in _n["awards"]:
        BLUEPRINT_NODE.setdefault(_a["blueprint"], _n["name"])


def _merge(*reqs: Req) -> Req:
    counts: Dict[str, int] = {}
    groups: Set[FrozenSet[str]] = set()
    for items, g in reqs:
        for name, count in items:
            counts[name] = max(counts.get(name, 0), count)
        groups |= g
    return frozenset(counts.items()), frozenset(groups)


def biome_req(biome: str) -> Req:
    """Items needed to reach `biome`."""
    if biome == START_BIOME:
        return EMPTY
    return frozenset({(biome_item_name(biome), 1), node_item(NODE_BY_NAME[SCANNER_NODE])}), frozenset()


def holding(name: str) -> Req:
    """Requirements to complete research `name` and hold its reward."""
    node = NODE_BY_NAME[name]
    req = node_access(name)
    if node["starting"]:
        return req
    return _merge(req, (frozenset({node_item(node)}), frozenset()))


def resource_req(resource: str) -> Req:
    if resource in FREE_RESOURCES:
        return EMPTY
    if resource == "analysis":
        return holding(ANALYSIS_NODE)
    reqs = [holding(RESOURCE_HANDLING[resource])]
    if resource in RARE_RESOURCES:
        reqs.append(holding(RARE_MINE_NODE))
    reqs.append((frozenset(), frozenset({RESOURCE_BIOMES[resource]})))
    return _merge(*reqs)


_cache: Dict[str, Req] = {}


def node_access(name: str) -> Req:
    """Requirements to complete research `name`."""
    if name not in _cache:
        node = NODE_BY_NAME[name]
        _cache[name] = EMPTY   # recursion guard (the tree is acyclic)
        reqs: List[Req] = [node_access(r) for r in node["requires"]]
        reqs += [resource_req(r) for r, amount in node["costs"].items() if amount > 0]
        for s in node["scripts"]:
            if not s["requirement"]:
                continue
            if s["script"] == "building_exists":
                src = BLUEPRINT_NODE.get(s["params"].get("building_blueprint", ""))
                if src:
                    reqs.append(holding(src))
            elif s["script"] == "familiarity_level":
                biomes = SPECIES_BIOMES.get(species_key(s["params"]))
                if biomes is None:
                    reqs += [biome_req(b) for b in OFFWORLD_BIOMES]
                else:
                    reqs.append((frozenset(), frozenset({biomes})))
        _cache[name] = _merge(*reqs)
    return _cache[name]


def goal_req(goal: str) -> Req:
    return _merge(*[holding(n) for n in GOAL_NODES[goal]])


def _progression_items() -> Set[str]:
    out: Set[str] = {biome_item_name(b) for b in OFFWORLD_BIOMES}
    reqs = [node_access(n["name"]) for n in RANDOMIZED] + [goal_req(g) for g in GOAL_NODES]
    for items, groups in reqs:
        out |= {name for name, _ in items}
        for g in groups:
            for b in g:
                out |= {name for name, _ in biome_req(b)[0]}
    return out


PROGRESSION_ITEMS: FrozenSet[str] = frozenset(_progression_items())
FILLER_KEYWORDS = ("decoration", "floor_", "lamp")
_NODE_BY_ITEM = {n["display"]: n for n in RANDOMIZED if "group" not in n}


def item_class(name: str) -> str:
    if name in PROGRESSION_ITEMS:
        return "progression"
    if any(f["name"] == name for f in FILLERS):
        return "filler"
    node = _NODE_BY_ITEM.get(name)
    if node and any(k in a["blueprint"] for a in node["awards"] for k in FILLER_KEYWORDS):
        return "filler"
    return "useful"
