"""Build the Riftbreaker Archipelago mod and apworld.

Usage: python -I build.py [--install] [--release]

  dist/Archipelago/          the game mod as an unpacked folder (Archipelago.manifest + mod files)
  dist/Archipelago.zip       the same folder zipped, bundled into the apworld for the client to install
  dist/riftbreaker.apworld   the apworld
  dist/RiftbreakerAP-<v>.zip --release: mods/Archipelago + apworld + YAML + SETUP.md
  --install                  copy the apworld to Archipelago's custom_worlds and the mod folder to <game>/mods

Why a folder: the game's local mod loader (Exor::ExternalContentUserMods, "ModsDirectory") accepts both folders and
.zip files in <game>/mods, but only reads a WorkspaceManifest from folders. A local .zip mod is mounted with name
"unknown" and game version "Unknown", which triggers the incompatible-mods popup. The local parser reads the keys
author, homepage, version, game_version and tags (a comma-separated string) from any *.manifest file in the folder.
"""
import os
import re
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
GAME_DIR = os.path.dirname(PROJECT)
MOD_SRC = os.path.join(PROJECT, "mod")
APWORLD_SRC = os.path.join(PROJECT, "apworld", "riftbreaker")
DIST = os.path.join(PROJECT, "dist")
CUSTOM_WORLDS = r"C:\ProgramData\Archipelago\custom_worlds"

MOD_FOLDER = "Archipelago"   # must match client.MOD_FOLDER
MOD_VERSION = "0.4.0"
LEGACY_FILES = ["{6F1D2A5C-3B8E-4C7A-9E21-5A0B7C4D8E13}" + ext for ext in (".zip", ".crc", ".manifest")]
FALLBACK_GAME_VERSION = "EXE: 1186 DATA: 847"


def game_version() -> str:
    log = os.path.join(os.path.expanduser("~"), "Documents", "The Riftbreaker", "exor_logs.txt")
    try:
        m = re.search(r"The Riftbreaker (EXE: \d+ DATA: \d+)", open(log, encoding="utf-8", errors="ignore").read())
        if m:
            return m.group(1)
    except OSError:
        pass
    return FALLBACK_GAME_VERSION


def manifest() -> str:
    return (
        "WorkspaceManifest\n{\n"
        '\tauthor "Riftbreaker AP"\n'
        '\thomepage ""\n'
        f'\tversion "{MOD_VERSION}"\n'
        f'\tgame_version "{game_version()}"\n'
        '\ttags "Other"\n'
        "}\n"
    )


def build_mod() -> str:
    """Builds dist/Archipelago/ and dist/Archipelago.zip; returns the zip path."""
    folder = os.path.join(DIST, MOD_FOLDER)
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    shutil.copytree(MOD_SRC, folder)
    with open(os.path.join(folder, MOD_FOLDER + ".manifest"), "w", encoding="utf-8", newline="\n") as f:
        f.write(manifest())
    out = os.path.join(DIST, MOD_FOLDER + ".zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(folder):
            for name in sorted(files):
                full = os.path.join(root, name)
                z.write(full, os.path.relpath(full, folder).replace("\\", "/"))
    for stale in LEGACY_FILES:
        p = os.path.join(DIST, stale)
        if os.path.exists(p):
            os.remove(p)
    return out


def build_apworld(mod_zip: str) -> str:
    out = os.path.join(DIST, "riftbreaker.apworld")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(APWORLD_SRC):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "mod")]
            for f in sorted(files):
                if f.endswith(".pyc"):
                    continue
                full = os.path.join(root, f)
                z.write(full, "riftbreaker/" + os.path.relpath(full, APWORLD_SRC).replace("\\", "/"))
        z.write(mod_zip, "riftbreaker/mod/" + os.path.basename(mod_zip))
    return out


def build_release(apworld: str) -> str:
    """dist/RiftbreakerAP-<version>.zip: mods/Archipelago folder, the apworld, a player YAML and the setup guide."""
    out = os.path.join(DIST, f"RiftbreakerAP-{MOD_VERSION}.zip")
    folder = os.path.join(DIST, MOD_FOLDER)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(folder):
            for name in sorted(files):
                full = os.path.join(root, name)
                z.write(full, "mods/" + MOD_FOLDER + "/" + os.path.relpath(full, folder).replace("\\", "/"))
        z.write(apworld, "riftbreaker.apworld")
        z.write(os.path.join(PROJECT, "yaml", "The Riftbreaker.yaml"), "The Riftbreaker.yaml")
        z.write(os.path.join(APWORLD_SRC, "docs", "setup_en.md"), "SETUP.md")
    return out


def main() -> None:
    mod_zip = build_mod()
    apworld = build_apworld(mod_zip)
    print("built", os.path.join(DIST, MOD_FOLDER))
    print("built", apworld)
    if "--release" in sys.argv:
        print("built", build_release(apworld))
    if "--install" in sys.argv:
        shutil.copy2(apworld, os.path.join(CUSTOM_WORLDS, "riftbreaker.apworld"))
        mods = os.path.join(GAME_DIR, "mods")
        target = os.path.join(mods, MOD_FOLDER)
        if os.path.isdir(target):
            shutil.rmtree(target)
        shutil.copytree(os.path.join(DIST, MOD_FOLDER), target)
        for stale in LEGACY_FILES:
            p = os.path.join(mods, stale)
            if os.path.exists(p):
                os.remove(p)
        print("installed apworld ->", CUSTOM_WORLDS)
        print("installed mod ->", target)


if __name__ == "__main__":
    main()
