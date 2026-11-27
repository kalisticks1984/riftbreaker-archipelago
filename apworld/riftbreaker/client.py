"""The Riftbreaker Archipelago client.

The game's Lua has no networking or file writing, so the client and the in-game mod talk through files:

game -> client
  Documents/The Riftbreaker/exor_logs.txt (the game's log). The mod writes lines like
    [AP] HELLO 1 | BOUND <session> | MISMATCH <session> | CHECKS id,id | CHECK id | BIOME acid | GOAL arcology
client -> game
  <game>/archipelago/inbox.lua, which the mod loads every 2 seconds:
    return { session = "<seed>:<slot>", items = { <item id>, ... } }

A campaign is bound to the first slot that connects to it. Reports from a campaign bound to a different slot
are ignored, so an old save never sends checks to a new seed.
"""
import asyncio
import ctypes
import io
import json
import os
import pkgutil
import re
import shutil
import zipfile
from typing import Optional, Set

import Utils
from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, logger, server_loop
from NetUtils import ClientStatus

from . import data as D

SETTINGS_FILE = "riftbreaker_client.json"
GAME_FOLDER = "Riftbreaker"
GAME_EXE = os.path.join("bin", "riftbreaker_win_release.exe")
MOD_FOLDER = "Archipelago"
LOCALIZATION_FILE = "gui/archipelago_localizations.csv"
LOC_HEADER = ";ENGLISH;POLISH;RUSSIAN;FRENCH;GERMAN;SPANISH;BRASILIAN;CHINESE_SP;JAPANESE;KOREAN"
RESEARCH_NAME_KEY = "gui/menu/research/name/"
RESEARCH_DESC_KEY = "gui/menu/research/description/"
FLAG_PROGRESSION, FLAG_USEFUL, FLAG_TRAP = 0b001, 0b010, 0b100
LEGACY_MOD_FILES = ["{6F1D2A5C-3B8E-4C7A-9E21-5A0B7C4D8E13}" + ext for ext in (".zip", ".crc", ".manifest")]
LINE_RE = re.compile(r"\[AP\] ([A-Z_]+) ?([^\r\n]*)")


# ------------------------------------------------------------------ paths
def documents_dir() -> str:
    """The user's Documents folder (follows OneDrive/folder redirection)."""
    try:
        from ctypes import wintypes
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:   # CSIDL_PERSONAL
            return buf.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def find_game_dir() -> Optional[str]:
    libs = []
    for root in (os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), os.environ.get("ProgramFiles", "")):
        if root:
            libs.append(os.path.join(root, "Steam"))
    for steam in list(libs):
        try:
            with open(os.path.join(steam, "steamapps", "libraryfolders.vdf"), encoding="utf-8", errors="ignore") as f:
                libs += [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s+"([^"]+)"', f.read())]
        except OSError:
            pass
    for lib in libs:
        p = os.path.join(lib, "steamapps", "common", GAME_FOLDER)
        if os.path.isfile(os.path.join(p, GAME_EXE)):
            return p
    return None


def lua_string(s: str) -> str:
    """Quote for Lua 5.1 (no \\u escapes): printable ASCII as-is, everything else as \\ddd bytes."""
    out = []
    for b in s.encode("utf-8"):
        c = chr(b)
        if c in '"\\' or b < 32 or b > 126:
            out.append("\\%d" % b)
        else:
            out.append(c)
    return '"' + "".join(out) + '"'


