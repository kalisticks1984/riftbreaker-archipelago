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

_CLS = {
    "progression": ItemClassification.progression,
    "useful": ItemClassification.useful,
    "filler": ItemClassification.filler,
}


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


class RiftbreakerWorld(World):
    """
    The Riftbreaker is a base-building, survival and action game. In the open campaign every research project is a
    check, its reward comes from the multiworld, and each biome stays closed until its Biome item arrives.
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
        "Progressive": {g["display"] for g in D.GROUPS},
    }
    location_name_groups = {
        cat.replace("_", " ").title(): {D.research_location_name(n) for n in D.RANDOMIZED if n["category"] == cat}
        for cat in sorted({n["category"] for n in D.RANDOMIZED})
    }

    def _rule(self, req: D.Req) -> Callable[[CollectionState], bool]:
        items, groups = req
        player = self.player
        item_list = sorted(items)
        group_options = [[sorted(D.biome_req(b)[0]) for b in sorted(g)] for g in groups]

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
        for node in D.RANDOMIZED:
            name = D.research_location_name(node)
            loc = RiftbreakerLocation(self.player, name, D.LOCATION_NAME_TO_ID[name], base)
            loc.access_rule = self._rule(D.node_access(node["name"]))
            base.locations.append(loc)
        victory = RiftbreakerLocation(self.player, "Victory", None, base)
        victory.access_rule = self._rule(D.goal_req(self.options.goal.current_key))
        victory.place_locked_item(RiftbreakerItem("Victory", ItemClassification.progression, None, self.player))
        base.locations.append(victory)

    def create_item(self, name: str) -> RiftbreakerItem:
        return RiftbreakerItem(name, _CLS[D.item_class(name)], D.ITEM_NAME_TO_ID[name], self.player)

    def get_filler_item_name(self) -> str:
        return self.random.choice(D.FILLERS)["name"]

    def create_items(self) -> None:
        pool: List[RiftbreakerItem] = [self.create_item(name) for name in D.POOL]
        slots = len(self.multiworld.get_unfilled_locations(self.player))   # Victory already holds its locked item
        # There are 7 more items (the biomes) than research locations: start with that many non-progression
        # rewards, filler first, then random useful ones. Progression items always stay in the pool.
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
        return {"protocol": D.PROTOCOL, "goal": self.options.goal.current_key}
