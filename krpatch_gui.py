import os
import re
import json
import time
import datetime
import difflib
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
from pathlib import Path

APP_VERSION = "0.1"

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "krpatch_config.json"
API_URL = "https://retrodb.info/krpatch/api/list"

DEFAULT_CONSOLE_MAPPING = {
    "FC": ("Nintendo", "FC"), "FAMICOM": ("Nintendo", "FC"),
    "NES": ("Nintendo", "NES"),
    "SFC": ("Nintendo", "SFC"), "SUPERFAMICOM": ("Nintendo", "SFC"),
    "SNES": ("Nintendo", "SNES"),
    "N64": ("Nintendo", "N64"), "NINTENDO64": ("Nintendo", "N64"),
    "GC": ("Nintendo", "GameCube"), "GAMECUBE": ("Nintendo", "GameCube"),
    "WII": ("Nintendo", "Wii"),
    "GB": ("Nintendo", "Game Boy"), "GAMEBOY": ("Nintendo", "Game Boy"),
    "GBC": ("Nintendo", "Game Boy Color"), "GAMEBOYCOLOR": ("Nintendo", "Game Boy Color"),
    "GBA": ("Nintendo", "Game Boy Advance"), "GAMEBOYADVANCE": ("Nintendo", "Game Boy Advance"),
    "NDS": ("Nintendo", "NDS"), "DS": ("Nintendo", "NDS"), "NINTENDODS": ("Nintendo", "NDS"),
    "3DS": ("Nintendo", "3DS"), "NINTENDO3DS": ("Nintendo", "3DS"),
    "VB": ("Nintendo", "Virtual Boy"),

    # 소니
    "PS1": ("Sony", "PS1"), "PSX": ("Sony", "PS1"), "PLAYSTATION": ("Sony", "PS1"), "PLAYSTATION1": ("Sony", "PS1"),
    "PS2": ("Sony", "PS2"), "PLAYSTATION2": ("Sony", "PS2"),
    "PS3": ("Sony", "PS3"),
    "PSP": ("Sony", "PSP"), "PLAYSTATIONPORTABLE": ("Sony", "PSP"),
    "PSV": ("Sony", "PS Vita"), "PSVITA": ("Sony", "PS Vita"), "VITA": ("Sony", "PS Vita"),

    # 세가
    "GEN": ("SEGA", "Mega Drive"), "MD": ("SEGA", "Mega Drive"), "MEGADRIVE": ("SEGA", "Mega Drive"), "GENESIS": ("SEGA", "Mega Drive"),
    "SAT": ("SEGA", "Saturn"), "SATURN": ("SEGA", "Saturn"),
    "DC": ("SEGA", "Dreamcast"), "DREAMCAST": ("SEGA", "Dreamcast"),
    "GG": ("SEGA", "Game Gear"), "GAMEGEAR": ("SEGA", "Game Gear"),
    "SMS": ("SEGA", "Master System"), "MASTERSYSTEM": ("SEGA", "Master System"),

    # 마이크로소프트
    "XBOX": ("Microsoft", "XBOX"),
}

DEFAULT_CONFIG = {
    "api_key": "855a97d9d5e304ac60f1c0ee940e6a94",
    "base_dir": r"C:\share\KRPATCH",
    "cache_file": "retrodb_krpatch_cache.json",
    "cache_ttl": 3600,
    "version_filename": ".retrodb_ver",
    "rename_log_file": "krpatch_folder_rename.log",
    "console_mapping": {k: list(v) for k, v in DEFAULT_CONSOLE_MAPPING.items()},
}


class InitialConfigDialog(tk.Toplevel):
    def __init__(self, parent, initial_api_key: str, initial_base_dir: str):
        super().__init__(parent)
        self.title("초기 환경설정")
        self.geometry("560x210")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.api_key_var = tk.StringVar(value=initial_api_key)
        self.base_dir_var = tk.StringVar(value=initial_base_dir)
        self.saved = False

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

    def _build_ui(self):
        container = ttk.Frame(self, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            container,
            text="환경설정 파일(krpatch_config.json)이 없어 새로 생성합니다. 발급키와 폴더를 지정해 주세요.",
        ).pack(anchor=tk.W, pady=(0, 14))

        key_row = ttk.Frame(container)
        key_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(key_row, text="API 발급키:", width=12).pack(side=tk.LEFT)
        key_entry = ttk.Entry(key_row, textvariable=self.api_key_var)
        key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        key_entry.focus_set()

        dir_row = ttk.Frame(container)
        dir_row.pack(fill=tk.X, pady=(0, 18))
        ttk.Label(dir_row, text="최상위 폴더:", width=12).pack(side=tk.LEFT)
        dir_entry = ttk.Entry(dir_row, textvariable=self.base_dir_var)
        dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(dir_row, text="찾아보기", command=self.browse_folder).pack(side=tk.LEFT)

        btn_row = ttk.Frame(container)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="취소", command=self.on_cancel).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(btn_row, text="저장", command=self.on_save).pack(side=tk.RIGHT)

    def browse_folder(self):
        current = self.base_dir_var.get().strip()
        initial_dir = current if current and os.path.isdir(current) else str(SCRIPT_DIR)
        selected = filedialog.askdirectory(title="최상위 한글패치 폴더 선택", initialdir=initial_dir, parent=self)
        if selected:
            self.base_dir_var.set(selected)

    def on_save(self):
        self.saved = True
        self.destroy()

    def on_cancel(self):
        self.saved = False
        self.destroy()