def write_atomic(path: str, text: str) -> None:
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                return
    except OSError:
        pass
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def install_mod(game_dir: str) -> str:
    """Unpack the bundled mod into <game>/mods/Archipelago. Returns a status message.

    The game only reads a mod's manifest (version, game version) for folder mods; zipped local mods show up as
    "unknown" / incompatible, so the mod is installed unpacked."""
    blob = pkgutil.get_data(__name__.rsplit(".", 1)[0], "mod/" + MOD_FOLDER + ".zip")
    if not blob:
        return "The mod is missing from the apworld."
    mods = os.path.join(game_dir, "mods")
    target = os.path.join(mods, MOD_FOLDER)
    for legacy in LEGACY_MOD_FILES:
        try:
            os.remove(os.path.join(mods, legacy))
        except OSError:
            pass
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        # The localization file is rewritten per seed by the client, so it does not count as out of date.
        wanted = {n for n in z.namelist() if not n.endswith("/") and n != LOCALIZATION_FILE}
        up_to_date = os.path.isdir(target)
        if up_to_date:
            for name in wanted:
                try:
                    with open(os.path.join(target, name), "rb") as f:
                        if f.read() != z.read(name):
                            up_to_date = False
                            break
                except OSError:
                    up_to_date = False
                    break
        if up_to_date:
            return "Archipelago mod is installed and up to date."
        if os.path.isdir(target):
            shutil.rmtree(target)
        z.extractall(target)
    return "Installed the Archipelago mod into the game's mods folder (restart the game if it was running)."


# ------------------------------------------------------------------ game state from the log
class GameState:
    def __init__(self) -> None:
        self.bound: Optional[str] = None
        self.mismatch: Optional[str] = None
        self.research: Set[int] = set()
        self.goals: Set[str] = set()
        self.hello = False


class RiftbreakerCommandProcessor(ClientCommandProcessor):
    def _cmd_gamedir(self, path: str = "") -> bool:
        """Show or set The Riftbreaker install folder."""
        ctx: RiftbreakerContext = self.ctx
        if path:
            if not os.path.isfile(os.path.join(path, GAME_EXE)):
                self.output(f"No {GAME_EXE} in {path}")
                return False
            ctx.rb_settings["game_dir"] = path
            ctx.save_settings()
            self.output(install_mod(path))
        self.output(f"Game folder: {ctx.game_dir}")
        return True

    def _cmd_status(self) -> bool:
        """Show the bridge status."""
        ctx: RiftbreakerContext = self.ctx
        st = ctx.rb_state
        self.output(f"Game folder: {ctx.game_dir}")
        self.output(f"Game log: {ctx.log_path} ({'found' if os.path.exists(ctx.log_path) else 'missing'})")
        self.output(f"Campaign bound to: {st.bound or '(not yet)'}; this slot: {ctx.session or '(not connected)'}")
        if st.mismatch:
            self.output(f"The loaded campaign belongs to another slot ({st.mismatch}). Start a new open campaign.")
        self.output(f"Mod running in the game: {'yes' if st.hello else 'not seen in the current log'}")
        self.output(f"Research checks seen: {len(st.research)}")
        self.output(f"Items received: {len(ctx.items_received)}")
        return True

    def _cmd_resync(self) -> bool:
        """Re-read the whole game log."""
        ctx: RiftbreakerContext = self.ctx
        ctx.log_pos = 0
        ctx.rb_state = GameState()
        return True


