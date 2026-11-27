# The Riftbreaker

## What does randomization do to this game?

This world uses the **open campaign**. Every check is in the research tree.

Every research project except the free starting kit is a check. Researching one sends a check instead of giving you
its buildings, weapons or upgrades. Those rewards are items in the multiworld.

Once the client has connected, each research node shows the item it sends, with the receiving player when it's for
someone else. Its description says whether that item is progression, useful, filler or a trap.

**Research is near-instant:** the mod sets the game's "Research time factor" difficulty setting to 0.01. Research
still costs its listed resources. Only the time is removed.

**Progressive items:** research that comes in levels arrives in order. For example, the first Progressive Renewable
Energy you receive is level 1, the second is level 2, and so on. This covers Headquarters, towers, energy, storage,
megastructures and every other `lvl` family.

**Biomes:** the seven biomes other than the Jungle stay locked until their Biome item arrives. The Planetary Scanner no
longer unlocks them. You still need the Planetary Scanner, which comes from the "Orbital Scanning" item, to travel.

## What is the goal?

- **arcology** (default): complete the Arcology assembly.
- **prime_rift**: build and activate the Prime Rift Station and return to Earth.

## How is logic decided?

A research check is in logic when you could pay for it and everything it depends on:

- **Common ores:** cobalt, palladium, titanium and uranium need their Resource Handling item, plus access to a biome
  that spawns them.
- **Rare crystals:** these also need Rare Element Mining.
- **Analysis:** needs the Laboratory, which is Progressive Alien Research #1.
- **Building requirements:** research that needs a building already built needs that building's progressive level.
  For example, Headquarters lvl. 5 research needs Progressive Headquarters ×2, which is the HQ lvl. 4 building.
- **Familiarity:** research that needs familiarity with a creature or plant needs access to a biome where it lives.

## In game

- The HUD shows "Archipelago: connected as …" when the client links up, and "Archipelago: received …" for each item.
- Console `ap_status` shows the status again.
- Console `ap_research` opens the research screen anywhere. Research only unlocks once you own a Communications Hub (the game hard-codes this); for testing, console `ap_hub` places one next to you for free.
