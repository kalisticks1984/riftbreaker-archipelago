from dataclasses import dataclass

from Options import Choice, PerGameCommonOptions


class Goal(Choice):
    """What you need to do to finish.
    arcology: complete the Arcology assembly (Arcology Workshop with the Gravitational Hyper Lens, Hydroponic Lab
    and Nanobot Center).
    prime_rift: go on to build and activate the Prime Rift Station and return to Earth (the end credits)."""
    display_name = "Goal"
    option_arcology = 0
    option_prime_rift = 1
    default = 0


@dataclass
class RiftbreakerOptions(PerGameCommonOptions):
    goal: Goal
