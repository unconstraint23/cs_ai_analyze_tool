"""
CS2 地图知识库：
1. 官方雷达坐标投影参数 (pos_x, pos_y, scale) -> 归一化 [0, 100] 2D 战术面板坐标
2. CS2 引擎内部 m_szLastPlaceName (last_place_name) -> 中文报点 + 宏观区域 (A区/中路/B区/出生点)
3. CT 前压判定区域 (用于在 Demo 中自动识别某名玩家做 CT 时是否喜欢激进前顶偷人)
4. 地图关键战术地标坐标 (供前端绘制 2D 战术示意图底图)
"""

from __future__ import annotations
from typing import Any, Dict, Tuple

MAP_META: Dict[str, Dict[str, Any]] = {
    "de_mirage": {
        "name": "de_mirage",
        "cn_name": "荒漠迷城 (Mirage)",
        "pos_x": -3230.0,
        "pos_y": 1713.0,
        "scale": 5.0,
        "landmarks": [
            {"label": "A包点", "x": 54, "y": 73, "zone": "A"},
            {"label": "A二楼 (Palace)", "x": 69, "y": 79, "zone": "A"},
            {"label": "A斜坡 (Ramp)", "x": 68, "y": 66, "zone": "A"},
            {"label": "Jungle", "x": 45, "y": 64, "zone": "A"},
            {"label": "拱门/连接", "x": 50, "y": 54, "zone": "MID"},
            {"label": "VIP (Window)", "x": 40, "y": 52, "zone": "MID"},
            {"label": "中路 (Mid)", "x": 55, "y": 46, "zone": "MID"},
            {"label": "中路远点/匪口", "x": 69, "y": 38, "zone": "MID"},
            {"label": "下水道", "x": 45, "y": 39, "zone": "MID"},
            {"label": "B二楼 (Apps)", "x": 38, "y": 24, "zone": "B"},
            {"label": "B包点", "x": 24, "y": 29, "zone": "B"},
            {"label": "超市 (Market)", "x": 24, "y": 46, "zone": "B"},
            {"label": "警家 (CT)", "x": 34, "y": 70, "zone": "SPAWN"},
            {"label": "匪家 (T)", "x": 83, "y": 44, "zone": "SPAWN"},
        ],
    },
    "de_inferno": {
        "name": "de_inferno",
        "cn_name": "炼狱小镇 (Inferno)",
        "pos_x": -2087.0,
        "pos_y": 3870.0,
        "scale": 4.9,
        "landmarks": [
            {"label": "B包点", "x": 47, "y": 22, "zone": "B"},
            {"label": "棺材/警家连接", "x": 54, "y": 17, "zone": "B"},
            {"label": "香蕉道 (Banana)", "x": 44, "y": 43, "zone": "B"},
            {"label": "匪口/中路", "x": 46, "y": 65, "zone": "MID"},
            {"label": "侧道 (2nd Mid)", "x": 57, "y": 72, "zone": "MID"},
            {"label": "中路近点/锅炉房", "x": 64, "y": 57, "zone": "A"},
            {"label": "A二楼 (Apps)", "x": 74, "y": 66, "zone": "A"},
            {"label": "大坑 (Pit)", "x": 84, "y": 58, "zone": "A"},
            {"label": "A包点", "x": 77, "y": 48, "zone": "A"},
            {"label": "书房/拱门 (Arch)", "x": 69, "y": 36, "zone": "A"},
            {"label": "警家 (CT)", "x": 67, "y": 23, "zone": "SPAWN"},
            {"label": "匪家 (T)", "x": 24, "y": 69, "zone": "SPAWN"},
        ],
    },
    "de_dust2": {
        "name": "de_dust2",
        "cn_name": "炙热沙城 II (Dust2)",
        "pos_x": -2476.0,
        "pos_y": 3239.0,
        "scale": 4.4,
        "landmarks": [
            {"label": "A包点", "x": 79, "y": 20, "zone": "A"},
            {"label": "A大 (Long A)", "x": 83, "y": 48, "zone": "A"},
            {"label": "A门 (Long Doors)", "x": 74, "y": 64, "zone": "A"},
            {"label": "A小道 (Short/Cat)", "x": 60, "y": 39, "zone": "MID"},
            {"label": "中门 (Mid Doors)", "x": 49, "y": 43, "zone": "MID"},
            {"label": "中路 (Mid)", "x": 50, "y": 60, "zone": "MID"},
            {"label": "B洞 (Tunnels)", "x": 22, "y": 52, "zone": "B"},
            {"label": "B包点", "x": 22, "y": 24, "zone": "B"},
            {"label": "警家 (CT)", "x": 57, "y": 24, "zone": "SPAWN"},
            {"label": "匪家 (T)", "x": 44, "y": 84, "zone": "SPAWN"},
        ],
    },
    "de_ancient": {
        "name": "de_ancient",
        "cn_name": "远古遗迹 (Ancient)",
        "pos_x": -2953.0,
        "pos_y": 2164.0,
        "scale": 5.0,
        "landmarks": [
            {"label": "A包点", "x": 28, "y": 29, "zone": "A"},
            {"label": "甜甜圈 (Donut)", "x": 40, "y": 38, "zone": "MID"},
            {"label": "中路 (Mid)", "x": 50, "y": 48, "zone": "MID"},
            {"label": "黑屋 (Cave/House)", "x": 66, "y": 37, "zone": "B"},
            {"label": "B斜坡 (B Ramp)", "x": 78, "y": 48, "zone": "B"},
            {"label": "B包点", "x": 75, "y": 29, "zone": "B"},
            {"label": "警家 (CT)", "x": 51, "y": 18, "zone": "SPAWN"},
            {"label": "匪家 (T)", "x": 50, "y": 82, "zone": "SPAWN"},
        ],
    },
    "de_anubis": {
        "name": "de_anubis",
        "cn_name": "阿努比斯 (Anubis)",
        "pos_x": -2796.0,
        "pos_y": 3328.0,
        "scale": 5.22,
        "landmarks": [
            {"label": "A包点", "x": 74, "y": 30, "zone": "A"},
            {"label": "A大 (A Main)", "x": 78, "y": 49, "zone": "A"},
            {"label": "中路/桥上", "x": 51, "y": 48, "zone": "MID"},
            {"label": "水下 (Canal)", "x": 56, "y": 60, "zone": "MID"},
            {"label": "黑屋/B连接", "x": 40, "y": 54, "zone": "B"},
            {"label": "B外/B大", "x": 27, "y": 51, "zone": "B"},
            {"label": "B包点", "x": 30, "y": 33, "zone": "B"},
        ],
    },
    "de_nuke": {
        "name": "de_nuke",
        "cn_name": "核子危机 (Nuke)",
        "pos_x": -3453.0,
        "pos_y": 2887.0,
        "scale": 7.0,
        "landmarks": [
            {"label": "内场/A包点", "x": 57, "y": 47, "zone": "A"},
            {"label": "黄房 (Hut)", "x": 51, "y": 54, "zone": "A"},
            {"label": "外场 (Outside)", "x": 58, "y": 66, "zone": "MID"},
            {"label": "铁板 (Ramp)", "x": 45, "y": 38, "zone": "B"},
            {"label": "B包点 (下层)", "x": 57, "y": 42, "zone": "B"},
        ],
    },
    "de_train": {
        "name": "de_train",
        "cn_name": "列车停放站 (Train)",
        "pos_x": -2477.0,
        "pos_y": 2392.0,
        "scale": 4.7,
        "landmarks": [
            {"label": "外场/A包点", "x": 58, "y": 48, "zone": "A"},
            {"label": "匪口 (T Main)", "x": 41, "y": 53, "zone": "A"},
            {"label": "绿通 (Ivy)", "x": 74, "y": 46, "zone": "A"},
            {"label": "内场/B包点", "x": 55, "y": 72, "zone": "B"},
        ],
    },
}


