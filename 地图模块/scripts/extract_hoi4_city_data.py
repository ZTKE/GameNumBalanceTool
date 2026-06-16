from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path


GAME_DIR = Path(r"D:\Steam\steamapps\common\Hearts of Iron IV")
OUT_DIR = Path(__file__).resolve().parents[1]


def strip_comments(text: str) -> str:
    out: list[str] = []
    i = 0
    in_string = False
    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < len(text):
                i += 1
                out.append(text[i])
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "#":
            while i < len(text) and text[i] not in "\r\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    text = strip_comments(text)
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch in "{}=":
            tokens.append(ch)
            i += 1
            continue
        if ch == '"':
            i += 1
            buf: list[str] = []
            while i < len(text):
                c = text[i]
                if c == "\\" and i + 1 < len(text):
                    i += 1
                    buf.append(text[i])
                elif c == '"':
                    i += 1
                    break
                else:
                    buf.append(c)
                i += 1
            tokens.append("".join(buf))
            continue

        start = i
        while i < len(text) and not text[i].isspace() and text[i] not in "{}=":
            i += 1
        tokens.append(text[start:i])
    return tokens


Entry = tuple[str, object] | str


class Parser:
    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.i = 0

    def parse(self) -> list[Entry]:
        return self.parse_entries(stop_at_brace=False)

    def parse_entries(self, stop_at_brace: bool) -> list[Entry]:
        entries: list[Entry] = []
        while self.i < len(self.tokens):
            token = self.tokens[self.i]
            if token == "}":
                if stop_at_brace:
                    self.i += 1
                    break
                raise ValueError("Unexpected closing brace")
            if (
                self.i + 1 < len(self.tokens)
                and self.tokens[self.i + 1] == "="
                and token not in "{}="
            ):
                key = token
                self.i += 2
                entries.append((key, self.parse_value()))
            else:
                entries.append(token)
                self.i += 1
        return entries

    def parse_value(self) -> object:
        if self.i >= len(self.tokens):
            return ""
        token = self.tokens[self.i]
        if token == "{":
            self.i += 1
            return self.parse_entries(stop_at_brace=True)
        self.i += 1
        return token


def parse_pdx_file(path: Path) -> list[Entry]:
    return Parser(tokenize(path.read_text(encoding="utf-8-sig"))).parse()


def values(entries: list[Entry], key: str) -> list[object]:
    return [v for item in entries if isinstance(item, tuple) for k, v in [item] if k == key]


def first(entries: list[Entry], key: str, default: object = "") -> object:
    found = values(entries, key)
    return found[0] if found else default


def atoms(block: object) -> list[str]:
    if not isinstance(block, list):
        return []
    return [str(item) for item in block if not isinstance(item, tuple)]


