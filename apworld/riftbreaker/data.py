"""Static data and logic for The Riftbreaker (open campaign, story campaign, survival).

data.json is generated from the game files by tools/gen_data.py. The tables here were read from the game's data packs
(biome/mission files, research tree scripts, campaign graphs); comments name the sources. The world and the client's
tracker both evaluate checks through Logic, so they always agree.
"""
import json
import pkgutil
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

GAME = "The Riftbreaker"
PROTOCOL = 3

_RAW = json.loads(pkgutil.get_data(__name__, "data.json").decode("utf-8"))
BASE_ID: int = _RAW["base_id"]
BIOMES: List[str] = _RAW["biomes"]
START_BIOME = "jungle"
OFFWORLD_BIOMES = [b for b in BIOMES if b != START_BIOME]
MODES = ["open", "story", "survival"]
MODE_DATA: Dict[str, dict] = _RAW["modes"]
FILLERS: List[dict] = _RAW["fillers"]
GROUP_IDS: Dict[str, int] = _RAW["groups"]
BUILDS: List[dict] = _RAW["builds"]
MISSIONS: List[dict] = _RAW["missions"]
SURVIVAL_MAPS: Dict[str, dict] = _RAW["survival_maps"]
SURVIVAL_TIME_BASE: int = _RAW["survival_time_base"]
SURVIVAL_MAX_MINUTES: int = _RAW["survival_max_minutes"]

BIOME_DISPLAY = {"jungle": "Jungle", "desert": "Desert", "acid": "Acid Fields", "magma": "Magma",
                 "ice": "Cryo Fields", "metallic": "Metallic Valley", "caverns": "Caverns", "swamp": "Swamp"}
STORY_BIOMES = ["jungle", "desert", "acid", "magma"]   # base story campaign (no DLC)

# ---------------------------------------------------------------- resources
# Open campaign: missions/campaigns/open/headquarters_<biome>.mission (random_resources volumes, resource shards).
RESOURCE_BIOMES_OPEN: Dict[str, FrozenSet[str]] = {
    "cobalt":    frozenset(BIOMES),
    "palladium": frozenset({"acid", "ice", "swamp"}),
    "titanium":  frozenset({"magma", "swamp"}),
    "uranium":   frozenset({"desert", "swamp"}),
    "rhodonite": frozenset({"acid", "swamp"}),
    "tanzanite": frozenset({"desert", "ice", "swamp"}),
    "hazenite":  frozenset({"jungle", "metallic", "swamp"}),
    "ferdonite": frozenset({"magma", "swamp"}),
}
# Story campaign: each new resource is found by that biome's "find new/rare resource" mission
# (logic/campaigns/story/*_2.logic, discover_<biome>_rare_resource.logic).
RESOURCE_BIOMES_STORY: Dict[str, FrozenSet[str]] = {
    "cobalt": frozenset(STORY_BIOMES), "palladium": frozenset({"acid"}), "titanium": frozenset({"magma"}),
    "uranium": frozenset({"desert"}), "rhodonite": frozenset({"acid"}), "tanzanite": frozenset({"desert"}),
    "hazenite": frozenset({"jungle"}), "ferdonite": frozenset({"magma"}),
}
RARE_RESOURCES = {"rhodonite", "tanzanite", "hazenite", "ferdonite"}
FREE_RESOURCES = {"carbonium", "steel", "download"}   # starting kit: carbonium/ironium factories, comms hub
VEIN_FOR = {"cobalt": "cobalt_vein", "palladium": "palladium_vein", "titanium": "titanium_vein",
            "uranium": "uranium_ore_vein"}
ANALYSIS_NODE = "alien_research"        # Laboratory produces "analysis"
RARE_MINE_NODE = "rare_element_mining_lvl1"
SCANNER_NODE = "orbital_scanning"       # Planetary Scanner: needed to travel (open) / to unlock scouting (story)