# (中文报点, 宏观分路 A/MID/B/SPAWN, 是否属于CT激进前顶区域)
PLACE_NAME_MAPPING: Dict[str, Tuple[str, str, bool]] = {
    # 通用包点与出生点
    "BombsiteA": ("A包点", "A", False),
    "BombsiteB": ("B包点", "B", False),
    "CTSpawn": ("警家", "SPAWN", False),
    "TSpawn": ("匪家", "SPAWN", True),
    # Mirage / 通用点位
    "TopofMid": ("中路远点/匪口", "MID", True),
    "Middle": ("中路", "MID", True),
    "SnipersNest": ("VIP/狙击房", "MID", False),
    "Window": ("VIP窗口", "MID", False),
    "Connector": ("拱门/A连接", "MID", False),
    "Jungle": ("Jungle", "A", False),
    "Stairs": ("A跳台", "A", False),
    "Ticket": ("售票亭/警家口", "A", False),
    "PalaceAlley": ("A二楼深处", "A", True),
    "PalaceInterior": ("A二楼", "A", True),
    "Scaffolding": ("A二楼阳台", "A", False),
    "Ramp": ("A一楼斜坡", "A", True),
    "TRamp": ("A斜坡匪口", "A", True),
    "Underpass": ("下水道", "MID", True),
    "Apartments": ("二楼", "B", True),
    "BackAlley": ("B二楼后巷", "B", True),
    "House": ("匪家二楼入口", "B", True),
    "Shop": ("B超市", "B", False),
    "Market": ("B超市", "B", False),
    "Catwalk": ("小道", "MID", False),
    "Short": ("小道", "MID", False),
    "Van": ("B白车", "B", False),
    "Bench": ("B长椅", "B", False),
    # Inferno 专属/常见
    "Banana": ("香蕉道", "B", True),
    "Logs": ("香蕉道木堆", "B", True),
    "Car": ("香蕉道石板/车位", "B", True),
    "Ruins": ("B废墟/教堂", "B", False),
    "Construction": ("B棺材/工地", "B", False),
    "SecondMid": ("侧道", "MID", True),
    "Boiler": ("锅炉房", "A", True),
    "Pit": ("A大坑", "A", False),
    "Graveyard": ("墓地", "A", False),
    "Balcony": ("A二楼阳台", "A", False),
    "Arch": ("书房口/拱门", "A", False),
    "Library": ("书房", "A", False),
    "Quad": ("A草车/死角", "A", False),
    "Bridge": ("桥上", "MID", True),
    # Dust2 专属/常见
    "LongDoors": ("A门", "A", True),
    "LongA": ("A大", "A", False),
    "ExtendedA": ("A平台", "A", False),
    "ARamp": ("A斜坡", "A", False),
    "MidDoors": ("中门", "MID", False),
    "LowerTunnel": ("B一层洞", "B", True),
    "UpperTunnel": ("B二层洞", "B", True),
    "TunnelStairs": ("B洞楼梯", "B", True),
    "BDoors": ("B门", "B", False),
    "Hole": ("B狗洞", "B", False),
    "Xbox": ("中路箱子", "MID", True),
    # Ancient / Anubis / Nuke
    "Donut": ("甜甜圈", "MID", False),
    "Cave": ("黑屋", "B", False),
    "Alley": ("外道/侧巷", "A", True),
    "Main": ("主道/A大", "A", True),
    "Canal": ("水下", "MID", True),
    "Water": ("水下", "MID", True),
    "Outside": ("外场", "MID", True),
    "Yard": ("外场", "MID", True),
    "Silo": ("外场棉花糖", "MID", True),
    "Secret": ("K1/秘密通道", "B", False),
    "Hut": ("黄房", "A", False),
    "Squeaky": ("铁门", "A", False),
    "Heaven": ("三楼/天堂", "A", False),
    "Hell": ("三楼下", "A", False),
    "Radio": ("电台房", "B", False),
    "Trophy": ("奖杯房", "B", False),
    "Vents": ("管道", "B", False),
    "Lobby": ("匪厅", "A", True),
    "Ivy": ("绿通", "A", False),
}


