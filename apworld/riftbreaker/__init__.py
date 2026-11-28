from typing import Any, Callable, Dict, List

from BaseClasses import CollectionState, Item, ItemClassification, Location, Region, Tutorial
from worlds.AutoWorld import WebWorld, World
from worlds.LauncherComponents import Component, Type, components, launch_subprocess

from . import data as D
from .options import RiftbreakerOptions


def launch_client(*args) -> None:
    from .client import launch
    launch_subprocess(launch, name="RiftbreakerClient", args=args)


components.append(Component("The Riftbreaker Client", func=launch_client, component_type=Type.CLIENT))


class RiftbreakerItem(Item):
    game = D.GAME


class RiftbreakerLocation(Location):
    game = D.GAME


class RiftbreakerWeb(WebWorld):
    theme = "jungle"
    tutorials = [Tutorial(
        "Multiworld Setup Guide",
        "Installing The Riftbreaker Archipelago mod and client.",
        "English", "setup_en.md", "setup/en", ["Riftbreaker AP"],
    )]


def slot_options(options) -> Dict[str, Any]:
    """The option values Logic.locations reads (also sent to the client for its tracker)."""
    return {
        "game_mode": options.game_mode.current_key,
        "survival_map": options.survival_map.current_key,
        "survival_time_interval": options.survival_time_interval.value,
        "build_checks": bool(options.build_checks.value),
        "biome_arrival_checks": bool(options.biome_arrival_checks.value),
        "mission_checks": bool(options.mission_checks.value),
        "goal": options.goal.current_key,
    }


class RiftbreakerWorld(World):
    """
    The Riftbreaker is a base-building, survival and action game. Research projects, building milestones, story
    missions, biome arrivals and survival time are checks; research rewards and biome access come from the multiworld.
    Plays the open campaign, the story campaign or survival.
    """
    game = D.GAME
    web = RiftbreakerWeb()
    options_dataclass = RiftbreakerOptions
    options: RiftbreakerOptions
    topology_present = False

    item_name_to_id = D.ITEM_NAME_TO_ID
    location_name_to_id = D.LOCATION_NAME_TO_ID
    item_name_groups = {
        "Biomes": {D.biome_item_name(b) for b in D.OFFWORLD_BIOMES},
        "Progressive": set(D.GROUP_IDS),
        "Filler": set(D.FILLER_NAMES),
    }
    location_name_groups = {
        "Builds": {b["name"] for b in D.BUILDS},
        "Story Missions": {m["name"] for m in D.MISSIONS},
        "Biome Arrivals": {D.biome_location_name(b) for b in D.OFFWORLD_BIOMES},
        "Survival Time": {D.survival_location_name(m) for m in range(1, D.SURVIVAL_MAX_MINUTES + 1)},
    }

    def generate_early(self) -> None:
        opts = slot_options(self.options)
        self.logic = D.Logic(opts["game_mode"], opts["survival_map"])
        self.location_reqs = self.logic.locations(opts)
        self.progression = self.logic.progression_items(self.location_reqs, opts["goal"])
        mode = self.options.early_progression.current_key
        if mode != "off":
            target = self.multiworld.local_early_items if mode == "local" else self.multiworld.early_items
            for name in self.logic.early_items():
                target[self.player][name] = 1

    def _rule(self, req: D.Req) -> Callable[[CollectionState], bool]:
        items, groups = req
        player = self.player
        item_list = sorted(items)
        group_options = [[sorted(self.logic.biome_req(b)[0]) for b in sorted(g)] for g in groups]

        def has(state: CollectionState, needs) -> bool:
            return all(state.has(name, player, count) for name, count in needs)

        def rule(state: CollectionState) -> bool:
            if not has(state, item_list):
                return False
            return all(any(has(state, need) for need in options) for options in group_options)
        return rule

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        base = Region("Base", self.player, self.multiworld)
        self.multiworld.regions += [menu, base]
        menu.connect(base)
        for name, req in self.location_reqs.items():
            loc = RiftbreakerLocation(self.player, name, D.LOCATION_NAME_TO_ID[name], base)
            loc.access_rule = self._rule(req)
            base.locations.append(loc)
        victory = RiftbreakerLocation(self.player, "Victory", None, base)
        victory.access_rule = self._rule(self.logic.goal_req(self.options.goal.current_key))
        victory.place_locked_item(RiftbreakerItem("Victory", ItemClassification.progression, None, self.player))
        base.locations.append(victory)

    def create_item(self, name: str) -> RiftbreakerItem:
        if name in self.progression:
            cls = ItemClassification.progression
        elif name in D.FILLER_NAMES or D.is_filler_reward(self.logic, name):
            cls = ItemClassification.filler
        else:
            cls = ItemClassification.useful
        return RiftbreakerItem(name, cls, D.ITEM_NAME_TO_ID[name], self.player)

    def get_filler_item_name(self) -> str:
        return self.random.choice(D.FILLERS)["name"]

    def create_items(self) -> None:
        pool: List[RiftbreakerItem] = [self.create_item(name) for name in self.logic.item_pool()]
        slots = len(self.multiworld.get_unfilled_locations(self.player))   # Victory already holds its locked item
        # More items than locations: start with some rewards instead, filler first, then random useful ones.
        # Progression items always stay in the pool.
        if len(pool) > slots:
            filler = [i for i in pool if i.classification == ItemClassification.filler]
            useful = [i for i in pool if i.classification == ItemClassification.useful]
            self.random.shuffle(useful)
            for spare in (filler + useful)[:len(pool) - slots]:
                pool.remove(spare)
                self.multiworld.push_precollected(spare)
        while len(pool) < slots:
            pool.append(self.create_item(self.get_filler_item_name()))
        self.multiworld.itempool += pool

    def set_rules(self) -> None:
        self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)

    def fill_slot_data(self) -> Dict[str, Any]:
        return {
            "protocol": D.PROTOCOL,
            **slot_options(self.options),
            "energy_link": bool(self.options.energy_link.value),
        }
