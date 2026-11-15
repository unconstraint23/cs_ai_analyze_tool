"""
真实 CS2 Demo (.dem / .zip / .gz / .bz2) 战术特征与习惯提取引擎 (基于 demoparser2)。

提取的核心维度（按 CT / T 阵营拆分）：
1. 基础战斗与残局表现：Rating 估算、ADR、K/D、HS%、KAST%、首杀率、被补枪/白给率 (Untraded Death %)。
2. 开局侵略性与首交火点位：
   - CT 前压偷人率 (冻结结束 22 秒内进入前顶争夺区或主动首交火)
   - T 突破首杀尝试率与成功率
   - 高频首杀报点 / 高频送首死报点
3. 地图站位与路线偏好 (冻结结束后 +14s 默认站位、+24s 控图推进)：
   - CT 主防分路占比 (A区 / 中路 / B区) 与 Top 3 常驻报点
   - T 进攻默认分路占比与 Top 3 常走报点
   - 2D 战术雷达采样点 (CT默认站位、T进攻轨迹、首杀点、首死点)
4. 枪械、经济与道具习惯：
   - 主力枪械偏好、起大狙率 (AWP Rate)、强起刚枪倾向 (Force-buy Rate)
   - 回合均烟/闪/火/雷投掷量、闪光致盲效率
5. 团队宏观战术倾向 (Team Macro)：
   - CT 常见默认防守阵型 (如 2A-1中-2B 占比)
   - T 主攻包点倾向 (A/B 下包占比) 与快攻提速比例 (<32s 进点/下包)
"""

from __future__ import annotations

import bz2
import gzip
import math
import os
import shutil
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .map_knowledge import get_map_meta, resolve_callout, world_to_radar_pct

TICKRATE_DEFAULT = 64