def resolve_callout(raw_place: Any, map_name: str = "") -> Tuple[str, str, bool]:
    """
    将 CS2 原始 last_place_name 解析为 (中文报点, 宏观区域 A/MID/B/SPAWN, 是否CT激进前压点)。
    针对特定地图同名报点（如 Inferno 的 Apartments 是 A二楼，Mirage 的 Apartments 是 B二楼）做精确修正。
    """
    if not raw_place or not isinstance(raw_place, str):
        return ("未知区域", "MID", False)
    clean = raw_place.strip()
    if not clean:
        return ("未知区域", "MID", False)

    # 地图特定消歧
    if map_name == "de_inferno" and clean in ("Apartments", "BackAlley", "Balcony"):
        return ("A二楼", "A", clean == "Apartments")
    if map_name == "de_mirage" and clean == "Apartments":
        return ("B二楼", "B", True)
    if map_name == "de_nuke" and clean == "Ramp":
        return ("铁板 (Ramp)", "B", False)

    if clean in PLACE_NAME_MAPPING:
        return PLACE_NAME_MAPPING[clean]

    low = clean.lower()
    if "bombsitea" in low or low.startswith("a") and "site" in low:
        return ("A包点", "A", False)
    if "bombsiteb" in low or low.startswith("b") and "site" in low:
        return ("B包点", "B", False)
    if "mid" in low or "catwalk" in low or "conn" in low or "window" in low:
        return (f"中路({clean})", "MID", "top" in low)
    if "spawn" in low:
        return ("警家" if "ct" in low else "匪家", "SPAWN", "t" in low and "ct" not in low)
    if "banana" in low or "tunnel" in low or "market" in low or "cave" in low:
        return (clean, "B", "banana" in low or "tunnel" in low)
    if "palace" in low or "long" in low or "pit" in low or "arch" in low:
        return (clean, "A", "palace" in low)

    return (clean, "MID", False)


