"""The Riftbreaker Archipelago client.

The game's Lua has no networking or file writing, so the client and the in-game mod talk through files:

game -> client
  Documents/The Riftbreaker/exor_logs.txt (the game's log). The mod writes lines like
    [AP] HELLO 3 | MODE story | BOUND <session> | CHECKS id,id | CHECK id | BIOME acid | SURVIVE 1260 |
    GOAL arcology | EL_DEPOSIT <seq> carbonium 500 | EL_WITHDRAW <seq> energy 2000
client -> game
  <game>/archipelago/inbox.lua, which the mod loads every 2 seconds:
    return { session, connected, player, mode, survival_map, energy_link, energy, items, labels, grants, tracker }
  <game>/mods/Archipelago/gui/archipelago_localizations.csv: this seed's research labels (read at game start)

A campaign is bound to the first slot that connects to it; reports from a campaign bound to another slot are ignored.
In co-op only the host runs this client: everyone in the session shares the slot.
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
from typing import Dict, List, Optional, Set

import Utils
from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, logger, server_loop
from NetUtils import ClientStatus

from . import data as D

SETTINGS_FILE = "riftbreaker_client.json"
GAME_FOLDER = "Riftbreaker"
GAME_EXE = os.path.join("bin", "riftbreaker_win_release.exe")
MOD_FOLDER = "Archipelago"
LOCALIZATION_FILE = "gui/archipelago_localizations.csv"
LEGACY_MOD_FILES = ["{6F1D2A5C-3B8E-4C7A-9E21-5A0B7C4D8E13}" + ext for ext in (".zip", ".crc", ".manifest")]
LOC_HEADER = ";ENGLISH;POLISH;RUSSIAN;FRENCH;GERMAN;SPANISH;BRASILIAN;CHINESE_SP;JAPANESE;KOREAN"
RESEARCH_NAME_KEY = "gui/menu/research/name/"
RESEARCH_DESC_KEY = "gui/menu/research/description/"
FLAG_PROGRESSION, FLAG_USEFUL, FLAG_TRAP = 0b001, 0b010, 0b100
LINE_RE = re.compile(r"\[AP\] ([A-Z_]+) ?([^\r\n]*)")

# Energy Link exchange rates: Energy Link units (J) per unit of each resource.
EL_RATES = {"carbonium": 100_000, "steel": 100_000, "cobalt": 500_000, "palladium": 1_000_000,
            "titanium": 1_000_000, "uranium": 2_000_000, "energy": 10_000}
EL_NAMES = {"steel": "ironium"}


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


def format_joules(value: float) -> str:
    for unit, scale in (("TJ", 1e12), ("GJ", 1e9), ("MJ", 1e6), ("kJ", 1e3)):
        if abs(value) >= scale:
            return f"{value / scale:.2f} {unit}"
    return f"{value:.0f} J"


# ------------------------------------------------------------------ game state from the log
class GameState:
    def __init__(self) -> None:
        self.bound: Optional[str] = None
        self.mismatch: Optional[str] = None
        self.mode: Optional[str] = None
        self.done: Set[int] = set()
        self.biomes: Set[str] = set()
        self.survival_seconds = 0
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
        self.output(f"Slot mode: {ctx.rb_slot.get('game_mode', '?')}; game mode: {st.mode or '(not seen)'}")
        self.output(f"Campaign bound to: {st.bound or '(not yet)'}; this slot: {ctx.session or '(not connected)'}")
        if st.mismatch:
            self.output(f"The loaded campaign belongs to another slot ({st.mismatch}). Start a new game.")
        self.output(f"Mod running in the game: {'yes' if st.hello else 'not seen in the current log'}")
        self.output(f"Checks seen: {len(ctx.found_locations())}; items received: {len(ctx.items_received)}")
        if ctx.rb_slot.get("energy_link"):
            self.output(f"Energy Link pool: {format_joules(ctx.el_value or 0)}")
        return True

    def _cmd_tracker(self) -> bool:
        """List the non-research checks and what is in logic."""
        ctx: RiftbreakerContext = self.ctx
        for line in ctx.tracker_lines(include_research=False):
            self.output(line)
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
        self.logic: Optional[D.Logic] = None
        self.location_reqs: Dict[str, D.Req] = {}
        self.log_pos = 0
        self.log_ctime = None
        self.goal_sent = False
        self.warned_mismatch = None
        self.el_value: Optional[float] = None
        self.tracker_widget = None

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

    @property
    def el_key(self) -> str:
        return f"EnergyLink{self.team}"

    def el_state(self) -> dict:
        """Per-session Energy Link bookkeeping, persisted so requests are never applied twice."""
        store = self.rb_settings.setdefault("energy_link", {})
        return store.setdefault(self.session or "?", {"done": 0, "grants": []})

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
            self.logic = D.Logic(self.rb_slot.get("game_mode", "open"), self.rb_slot.get("survival_map", "desert"))
            self.location_reqs = self.logic.locations(self.rb_slot)
            locations = sorted(set(self.missing_locations) | set(self.checked_locations))
            msgs = []
            if locations:
                msgs.append({"cmd": "LocationScouts", "locations": locations, "create_as_hint": 0})
            if self.rb_slot.get("energy_link"):
                self.tags.add("EnergyLink")
                msgs += [{"cmd": "ConnectUpdate", "tags": sorted(self.tags)},
                         {"cmd": "SetNotify", "keys": [self.el_key]},
                         {"cmd": "Get", "keys": [self.el_key]}]
            if msgs:
                asyncio.create_task(self.send_msgs(msgs))
        elif cmd == "LocationInfo":
            self.write_research_labels(list(self.locations_info.values()))
        elif cmd == "Retrieved":
            if self.el_key in args.get("keys", {}):
                self.el_value = float(args["keys"][self.el_key] or 0)
        elif cmd == "SetReply":
            if args.get("key") == self.el_key:
                self.el_value = float(args.get("value") or 0)
                if "riftbreaker_seq" in args:
                    self.finish_withdraw(args)
        self.write_inbox()

    async def connection_closed(self):
        await super().connection_closed()
        self.write_inbox()

    async def shutdown(self):
        self.write_inbox(force_disconnected=True)
        await super().shutdown()

    def run_gui(self):
        from kvui import GameManager

        ctx = self

        class RiftbreakerManager(GameManager):
            logging_pairs = [("Client", "Archipelago")]
            base_title = "Archipelago The Riftbreaker Client"

            def build(self):
                container = super().build()
                from kivy.uix.label import Label
                from kivy.uix.scrollview import ScrollView
                scroll = ScrollView(do_scroll_x=False)
                label = Label(text="Connect to see the tracker.", markup=True, size_hint_y=None,
                              halign="left", valign="top", padding=(12, 12))
                label.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)),
                           texture_size=lambda inst, s: setattr(inst, "height", s[1]))
                scroll.add_widget(label)
                self.add_client_tab("Tracker", scroll)
                ctx.tracker_widget = label
                return container

        self.ui = RiftbreakerManager(self)
        self.ui_task = asyncio.create_task(self.ui.async_run(), name="UI")

    # ---- research labels
    def write_research_labels(self, infos) -> None:
        """Write the research tree's names/descriptions for this seed into the mod's localization file.
        The game reads localization when it starts, so changes show after a game restart."""
        if not self.game_dir or not self.logic:
            return
        node_by_loc = {n["location_id"]: n for n in self.logic.randomized}
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
            desc = f"Archipelago check. Completing this research sends {item} to {target}. This item is {worth}."
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

    # ---- tracker
    def item_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for i in self.items_received:
            name = self.item_names.lookup_in_game(i.item)
            counts[name] = counts.get(name, 0) + 1
        return counts

    def in_logic(self, req: D.Req, counts: Dict[str, int]) -> bool:
        items, groups = req
        has = lambda needs: all(counts.get(n, 0) >= c for n, c in needs)
        if not has(items):
            return False
        return all(any(has(self.logic.biome_req(b)[0]) for b in g) for g in groups)

    def tracker_lines(self, include_research: bool = True) -> List[str]:
        if not self.logic:
            return ["Not connected."]
        counts = self.item_counts()
        checked = set(self.checked_locations)
        sections: Dict[str, List[str]] = {}
        research = [0, 0, 0]   # done, in logic, total
        for name, req in self.location_reqs.items():
            loc_id = D.LOCATION_NAME_TO_ID[name]
            done = loc_id in checked
            ok = done or self.in_logic(req, counts)
            if name.startswith("Research: "):
                research[0] += done
                research[1] += ok and not done
                research[2] += 1
                if not include_research:
                    continue
                section = "Research"
            elif name.startswith("Survive "):
                section = "Survival time"
            elif name.startswith("Arrive in "):
                section = "Biome arrivals"
            elif name.startswith("Complete "):
                section = "Story missions"
            else:
                section = "Builds"
            mark = "[done]" if done else ("[in logic]" if ok else "[locked]")
            sections.setdefault(section, []).append(f"{mark} {name}")
        lines = [f"Research: {research[0]}/{research[2]} done, {research[1]} more in logic"]
        order = ["Builds", "Story missions", "Biome arrivals", "Survival time", "Research"]
        for section in order:
            if section in sections:
                entries = sections[section]
                lines.append(f"{section} ({sum(e.startswith('[done]') for e in entries)}/{len(entries)}):")
                lines += ["  " + e for e in sorted(entries, key=lambda e: (not e.startswith('[in'), e))]
        return lines

    def tracker_summary(self) -> str:
        """One line for the in-game ap_tracker command."""
        if not self.logic:
            return ""
        counts = self.item_counts()
        checked = set(self.checked_locations)
        parts: Dict[str, List[int]] = {}
        for name, req in self.location_reqs.items():
            kind = ("Research" if name.startswith("Research: ") else "Survival" if name.startswith("Survive ")
                    else "Arrivals" if name.startswith("Arrive in ") else "Missions" if name.startswith("Complete ")
                    else "Builds")
            p = parts.setdefault(kind, [0, 0, 0])
            done = D.LOCATION_NAME_TO_ID[name] in checked
            p[0] += done
            p[1] += (not done) and self.in_logic(req, counts)
            p[2] += 1
        return "Archipelago: " + " | ".join(f"{k} {v[0]}/{v[2]} ({v[1]} in logic)" for k, v in parts.items())

    def refresh_tracker(self) -> None:
        if self.tracker_widget is not None and self.logic:
            text = "\n".join(self.tracker_lines())
            if self.tracker_widget.text != text:
                self.tracker_widget.text = text

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
        grants = ", ".join(f"{{ {g[0]}, {lua_string(g[1])}, {g[2]} }}" for g in self.el_state()["grants"])
        energy = lua_string(format_joules(self.el_value)) if self.el_value is not None else "nil"
        text = (f"return {{ session = {lua_string(self.session)}, connected = {'true' if connected else 'false'},\n"
                f"  player = {lua_string(self.auth or '')}, mode = {lua_string(self.rb_slot.get('game_mode', 'open'))},\n"
                f"  survival_map = {lua_string(self.rb_slot.get('survival_map', ''))},\n"
                f"  energy_link = {'true' if self.rb_slot.get('energy_link') else 'false'}, energy = {energy},\n"
                f"  tracker = {lua_string(self.tracker_summary())},\n"
                f"  items = {{ {ids} }},\n  labels = {{ {', '.join(labels)} }},\n  grants = {{ {grants} }} }}\n")
        write_atomic(os.path.join(box, "inbox.lua"), text)

    # ---- Energy Link
    def energy_link_request(self, kind: str, seq: int, resource: str, amount: int) -> None:
        state = self.el_state()
        if seq <= state["done"] or resource not in EL_RATES or not self.rb_slot.get("energy_link"):
            return
        state["done"] = seq
        self.save_settings()
        joules = amount * EL_RATES[resource]
        if kind == "deposit":
            asyncio.create_task(self.send_msgs([{"cmd": "Set", "key": self.el_key, "default": 0, "want_reply": True,
                                                 "operations": [{"operation": "add", "value": joules}]}]))
            logger.info(f"Energy Link: deposited {amount} {EL_NAMES.get(resource, resource)} ({format_joules(joules)}).")
        else:
            asyncio.create_task(self.send_msgs([{
                "cmd": "Set", "key": self.el_key, "default": 0, "want_reply": True,
                "operations": [{"operation": "add", "value": -joules}, {"operation": "max", "value": 0}],
                "riftbreaker_seq": seq, "riftbreaker_resource": resource, "riftbreaker_amount": amount}]))

    def finish_withdraw(self, args: dict) -> None:
        state = self.el_state()
        seq = int(args["riftbreaker_seq"])
        if any(g[0] == seq for g in state["grants"]):
            return
        resource = args.get("riftbreaker_resource", "carbonium")
        rate = EL_RATES.get(resource, 1)
        given = max(0.0, float(args.get("original_value") or 0) - float(args.get("value") or 0))
        units = int(given // rate)
        leftover = given - units * rate
        if leftover > 0:   # return what could not buy a whole unit
            asyncio.create_task(self.send_msgs([{"cmd": "Set", "key": self.el_key, "default": 0,
                                                 "operations": [{"operation": "add", "value": leftover}]}]))
        state["grants"].append([seq, resource, units])
        state["grants"] = state["grants"][-50:]
        self.save_settings()
        logger.info(f"Energy Link: withdrew {units} {EL_NAMES.get(resource, resource)} "
                    f"(asked for {args.get('riftbreaker_amount')}).")

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
        elif kind == "MODE":
            st.mode = arg
        elif kind == "BOUND":
            st.bound, st.mismatch = arg, None
        elif kind == "MISMATCH":
            st.bound, st.mismatch = None, arg
            if self.warned_mismatch != arg:
                self.warned_mismatch = arg
                logger.warning("The loaded campaign belongs to a different slot or seed. Start a new game.")
        elif st.bound and st.bound == self.session:
            if kind in ("CHECKS", "CHECK"):
                st.done |= {int(x) for x in arg.split(",") if x.strip().isdigit()}
            elif kind == "BIOME":
                st.biomes.add(arg)
            elif kind == "SURVIVE" and arg.isdigit():
                st.survival_seconds = max(st.survival_seconds, int(arg))
            elif kind == "GOAL":
                st.goals.add(arg)
            elif kind in ("EL_DEPOSIT", "EL_WITHDRAW"):
                parts = arg.split()
                if len(parts) == 3 and parts[0].isdigit() and parts[2].isdigit():
                    self.energy_link_request("deposit" if kind == "EL_DEPOSIT" else "withdraw",
                                             int(parts[0]), parts[1], int(parts[2]))

    def found_locations(self) -> Set[int]:
        st = self.rb_state
        out = set(st.done)
        if self.rb_slot.get("game_mode") == "open" and self.rb_slot.get("biome_arrival_checks"):
            out |= {D.BIOME_LOCATION_ID[b] for b in st.biomes if b in D.BIOME_LOCATION_ID}
        if self.rb_slot.get("game_mode") == "survival":
            step = int(self.rb_slot.get("survival_time_interval", 0))
            if step > 0:
                minutes = st.survival_seconds // 60
                out |= {D.SURVIVAL_TIME_BASE + m for m in range(step, min(minutes, D.SURVIVAL_MAX_MINUTES) + 1, step)}
        return out

    def goal_reached(self) -> bool:
        if self.rb_slot.get("game_mode") == "survival":
            return "survival" in self.rb_state.goals
        return self.rb_slot.get("goal") in self.rb_state.goals

    async def sync(self) -> None:
        if not self.rb_slot or self.server is None or self.server.socket.closed:
            return
        new = self.found_locations() & self.missing_locations
        if new:
            await self.send_msgs([{"cmd": "LocationChecks", "locations": sorted(new)}])
        if not self.goal_sent and self.goal_reached():
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
                ctx.refresh_tracker()
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
