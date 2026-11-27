# The Riftbreaker Archipelago Setup

## Requirements

- The Riftbreaker (Steam). No DLC needed.
- Archipelago 0.6.4 or newer.
- `riftbreaker.apworld`, copied into Archipelago's `custom_worlds` folder.

## Installing

1. Put `riftbreaker.apworld` in `custom_worlds` and restart the Archipelago Launcher.
2. In the Launcher, open **The Riftbreaker Client**. On first start it unpacks the Archipelago mod into
   `<Riftbreaker>/mods/Archipelago/`. If the game folder isn't found, use `/gamedir <path>`.
   - To install the mod by hand instead, unzip `RiftbreakerAP-<version>.zip` into `<Riftbreaker>/mods/`, so that the
     folder `<Riftbreaker>/mods/Archipelago/` exists. Local mods must be folders. The game ignores the manifest of a
     zipped local mod and flags it as incompatible.

## Playing

1. Open the client and connect it to the server with your slot name **before starting the game**. On connecting, the
   client writes this seed's item names into the mod. The game reads them when it starts, so if the game was already
   running, restart it.
2. Start a **new open campaign**. A campaign is bound to the first slot that connects to it. Loading a campaign that
   belongs to another slot or seed does nothing, and the client warns you.
3. Leave the client running while you play. Research checks and the goal are sent automatically. Received items appear
   within about two seconds, and the HUD shows "Archipelago: received …".

## Commands

- `/status`: game folder, log file, campaign binding, and checks seen.
- `/gamedir <path>`: set the game folder.
- `/resync`: re-read the game log.

Console commands in the game:
- `ap_status`: show the Archipelago status.
- `ap_research`: open the research screen.
- `ap_hub`: place a free Communications Hub, for testing. The game only enables research while you own one.