# ---------------------------------------------------------------- creatures / flora (familiarity requirements)
# creature_species in missions/campaigns/open/headquarters_<biome>.mission + dom_waves_<biome>_*.lua; flora from
# logic/campaigns/story/discover_<biome>_rare_resource.logic and biomes/<biome>/ tiles.
SPECIES_BIOMES: Dict[str, FrozenSet[str]] = {k: frozenset(v) for k, v in {
    "flurian": {"metallic"}, "crawlog": {"caverns"}, "gulgor": {"caverns"}, "stregaros_crystal": {"caverns"},
    "baxmoth": {"jungle", "acid", "swamp"}, "krocoon": {"jungle", "acid", "magma", "ice", "metallic"},
    "geotrupex": {"desert"}, "mushbit": {"desert"}, "spawner_canoptrix": {"jungle"},
    "kermon": {"jungle", "desert", "ice", "metallic"}, "gnerot": {"jungle", "desert", "magma", "caverns"},
    "cryo_plant": {"desert", "magma"}, "morirot": {"magma"}, "lesigian": {"desert", "metallic"},
    "granan": {"acid", "ice"}, "stregaros": {"desert"}, "bomogan": {"jungle", "acid", "magma", "ice"},
    "bradron": {"metallic"}, "wingmite": {"metallic"}, "nurglax": {"acid", "swamp"}, "necrodon": {"caverns"},
    "magmoth": {"magma", "ice"}, "plutrodon": {"ice", "swamp"}, "carnicinth": {"swamp"},
    "phirian": {"jungle", "acid", "magma", "swamp"}, "artigian": {"swamp"}, "drexolian": {"magma", "swamp"},
    "stickrid": {"swamp"}, "fungor": {"swamp"},
    "drillgor": {"caverns"},   # logic/missions/survival/caverns/attack_drillgor.logic
    "prop_name/crystal_pure_red": {"acid"}, "prop_name/cactus_pear_purple": {"desert"},
    "prop_name/mushroom_spiky_bulb_red": {"jungle"}, "prop_name/crystal_entwined_blue": {"magma"},
    "prop_name/cryo_plant": {"desert", "magma"},
}.items()}
FLORA_PREFIX = "prop_name/"
CREATURE_SUFFIXES = tuple(BIOMES) + ("alpha", "ultra", "boss")


def species_key(params: dict) -> str:
    return params.get("sub_species_name") or params.get("species_name", "")


# ---------------------------------------------------------------- goals
GOAL_NODES = {
    "arcology": ["arcology_workshop", "gravitational_hyper_lens", "hydroponic_lab", "nanobot_center"],
    "prime_rift": ["arcology_workshop", "gravitational_hyper_lens", "hydroponic_lab", "nanobot_center",
                   "prime_rift_station"],
}

# ---------------------------------------------------------------- names and ids
FILLER_NAMES = {f["name"] for f in FILLERS}


def biome_item_name(biome: str) -> str:
    return f"Biome: {BIOME_DISPLAY[biome]}"


def biome_location_name(biome: str) -> str:
    return f"Arrive in {BIOME_DISPLAY[biome]}"


def survival_location_name(minutes: int) -> str:
    return f"Survive {minutes} Minutes"


def research_location_name(node: dict) -> str:
    return f"Research: {node['display']}"


def node_item(node: dict) -> Tuple[str, int]:
    """(item name, copies needed) that grants this node's reward."""
    if "group" in node:
        return node["group"], node["level"]
    return node["display"], 1


ITEM_NAME_TO_ID: Dict[str, int] = {}
LOCATION_NAME_TO_ID: Dict[str, int] = {}
for _mode in MODES:
    for _n in MODE_DATA[_mode]["nodes"]:
        if _n["starting"]:
            continue
        LOCATION_NAME_TO_ID[research_location_name(_n)] = _n["location_id"]
        _name, _ = node_item(_n)
        ITEM_NAME_TO_ID[_name] = _n["item_id"]
for _i, _b in enumerate(BIOMES):
    if _b != START_BIOME:
        ITEM_NAME_TO_ID[biome_item_name(_b)] = BASE_ID + 1100 + _i
        LOCATION_NAME_TO_ID[biome_location_name(_b)] = BASE_ID + 1000 + _i
for _f in FILLERS:
    ITEM_NAME_TO_ID[_f["name"]] = _f["id"]
for _b in BUILDS:
    LOCATION_NAME_TO_ID[_b["name"]] = _b["id"]
for _m in MISSIONS:
    LOCATION_NAME_TO_ID[_m["name"]] = _m["id"]
for _minute in range(1, SURVIVAL_MAX_MINUTES + 1):
    LOCATION_NAME_TO_ID[survival_location_name(_minute)] = SURVIVAL_TIME_BASE + _minute
assert len(set(ITEM_NAME_TO_ID.values())) == len(ITEM_NAME_TO_ID), "duplicate item ids"
assert len(set(LOCATION_NAME_TO_ID.values())) == len(LOCATION_NAME_TO_ID), "duplicate location ids"
ITEM_ID_TO_NAME = {v: k for k, v in ITEM_NAME_TO_ID.items()}
LOCATION_ID_TO_NAME = {v: k for k, v in LOCATION_NAME_TO_ID.items()}
BIOME_LOCATION_ID = {b: LOCATION_NAME_TO_ID[biome_location_name(b)] for b in OFFWORLD_BIOMES}