def world_to_radar_pct(x: float, y: float, map_name: str) -> Tuple[float, float]:
    """将游戏世界 3D 坐标 (X, Y) 转换为 [0, 100] 的 2D 战术雷达百分比坐标。"""
    meta = MAP_META.get(map_name)
    if not meta:
        # 未知地图做通用缩放兜底
        nx = max(4.0, min(96.0, (x + 3000.0) / 6000.0 * 100.0))
        ny = max(4.0, min(96.0, (3000.0 - y) / 6000.0 * 100.0))
        return round(nx, 1), round(ny, 1)

    px = (x - meta["pos_x"]) / meta["scale"]
    py = (meta["pos_y"] - y) / meta["scale"]
    nx = max(2.0, min(98.0, (px / 1024.0) * 100.0))
    ny = max(2.0, min(98.0, (py / 1024.0) * 100.0))
    return round(nx, 1), round(ny, 1)


def get_map_meta(map_name: str) -> Dict[str, Any]:
    if map_name in MAP_META:
        return MAP_META[map_name]
    return {
        "name": map_name or "unknown_map",
        "cn_name": map_name or "未知地图",
        "pos_x": -3000.0,
        "pos_y": 3000.0,
        "scale": 5.5,
        "landmarks": [
            {"label": "A区", "x": 70, "y": 32, "zone": "A"},
            {"label": "中路", "x": 50, "y": 50, "zone": "MID"},
            {"label": "B区", "x": 28, "y": 32, "zone": "B"},
        ],
    }
