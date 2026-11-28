from dataclasses import dataclass

from Options import Choice, PerGameCommonOptions, Range, Toggle


class GameMode(Choice):
    """Which game mode to play.
    open: the open campaign (start in the Jungle, biomes unlock through Biome items).
    story: the story campaign (biomes and missions unlock through the story; no DLC needed).
    survival: one survival map (pick it with Survival Map); win by surviving the mission duration."""
    display_name = "Game Mode"
    option_open = 0
    option_story = 1
    option_survival = 2
    default = 0


class Goal(Choice):
    """Campaign goal (open and story; survival is won by surviving).
    arcology: complete the Arcology assembly.
    prime_rift: return to Earth (open: build and activate the Prime Rift Station; story: finish the campaign)."""
    display_name = "Goal"
    option_arcology = 0
    option_prime_rift = 1
    default = 0


class SurvivalMap(Choice):
    """Survival map, when Game Mode is survival. The map must be unlocked in your game profile."""
    display_name = "Survival Map"
    option_acid = 0
    option_caverns = 1
    option_desert = 2
    option_ice = 3
    option_jungle = 4
    option_magma = 5
    option_metallic = 6
    option_swamp = 7
    default = 2


class SurvivalTimeInterval(Range):
    """Survival: a check every this many minutes survived, up to 90 minutes (the standard mission duration).
    0 disables time checks."""
    display_name = "Survival Time Check Interval"
    range_start = 0
    range_end = 30
    default = 10


class BuildChecks(Toggle):
    """Building milestones are checks: Headquarters levels 3-7, Laboratory, Planetary Scanner, Rare Element Mine and
    the megastructures (whichever exist in the game mode)."""
    display_name = "Build Checks"
    default = 1


class BiomeArrivalChecks(Toggle):
    """Open campaign: arriving in each biome other than the Jungle for the first time is a check."""
    display_name = "Biome Arrival Checks"
    default = 1


class MissionChecks(Toggle):
    """Story campaign: completing each of the 16 base story missions is a check."""
    display_name = "Mission Checks"
    default = 1


class EarlyProgression(Choice):
    """Place key progression early (sphere 1): Orbital Scanning, Cobalt Handling, the Laboratory and the first
    Headquarters upgrade (whichever the mode uses).
    off: normal placement. early: anywhere in the multiworld's first sphere. local: in your own first sphere."""
    display_name = "Early Progression"
    option_off = 0
    option_early = 1
    option_local = 2
    default = 0


class EnergyLink(Toggle):
    """Energy Link: deposit spare resources or electricity into the multiworld's shared Energy Link pool and
    withdraw from it (console commands ap_deposit / ap_withdraw / ap_energylink)."""
    display_name = "Energy Link"
    default = 1


@dataclass
class RiftbreakerOptions(PerGameCommonOptions):
    game_mode: GameMode
    goal: Goal
    survival_map: SurvivalMap
    survival_time_interval: SurvivalTimeInterval
    build_checks: BuildChecks
    biome_arrival_checks: BiomeArrivalChecks
    mission_checks: MissionChecks
    early_progression: EarlyProgression
    energy_link: EnergyLink