# ---------------------------------------------------------------- requirements
# A requirement is (items, biome_groups): items is a frozenset of (item name, count); biome_groups is a frozenset of
# biome sets, each needing access to at least one of its biomes. IMPOSSIBLE marks checks that can never be done.
Req = Tuple[FrozenSet[Tuple[str, int]], FrozenSet[FrozenSet[str]]]
EMPTY: Req = (frozenset(), frozenset())
IMPOSSIBLE_ITEM = "__impossible__"
IMPOSSIBLE: Req = (frozenset({(IMPOSSIBLE_ITEM, 1)}), frozenset())


def merge(*reqs: Req) -> Req:
    counts: Dict[str, int] = {}
    groups: Set[FrozenSet[str]] = set()
    for items, g in reqs:
        for name, count in items:
            counts[name] = max(counts.get(name, 0), count)
        groups |= g
    return frozenset(counts.items()), frozenset(groups)


def is_impossible(req: Req) -> bool:
    return any(name == IMPOSSIBLE_ITEM for name, _ in req[0])


class Logic:
    """Requirements for one slot: a game mode (and survival map)."""

    def __init__(self, mode: str, survival_map: str = "desert") -> None:
        self.mode = mode
        self.survival_map = survival_map
        self.nodes: List[dict] = MODE_DATA[mode]["nodes"]
        self.by_name: Dict[str, dict] = {n["name"]: n for n in self.nodes}
        self.randomized = [n for n in self.nodes if not n["starting"]]
        self.blueprint_node: Dict[str, str] = {}
        for n in self.nodes:
            for a in n["awards"]:
                self.blueprint_node.setdefault(a["blueprint"], n["name"])
        self._cache: Dict[str, Req] = {}
        if mode == "survival":
            m = SURVIVAL_MAPS[survival_map]
            self.map_resources = {r for r, vein in VEIN_FOR.items() if vein in m["veins"]}
            self.map_resources |= {r for r in RARE_RESOURCES if r in m["shards"]}
            self.map_creatures = set(m["creatures"])

    # ---- biomes
    def biome_req(self, biome: str) -> Req:
        if self.mode == "open":
            if biome == START_BIOME:
                return EMPTY
            return merge((frozenset({(biome_item_name(biome), 1)}), frozenset()), self.holding(SCANNER_NODE))
        if self.mode == "story":
            if biome == START_BIOME:
                return EMPTY
            if biome not in STORY_BIOMES:
                return IMPOSSIBLE
            # Scouting missions unlock once a Planetary Scanner and the Alien Lab exist
            # (logic/campaigns/story/default.logic: planet_scanner + global.AlienLabIsBuilt).
            return merge(self.holding(SCANNER_NODE), self.holding(ANALYSIS_NODE))
        return EMPTY if biome == self.survival_map else IMPOSSIBLE

    def any_biome(self, biomes) -> Req:
        options = [b for b in biomes if not is_impossible(self.biome_req(b))]
        if not options:
            return IMPOSSIBLE
        return frozenset(), frozenset({frozenset(options)})

    # ---- research
    def holding(self, name: str) -> Req:
        """Complete research `name` and hold its reward."""
        node = self.by_name.get(name)
        if node is None:
            return IMPOSSIBLE
        req = self.node_access(name)
        if node["starting"]:
            return req
        return merge(req, (frozenset({node_item(node)}), frozenset()))

    def resource_req(self, resource: str) -> Req:
        if resource in FREE_RESOURCES:
            return EMPTY
        if resource == "analysis":
            return self.holding(ANALYSIS_NODE)
        if resource not in RESOURCE_BIOMES_OPEN:
            return EMPTY   # no research costs other resources; kept as a safe default
        reqs = [self.holding(f"resource_handling_{resource}")]
        if resource in RARE_RESOURCES:
            reqs.append(self.holding(RARE_MINE_NODE))
        if self.mode == "open":
            reqs.append(self.any_biome(RESOURCE_BIOMES_OPEN[resource]))
        elif self.mode == "story":
            reqs.append(self.any_biome(RESOURCE_BIOMES_STORY[resource]))
        elif resource not in self.map_resources:
            return IMPOSSIBLE
        return merge(*reqs)

    def species_req(self, params: dict) -> Req:
        key = species_key(params)
        if self.mode == "survival":
            if key.startswith(FLORA_PREFIX):
                return EMPTY if self.survival_map in SPECIES_BIOMES.get(key, frozenset()) else IMPOSSIBLE
            for c in self.map_creatures:
                if c == key or (c.startswith(key + "_") and c[len(key) + 1:] in CREATURE_SUFFIXES):
                    return EMPTY
            return IMPOSSIBLE
        biomes = SPECIES_BIOMES.get(key)
        if biomes is None:
            # Unplaced species: open campaign requires every biome (always sufficient); story excludes the check.
            return merge(*[self.biome_req(b) for b in OFFWORLD_BIOMES]) if self.mode == "open" else IMPOSSIBLE
        return self.any_biome(biomes)

    def story_lock_req(self, name: str) -> Req:
        """Extra requirements of the story campaign's locked research (when the story enables it).
        Sources: logic/campaigns/story/*.logic and logic/missions/campaigns/story/*.logic."""
        n = self.node_access
        table = {
            "floor_acid": lambda: self.biome_req("acid"),
            "environmental_shielding_acid": lambda: self.biome_req("acid"),
            "floor_desert": lambda: self.biome_req("desert"),
            "environmental_shielding_sun": lambda: self.biome_req("desert"),
            "environmental_shielding_radiation": lambda: self.biome_req("desert"),
            "cryo_technology": lambda: self.biome_req("magma"),
            # acid_find_new_resource unlocks after acid_find_samples (floor_acid + research_station research)
            "resource_handling_palladium": lambda: merge(self.biome_req("acid"), n("floor_acid"),
                                                         n("research_station")),
            # desert_find_new_resource follows desert_find_samples (Stregaros encounter in the desert)
            "resource_handling_uranium": lambda: merge(self.biome_req("desert"),
                                                       self.species_req({"species_name": "stregaros"})),
            # magma_find_new_resource follows magma_find_samples (cryo_technology + auxiliary_buildings_lvl1)
            "resource_handling_titanium": lambda: merge(self.biome_req("magma"), n("cryo_technology"),
                                                        n("auxiliary_buildings_lvl1")),
            # the endgame (and its QCL research) starts once the three resource outposts are done
            "quantum_cortex_laboratory": lambda: merge(*[self.holding(f"resource_handling_{r}")
                                                         for r in ("uranium", "palladium", "titanium")]),
        }
        if name in table:
            return table[name]()
        return IMPOSSIBLE   # locked with no known story trigger (towers_morphium_lvl1)

    def node_access(self, name: str) -> Req:
        """Requirements to complete research `name`."""
        if name not in self._cache:
            node = self.by_name[name]
            self._cache[name] = EMPTY   # recursion guard (the trees are acyclic)
            reqs: List[Req] = [self.node_access(r) for r in node["requires"] if r in self.by_name]
            if any(r not in self.by_name for r in node["requires"]):
                reqs.append(IMPOSSIBLE)
            reqs += [self.resource_req(r) for r, amount in node["costs"].items() if amount > 0]
            for s in node["scripts"]:
                if not s["requirement"]:
                    continue
                if s["script"] == "building_exists":
                    src = self.blueprint_node.get(s["params"].get("building_blueprint", ""))
                    if src:
                        reqs.append(self.holding(src))
                elif s["script"] == "familiarity_level":
                    reqs.append(self.species_req(s["params"]))
            if node.get("locked"):
                if self.mode == "story":
                    reqs.append(self.story_lock_req(name.strip()))
                elif self.mode == "survival" and name.strip() == "towers_morphium_lvl1":
                    # enabled by logic/loadout/player_loadout_survival_metallic.logic on the metallic map only
                    reqs.append(EMPTY if self.survival_map == "metallic" else IMPOSSIBLE)
                else:
                    reqs.append(IMPOSSIBLE)
            self._cache[name] = merge(*reqs)
        return self._cache[name]

    # ---- other checks
    def build_req(self, build: dict) -> Optional[Req]:
        info = build["modes"].get(self.mode)
        if info is None:
            return None
        return self.holding(info["node"])

    def mission_req(self, mission: str) -> Req:
        """Story mission completion (traced from the story campaign graphs)."""
        n, h, b = self.node_access, self.holding, self.biome_req
        table = {
            "desert_scouting": lambda: b("desert"),
            "desert_find_samples": lambda: merge(b("desert"), self.species_req({"species_name": "stregaros"})),
            "desert_find_new_resource": lambda: merge(b("desert"), n("resource_handling_uranium")),
            "desert_find_rare_resource": lambda: merge(b("desert"), n("resource_handling_tanzanite")),
            "Desert Resource Outpost": lambda: merge(b("desert"), h("resource_handling_uranium")),
            "acid_scouting": lambda: b("acid"),
            "acid_find_samples": lambda: merge(b("acid"), n("floor_acid"), n("research_station")),
            "acid_find_new_resource": lambda: merge(b("acid"), n("resource_handling_palladium")),
            "Acid Find Rare Resource": lambda: merge(b("acid"), n("resource_handling_rhodonite")),
            "acid_resource_outpost": lambda: merge(b("acid"), h("resource_handling_palladium")),
            "magma_scouting": lambda: b("magma"),
            "magma_find_samples": lambda: merge(b("magma"), n("cryo_technology"), n("auxiliary_buildings_lvl1")),
            "magma_find_new_resource": lambda: merge(b("magma"), n("resource_handling_titanium")),
            "magma_find_rare_resource": lambda: merge(b("magma"), n("resource_handling_ferdonite")),
            "magma_resource_outpost": lambda: merge(b("magma"), h("resource_handling_titanium")),
            "jungle_find_rare_resource": lambda: n("resource_handling_hazenite"),
        }
        return table[mission]()

    def goal_req(self, goal: str) -> Req:
        if self.mode == "survival":
            return EMPTY   # survive the mission duration
        return merge(*[self.holding(x) for x in GOAL_NODES[goal] if x in self.by_name])

    # ---- every check of a slot
    def locations(self, options: dict) -> Dict[str, Req]:
        """Location name -> requirement for this slot (impossible checks left out)."""
        out: Dict[str, Req] = {}
        for node in self.randomized:
            out[research_location_name(node)] = self.node_access(node["name"])
        if options.get("build_checks", True):
            for build in BUILDS:
                req = self.build_req(build)
                if req is not None:
                    out[build["name"]] = req
        if self.mode == "open" and options.get("biome_arrival_checks", True):
            for biome in OFFWORLD_BIOMES:
                out[biome_location_name(biome)] = self.biome_req(biome)
        if self.mode == "story" and options.get("mission_checks", True):
            for m in MISSIONS:
                out[m["name"]] = self.mission_req(m["mission"])
        if self.mode == "survival":
            step = int(options.get("survival_time_interval", 10))
            if step > 0:
                for minute in range(step, SURVIVAL_MAX_MINUTES + 1, step):
                    out[survival_location_name(minute)] = EMPTY
        return {k: v for k, v in out.items() if not is_impossible(v)}

    def item_pool(self) -> List[str]:
        """One copy per randomized node (progressive items once per level), plus biome items in the open campaign."""
        pool = [node_item(n)[0] for n in self.randomized]
        if self.mode == "open":
            pool += [biome_item_name(b) for b in OFFWORLD_BIOMES]
        return pool

    def early_items(self) -> List[str]:
        """Key progression to place early when early_progression is on."""
        names = {
            "open": [("resource_handling_cobalt", 1), (SCANNER_NODE, 1), (ANALYSIS_NODE, 1), ("headquarters_lvl3", 1)],
            "story": [(SCANNER_NODE, 1), (ANALYSIS_NODE, 1), ("resource_handling_cobalt", 1), ("headquarters_lvl3", 1)],
            "survival": [("headquarters_lvl3", 1), ("resource_handling_liquid_lvl2", 1)],
        }[self.mode]
        out = []
        for name, _ in names:
            node = self.by_name.get(name)
            if node and not node["starting"]:
                out.append(node_item(node)[0])
        return out

    def progression_items(self, location_reqs: Dict[str, Req], goal: str) -> Set[str]:
        out: Set[str] = set()
        for items, groups in list(location_reqs.values()) + [self.goal_req(goal)]:
            out |= {name for name, _ in items}
            for g in groups:
                for b in g:
                    out |= {name for name, _ in self.biome_req(b)[0]}
        if self.mode == "open":
            out |= {biome_item_name(b) for b in OFFWORLD_BIOMES}
        out.discard(IMPOSSIBLE_ITEM)
        return out


FILLER_KEYWORDS = ("decoration", "floor_", "lamp")


def is_filler_reward(logic: Logic, item_name: str) -> bool:
    for n in logic.randomized:
        if "group" not in n and n["display"] == item_name:
            return any(k in a["blueprint"] for a in n["awards"] for k in FILLER_KEYWORDS)
    return False
