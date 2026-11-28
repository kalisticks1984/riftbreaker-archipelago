# The Riftbreaker

## Game modes

Pick one with the `game_mode` option:

- **open:** the open campaign. You start in the Jungle, and the other seven biomes unlock through **Biome** items. You
  also need the Planetary Scanner, from the "Orbital Scanning" item, to travel.
- **story:** the base story campaign (no DLC). Biomes and missions unlock through the story as usual.
- **survival:** one survival map, chosen with `survival_map`. You win by surviving the mission duration.

## What is a check?

- **Research:** every research project except the free starting kit. Researching it sends the check instead of giving
  you its buildings, weapons or upgrades. Once the client connects, each research node shows the item it sends, and
  its description says whether that item is progression, useful, filler or a trap.
- **Builds** (`build_checks`): Headquarters levels 3 to 7, Laboratory, Planetary Scanner, Rare Element Mine, and the
  megastructures, whichever exist in the mode.
- **Biome arrivals** (open, `biome_arrival_checks`): arriving in each non-Jungle biome for the first time.
- **Story missions** (story, `mission_checks`): completing each of the 16 base story missions.
- **Survival time** (survival, `survival_time_interval`): every N minutes survived, up to 90.

Research that can never be done in a mode is left out. For example, a creature it needs may not live there.

## Items

- **Research rewards:** leveled research (Headquarters, towers, energy, storage, megastructures and so on) arrives as
  **progressive** items, granted in order.
- **Biome items:** open campaign only.
- **Filler:** resource caches of carbonium, ironium and cobalt.

## Goal

- **Open and story:** `arcology` (complete the Arcology assembly) or `prime_rift` (return to Earth).
- **Survival:** survive the full mission duration.

## Other options

- **early_progression:** `early` or `local` places key progression (Orbital Scanning, Cobalt Handling, the
  Laboratory, the first HQ upgrade) in sphere 1.
- **energy_link:** shares resources and electricity through the multiworld's Energy Link pool. In the game console:
  - `ap_deposit <resource> <amount>`
  - `ap_withdraw <resource> <amount>`
  - `ap_energylink`

  Resources are carbonium, ironium, cobalt, palladium, titanium, uranium and energy. Rates in Energy Link units
  (J) per unit:

  | Resource | J per unit |
  |---|---|
  | Carbonium, ironium | 100 k |
  | Cobalt | 500 k |
  | Palladium, titanium | 1 M |
  | Uranium | 2 M |
  | Energy | 10 k |

## Co-op

Everyone in a co-op session shares one slot. Only the host runs the client. Rewards are granted to every player,
and every player needs the mod installed.

## In game

- **HUD messages:** "Archipelago: connected as …" and "Archipelago: received …".
- **Console commands:**
  - `ap_status`
  - `ap_tracker`: progress on each kind of check, and how many are in logic.
  - `ap_research`
  - `ap_hub`: places a free Communications Hub for testing. Research only unlocks while you own one.
- **Research speed:** research is near-instant. The game's "Research time factor" is set to 0.01, and costs are
  unchanged.

## Client

The client's **Tracker** tab lists every check as done, in logic or locked. `/tracker` prints the non-research checks.
