"""Extract the game data gen_open.py needs from The Riftbreaker's packs.

Usage: python -I extract_data.py <game_dir> <out_dir>

Later packs override earlier ones (packs are applied in name order, like the game mounts them).
"""
import glob
import os
import sys
import zipfile

WANTED_PREFIXES = (
    "scripts/research/", "scripts/difficulty/", "logic/campaigns/open/", "missions/survival/", "gui/",
)


def main(game_dir: str, out_dir: str) -> None:
    packs = sorted(glob.glob(os.path.join(game_dir, "packs", "*_win_data.zip")))
    packs += sorted(glob.glob(os.path.join(game_dir, "packs", "startup", "*_win_startup.zip")))
    count = 0
    for pack in packs:
        with zipfile.ZipFile(pack) as z:
            for info in z.infolist():
                name = info.filename
                if info.file_size == 0 or not name.startswith(WANTED_PREFIXES):
                    continue
                if name.startswith("gui/") and not name.endswith("_localizations.csv"):
                    continue
                dest = os.path.join(out_dir, *name.split("/"))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(z.read(name))
                count += 1
    print(f"extracted {count} files from {len(packs)} packs into {out_dir}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