class RiftbreakerContext(CommonContext):
    game = D.GAME
    command_processor = RiftbreakerCommandProcessor
    items_handling = 0b111

    def __init__(self, server_address, password):
        super().__init__(server_address, password)
        self.rb_settings = self.load_settings()
        self.rb_state = GameState()
        self.rb_slot: dict = {}
        self.rb_seed: Optional[str] = None
        self.log_pos = 0
        self.log_ctime = None
        self.goal_sent = False
        self.warned_mismatch = None

    # ---- settings / paths
    def load_settings(self) -> dict:
        try:
            with open(Utils.user_path(SETTINGS_FILE), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def save_settings(self) -> None:
        with open(Utils.user_path(SETTINGS_FILE), "w", encoding="utf-8") as f:
            json.dump(self.rb_settings, f, indent=2)

    @property
    def game_dir(self) -> Optional[str]:
        return self.rb_settings.get("game_dir") or find_game_dir()

    @property
    def log_path(self) -> str:
        return os.path.join(documents_dir(), "The Riftbreaker", "exor_logs.txt")

    @property
    def session(self) -> Optional[str]:
        # CommonContext (0.6.7) never stores RoomInfo's seed_name on itself, so it is captured in on_package.
        seed = self.rb_seed or self.seed_name
        if not seed or self.slot is None:
            return None
        return f"{seed}:{self.slot}"

    # ---- AP callbacks
    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict):
        if cmd == "RoomInfo":
            self.rb_seed = args.get("seed_name") or self.rb_seed
        elif cmd == "Connected":
            self.rb_slot = args.get("slot_data", {}) or {}
            if self.rb_slot.get("protocol") != D.PROTOCOL:
                logger.warning("This slot was generated with a different version of the Riftbreaker apworld.")
            # Ask what every research location holds, to label the research tree.
            locations = sorted(set(self.missing_locations) | set(self.checked_locations))
            if locations:
                asyncio.create_task(self.send_msgs([{"cmd": "LocationScouts", "locations": locations,
                                                     "create_as_hint": 0}]))
        elif cmd == "LocationInfo":
            # CommonContext has already stored these as NetworkItems in locations_info.
            self.write_research_labels(list(self.locations_info.values()))
        self.write_inbox()

    def write_research_labels(self, infos) -> None:
        """Write the research tree's names/descriptions for this seed into the mod's localization file.
        The game reads localization when it starts, so changes show after a game restart."""
        if not self.game_dir:
            return
        node_by_loc = {n["id"]: n for n in D.RANDOMIZED}
        rows = [LOC_HEADER]
        for info in infos:
            node = node_by_loc.get(info.location)
            if not node:
                continue
            item = self.item_names.lookup_in_slot(info.item, info.player)
            receiver = self.player_names.get(info.player, "?")
            own = info.player == self.slot
            name = item if own else f"{item} ({receiver})"
            if info.flags & FLAG_TRAP:
                worth = "a trap"
            elif info.flags & FLAG_PROGRESSION:
                worth = "progression: it unlocks further checks"
            elif info.flags & FLAG_USEFUL:
                worth = "useful, though not required"
            else:
                worth = "filler"
            target = "you" if own else receiver
            desc = (f"Archipelago check. Completing this research sends {item} to {target}. "
                    f"This item is {worth}.")
            clean = lambda s: s.replace(";", ",").replace("\r", " ").replace("\n", " ")
            rows.append(f"{RESEARCH_NAME_KEY}{node['name']};{clean(name)};;;;;;;;;")
            rows.append(f"{RESEARCH_DESC_KEY}{node['name']};{clean(desc)};;;;;;;;;")
        if len(rows) == 1:
            return
        path = os.path.join(self.game_dir, "mods", MOD_FOLDER, *LOCALIZATION_FILE.split("/"))
        text = "\r\n".join(rows) + "\r\n"
        try:
            with open(path, encoding="utf-8") as f:
                if f.read() == text:
                    return
        except OSError:
            pass
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        logger.info(f"Research tree now shows this seed's items ({len(rows) // 2} research). "
                    "If The Riftbreaker is already running, restart it to see them.")

    async def connection_closed(self):
        await super().connection_closed()
        self.write_inbox()

    async def shutdown(self):
        self.write_inbox(force_disconnected=True)
        await super().shutdown()

    def run_gui(self):
        from kvui import GameManager

        class RiftbreakerManager(GameManager):
            logging_pairs = [("Client", "Archipelago")]
            base_title = "Archipelago The Riftbreaker Client"

        self.ui = RiftbreakerManager(self)
        self.ui_task = asyncio.create_task(self.ui.async_run(), name="UI")

    # ---- client -> game
    def write_inbox(self, force_disconnected: bool = False) -> None:
        """Write everything the mod needs. Called on every bridge tick; unchanged content is not rewritten."""
        if not self.game_dir or not self.session:
            return
        box = os.path.join(self.game_dir, "archipelago")
        os.makedirs(box, exist_ok=True)
        connected = (not force_disconnected and self.server is not None and self.server.socket is not None
                     and not self.server.socket.closed)
        ids = ", ".join(str(i.item) for i in self.items_received)
        labels = []
        for i in self.items_received:
            name = self.item_names.lookup_in_game(i.item)
            sender = self.player_names.get(i.player, "?")
            labels.append(lua_string(name if i.player == self.slot else f"{name} (from {sender})"))
        text = (f"return {{ session = {lua_string(self.session)}, connected = {'true' if connected else 'false'}, "
                f"player = {lua_string(self.auth or '')},\n  items = {{ {ids} }},\n"
                f"  labels = {{ {', '.join(labels)} }} }}\n")
        write_atomic(os.path.join(box, "inbox.lua"), text)

    # ---- game -> client
    def read_log(self) -> None:
        path = self.log_path
        if not os.path.exists(path):
            return
        stat = os.stat(path)
        size = stat.st_size
        if size < self.log_pos or stat.st_ctime != self.log_ctime:   # the game restarted and began a new log
            self.log_ctime = stat.st_ctime
            self.log_pos = 0
            self.rb_state = GameState()
        if size == self.log_pos:
            return
        with open(path, "rb") as f:
            f.seek(self.log_pos)
            chunk = f.read()
        end = chunk.rfind(b"\n")
        if end < 0:
            return
        self.log_pos += end + 1
        for m in LINE_RE.finditer(chunk[:end + 1].decode("utf-8", "replace")):
            self.handle(m.group(1), m.group(2).strip())

    def handle(self, kind: str, arg: str) -> None:
        st = self.rb_state
        if kind == "HELLO":                     # new map or save loaded: forget the previous binding
            st.bound, st.mismatch, st.hello = None, None, True
        elif kind == "BOUND":
            st.bound, st.mismatch = arg, None
        elif kind == "MISMATCH":
            st.bound, st.mismatch = None, arg
            if self.warned_mismatch != arg:
                self.warned_mismatch = arg
                logger.warning("The loaded campaign belongs to a different slot or seed. "
                               "Start a new open campaign for this slot.")
        elif st.bound and st.bound == self.session:
            if kind in ("CHECKS", "CHECK"):
                st.research |= {int(x) for x in arg.split(",") if x.strip().isdigit()}
            elif kind == "GOAL":
                st.goals.add(arg)

    async def sync(self) -> None:
        if not self.rb_slot or self.server is None or self.server.socket.closed:
            return
        new = self.rb_state.research & self.missing_locations
        if new:
            await self.send_msgs([{"cmd": "LocationChecks", "locations": sorted(new)}])
        if not self.goal_sent and self.rb_slot.get("goal") in self.rb_state.goals:
            self.goal_sent = True
            await self.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])


async def bridge_loop(ctx: RiftbreakerContext) -> None:
    warned = False
    installed = False
    while not ctx.exit_event.is_set():
        try:
            if not ctx.game_dir:
                if not warned:
                    logger.warning("The Riftbreaker was not found. Use /gamedir <path> to set its folder.")
                    warned = True
            else:
                if not installed:
                    installed = True
                    logger.info(install_mod(ctx.game_dir))
                ctx.write_inbox()
                ctx.read_log()
                await ctx.sync()
        except Exception as e:   # keep the bridge alive
            logger.exception(f"Bridge error: {e}")
        await asyncio.sleep(1)


def launch(*args) -> None:
    async def main(argv):
        parser = get_base_parser(description="The Riftbreaker Archipelago client")
        parsed = parser.parse_args(argv)
        ctx = RiftbreakerContext(parsed.connect, parsed.password)
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        bridge = asyncio.create_task(bridge_loop(ctx), name="bridge")
        await ctx.exit_event.wait()
        bridge.cancel()
        await ctx.shutdown()

    import colorama
    colorama.just_fix_windows_console()
    asyncio.run(main(list(args)))
