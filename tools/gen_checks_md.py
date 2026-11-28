"""Write CHECKS.md: every location per game mode, with the item each research reward becomes.

Usage: python -I gen_checks_md.py
"""
import importlib.util
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
PKG = os.path.join(PROJECT, "apworld", "riftbreaker")

pkg = types.ModuleType("riftbreaker")
pkg.__path__ = [PKG]
sys.modules["riftbreaker"] = pkg
spec = importlib.util.spec_from_file_location("riftbreaker.data", os.path.join(PKG, "data.py"))
D = importlib.util.module_from_spec(spec)
sys.modules["riftbreaker.data"] = D
spec.loader.exec_module(D)

TITLES = {"base_buildings": "Base and Buildings", "weapons_equipment": "Weapons and Equipment",
          "alien": "Alien Technology", "megastructures": "Megastructures"}
RES = {"steel": "ironium"}
ALL_ON = {"build_checks": True, "biome_arrival_checks": True, "mission_checks": True, "survival_time_interval": 10}


def main() -> None:
    lines = ["# Checks", "",
             "Locations per game mode with every check option on (survival: desert map, a time check every 10 minutes).",
             "Research rewards are shuffled into the item pool as the item in the last column; progressive items grant "
             "their levels in order. Research that can never be done in a mode (for example, it needs a creature that "
             "does not live there) is left out.", ""]
    for mode in D.MODES:
        logic = D.Logic(mode, "desert")
        locs = logic.locations(ALL_ON)
        research = [n for n in logic.randomized if D.research_location_name(n) in locs]
        other = [name for name in locs if not name.startswith("Research: ")]
        lines += [f"## {mode.title()} ({len(locs)} checks)", "", f"### Other checks ({len(other)})", ""]
        lines += [f"- {name}" for name in sorted(other)]
        by_cat = {}
        for n in research:
            by_cat.setdefault(n["category"], []).append(n)
        for cat, nodes in by_cat.items():
            lines += ["", f"### {TITLES.get(cat, cat)} ({len(nodes)})", "", "| Location | Cost | Item in the pool |",
                      "|---|---|---|"]
            for n in sorted(nodes, key=lambda x: x["display"].lower()):
                cost = ", ".join(f"{v:,} {RES.get(r, r)}" for r, v in n["costs"].items() if v)
                name, level = D.node_item(n)
                item = f"{name} (level {level})" if "group" in n else name
                lines.append(f"| Research: {n['display']} | {cost} | {item} |")
        lines.append("")
    with open(os.path.join(PROJECT, "CHECKS.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    print("wrote CHECKS.md")


if __name__ == "__main__":
    main()