def as_int(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def scalar(value: object) -> int | float | str:
    raw = str(value)
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    return raw


def to_python(value: object) -> object:
    if not isinstance(value, list):
        return scalar(value)

    result: dict[str, object] = {}
    loose_values: list[object] = []
    for item in value:
        if isinstance(item, tuple):
            key, child = item
            child_value = to_python(child)
            if key in result:
                if not isinstance(result[key], list):
                    result[key] = [result[key]]
                result[key].append(child_value)
            else:
                result[key] = child_value
        else:
            loose_values.append(scalar(item))

    if result:
        if loose_values:
            result["_values"] = loose_values
        return result
    return loose_values


def parse_key_values(block: object) -> dict[str, object]:
    result: dict[str, object] = {}
    if not isinstance(block, list):
        return result
    for item in block:
        if not isinstance(item, tuple):
            continue
        key, value = item
        result[key] = to_python(value)
    return result


def parse_buildings(block: object) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    state_buildings: dict[str, object] = {}
    province_buildings: dict[str, dict[str, object]] = {}
    if not isinstance(block, list):
        return state_buildings, province_buildings

    for item in block:
        if not isinstance(item, tuple):
            continue
        key, value = item
        if key.isdigit() and isinstance(value, list):
            province_buildings[key] = parse_key_values(value)
        else:
            state_buildings[key] = to_python(value)
    return state_buildings, province_buildings


def parse_victory_points(history_block: object) -> list[dict[str, int]]:
    result: list[dict[str, int]] = []
    for vp_block in values(history_block if isinstance(history_block, list) else [], "victory_points"):
        nums = atoms(vp_block)
        if len(nums) >= 2:
            result.append({"province_id": as_int(nums[0]), "victory_points": as_int(nums[1])})
    return result


def parse_history_summary(history_block: object) -> dict[str, object]:
    block = history_block if isinstance(history_block, list) else []
    buildings = first(block, "buildings", [])
    state_buildings, province_buildings = parse_buildings(buildings)
    known = {
        "owner",
        "controller",
        "victory_points",
        "buildings",
        "add_core_of",
        "add_claim_by",
    }
    other_keys = sorted(
        {
            key
            for item in block
            if isinstance(item, tuple)
            for key, _ in [item]
            if key not in known and not re.fullmatch(r"\d{4}\.\d{1,2}\.\d{1,2}", key)
        }
    )
    return {
        "owner": str(first(block, "owner", "")),
        "controller": str(first(block, "controller", "")),
        "cores": [str(v) for v in values(block, "add_core_of") if not isinstance(v, list)],
        "claims": [str(v) for v in values(block, "add_claim_by") if not isinstance(v, list)],
        "victory_points": parse_victory_points(block),
        "state_buildings": state_buildings,
        "province_buildings": province_buildings,
        "other_keys": other_keys,
    }


def load_localisation(path: Path) -> dict[str, str]:
    loc: dict[str, str] = {}
    if not path.exists():
        return loc
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("l_"):
            continue
        match = re.match(r'^([^:\s]+):(?:\d+)?\s+"((?:\\.|[^"])*)"', stripped)
        if not match:
            continue
        value = match.group(2).replace('\\"', '"')
        loc[match.group(1)] = value
    return loc


def load_country_names(loc: dict[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for tag in {key[:3] for key in loc if re.match(r"^[A-Z0-9]{3}_", key)}:
        for ideology in ("neutrality", "democratic", "fascism", "communism"):
            value = loc.get(f"{tag}_{ideology}")
            if value:
                result[tag] = value
                break
    return result


def load_vp_variants(loc: dict[str, str]) -> dict[str, dict[str, str]]:
    variants: dict[str, dict[str, str]] = defaultdict(dict)
    for key, name in loc.items():
        match = re.match(r"^(?:([A-Z0-9]{3})_)?VICTORY_POINTS_(\d+)$", key)
        if not match:
            continue
        tag, province_id = match.groups()
        variants[province_id]["DEFAULT" if tag is None else tag] = name
    return variants


def render_variants(variants: dict[str, str]) -> str:
    return "; ".join(f"{tag}:{name}" for tag, name in sorted(variants.items()) if tag != "DEFAULT")


def choose_vp_name(
    province_id: str,
    loc: dict[str, str],
    variants: dict[str, dict[str, str]],
    owner_tag: str,
    state_name: object,
) -> str:
    default_key = f"VICTORY_POINTS_{province_id}"
    province_variants = variants.get(province_id, {})
    return (
        province_variants.get("DEFAULT")
        or loc.get(default_key)
        or province_variants.get(owner_tag)
        or str(state_name or "")
        or next(iter(province_variants.values()), "")
        or default_key
    )


def load_state_categories() -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for path in (GAME_DIR / "common" / "state_category").glob("*.txt"):
        entries = parse_pdx_file(path)
        container = first(entries, "state_categories", [])
        if not isinstance(container, list):
            continue
        for item in container:
            if not isinstance(item, tuple):
                continue
            category, block = item
            result[category] = {
                "local_building_slots": as_int(first(block if isinstance(block, list) else [], "local_building_slots", 0)),
                "color": " ".join(atoms(first(block if isinstance(block, list) else [], "color", []))),
            }
    return result


def load_continents() -> dict[str, str]:
    path = GAME_DIR / "map" / "continent.txt"
    entries = parse_pdx_file(path)
    names = atoms(first(entries, "continents", []))
    return {"0": "unknown"} | {str(i + 1): name for i, name in enumerate(names)}


def load_definition(continents: dict[str, str]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    path = GAME_DIR / "map" / "definition.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f, delimiter=";"):
            if len(row) < 8 or not row[0].isdigit():
                continue
            province_id, r, g, b, province_type, coastal, terrain, continent = row[:8]
            result[province_id] = {
                "rgb": f"{r},{g},{b}",
                "province_type": province_type,
                "coastal": coastal,
                "terrain": terrain,
                "continent_id": continent,
                "continent": continents.get(continent, continent),
            }
    return result


def load_unitstacks() -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    path = GAME_DIR / "map" / "unitstacks.txt"
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = [p.strip() for p in stripped.split(";")]
        if len(parts) < 7 or not parts[0].isdigit():
            continue
        result[parts[0]] = {
            "unitstack_type": parts[1],
            "map_x": parts[2],
            "map_y": parts[3],
            "map_z": parts[4],
            "map_rotation": parts[5],
            "map_scale": parts[6],
        }
    return result


def load_supply_nodes() -> dict[str, str]:
    result: dict[str, str] = {}
    path = GAME_DIR / "map" / "supply_nodes.txt"
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) >= 2 and parts[1].isdigit():
            result[parts[1]] = parts[0]
    return result


def load_railways() -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = defaultdict(lambda: {"railway_count": 0, "railway_max_level": 0})
    path = GAME_DIR / "map" / "railways.txt"
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 3 or not parts[0].isdigit():
            continue
        level = int(parts[0])
        for province_id in parts[2:]:
            if not province_id.isdigit():
                continue
            result[province_id]["railway_count"] += 1
            result[province_id]["railway_max_level"] = max(result[province_id]["railway_max_level"], level)
    return result


def json_field(value: object) -> str:
    if value in ({}, [], None, ""):
        return ""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def extract_states() -> list[dict[str, object]]:
    state_name_zh = load_localisation(GAME_DIR / "localisation" / "simp_chinese" / "state_names_l_simp_chinese.yml")
    state_name_en = load_localisation(GAME_DIR / "localisation" / "english" / "state_names_l_english.yml")
    categories = load_state_categories()

    states: list[dict[str, object]] = []
    for path in sorted((GAME_DIR / "history" / "states").glob("*.txt")):
        entries = parse_pdx_file(path)
        state_block = first(entries, "state", [])
        if not isinstance(state_block, list):
            continue

        history = first(state_block, "history", [])
        history_summary = parse_history_summary(history)
        state_key = str(first(state_block, "name", ""))
        category = str(first(state_block, "state_category", ""))
        resources = parse_key_values(first(state_block, "resources", []))
        province_ids = atoms(first(state_block, "provinces", []))
        dated_history = {}
        if isinstance(history, list):
            for item in history:
                if not isinstance(item, tuple):
                    continue
                key, block = item
                if re.fullmatch(r"\d{4}\.\d{1,2}\.\d{1,2}", key):
                    dated_history[key] = parse_history_summary(block)

        state = {
            "state_id": as_int(first(state_block, "id", 0)),
            "state_key": state_key,
            "state_name_zh": state_name_zh.get(state_key, state_key),
            "state_name_en": state_name_en.get(state_key, state_key),
            "state_population_manpower": as_int(first(state_block, "manpower", 0)),
            "state_category": category,
            "local_building_slots": categories.get(category, {}).get("local_building_slots", ""),
            "local_supplies": as_float(first(state_block, "local_supplies", 0.0)),
            "resources": resources,
            "provinces": province_ids,
            "province_count": len(province_ids),
            "impassable": str(first(state_block, "impassable", "no")),
            "source_state_file": str(path),
            "dated_history": dated_history,
            **history_summary,
        }
        states.append(state)
    return sorted(states, key=lambda item: int(item["state_id"]))


def write_outputs() -> None:
    launcher = json.loads((GAME_DIR / "launcher-settings.json").read_text(encoding="utf-8-sig"))
    loc_zh_vp = load_localisation(GAME_DIR / "localisation" / "simp_chinese" / "victory_points_l_simp_chinese.yml")
    loc_en_vp = load_localisation(GAME_DIR / "localisation" / "english" / "victory_points_l_english.yml")
    zh_vp_variants = load_vp_variants(loc_zh_vp)
    en_vp_variants = load_vp_variants(loc_en_vp)
    country_zh = load_country_names(load_localisation(GAME_DIR / "localisation" / "simp_chinese" / "countries_l_simp_chinese.yml"))
    country_en = load_country_names(load_localisation(GAME_DIR / "localisation" / "english" / "countries_l_english.yml"))
    definition = load_definition(load_continents())
    unitstacks = load_unitstacks()
    supply_nodes = load_supply_nodes()
    railways = load_railways()
    states = extract_states()

    city_rows: list[dict[str, object]] = []
    for state in states:
        vp_sets = [("base", state["victory_points"])]
        for date, summary in (state.get("dated_history") or {}).items():
            dated_vps = summary.get("victory_points") if isinstance(summary, dict) else []
            if dated_vps:
                vp_sets.append((date, dated_vps))
        for effective_date, victory_points in vp_sets:
            for vp in victory_points:
                province_id = str(vp["province_id"])
                default_key = f"VICTORY_POINTS_{province_id}"
                province = definition.get(province_id, {})
                unit = unitstacks.get(province_id, {})
                rail = railways.get(province_id, {"railway_count": 0, "railway_max_level": 0})
                owner = str(state.get("owner") or "")
                controller = str(state.get("controller") or "")
                province_buildings = state.get("province_buildings") or {}
                city_rows.append(
                    {
                        "生效日期": effective_date,
                        "城市省份ID": province_id,
                        "城市名_中文": choose_vp_name(province_id, loc_zh_vp, zh_vp_variants, owner, state["state_name_zh"]),
                        "城市名_英文": choose_vp_name(province_id, loc_en_vp, en_vp_variants, owner, state["state_name_en"]),
                        "胜利点": vp["victory_points"],
                        "城市人口_原版无独立字段": "",
                        "人口口径": "所属地区manpower",
                        "所属地区人口": state["state_population_manpower"],
                        "所属地区ID": state["state_id"],
                        "所属地区_中文": state["state_name_zh"],
                        "所属地区_英文": state["state_name_en"],
                        "地区类型": state["state_category"],
                        "地区建筑槽": state["local_building_slots"],
                        "本地补给": state["local_supplies"],
                        "地区省份数": state["province_count"],
                        "拥有者TAG": owner,
                        "拥有者_中文": country_zh.get(owner, owner),
                        "拥有者_英文": country_en.get(owner, owner),
                        "控制者TAG": controller,
                        "核心TAG": ";".join(state.get("cores") or []),
                        "宣称TAG": ";".join(state.get("claims") or []),
                        "省份类型": province.get("province_type", ""),
                        "地形": province.get("terrain", ""),
                        "是否沿海": province.get("coastal", ""),
                        "大陆": province.get("continent", ""),
                        "大陆ID": province.get("continent_id", ""),
                        "省份RGB": province.get("rgb", ""),
                        "地图X": unit.get("map_x", ""),
                        "地图高度Y": unit.get("map_y", ""),
                        "地图Z": unit.get("map_z", ""),
                        "地图旋转": unit.get("map_rotation", ""),
                        "地图缩放": unit.get("map_scale", ""),
                        "是否补给节点": "yes" if province_id in supply_nodes else "no",
                        "补给节点等级字段": supply_nodes.get(province_id, ""),
                        "铁路经过数量": rail["railway_count"],
                        "铁路最高等级": rail["railway_max_level"],
                        "地区资源": json_field(state.get("resources")),
                        "地区建筑": json_field(state.get("state_buildings")),
                        "本省建筑": json_field(province_buildings.get(province_id, {}) if isinstance(province_buildings, dict) else {}),
                        "城市特殊名_中文": render_variants(zh_vp_variants.get(province_id, {})),
                        "城市特殊名_英文": render_variants(en_vp_variants.get(province_id, {})),
                        "来源州文件": state["source_state_file"],
                    }
                )

    state_rows: list[dict[str, object]] = []
    for state in states:
        vp_summary = [
            f'{vp["province_id"]}:{zh_vp_variants.get(str(vp["province_id"]), {}).get("DEFAULT", vp["province_id"])}({vp["victory_points"]})'
            for vp in state.get("victory_points", [])
        ]
        state_rows.append(
            {
                "地区ID": state["state_id"],
                "地区_中文": state["state_name_zh"],
                "地区_英文": state["state_name_en"],
                "人口_manpower": state["state_population_manpower"],
                "地区类型": state["state_category"],
                "地区建筑槽": state["local_building_slots"],
                "本地补给": state["local_supplies"],
                "不可通行": state["impassable"],
                "拥有者TAG": state.get("owner", ""),
                "拥有者_中文": country_zh.get(str(state.get("owner", "")), str(state.get("owner", ""))),
                "拥有者_英文": country_en.get(str(state.get("owner", "")), str(state.get("owner", ""))),
                "控制者TAG": state.get("controller", ""),
                "省份数": state["province_count"],
                "省份ID列表": " ".join(state["provinces"]),
                "胜利点城市数": len(state.get("victory_points", [])),
                "胜利点合计": sum(vp["victory_points"] for vp in state.get("victory_points", [])),
                "胜利点列表": "; ".join(vp_summary),
                "资源": json_field(state.get("resources")),
                "地区建筑": json_field(state.get("state_buildings")),
                "省份建筑": json_field(state.get("province_buildings")),
                "核心TAG": ";".join(state.get("cores") or []),
                "宣称TAG": ";".join(state.get("claims") or []),
                "其他历史字段": ";".join(state.get("other_keys") or []),
                "日期历史": json_field(state.get("dated_history")),
                "来源州文件": state["source_state_file"],
            }
        )

    city_csv = OUT_DIR / "钢铁雄心4_城市胜利点数据.csv"
    state_csv = OUT_DIR / "钢铁雄心4_地区州数据.csv"
    raw_json = OUT_DIR / "钢铁雄心4_地图城市数据.json"
    readme = OUT_DIR / "钢铁雄心4_地图城市数据说明.md"

    with city_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(city_rows[0].keys()))
        writer.writeheader()
        writer.writerows(city_rows)

    with state_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(state_rows[0].keys()))
        writer.writeheader()
        writer.writerows(state_rows)

    raw_json.write_text(
        json.dumps(
            {
                "game_version": launcher.get("version"),
                "raw_version": launcher.get("rawVersion"),
                "game_dir": str(GAME_DIR),
                "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "notes": [
                    "HOI4 has no separate vanilla city population field. City rows use the owning state's manpower as the population reference.",
                    "Named map cities are victory_points in history/states plus VICTORY_POINTS localisation.",
                ],
                "cities": city_rows,
                "states": state_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    top_vps = sorted(city_rows, key=lambda row: (int(row["胜利点"]), int(row["所属地区人口"])), reverse=True)[:20]
    top_lines = [
        f'| {row["城市名_中文"]} | {row["城市名_英文"]} | {row["胜利点"]} | {row["所属地区_中文"]} | {row["所属地区人口"]:,} | {row["拥有者TAG"]} |'
        for row in top_vps
    ]

    readme.write_text(
        "\n".join(
            [
                "# 钢铁雄心4地图城市数据说明",
                "",
                f"- 游戏版本：{launcher.get('version')} / raw {launcher.get('rawVersion')}",
                f"- 数据来源：`{GAME_DIR}`",
                f"- 生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
                f"- 城市/胜利点记录：{len(city_rows)} 条",
                f"- 地区/州记录：{len(state_rows)} 条",
                "",
                "## 口径",
                "",
                "- 钢四原版没有“城市人口”独立字段。CSV 里的 `所属地区人口` 来自州文件的 `manpower`，也就是该城市所在地区/州的人口。",
                "- 地图上可命名城市来自 `history/states/*.txt` 的 `victory_points`，城市名来自 `localisation/*/victory_points_*.yml`。",
                "- 城市坐标来自 `map/unitstacks.txt`；地形、沿海、大陆来自 `map/definition.csv`；补给节点和铁路来自 `map/supply_nodes.txt` 与 `map/railways.txt`。",
                "- `生效日期=base` 表示州文件基础历史；如果某个日期块内直接定义胜利点，会以日期显示。",
                "- State 不等同于现实行政省。部分现实省份会被拆成多个游戏 State，例如现实江苏在当前数据中拆为 `江苏`、`苏州`、`南京`。",
                "- 当 `地区_中文` 和 `城市名_中文` 相同，例如 `南京`、`苏州`、`柏林`、`华沙`，含义不是重复：前者是地图 State 名，后者是该 State 内的胜利点城市名。",
                "",
                "## 文件",
                "",
                "- `钢铁雄心4_城市胜利点数据.csv`：城市/胜利点维度，适合直接筛选城市、胜利点、州人口、地形、坐标。",
                "- `钢铁雄心4_地区州数据.csv`：地区/州维度，包含人口、资源、建筑、核心、宣称、日期历史摘要。",
                "- `钢铁雄心4_地图城市数据.json`：同一批数据的结构化 JSON 版本。",
                "- `scripts/extract_hoi4_city_data.py`：可重复运行的提取脚本。",
                "",
                "## 胜利点最高的城市 Top 20",
                "",
                "| 城市 | 英文 | 胜利点 | 所属地区 | 所属地区人口 | 拥有者 |",
                "| --- | --- | ---: | --- | ---: | --- |",
                *top_lines,
                "",
                "## 参考",
                "",
                "- ParaWikis 地区模改说明：https://hoi4.parawikis.com/wiki/State_modding",
                "- ParaWikis 地图修改说明：https://hoi4.parawikis.com/wiki/地图修改",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"cities={len(city_rows)} states={len(state_rows)}")
    print(city_csv)
    print(state_csv)
    print(raw_json)
    print(readme)


if __name__ == "__main__":
    write_outputs()