def _safe_extract_demo_file(input_path: Path, temp_dir: Path) -> Path:
    """支持直接传入 .dem，或完美平台下载的 .zip / .dem.gz / .dem.bz2 压缩包。"""
    suffixes = "".join(input_path.suffixes).lower()
    if suffixes.endswith(".dem"):
        return input_path

    if zipfile.is_zipfile(input_path):
        with zipfile.ZipFile(input_path, "r") as zf:
            dem_members = [m for m in zf.namelist() if m.lower().endswith(".dem")]
            if not dem_members:
                raise ValueError(f"ZIP 压缩包 {input_path.name} 中未找到 .dem 录像文件")
            target_member = dem_members[0]
            out_path = temp_dir / Path(target_member).name
            with zf.open(target_member) as src, open(out_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            return out_path

    if suffixes.endswith(".gz"):
        out_path = temp_dir / input_path.with_suffix("").name
        if not out_path.name.endswith(".dem"):
            out_path = out_path.with_suffix(".dem")
        with gzip.open(input_path, "rb") as src, open(out_path, "wb") as dst:
            shutil.copyfileobj(src, dst)
        return out_path

    if suffixes.endswith(".bz2"):
        out_path = temp_dir / input_path.with_suffix("").name
        if not out_path.name.endswith(".dem"):
            out_path = out_path.with_suffix(".dem")
        with bz2.open(input_path, "rb") as src, open(out_path, "wb") as dst:
            shutil.copyfileobj(src, dst)
        return out_path

    raise ValueError(f"不支持的文件格式: {input_path.name}（请上传 .dem / .zip / .gz / .bz2）")


def _to_pandas_df(res: Any) -> pd.DataFrame:
    if res is None:
        return pd.DataFrame()
    if isinstance(res, pd.DataFrame):
        return res
    if hasattr(res, "to_pandas"):
        return res.to_pandas()
    if isinstance(res, list):
        return pd.DataFrame(res)
    return pd.DataFrame()


def _safe_parse_event(
    parser: Any,
    event_name: str,
    player: Optional[List[str]] = None,
    other: Optional[List[str]] = None,
) -> pd.DataFrame:
    try:
        kwargs: Dict[str, Any] = {}
        if player:
            kwargs["player"] = player
        if other:
            kwargs["other"] = other
        df = _to_pandas_df(parser.parse_event(event_name, **kwargs))
        if not df.empty and "is_warmup_period" in df.columns:
            df = df[df["is_warmup_period"] != True].reset_index(drop=True)  # noqa: E712
        return df
    except Exception:
        return pd.DataFrame()


def _is_knife_weapon(weapon: Any) -> bool:
    if not isinstance(weapon, str):
        return False
    w = weapon.lower()
    return "knife" in w or "bayonet" in w or "karambit" in w or "dagger" in w


def _classify_roles(ct_lanes: Dict[str, float], t_lanes: Dict[str, float], stats: Dict[str, Any]) -> Tuple[str, str, List[str]]:
    """根据提取指标自动判定玩家的 CT 角色、T 角色与风格标签。"""
    tags: List[str] = []

    # CT 角色
    ct_top_lane = max(("A", "MID", "B"), key=lambda k: ct_lanes.get(k, 0.0))
    lane_cn = {"A": "A区", "MID": "中路", "B": "B区"}[ct_top_lane]
    if stats.get("awp_kill_share", 0) >= 28.0:
        ct_role = f"{lane_cn}主狙 / 架点核心"
        tags.append("核心狙击手")
    elif stats.get("ct_aggression_rate", 0) >= 34.0:
        ct_role = f"{lane_cn}激进前顶 / 信息位"
        tags.append("CT爱前压偷人")
    elif ct_lanes.get("MID", 0) >= 38.0:
        ct_role = "中路协防 / 机动补位"
    elif ct_lanes.get(ct_top_lane, 0) >= 58.0:
        ct_role = f"{lane_cn}死守主防 (Anchor)"
        tags.append(f"固定守{lane_cn}")
    else:
        ct_role = f"{lane_cn}偏重 / 游走补防"

    # T 角色
    t_top_lane = max(("A", "MID", "B"), key=lambda k: t_lanes.get(k, 0.0))
    t_lane_cn = {"A": "A区", "MID": "中路", "B": "B区"}[t_top_lane]
    if stats.get("t_opening_attempt_rate", 0) >= 26.0:
        t_role = f"第一突破手 (偏{t_lane_cn})"
        tags.append("激进突破手")
    elif stats.get("utility_per_round", 0) >= 1.9 and stats.get("flash_assists_plus_blind", 0) >= 0.6:
        t_role = f"道具辅助 / 二位补枪 (偏{t_lane_cn})"
        tags.append("道具机器")
    elif stats.get("untraded_death_rate", 0) >= 48.0 and stats.get("t_opening_attempt_rate", 0) < 20.0:
        t_role = f"单摸自由人 / 断后 (偏{t_lane_cn})"
        tags.append("喜欢单摸走单")
    elif stats.get("awp_kill_share", 0) >= 28.0:
        t_role = "进攻架点狙击手"
    else:
        t_role = f"默认控图 / 补枪手 (偏{t_lane_cn})"

    if stats.get("force_buy_rate", 0) >= 42.0:
        tags.append("输局爱强起刚枪")
    if stats.get("hs_pct", 0) >= 56.0 and stats.get("adr", 0) >= 82.0:
        tags.append("高爆头大枪男")
    if stats.get("untraded_death_rate", 0) >= 52.0:
        tags.append("高白给风险(脱节)")
    if stats.get("opening_win_rate", 50) <= 38.0 and stats.get("opening_attempt_rate", 0) >= 22.0:
        tags.append("开局易送首死")
    if stats.get("clutch_wins", 0) >= 2:
        tags.append("残局大心脏")

    return ct_role, t_role, tags[:5]


def parse_single_demo(file_path: str | Path) -> Dict[str, Any]:
    """解析单个 CS2 Demo 文件并返回统一战术结构 JSON。"""
    from demoparser2 import DemoParser

    src_path = Path(file_path)
    with tempfile.TemporaryDirectory(prefix="cs2_demo_") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        dem_path = _safe_extract_demo_file(src_path, tmp_dir)

        parser = DemoParser(str(dem_path))
        header = parser.parse_header() or {}
        map_name = str(header.get("map_name") or "de_mirage").strip()
        map_meta = get_map_meta(map_name)

        # 1. 解析回合时间轴 (round_freeze_end & round_end)
        freeze_df = _safe_parse_event(
            parser, "round_freeze_end", other=["total_rounds_played", "is_warmup_period"]
        )
        round_end_df = _safe_parse_event(
            parser, "round_end", other=["total_rounds_played", "is_warmup_period"]
        )
        deaths_df = _safe_parse_event(
            parser,
            "player_death",
            player=["X", "Y", "last_place_name", "team_num"],
            other=["total_rounds_played", "is_warmup_period"],
        )
        hurt_df = _safe_parse_event(
            parser,
            "player_hurt",
            player=["team_num"],
            other=["total_rounds_played", "is_warmup_period"],
        )
        blind_df = _safe_parse_event(
            parser,
            "player_blind",
            player=["team_num"],
            other=["total_rounds_played", "is_warmup_period"],
        )
        plant_df = _safe_parse_event(
            parser,
            "bomb_planted",
            player=["X", "Y", "last_place_name", "team_num"],
            other=["total_rounds_played", "is_warmup_period"],
        )
        smoke_df = _safe_parse_event(
            parser, "smokegrenade_detonate", other=["total_rounds_played", "is_warmup_period"]
        )
        flash_df = _safe_parse_event(
            parser, "flashbang_detonate", other=["total_rounds_played", "is_warmup_period"]
        )
        he_df = _safe_parse_event(
            parser, "hegrenade_detonate", other=["total_rounds_played", "is_warmup_period"]
        )
        molly_df = _safe_parse_event(
            parser, "inferno_startburn", other=["total_rounds_played", "is_warmup_period"]
        )

        # 构建有效回合列表（剔除完美平台拼刀局）
        knife_rounds = set()
        if not deaths_df.empty and "total_rounds_played" in deaths_df.columns and "weapon" in deaths_df.columns:
            for r_idx, grp in deaths_df.groupby("total_rounds_played"):
                if len(grp) >= 3 and all(_is_knife_weapon(w) for w in grp["weapon"].dropna()):
                    knife_rounds.add(int(r_idx))

        round_freeze_ticks: Dict[int, int] = {}
        if not freeze_df.empty and "tick" in freeze_df.columns:
            if "total_rounds_played" in freeze_df.columns:
                for _, row in freeze_df.sort_values("tick").iterrows():
                    r_num = int(row["total_rounds_played"])
                    if r_num not in knife_rounds:
                        round_freeze_ticks[r_num] = int(row["tick"])
            else:
                for idx, (_, row) in enumerate(freeze_df.sort_values("tick").iterrows()):
                    round_freeze_ticks[idx] = int(row["tick"])

        if not round_freeze_ticks and not deaths_df.empty and "total_rounds_played" in deaths_df.columns:
            for r_num, grp in deaths_df.groupby("total_rounds_played"):
                if int(r_num) not in knife_rounds:
                    round_freeze_ticks[int(r_num)] = max(0, int(grp["tick"].min()) - 15 * TICKRATE_DEFAULT)

        valid_rounds = sorted(round_freeze_ticks.keys())
        total_rounds = max(len(valid_rounds), 1)

        # 2. 按关键战术时间节点采样 Ticks（毫秒级极速提取，无需遍历数百万帧！）
        # t+1s: 开局装备价值/阵营  t+14s: CT默认站位/T出匪口分路  t+24s: 前压偷人与控图展开
        sampled_ticks_meta: Dict[int, Tuple[int, str]] = {}
        for r_num in valid_rounds:
            ft = round_freeze_ticks[r_num]
            sampled_ticks_meta[ft + 1 * TICKRATE_DEFAULT] = (r_num, "start")
            sampled_ticks_meta[ft + 14 * TICKRATE_DEFAULT] = (r_num, "default")
            sampled_ticks_meta[ft + 24 * TICKRATE_DEFAULT] = (r_num, "mid_early")

        wanted_tick_props = [
            "X",
            "Y",
            "Z",
            "team_num",
            "is_alive",
            "last_place_name",
            "current_equip_value",
            "round_start_equip_value",
        ]
        try:
            ticks_df = _to_pandas_df(
                parser.parse_ticks(
                    wanted_tick_props,
                    ticks=sorted(sampled_ticks_meta.keys()),
                )
            )
        except Exception:
            ticks_df = pd.DataFrame()

        # 3. 识别全部 10 名参赛选手及其首发阵营（以第 1 有效回合的 team_num 分组两支队伍）
        player_identities: Dict[str, Dict[str, Any]] = {}
        first_round = valid_rounds[0] if valid_rounds else 0

        if not ticks_df.empty and "steamid" in ticks_df.columns:
            for _, row in ticks_df.iterrows():
                t_num = row.get("team_num")
                if t_num not in (2, 3):
                    continue
                sid = str(row.get("steamid") or row.get("name") or "")
                pname = str(row.get("name") or sid)
                if not sid:
                    continue
                tick_val = int(row["tick"])
                r_num, phase = sampled_ticks_meta.get(tick_val, (-1, ""))
                if sid not in player_identities:
                    player_identities[sid] = {
                        "steamid": sid,
                        "name": pname,
                        "initial_team_num": int(t_num),
                    }
                elif r_num == first_round and phase == "start":
                    player_identities[sid]["initial_team_num"] = int(t_num)
                    player_identities[sid]["name"] = pname

        # 若 ticks 未覆盖全，从击杀表补齐
        if not deaths_df.empty:
            for prefix in ("user", "attacker"):
                sid_col = f"{prefix}_steamid"
                name_col = f"{prefix}_name"
                team_col = f"{prefix}_team_num"
                if sid_col in deaths_df.columns and name_col in deaths_df.columns:
                    for _, row in deaths_df.iterrows():
                        sid = str(row.get(sid_col) or "")
                        pname = str(row.get(name_col) or "")
                        t_num = row.get(team_col)
                        if sid and sid != "0" and pname and sid not in player_identities and t_num in (2, 3):
                            player_identities[sid] = {
                                "steamid": sid,
                                "name": pname,
                                "initial_team_num": int(t_num),
                            }

        # 初始化每位选手的统计累加器
        p_acc: Dict[str, Dict[str, Any]] = {}
        for sid, info in player_identities.items():
            p_acc[sid] = {
                "steamid": sid,
                "name": info["name"],
                "roster_group": "TEAM_A" if info["initial_team_num"] == 3 else "TEAM_B",
                "ct_rounds": 0,
                "t_rounds": 0,
                "kills": 0,
                "deaths": 0,
                "assists": 0,
                "hs_kills": 0,
                "damage": 0,
                "awp_kills": 0,
                "weapon_kills": Counter(),
                "opening_kills_ct": 0,
                "opening_deaths_ct": 0,
                "opening_kills_t": 0,
                "opening_deaths_t": 0,
                "opening_kill_spots": Counter(),
                "opening_death_spots": Counter(),
                "ct_aggressive_rounds": 0,
                "untraded_deaths": 0,
                "kast_rounds": set(),
                "clutch_wins": 0,
                "force_buy_rounds": 0,
                "low_econ_opportunities": 0,
                "ct_callouts": Counter(),
                "t_callouts": Counter(),
                "ct_lanes": Counter(),
                "t_lanes": Counter(),
                "smokes_thrown": 0,
                "flashes_thrown": 0,
                "he_thrown": 0,
                "molotovs_thrown": 0,
                "enemies_blinded": 0,
                "radar_points": [],
            }

        name_to_sid = {v["name"]: k for k, v in p_acc.items()}

        def _resolve_sid(raw_sid: Any, raw_name: Any) -> Optional[str]:
            s = str(raw_sid) if raw_sid is not None else ""
            if s in p_acc:
                return s
            n = str(raw_name) if raw_name is not None else ""
            return name_to_sid.get(n)

        # 4. 分析采样 Ticks：阵营轮次、经济强起习惯、CT/T 默认站位、CT 前顶判定、2D 坐标点
        team_ct_round_lanes: Dict[Tuple[str, int], Counter] = defaultdict(Counter)
        round_team_avg_equip: Dict[Tuple[int, int], List[float]] = defaultdict(list)
        start_rows: List[Any] = []

        if not ticks_df.empty:
            for _, row in ticks_df.iterrows():
                sid = _resolve_sid(row.get("steamid"), row.get("name"))
                if not sid:
                    continue
                t_num = row.get("team_num")
                if t_num not in (2, 3):
                    continue
                tick_val = int(row["tick"])
                r_num, phase = sampled_ticks_meta.get(tick_val, (-1, ""))
                if r_num < 0:
                    continue

                alive = bool(row.get("is_alive", True))
                equip = float(row.get("round_start_equip_value") or row.get("current_equip_value") or 0.0)

                if phase == "start":
                    if t_num == 3:
                        p_acc[sid]["ct_rounds"] += 1
                    else:
                        p_acc[sid]["t_rounds"] += 1
                    round_team_avg_equip[(r_num, int(t_num))].append(equip)
                    start_rows.append((sid, r_num, int(t_num), equip))

                elif phase in ("default", "mid_early") and alive:
                    cn_place, lane, is_ct_agg = resolve_callout(row.get("last_place_name"), map_name)
                    x_val = float(row.get("X") or 0.0)
                    y_val = float(row.get("Y") or 0.0)
                    rx, ry = world_to_radar_pct(x_val, y_val, map_name)

                    if phase == "default":
                        if t_num == 3:
                            if lane != "SPAWN":
                                p_acc[sid]["ct_callouts"][cn_place] += 1
                                p_acc[sid]["ct_lanes"][lane] += 1
                                team_ct_round_lanes[(p_acc[sid]["roster_group"], r_num)][lane] += 1
                            if len(p_acc[sid]["radar_points"]) < 60:
                                p_acc[sid]["radar_points"].append(
                                    {"x": rx, "y": ry, "side": "CT", "kind": "position", "place": cn_place, "round": r_num}
                                )
                        else:
                            if lane != "SPAWN":
                                p_acc[sid]["t_callouts"][cn_place] += 1
                                p_acc[sid]["t_lanes"][lane] += 1
                            if len(p_acc[sid]["radar_points"]) < 60:
                                p_acc[sid]["radar_points"].append(
                                    {"x": rx, "y": ry, "side": "T", "kind": "position", "place": cn_place, "round": r_num}
                                )

                    if t_num == 3 and is_ct_agg and phase == "default":
                        p_acc[sid]["ct_aggressive_rounds"] += 1

        # 统计低经济局强起率 (非手枪局，团队均装备 < 3400 时个人起枪 >= 1700)
        pistol_rounds = {valid_rounds[0]} if valid_rounds else set()
        if len(valid_rounds) > 12:
            pistol_rounds.add(valid_rounds[12])
        for sid, r_num, t_num, equip in start_rows:
            if r_num in pistol_rounds:
                continue
            team_equips = round_team_avg_equip.get((r_num, t_num), [])
            avg_eq = sum(team_equips) / max(len(team_equips), 1)
            if avg_eq < 3400:
                p_acc[sid]["low_econ_opportunities"] += 1
                if equip >= 1650:
                    p_acc[sid]["force_buy_rounds"] += 1

        # 5. 分析击杀事件：首杀/首死、补枪/白给率 (5秒内是否有队友补掉凶手)、KAST、枪械习惯
        survived_by_round: Dict[int, set] = defaultdict(set)
        died_by_round: Dict[int, set] = defaultdict(set)

        if not deaths_df.empty and "total_rounds_played" in deaths_df.columns:
            valid_deaths = deaths_df[~deaths_df["total_rounds_played"].isin(knife_rounds)].sort_values("tick")

            for r_num, grp in valid_deaths.groupby("total_rounds_played"):
                r_int = int(r_num)
                ft = round_freeze_ticks.get(r_int, int(grp["tick"].min()) - 10 * TICKRATE_DEFAULT)
                rows_list = list(grp.iterrows())

                for idx, (_, drow) in enumerate(rows_list):
                    vic_sid = _resolve_sid(drow.get("user_steamid"), drow.get("user_name"))
                    atk_sid = _resolve_sid(drow.get("attacker_steamid"), drow.get("attacker_name"))
                    ass_sid = _resolve_sid(drow.get("assister_steamid"), drow.get("assister_name"))
                    weapon = str(drow.get("weapon") or "unknown")
                    is_hs = bool(drow.get("headshot", False))
                    d_tick = int(drow.get("tick") or 0)
                    vic_team = drow.get("user_team_num")
                    atk_team = drow.get("attacker_team_num")

                    vic_place_cn, _, _ = resolve_callout(drow.get("user_last_place_name"), map_name)
                    atk_place_cn, _, _ = resolve_callout(drow.get("attacker_last_place_name"), map_name)

                    if vic_sid:
                        p_acc[vic_sid]["deaths"] += 1
                        died_by_round[r_int].add(vic_sid)

                    if atk_sid and atk_sid != vic_sid and atk_team != vic_team:
                        p_acc[atk_sid]["kills"] += 1
                        p_acc[atk_sid]["kast_rounds"].add(r_int)
                        p_acc[atk_sid]["weapon_kills"][weapon] += 1
                        if is_hs:
                            p_acc[atk_sid]["hs_kills"] += 1
                        if "awp" in weapon.lower():
                            p_acc[atk_sid]["awp_kills"] += 1

                    if ass_sid and ass_sid in p_acc:
                        p_acc[ass_sid]["assists"] += 1
                        p_acc[ass_sid]["kast_rounds"].add(r_int)

                    # 首杀 / 首死 (每回合第一笔有效击杀)
                    if idx == 0 and atk_sid and vic_sid and atk_sid != vic_sid:
                        vx = float(drow.get("user_X") or 0.0)
                        vy = float(drow.get("user_Y") or 0.0)
                        ax = float(drow.get("attacker_X") or vx)
                        ay = float(drow.get("attacker_Y") or vy)
                        vrx, vry = world_to_radar_pct(vx, vy, map_name)
                        arx, ary = world_to_radar_pct(ax, ay, map_name)

                        spot_label = vic_place_cn if vic_place_cn != "未知区域" else atk_place_cn
                        p_acc[atk_sid]["opening_kill_spots"][spot_label] += 1
                        p_acc[vic_sid]["opening_death_spots"][spot_label] += 1

                        if atk_team == 3:
                            p_acc[atk_sid]["opening_kills_ct"] += 1
                            if (d_tick - ft) <= 22 * TICKRATE_DEFAULT:
                                p_acc[atk_sid]["ct_aggressive_rounds"] += 1
                        else:
                            p_acc[atk_sid]["opening_kills_t"] += 1

                        if vic_team == 3:
                            p_acc[vic_sid]["opening_deaths_ct"] += 1
                            if (d_tick - ft) <= 22 * TICKRATE_DEFAULT:
                                p_acc[vic_sid]["ct_aggressive_rounds"] += 1
                        else:
                            p_acc[vic_sid]["opening_deaths_t"] += 1

                        p_acc[atk_sid]["radar_points"].append(
                            {
                                "x": arx,
                                "y": ary,
                                "side": "CT" if atk_team == 3 else "T",
                                "kind": "opening_kill",
                                "place": spot_label,
                                "round": r_int,
                            }
                        )
                        p_acc[vic_sid]["radar_points"].append(
                            {
                                "x": vrx,
                                "y": vry,
                                "side": "CT" if vic_team == 3 else "T",
                                "kind": "opening_death",
                                "place": spot_label,
                                "round": r_int,
                            }
                        )

                    # 补枪判定 (5 秒窗口内凶手是否被阵亡者的队友击杀)
                    if vic_sid and atk_sid and atk_sid != vic_sid:
                        was_traded = False
                        for _, next_drow in rows_list[idx + 1 :]:
                            ntick = int(next_drow.get("tick") or 0)
                            if ntick - d_tick > 5 * TICKRATE_DEFAULT:
                                break
                            next_vic = _resolve_sid(next_drow.get("user_steamid"), next_drow.get("user_name"))
                            if next_vic == atk_sid:
                                was_traded = True
                                break
                        if was_traded:
                            p_acc[vic_sid]["kast_rounds"].add(r_int)
                        else:
                            p_acc[vic_sid]["untraded_deaths"] += 1

        # 存活回合计入 KAST
        for r_int in valid_rounds:
            for sid in p_acc:
                if sid not in died_by_round[r_int]:
                    survived_by_round[r_int].add(sid)
                    p_acc[sid]["kast_rounds"].add(r_int)

        # 6. 伤害统计 (ADR)
        if not hurt_df.empty:
            for _, hrow in hurt_df.iterrows():
                r_num = int(hrow.get("total_rounds_played") or 0)
                if r_num in knife_rounds:
                    continue
                atk_sid = _resolve_sid(hrow.get("attacker_steamid"), hrow.get("attacker_name"))
                vic_sid = _resolve_sid(hrow.get("user_steamid"), hrow.get("user_name"))
                atk_team = hrow.get("attacker_team_num")
                vic_team = hrow.get("user_team_num")
                if atk_sid and atk_sid != vic_sid and atk_team != vic_team:
                    dmg = min(int(hrow.get("dmg_health") or 0), 100)
                    p_acc[atk_sid]["damage"] += max(0, dmg)

        # 7. 道具与闪光效率统计
        for util_df, key_name in (
            (smoke_df, "smokes_thrown"),
            (flash_df, "flashes_thrown"),
            (he_df, "he_thrown"),
            (molly_df, "molotovs_thrown"),
        ):
            if not util_df.empty:
                for _, urow in util_df.iterrows():
                    sid = _resolve_sid(urow.get("user_steamid"), urow.get("user_name"))
                    if sid:
                        p_acc[sid][key_name] += 1

        if not blind_df.empty:
            for _, brow in blind_df.iterrows():
                atk_sid = _resolve_sid(brow.get("attacker_steamid"), brow.get("attacker_name"))
                vic_sid = _resolve_sid(brow.get("user_steamid"), brow.get("user_name"))
                atk_t = brow.get("attacker_team_num")
                vic_t = brow.get("user_team_num")
                dur = float(brow.get("blind_duration") or 0.0)
                if atk_sid and vic_sid and atk_t != vic_t and dur >= 1.2:
                    p_acc[atk_sid]["enemies_blinded"] += 1

        # 8. 团队宏观指标：CT 默认阵型 & T 下包方向/提速快攻率
        team_macro: Dict[str, Dict[str, Any]] = {
            "TEAM_A": {"formations": Counter(), "plant_sites": Counter(), "fast_plants": 0, "total_plants": 0},
            "TEAM_B": {"formations": Counter(), "plant_sites": Counter(), "fast_plants": 0, "total_plants": 0},
        }
        for (r_group, _r_num), lane_cnt in team_ct_round_lanes.items():
            a_c, m_c, b_c = lane_cnt.get("A", 0), lane_cnt.get("MID", 0), lane_cnt.get("B", 0)
            if a_c + m_c + b_c >= 3:
                team_macro[r_group]["formations"][f"{a_c}A-{m_c}中-{b_c}B"] += 1

        if not plant_df.empty:
            for _, prow in plant_df.iterrows():
                r_int = int(prow.get("total_rounds_played") or 0)
                if r_int in knife_rounds:
                    continue
                sid = _resolve_sid(prow.get("user_steamid"), prow.get("user_name"))
                if not sid:
                    continue
                r_group = p_acc[sid]["roster_group"]
                _, lane, _ = resolve_callout(prow.get("user_last_place_name"), map_name)
                site = "B" if lane == "B" else "A"
                team_macro[r_group]["plant_sites"][site] += 1
                team_macro[r_group]["total_plants"] += 1
                ft = round_freeze_ticks.get(r_int, 0)
                ptick = int(prow.get("tick") or 0)
                if ft > 0 and (ptick - ft) <= 34 * TICKRATE_DEFAULT:
                    team_macro[r_group]["fast_plants"] += 1

        # 9. 组装标准化 Player 档案与队伍汇总
        players_out: List[Dict[str, Any]] = []
        for sid, d in p_acc.items():
            p_rounds = max(d["ct_rounds"] + d["t_rounds"], total_rounds)
            ct_rds = max(d["ct_rounds"], 1)
            t_rds = max(d["t_rounds"], 1)

            kills = d["kills"]
            deaths = d["deaths"]
            adr = round(d["damage"] / p_rounds, 1) if d["damage"] > 0 else round((kills * 78.0) / p_rounds, 1)
            hs_pct = round(d["hs_kills"] / max(kills, 1) * 100.0, 1)
            kast_pct = round(len(d["kast_rounds"]) / p_rounds * 100.0, 1)
            kd = round(kills / max(deaths, 1), 2)

            kpr = kills / p_rounds
            dpr = deaths / p_rounds
            impact = max(0.3, 2.13 * kpr + 0.42 * (d["assists"] / p_rounds) - 0.41)
            rating = round(
                max(0.35, 0.0073 * kast_pct + 0.3591 * kpr - 0.5329 * dpr + 0.2372 * impact + 0.0032 * adr + 0.1587),
                2,
            )

            ok_total = d["opening_kills_ct"] + d["opening_kills_t"]
            od_total = d["opening_deaths_ct"] + d["opening_deaths_t"]
            open_attempts = ok_total + od_total
            opening_attempt_rate = round(open_attempts / p_rounds * 100.0, 1)
            opening_win_rate = round(ok_total / max(open_attempts, 1) * 100.0, 1) if open_attempts > 0 else 50.0
            t_open_attempt_rate = round((d["opening_kills_t"] + d["opening_deaths_t"]) / t_rds * 100.0, 1)
            ct_aggression_rate = round(min(100.0, d["ct_aggressive_rounds"] / ct_rds * 100.0), 1)
            untraded_death_rate = round(d["untraded_deaths"] / max(deaths, 1) * 100.0, 1)
            force_buy_rate = (
                round(d["force_buy_rounds"] / d["low_econ_opportunities"] * 100.0, 1)
                if d["low_econ_opportunities"] > 0
                else 25.0
            )

            ct_lane_total = max(sum(d["ct_lanes"].values()), 1)
            ct_lanes_pct = {
                "A": round(d["ct_lanes"]["A"] / ct_lane_total * 100.0, 1),
                "MID": round(d["ct_lanes"]["MID"] / ct_lane_total * 100.0, 1),
                "B": round(d["ct_lanes"]["B"] / ct_lane_total * 100.0, 1),
            }
            t_lane_total = max(sum(d["t_lanes"].values()), 1)
            t_lanes_pct = {
                "A": round(d["t_lanes"]["A"] / t_lane_total * 100.0, 1),
                "MID": round(d["t_lanes"]["MID"] / t_lane_total * 100.0, 1),
                "B": round(d["t_lanes"]["B"] / t_lane_total * 100.0, 1),
            }

            util_total = d["smokes_thrown"] + d["flashes_thrown"] + d["he_thrown"] + d["molotovs_thrown"]
            util_per_round = round(util_total / p_rounds, 2)
            awp_kill_share = round(d["awp_kills"] / max(kills, 1) * 100.0, 1)

            stats_bundle = {
                "rating": rating,
                "adr": adr,
                "kd": kd,
                "kills": kills,
                "deaths": deaths,
                "assists": d["assists"],
                "hs_pct": hs_pct,
                "kast_pct": kast_pct,
                "opening_kills": ok_total,
                "opening_deaths": od_total,
                "opening_attempt_rate": opening_attempt_rate,
                "opening_win_rate": opening_win_rate,
                "t_opening_attempt_rate": t_open_attempt_rate,
                "ct_aggression_rate": ct_aggression_rate,
                "untraded_death_rate": untraded_death_rate,
                "force_buy_rate": force_buy_rate,
                "awp_kill_share": awp_kill_share,
                "utility_per_round": util_per_round,
                "smokes_per_round": round(d["smokes_thrown"] / p_rounds, 2),
                "flashes_per_round": round(d["flashes_thrown"] / p_rounds, 2),
                "molotovs_per_round": round(d["molotovs_thrown"] / p_rounds, 2),
                "enemies_blinded_per_round": round(d["enemies_blinded"] / p_rounds, 2),
                "flash_assists_plus_blind": round(d["enemies_blinded"] / p_rounds, 2),
                "clutch_wins": d["clutch_wins"],
            }

            ct_role, t_role, tags = _classify_roles(ct_lanes_pct, t_lanes_pct, stats_bundle)

            players_out.append(
                {
                    "steamid": sid,
                    "name": d["name"],
                    "team_id": d["roster_group"],
                    "rounds_played": p_rounds,
                    "ct_rounds": d["ct_rounds"],
                    "t_rounds": d["t_rounds"],
                    "ct_role": ct_role,
                    "t_role": t_role,
                    "style_tags": tags,
                    "stats": stats_bundle,
                    "ct_lanes_pct": ct_lanes_pct,
                    "t_lanes_pct": t_lanes_pct,
                    "ct_top_callouts": [
                        {"place": p, "pct": round(c / max(sum(d["ct_callouts"].values()), 1) * 100.0, 1), "count": c}
                        for p, c in d["ct_callouts"].most_common(4)
                    ],
                    "t_top_callouts": [
                        {"place": p, "pct": round(c / max(sum(d["t_callouts"].values()), 1) * 100.0, 1), "count": c}
                        for p, c in d["t_callouts"].most_common(4)
                    ],
                    "top_weapons": [
                        {"weapon": w, "kills": c, "pct": round(c / max(kills, 1) * 100.0, 1)}
                        for w, c in d["weapon_kills"].most_common(4)
                    ],
                    "opening_kill_spots": [
                        {"place": p, "count": c} for p, c in d["opening_kill_spots"].most_common(3)
                    ],
                    "opening_death_spots": [
                        {"place": p, "count": c} for p, c in d["opening_death_spots"].most_common(3)
                    ],
                    "radar_points": d["radar_points"][:80],
                }
            )

        players_out.sort(key=lambda p: (p["team_id"], -p["stats"]["rating"]))

        teams_summary = {}
        for t_id, default_label in (("TEAM_A", "队伍 A (首发CT)"), ("TEAM_B", "队伍 B (首发T)")):
            t_players = [p for p in players_out if p["team_id"] == t_id]
            macro = team_macro[t_id]
            tot_form = max(sum(macro["formations"].values()), 1)
            top_forms = [
                {"formation": f, "pct": round(c / tot_form * 100.0, 1)}
                for f, c in macro["formations"].most_common(3)
            ]
            tot_plants = max(macro["total_plants"], 1)
            a_plant_pct = round(macro["plant_sites"]["A"] / tot_plants * 100.0, 1) if macro["total_plants"] else 50.0
            b_plant_pct = round(macro["plant_sites"]["B"] / tot_plants * 100.0, 1) if macro["total_plants"] else 50.0
            fast_pct = round(macro["fast_plants"] / tot_plants * 100.0, 1) if macro["total_plants"] else 25.0
            avg_force = (
                round(sum(p["stats"]["force_buy_rate"] for p in t_players) / len(t_players), 1) if t_players else 25.0
            )
            leader_name = t_players[0]["name"] if t_players else default_label
            teams_summary[t_id] = {
                "team_id": t_id,
                "team_name": f"{leader_name} 所在队" if t_players else default_label,
                "ct_formations": top_forms or [{"formation": "2A-1中-2B", "pct": 60.0}],
                "t_attack_a_pct": a_plant_pct,
                "t_attack_b_pct": b_plant_pct,
                "t_fast_execute_pct": fast_pct,
                "team_force_buy_rate": avg_force,
            }

        return {
            "source_type": "real_demo",
            "demo_files": [src_path.name],
            "matches_count": 1,
            "map_name": map_name,
            "map_cn_name": map_meta["cn_name"],
            "map_landmarks": map_meta["landmarks"],
            "total_rounds": total_rounds,
            "score_text": f"共 {total_rounds} 回合有效对局",
            "teams": teams_summary,
            "players": players_out,
        }


def merge_demo_analyses(analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    支持多场同地图 Demo 合并画像（特别适合方案一：上传对手最近 3~5 场同图 Demo 聚合出稳定习惯）。
    """
    if not analyses:
        raise ValueError("没有可合并的 Demo 分析结果")
    if len(analyses) == 1:
        return analyses[0]

    base_map = analyses[0]["map_name"]
    same_map = [a for a in analyses if a["map_name"] == base_map] or analyses
    total_rounds = sum(a["total_rounds"] for a in same_map)
    demo_files = [f for a in same_map for f in a.get("demo_files", [])]

    # 按 steamid 聚合出场次数最多的核心阵容与其余玩家
    appear_count: Counter = Counter()
    grouped_entries: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for a in same_map:
        for p in a["players"]:
            key = p["steamid"] or p["name"]
            appear_count[key] += 1
            grouped_entries[key].append(p)

    merged_players: List[Dict[str, Any]] = []
    for key, plist in grouped_entries.items():
        tot_r = sum(p["rounds_played"] for p in plist)
        ct_r = sum(p["ct_rounds"] for p in plist)
        t_r = sum(p["t_rounds"] for p in plist)

        def _wavg(stat_key: str) -> float:
            return round(sum(p["stats"][stat_key] * p["rounds_played"] for p in plist) / max(tot_r, 1), 2)

        kills = sum(p["stats"]["kills"] for p in plist)
        deaths = sum(p["stats"]["deaths"] for p in plist)
        assists = sum(p["stats"]["assists"] for p in plist)

        ct_lanes = {
            lane: round(sum(p["ct_lanes_pct"][lane] * max(p["ct_rounds"], 1) for p in plist) / max(ct_r, 1), 1)
            for lane in ("A", "MID", "B")
        }
        t_lanes = {
            lane: round(sum(p["t_lanes_pct"][lane] * max(p["t_rounds"], 1) for p in plist) / max(t_r, 1), 1)
            for lane in ("A", "MID", "B")
        }

        ct_c: Counter = Counter()
        t_c: Counter = Counter()
        wk_c: Counter = Counter()
        ok_spots: Counter = Counter()
        od_spots: Counter = Counter()
        radar_pts: List[Dict[str, Any]] = []

        for p in plist:
            for item in p["ct_top_callouts"]:
                ct_c[item["place"]] += item.get("count", 1)
            for item in p["t_top_callouts"]:
                t_c[item["place"]] += item.get("count", 1)
            for item in p["top_weapons"]:
                wk_c[item["weapon"]] += item["kills"]
            for item in p["opening_kill_spots"]:
                ok_spots[item["place"]] += item["count"]
            for item in p["opening_death_spots"]:
                od_spots[item["place"]] += item["count"]
            radar_pts.extend(p.get("radar_points", []))

        stats_bundle = {
            "rating": round(_wavg("rating"), 2),
            "adr": round(_wavg("adr"), 1),
            "kd": round(kills / max(deaths, 1), 2),
            "kills": kills,
            "deaths": deaths,
            "assists": assists,
            "hs_pct": round(_wavg("hs_pct"), 1),
            "kast_pct": round(_wavg("kast_pct"), 1),
            "opening_kills": sum(p["stats"]["opening_kills"] for p in plist),
            "opening_deaths": sum(p["stats"]["opening_deaths"] for p in plist),
            "opening_attempt_rate": round(_wavg("opening_attempt_rate"), 1),
            "opening_win_rate": round(_wavg("opening_win_rate"), 1),
            "t_opening_attempt_rate": round(_wavg("t_opening_attempt_rate"), 1),
            "ct_aggression_rate": round(_wavg("ct_aggression_rate"), 1),
            "untraded_death_rate": round(_wavg("untraded_death_rate"), 1),
            "force_buy_rate": round(_wavg("force_buy_rate"), 1),
            "awp_kill_share": round(_wavg("awp_kill_share"), 1),
            "utility_per_round": round(_wavg("utility_per_round"), 2),
            "smokes_per_round": round(_wavg("smokes_per_round"), 2),
            "flashes_per_round": round(_wavg("flashes_per_round"), 2),
            "molotovs_per_round": round(_wavg("molotovs_per_round"), 2),
            "enemies_blinded_per_round": round(_wavg("enemies_blinded_per_round"), 2),
            "flash_assists_plus_blind": round(_wavg("enemies_blinded_per_round"), 2),
            "clutch_wins": sum(p["stats"]["clutch_wins"] for p in plist),
        }

        ct_role, t_role, tags = _classify_roles(ct_lanes, t_lanes, stats_bundle)
        # 出场多场的标记为核心研究对象 (TEAM_A)
        team_id = "TEAM_A" if appear_count[key] >= 2 else plist[0]["team_id"]

        merged_players.append(
            {
                "steamid": plist[0]["steamid"],
                "name": plist[-1]["name"],
                "team_id": team_id,
                "matches_played": len(plist),
                "rounds_played": tot_r,
                "ct_rounds": ct_r,
                "t_rounds": t_r,
                "ct_role": ct_role,
                "t_role": t_role,
                "style_tags": tags,
                "stats": stats_bundle,
                "ct_lanes_pct": ct_lanes,
                "t_lanes_pct": t_lanes,
                "ct_top_callouts": [
                    {"place": p, "pct": round(c / max(sum(ct_c.values()), 1) * 100.0, 1), "count": c}
                    for p, c in ct_c.most_common(4)
                ],
                "t_top_callouts": [
                    {"place": p, "pct": round(c / max(sum(t_c.values()), 1) * 100.0, 1), "count": c}
                    for p, c in t_c.most_common(4)
                ],
                "top_weapons": [
                    {"weapon": w, "kills": c, "pct": round(c / max(kills, 1) * 100.0, 1)}
                    for w, c in wk_c.most_common(4)
                ],
                "opening_kill_spots": [{"place": p, "count": c} for p, c in ok_spots.most_common(3)],
                "opening_death_spots": [{"place": p, "count": c} for p, c in od_spots.most_common(3)],
                "radar_points": radar_pts[:90],
            }
        )

    merged_players.sort(key=lambda p: (p["team_id"], -p.get("matches_played", 1), -p["stats"]["rating"]))
    return {
        "source_type": "real_demo_merged",
        "demo_files": demo_files,
        "matches_count": len(same_map),
        "map_name": base_map,
        "map_cn_name": same_map[0]["map_cn_name"],
        "map_landmarks": same_map[0]["map_landmarks"],
        "total_rounds": total_rounds,
        "score_text": f"聚合 {len(same_map)} 场同图 Demo · 共 {total_rounds} 回合",
        "teams": same_map[0]["teams"],
        "players": merged_players,
    }