def prompt_initial_config(parent: tk.Tk, config_data: dict) -> dict:
    dlg = InitialConfigDialog(
        parent,
        initial_api_key=str(config_data.get("api_key", "")),
        initial_base_dir=str(config_data.get("base_dir", r"C:\share\KRPATCH")),
    )
    parent.wait_window(dlg)
    if dlg.saved:
        config_data["api_key"] = dlg.api_key_var.get().strip()
        config_data["base_dir"] = dlg.base_dir_var.get().strip() or r"C:\share\KRPATCH"
    return config_data


def load_or_create_config(config_path: Path = CONFIG_PATH, parent: tk.Tk | None = None) -> tuple[dict, bool]:
    """설정 파일을 로드하거나, 없으면 대화상자로 입력받아 생성. 반환: (설정 dict, 신규 생성 여부)"""
    is_new_file = not config_path.exists()
    if is_new_file:
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))
        if parent is not None:
            cfg = prompt_initial_config(parent, cfg)
        with open(config_path, "w", encoding="utf-8") as cf:
            json.dump(cfg, cf, ensure_ascii=False, indent=2)
        return cfg, True

    with open(config_path, "r", encoding="utf-8") as cf:
        user_cfg = json.load(cf)

    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    for k, v in user_cfg.items():
        if k != "console_mapping" and v is not None:
            merged[k] = v

    if isinstance(user_cfg.get("console_mapping"), dict):
        custom_map = {}
        for code, pair in user_cfg["console_mapping"].items():
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                custom_map[str(code).upper()] = [str(pair[0]), str(pair[1])]
        if custom_map:
            merged["console_mapping"] = custom_map

    return merged, False


def apply_runtime_config(cfg: dict):
    global CONFIG, API_KEY, BASE_DIR, CACHE_FILE, CACHE_TTL
    global VERSION_FILENAME, RENAME_LOG_FILE, CONSOLE_MAPPING
    global CACHE_PATH, RENAME_LOG_PATH, EXCLUDE_FILENAMES

    CONFIG = cfg
    API_KEY = str(CONFIG.get("api_key", "")).strip()
    BASE_DIR = str(CONFIG.get("base_dir", r"C:\share\KRPATCH"))
    CACHE_FILE = str(CONFIG.get("cache_file", "retrodb_krpatch_cache.json"))
    CACHE_TTL = int(CONFIG.get("cache_ttl", 3600))
    VERSION_FILENAME = str(CONFIG.get("version_filename", ".retrodb_ver"))
    RENAME_LOG_FILE = str(CONFIG.get("rename_log_file", "krpatch_folder_rename.log"))
    CONSOLE_MAPPING = {
        str(k).upper(): (str(v[0]), str(v[1]))
        for k, v in CONFIG.get("console_mapping", {}).items()
        if isinstance(v, (list, tuple)) and len(v) == 2
    }

    CACHE_PATH = SCRIPT_DIR / CACHE_FILE
    RENAME_LOG_PATH = SCRIPT_DIR / RENAME_LOG_FILE
    EXCLUDE_FILENAMES = {VERSION_FILENAME.lower()}


# 모듈 임포트 시에도 기본 설정을 즉시 적용 (GUI 실행 시에는 KrpatchGUI에서 대화상자 연동)
apply_runtime_config(json.loads(json.dumps(DEFAULT_CONFIG)))
if CONFIG_PATH.exists():
    _loaded_cfg, _ = load_or_create_config(CONFIG_PATH, parent=None)
    apply_runtime_config(_loaded_cfg)

API_URL = "https://retrodb.info/krpatch/api/list"

# 제외할 파일 확장자 목록
EXCLUDE_EXTENSIONS = {".txt", ".lnk", ".mhtml"}

MAKER_FOLDER_PATTERN = re.compile(r"^(?P<title>.+?)\s*\[(?P<maker>[^\]]+)\]$")
_LOG_LOCK = threading.Lock()


def append_rename_log(old_path: Path, new_path: Path):
    now = datetime.datetime.now()
    ms = f"{now.microsecond // 1000:03d}"
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S") + f":{ms}"
    line = f"[{timestamp}] [{old_path.resolve()}] => [{new_path.resolve()}]\n"
    with _LOG_LOCK:
        with open(RENAME_LOG_PATH, "a", encoding="utf-8") as lf:
            lf.write(line)


def normalize_console_code(console_code: str) -> str:
    return re.sub(r"[\s\-_/]+", "", str(console_code or "")).upper()


def get_console_info(console_code: str) -> tuple:
    if not console_code:
        return ("ETC", "Unknown")
    clean_code = normalize_console_code(console_code)
    if clean_code in CONSOLE_MAPPING:
        return CONSOLE_MAPPING[clean_code]
    for key, info in CONSOLE_MAPPING.items():
        if key in clean_code or clean_code in key:
            return info
    return ("ETC", str(console_code))


def normalize_text(text: str) -> str:
    return re.sub(r"[\s\-_:·.,!'\"()\[\]]+", "", text).lower()


def sanitize_windows_name(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', " ", name)
    return re.sub(r"\s+", " ", cleaned).strip().rstrip(".")


def extract_folder_title_and_maker(folder_name: str) -> tuple[str, str | None]:
    match = MAKER_FOLDER_PATTERN.match(folder_name.strip())
    if match:
        return match.group("title").strip(), match.group("maker").strip()
    return folder_name.strip(), None


def extract_folder_title_query(folder_name: str) -> str:
    title, _ = extract_folder_title_and_maker(folder_name)
    return title


def has_maker_in_folder_name(folder_name: str) -> bool:
    return bool(MAKER_FOLDER_PATTERN.match(folder_name.strip()))


def ensure_maker_in_folder_name(folder_path: Path, title: str, maker: str) -> Path:
    """폴더명에 [제작자]가 없을 때 '타이틀 [제작자]' 형태로 폴더명 변경 및 로그 기록"""
    if not folder_path.exists() or not folder_path.is_dir():
        return folder_path
    if has_maker_in_folder_name(folder_path.name):
        return folder_path

    clean_title = sanitize_windows_name(title or extract_folder_title_query(folder_path.name))
    clean_maker = sanitize_windows_name(maker)
    if not clean_title or not clean_maker or clean_maker == "제작자미상":
        return folder_path

    new_name = f"{clean_title} [{clean_maker}]"
    if new_name == folder_path.name:
        return folder_path

    new_path = folder_path.parent / new_name
    if new_path.exists():
        return folder_path

    old_resolved = folder_path.resolve()
    folder_path.rename(new_path)
    append_rename_log(old_resolved, new_path.resolve())
    return new_path


def fetch_patch_list(force_refresh: bool = False) -> list:
    if not force_refresh and CACHE_PATH.exists():
        mtime = os.path.getmtime(CACHE_PATH)
        if time.time() - mtime < CACHE_TTL:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("patches", [])

    if not API_KEY or API_KEY == "여기에_발급받은_API_키를_입력하세요":
        raise RuntimeError(f"API 키가 설정되지 않았습니다. {CONFIG_PATH.name}의 api_key를 입력해 주세요.")

    headers = {"X-API-Key": API_KEY}
    while True:
        resp = requests.get(API_URL, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return data.get("patches", [])
        elif resp.status_code in (429, 503):
            retry_after = int(resp.headers.get("Retry-After", 60))
            time.sleep(retry_after)
        else:
            raise RuntimeError(f"API 호출 실패 (상태 코드: {resp.status_code}): {resp.text}")


def extract_maker(item: dict) -> str:
    for key in ("maker", "author", "distributor", "creator", "translator"):
        if item.get(key):
            return str(item[key]).strip()
    return "제작자미상"


def extract_patch_date(item: dict) -> str:
    raw = item.get("patch_date") or item.get("date") or item.get("updated_at") or ""
    return str(raw).split("T")[0].strip()


def extract_patch_url(patch_info: dict | None) -> str:
    if patch_info:
        for key in ("url", "link", "page_url", "detail_url", "source_url"):
            val = patch_info.get(key)
            if isinstance(val, str) and val.strip().startswith(("http://", "https://")):
                return val.strip()
    return "https://retrodb.info/krpatch"


def is_console_exact_match(folder_console: str, patch_console: str) -> bool:
    """CONSOLE_MAPPING 기준으로 양쪽 기종이 같은 기종인지 판별"""
    f_raw = str(folder_console or "").strip()
    p_raw = str(patch_console or "").strip()
    if not f_raw or not p_raw:
        return False

    f_mfg, f_sys = get_console_info(f_raw)
    p_mfg, p_sys = get_console_info(p_raw)

    if f_mfg != "ETC" and p_mfg != "ETC":
        return f_mfg == p_mfg and normalize_text(f_sys) == normalize_text(p_sys)

    return normalize_console_code(f_raw) == normalize_console_code(p_raw)


def find_strict_exact_matches(patches: list, console: str, folder_name: str) -> list:
    """기종, 타이틀, (폴더에 표기된 경우) 제작자가 모두 정확히 일치하는 DB 패치 목록 반환"""
    title_part, maker_part = extract_folder_title_and_maker(folder_name)
    norm_title = normalize_text(title_part)
    if not norm_title:
        return []

    norm_maker = normalize_text(maker_part) if maker_part else None

    exact_matches = []
    for p in patches:
        if not is_console_exact_match(console, str(p.get("console", ""))):
            continue
        if normalize_text(str(p.get("title", ""))) != norm_title:
            continue
        if norm_maker is not None:
            patch_maker = extract_maker(p)
            if patch_maker == "제작자미상" or normalize_text(patch_maker) != norm_maker:
                continue
        exact_matches.append(p)

    return exact_matches


def search_patches_by_title(patches: list, query: str) -> list:
    q = query.strip()
    if not q:
        return patches
    norm_q = normalize_text(q)
    q_lower = q.lower()

    scored = []
    for p in patches:
        title = str(p.get("title", ""))
        norm_t = normalize_text(title)
        if norm_q and norm_q == norm_t:
            scored.append((0, p))
        elif norm_q and norm_q in norm_t:
            scored.append((1, p))
        elif q_lower in title.lower():
            scored.append((2, p))
        elif difflib.SequenceMatcher(None, norm_q, norm_t).ratio() >= 0.45:
            scored.append((3, p))

    scored.sort(key=lambda x: (x[0], str(x[1].get("title", ""))))
    return [item for _, item in scored]


def check_file_dates_outdated(game_dir: Path, patch_date_str: str) -> tuple[bool, str]:
    if not patch_date_str:
        return False, ""

    try:
        patch_date = datetime.datetime.fromisoformat(str(patch_date_str).split("T")[0])
    except ValueError:
        return False, ""

    newest_file_time = None
    for file_path in game_dir.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() in EXCLUDE_EXTENSIONS or file_path.name.lower() in EXCLUDE_FILENAMES:
            continue
        try:
            file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
            if newest_file_time is None or file_mtime > newest_file_time:
                newest_file_time = file_mtime
        except Exception:
            continue

    if newest_file_time is None:
        return False, "날짜없음"

    has_older_file = newest_file_time < patch_date
    return has_older_file, newest_file_time.strftime("%Y-%m-%d")


def read_ver_file(folder_path: Path) -> dict:
    ver_file_path = folder_path / VERSION_FILENAME
    if ver_file_path.exists():
        try:
            with open(ver_file_path, "r", encoding="utf-8") as vf:
                return json.load(vf)
        except Exception:
            return {}
    return {}


def save_matched_ver_info(folder_path: Path, console_code: str, patch_info: dict):
    ver_file_path = folder_path / VERSION_FILENAME
    manufacturer, system_name = get_console_info(console_code)
    data = {
        "status": "matched",
        "not_in_db": False,
        "id": patch_info.get("id"),
        "title": patch_info.get("title", ""),
        "maker": extract_maker(patch_info),
        "version": str(patch_info.get("version", "")),
        "patch_date": extract_patch_date(patch_info),
        "console_raw": patch_info.get("console") or console_code,
        "console_normalized": f"{manufacturer}/{system_name}",
        "checked_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(ver_file_path, "w", encoding="utf-8") as vf:
        json.dump(data, vf, ensure_ascii=False, indent=2)


def save_unmatched_ver_info(folder_path: Path, console_code: str):
    ver_file_path = folder_path / VERSION_FILENAME
    manufacturer, system_name = get_console_info(console_code)
    title, maker_opt = extract_folder_title_and_maker(folder_path.name)
    maker = maker_opt if maker_opt else "제작자미상"

    data = {
        "status": "unmatched",
        "not_in_db": True,
        "title": title,
        "maker": maker,
        "folder": folder_path.name,
        "console_raw": console_code,
        "console_normalized": f"{manufacturer}/{system_name}",
        "checked_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(ver_file_path, "w", encoding="utf-8") as vf:
        json.dump(data, vf, ensure_ascii=False, indent=2)


def check_patch_status(folder_path: Path, patch_info: dict) -> tuple[bool, str, bool]:
    latest_ver = str(patch_info.get("version", "")).strip()
    latest_id = str(patch_info.get("id", "")).strip()
    saved_data = read_ver_file(folder_path)

    if saved_data.get("not_in_db") or saved_data.get("status") == "unmatched":
        return False, "미등록", True

    saved_id = str(saved_data.get("id", "")).strip()
    saved_ver = str(saved_data.get("version", "")).strip()
    is_latest = (bool(latest_id) and saved_id == latest_id) or (bool(latest_ver) and saved_ver == latest_ver)
    local_label = saved_ver or saved_id or "미기록"
    return is_latest, local_label, False


def discover_game_folders(base_path: Path):
    game_folders = []
    seen_dirs = set()

    for item in base_path.iterdir():
        if not item.is_dir() or item.name.startswith("."):
            continue

        item_upper = normalize_console_code(item.name)
        sub_dirs = [sub for sub in item.iterdir() if sub.is_dir() and not sub.name.startswith(".")]

        if item_upper in CONSOLE_MAPPING or any(
            normalize_console_code(s.name) in CONSOLE_MAPPING for s in sub_dirs
        ):
            if item_upper in CONSOLE_MAPPING:
                for game_dir in sub_dirs:
                    resolved = game_dir.resolve()
                    if resolved not in seen_dirs:
                        seen_dirs.add(resolved)
                        game_folders.append((game_dir, item.name))
            else:
                for console_dir in sub_dirs:
                    for game_dir in console_dir.iterdir():
                        if game_dir.is_dir() and not game_dir.name.startswith("."):
                            resolved = game_dir.resolve()
                            if resolved not in seen_dirs:
                                seen_dirs.add(resolved)
                                game_folders.append((game_dir, console_dir.name))
        else:
            for console_dir in sub_dirs:
                nested_dirs = [g for g in console_dir.iterdir() if g.is_dir() and not g.name.startswith(".")]
                if nested_dirs:
                    for game_dir in nested_dirs:
                        resolved = game_dir.resolve()
                        if resolved not in seen_dirs:
                            seen_dirs.add(resolved)
                            game_folders.append((game_dir, console_dir.name))
                else:
                    resolved = console_dir.resolve()
                    if resolved not in seen_dirs:
                        seen_dirs.add(resolved)
                        game_folders.append((console_dir, item.name))

    return game_folders


def evaluate_all_folders(
    base_path: Path,
    patches: list,
    show_maker_in_folder: bool = False,
    create_missing_ver: bool = False,
) -> tuple[list[dict], list[dict]]:
    """기종+타이틀+제작자 정확 일치(단일 건)만 자동 처리하고, 그 외 미등록 폴더는 DB 선택 대상으로 반환"""
    game_folders = discover_game_folders(base_path)
    records = []
    select_queue_items = []
    seen_keys = set()

    for game_dir, console_name in game_folders:
        manufacturer, system_name = get_console_info(console_name)
        console_label = f"{manufacturer}/{system_name}"
        folder_name = game_dir.name
        has_ver_file = (game_dir / VERSION_FILENAME).exists()
        saved_ver = read_ver_file(game_dir) if has_ver_file else {}
        is_marked_unmatched = bool(saved_ver.get("not_in_db") or saved_ver.get("status") == "unmatched")

        title_query = extract_folder_title_query(folder_name)
        strict_matches = find_strict_exact_matches(patches, console_name, folder_name)

        matched_patch = None
        if saved_ver.get("id") and not is_marked_unmatched:
            matched_patch = next(
                (p for p in patches if str(p.get("id", "")).strip() == str(saved_ver.get("id")).strip()),
                None,
            )

        needs_dialog = False
        if not matched_patch and not is_marked_unmatched:
            if len(strict_matches) == 1:
                matched_patch = strict_matches[0]
            else:
                needs_dialog = True

        if not has_ver_file and not is_marked_unmatched and needs_dialog:
            select_queue_items.append({
                "folder_path": str(game_dir.resolve()),
                "folder_name": folder_name,
                "console_raw": console_name,
                "title_query": title_query,
            })

        if matched_patch and not is_marked_unmatched:
            title = matched_patch.get("title", folder_name)
            maker = extract_maker(matched_patch)
            version = str(matched_patch.get("version", "-"))
            patch_date = extract_patch_date(matched_patch)

            if show_maker_in_folder:
                updated_dir = ensure_maker_in_folder_name(game_dir, title, maker)
                if updated_dir != game_dir:
                    game_dir = updated_dir
                    folder_name = game_dir.name

            if not has_ver_file and create_missing_ver:
                save_matched_ver_info(game_dir, console_name, matched_patch)
                has_ver_file = True
            elif has_ver_file and show_maker_in_folder:
                save_matched_ver_info(game_dir, console_name, matched_patch)

            is_latest, local_ver, _ = check_patch_status(game_dir, matched_patch)
            file_is_older, newest_file_date = check_file_dates_outdated(game_dir, patch_date)
            effective_is_latest = is_latest and not file_is_older

            unique_key = (console_label, normalize_text(title), normalize_text(maker))
            if unique_key in seen_keys:
                continue
            seen_keys.add(unique_key)

            status_tags = ["최신" if effective_is_latest else f"구버전({local_ver})"]
            if not has_ver_file:
                status_tags.append("ver파일없음")

            records.append({
                "console": console_label,
                "console_raw": console_name,
                "title": title,
                "maker": maker,
                "version": version,
                "patch_date": patch_date or "-",
                "file_date": newest_file_date or "-",
                "status": " / ".join(status_tags),
                "is_latest": effective_is_latest,
                "file_is_older": file_is_older,
                "has_ver_file": has_ver_file,
                "unmatched": False,
                "folder_path": str(game_dir.resolve()),
                "patch_url": extract_patch_url(matched_patch),
            })
        else:
            if show_maker_in_folder and saved_ver.get("maker"):
                updated_dir = ensure_maker_in_folder_name(game_dir, title_query, str(saved_ver.get("maker")))
                if updated_dir != game_dir:
                    game_dir = updated_dir
                    folder_name = game_dir.name

            unique_key = (console_label, str(game_dir.resolve()))
            if unique_key in seen_keys:
                continue
            seen_keys.add(unique_key)

            _, newest_file_date = check_file_dates_outdated(game_dir, "")
            if is_marked_unmatched:
                status_text = "DB없음(.retrodb_ver)"
            elif not has_ver_file:
                status_text = "DB선택필요(.retrodb_ver없음)"
            else:
                status_text = "DB미등록"

            records.append({
                "console": console_label,
                "console_raw": console_name,
                "title": folder_name,
                "maker": "-",
                "version": "-",
                "patch_date": "-",
                "file_date": newest_file_date or "-",
                "status": status_text,
                "is_latest": False,
                "file_is_older": False,
                "has_ver_file": has_ver_file,
                "unmatched": True,
                "folder_path": str(game_dir.resolve()),
                "patch_url": extract_patch_url(None),
            })

    return records, select_queue_items


class DBSelectDialog(tk.Toplevel):
    def __init__(self, parent, patches: list, initial_query: str, folder_path: Path):
        super().__init__(parent)
        self.folder_path = Path(folder_path).resolve()
        self.title(f"DB 선택 - {self.folder_path.name}")
        self.geometry("860x490")
        self.transient(parent)
        self.grab_set()

        self.patches = patches
        self.result_action: str = "cancel"
        self.selected_patch: dict | None = None
        self.shown_patches: list[dict] = []

        self.query_var = tk.StringVar(value=initial_query)
        self._build_ui()
        self.perform_search()

    def _build_ui(self):
        path_box = ttk.Frame(self, padding=(10, 10, 10, 0))
        path_box.pack(fill=tk.X)

        ttk.Label(path_box, text="절대경로:").pack(side=tk.LEFT, padx=(0, 6))
        path_entry = ttk.Entry(path_box)
        path_entry.insert(0, str(self.folder_path))
        path_entry.configure(state="readonly")
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(path_box, text="경로열기", command=self.open_folder).pack(side=tk.LEFT)

        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="제목 검색:").pack(side=tk.LEFT, padx=(0, 6))
        entry = ttk.Entry(top, textvariable=self.query_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        entry.bind("<Return>", lambda _e: self.perform_search())
        entry.focus_set()

        ttk.Button(top, text="검색", command=self.perform_search).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(top, text="초기화", command=self.reset_search).pack(side=tk.LEFT)

        mid = ttk.Frame(self, padding=(10, 0, 10, 10))
        mid.pack(fill=tk.BOTH, expand=True)

        columns = ("no", "console", "title", "maker", "version", "patch_date")
        self.tree = ttk.Treeview(mid, columns=columns, show="headings", selectmode="browse")

        headings = {
            "no": ("#", 45, tk.CENTER),
            "console": ("기종", 100, tk.CENTER),
            "title": ("DB 타이틀", 340, tk.W),
            "maker": ("제작자", 140, tk.W),
            "version": ("버전", 80, tk.CENTER),
            "patch_date": ("패치일", 105, tk.CENTER),
        }
        for col, (text, width, anchor) in headings.items():
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor=anchor)

        self.tree.bind("<Double-1>", lambda _e: self.on_confirm())

        vsb = ttk.Scrollbar(mid, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        bottom = ttk.Frame(self, padding=(10, 0, 10, 10))
        bottom.pack(fill=tk.X)

        self.count_var = tk.StringVar(value="검색 결과: 0건")
        ttk.Label(bottom, textvariable=self.count_var).pack(side=tk.LEFT)

        ttk.Button(bottom, text="취소", command=self.on_cancel).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(bottom, text="DB없음", command=self.on_no_db).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(bottom, text="확인", command=self.on_confirm).pack(side=tk.RIGHT)

    def open_folder(self):
        if not self.folder_path.exists():
            messagebox.showwarning("경로 없음", f"폴더가 존재하지 않습니다:\n{self.folder_path}", parent=self)
            return
        try:
            os.startfile(str(self.folder_path))
        except Exception as e:
            messagebox.showerror("폴더 열기 실패", str(e), parent=self)

    def reset_search(self):
        self.query_var.set("")
        self.perform_search()

    def perform_search(self):
        query = self.query_var.get()
        self.shown_patches = search_patches_by_title(self.patches, query)

        for item in self.tree.get_children():
            self.tree.delete(item)

        for idx, p in enumerate(self.shown_patches, 1):
            self.tree.insert(
                "",
                tk.END,
                values=(
                    idx,
                    str(p.get("console", "-")).upper(),
                    p.get("title", ""),
                    extract_maker(p),
                    str(p.get("version", "-")),
                    extract_patch_date(p) or "-",
                ),
            )

        if self.tree.get_children():
            first_id = self.tree.get_children()[0]
            self.tree.selection_set(first_id)
            self.tree.focus(first_id)

        self.count_var.set(f"검색 결과: {len(self.shown_patches)}건")

    def on_confirm(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("안내", "목록에서 적용할 DB 항목을 선택해 주세요.", parent=self)
            return
        idx = self.tree.index(sel[0])
        if 0 <= idx < len(self.shown_patches):
            self.selected_patch = self.shown_patches[idx]
            self.result_action = "select"
            self.destroy()

    def on_no_db(self):
        self.result_action = "no_db"
        self.selected_patch = None
        self.destroy()

    def on_cancel(self):
        self.result_action = "cancel"
        self.selected_patch = None
        self.destroy()


class KrpatchGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"RetroDB 한글패치 관리자 v{APP_VERSION}")
        self.geometry("1300x660")
        self.all_patches: list[dict] = []
        self.all_records: list[dict] = []
        self.item_to_record: dict[str, dict] = {}
        self.current_mode = "all"
        self._handling_ambiguous = False
        self.show_maker_var = tk.BooleanVar(value=False)

        self._build_ui()
        self.after(50, self._init_config_and_scan)

    def _init_config_and_scan(self):
        cfg, _ = load_or_create_config(CONFIG_PATH, parent=self)
        apply_runtime_config(cfg)
        self.run_scan(mode="all", force_refresh=False, prompt_ambiguous=True, create_missing_ver=True)

    def _build_ui(self):
        top_frame = ttk.Frame(self, padding=10)
        top_frame.pack(fill=tk.X)

        ttk.Button(top_frame, text="전체 목록", command=lambda: self.apply_filter("all")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(top_frame, text="최신", command=lambda: self.apply_filter("latest")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(top_frame, text="구버전", command=lambda: self.apply_filter("outdated")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(top_frame, text="DB없음", command=lambda: self.apply_filter("no-db")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(top_frame, text="캐시초기화", command=self.clear_cache_and_reload).pack(side=tk.LEFT, padx=(0, 6))

        ttk.Checkbutton(
            top_frame,
            text="폴더에 제작자 이름 표시",
            variable=self.show_maker_var,
            command=self.on_toggle_show_maker,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(top_frame, text="폴더 열기", command=self.open_selected_folder).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(top_frame, text="URL 열기", command=self.open_selected_url).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(top_frame, text="DB 선택", command=self.open_db_select_dialog).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(
            top_frame,
            text="다시 스캔",
            command=lambda: self.run_scan(
                mode=self.current_mode,
                force_refresh=False,
                prompt_ambiguous=True,
                create_missing_ver=True,
            ),
        ).pack(side=tk.RIGHT)

        table_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("no", "console", "title", "maker", "version", "patch_date", "file_date", "status")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        headings = {
            "no": ("#", 50, tk.CENTER),
            "console": ("기종", 140, tk.W),
            "title": ("타이틀", 310, tk.W),
            "maker": ("제작자", 130, tk.W),
            "version": ("DB버전", 90, tk.CENTER),
            "patch_date": ("DB패치일", 110, tk.CENTER),
            "file_date": ("파일수정일", 110, tk.CENTER),
            "status": ("상태", 190, tk.W),
        }

        for col, (text, width, anchor) in headings.items():
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor=anchor)

        self.tree.bind("<Double-1>", lambda _event: self.open_selected_folder())

        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.status_var = tk.StringVar(value="준비 중...")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=(10, 4))
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def on_toggle_show_maker(self):
        self.run_scan(mode=self.current_mode, force_refresh=False, prompt_ambiguous=False, create_missing_ver=False)

    def run_scan(
        self,
        mode: str = "all",
        force_refresh: bool = False,
        prompt_ambiguous: bool = False,
        create_missing_ver: bool = False,
    ):
        self.current_mode = mode
        show_maker = bool(self.show_maker_var.get())
        self.status_var.set("폴더 및 RetroDB 데이터를 불러오는 중...")

        def worker():
            try:
                base_path = Path(BASE_DIR)
                if not base_path.exists():
                    raise FileNotFoundError(f"경로를 찾을 수 없습니다: {BASE_DIR}")
                patches = fetch_patch_list(force_refresh=force_refresh)
                records, select_queue_items = evaluate_all_folders(
                    base_path,
                    patches,
                    show_maker_in_folder=show_maker,
                    create_missing_ver=create_missing_ver,
                )
                self.after(0, lambda: self._on_scan_complete(patches, records, select_queue_items, mode, prompt_ambiguous))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda msg=err_msg: self._on_scan_error(msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_complete(
        self,
        patches: list[dict],
        records: list[dict],
        select_queue_items: list[dict],
        mode: str,
        prompt_ambiguous: bool,
    ):
        self.all_patches = patches
        self.all_records = records
        self.apply_filter(mode)

        if prompt_ambiguous and select_queue_items and not self._handling_ambiguous:
            self._process_ambiguous_queue(select_queue_items)

    def _process_ambiguous_queue(self, queue: list[dict]):
        self._handling_ambiguous = True
        updated_any = False
        try:
            for item in queue:
                folder_path = Path(item["folder_path"])
                if not folder_path.exists() or (folder_path / VERSION_FILENAME).exists():
                    continue
                dlg = DBSelectDialog(
                    self,
                    self.all_patches,
                    initial_query=item["title_query"],
                    folder_path=folder_path,
                )
                self.wait_window(dlg)
                if dlg.result_action == "select" and dlg.selected_patch:
                    target_dir = folder_path
                    if self.show_maker_var.get():
                        target_dir = ensure_maker_in_folder_name(
                            target_dir,
                            dlg.selected_patch.get("title", item["title_query"]),
                            extract_maker(dlg.selected_patch),
                        )
                    save_matched_ver_info(target_dir, item.get("console_raw", ""), dlg.selected_patch)
                    updated_any = True
                elif dlg.result_action == "no_db":
                    save_unmatched_ver_info(folder_path, item.get("console_raw", ""))
                    updated_any = True
        finally:
            self._handling_ambiguous = False

        if updated_any:
            self.run_scan(mode=self.current_mode, force_refresh=False, prompt_ambiguous=False, create_missing_ver=False)

    def _on_scan_error(self, error_msg: str):
        self.status_var.set(f"오류: {error_msg}")
        messagebox.showerror("오류", error_msg)

    def apply_filter(self, mode: str):
        self.current_mode = mode

        if mode == "latest":
            filtered = [r for r in self.all_records if r["is_latest"]]
            label = "최신"
        elif mode == "outdated":
            filtered = [r for r in self.all_records if not r["unmatched"] and not r["is_latest"]]
            label = "구버전"
        elif mode == "no-db":
            filtered = [r for r in self.all_records if r["unmatched"]]
            label = "DB없음"
        else:
            filtered = self.all_records
            label = "전체 목록"

        for item in self.tree.get_children():
            self.tree.delete(item)
        self.item_to_record.clear()

        for idx, r in enumerate(filtered, 1):
            item_id = self.tree.insert(
                "",
                tk.END,
                values=(
                    idx,
                    r["console"],
                    r["title"],
                    r["maker"],
                    r["version"],
                    r["patch_date"],
                    r["file_date"],
                    r["status"],
                ),
            )
            self.item_to_record[item_id] = r

        self.status_var.set(f"[{label}] 표시 항목: {len(filtered)}개 / 전체 스캔: {len(self.all_records)}개")

    def get_selected_record(self) -> dict | None:
        selected = self.tree.selection()
        if not selected:
            return None
        return self.item_to_record.get(selected[0])

    def open_selected_folder(self):
        rec = self.get_selected_record()
        if not rec:
            messagebox.showinfo("안내", "폴더를 열 항목을 먼저 선택해 주세요.")
            return

        folder_path = rec.get("folder_path")
        if not folder_path or not os.path.exists(folder_path):
            messagebox.showwarning("경로 없음", f"폴더가 존재하지 않습니다:\n{folder_path}")
            return

        try:
            os.startfile(folder_path)
        except Exception as e:
            messagebox.showerror("폴더 열기 실패", str(e))

    def open_selected_url(self):
        rec = self.get_selected_record()
        target_url = rec.get("patch_url") if rec else "https://retrodb.info/krpatch"
        try:
            webbrowser.open(target_url or "https://retrodb.info/krpatch")
        except Exception as e:
            messagebox.showerror("URL 열기 실패", str(e))

    def open_db_select_dialog(self):
        rec = self.get_selected_record()
        if not rec:
            messagebox.showinfo("안내", "DB를 선택할 항목을 먼저 선택해 주세요.")
            return

        if not self.all_patches:
            try:
                self.all_patches = fetch_patch_list(force_refresh=False)
            except Exception as e:
                messagebox.showerror("DB 로드 실패", str(e))
                return

        folder_path = Path(rec["folder_path"]).resolve()
        initial_query = extract_folder_title_query(folder_path.name)
        dlg = DBSelectDialog(self, self.all_patches, initial_query=initial_query, folder_path=folder_path)
        self.wait_window(dlg)

        if dlg.result_action == "select" and dlg.selected_patch:
            target_dir = folder_path
            if self.show_maker_var.get():
                target_dir = ensure_maker_in_folder_name(
                    target_dir,
                    dlg.selected_patch.get("title", initial_query),
                    extract_maker(dlg.selected_patch),
                )
            save_matched_ver_info(target_dir, rec.get("console_raw", ""), dlg.selected_patch)
            self.run_scan(mode=self.current_mode, force_refresh=False, prompt_ambiguous=False, create_missing_ver=False)
        elif dlg.result_action == "no_db":
            save_unmatched_ver_info(folder_path, rec.get("console_raw", ""))
            self.run_scan(mode=self.current_mode, force_refresh=False, prompt_ambiguous=False, create_missing_ver=False)

    def clear_cache_and_reload(self):
        if CACHE_PATH.exists():
            try:
                elapsed = time.time() - os.path.getmtime(CACHE_PATH)
                if elapsed < CACHE_TTL:
                    messagebox.showinfo("안내", "한시간 이내 캐시초기화는 정책상 불가능합니다")
                    return
                CACHE_PATH.unlink()
            except OSError as e:
                messagebox.showerror("캐시 삭제 실패", str(e))
                return
        self.run_scan(mode=self.current_mode, force_refresh=True, prompt_ambiguous=False, create_missing_ver=False)


if __name__ == "__main__":
    app = KrpatchGUI()
    app.mainloop()