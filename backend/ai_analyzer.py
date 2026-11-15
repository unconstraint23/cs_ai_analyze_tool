"""
双模式战术 AI 分析引擎：
- 模式 1 (scouting)：方案一 · 赛前对手球探与针对性战术报告 (Anti-Strat)
- 模式 2 (diagnosis)：方案二 · 个人与固定车队地图打法习惯诊断 & 赛后复盘

同时支持：
1. 接入任意 OpenAI 兼容大模型 API (DeepSeek / 通义千问 Qwen / OpenAI / Kimi / 本地 Ollama)
2. 零配置离线「规则战术教练引擎」：无需 API Key 即可对任意真实解析出的 .dem 数据动态生成深度战术报告
3. 一键导出结构化 Prompt（方便直接复制到外部 AI 对话框）
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import dotenv_values, set_key

logger = logging.getLogger("cs2_tactical.llm")
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

# 鉴权失败熔断：同一组 (Base URL + Key) 一旦返回 401/403，后续请求不再重复打远端，
# 直到用户修改模型配置或「实测调用」成功后自动解除，避免每次切换选手/示例都刷一遍报错。
_AUTH_FAILED: Dict[str, str] = {}


def _cfg_fingerprint(base_url: str, api_key: str) -> str:
    import hashlib

    return hashlib.sha256(f"{base_url.strip().lower()}|{api_key.strip()}".encode()).hexdigest()[:16]


def _mask_key(k: str) -> str:
    return f"****{k[-4:]}" if len(k) >= 4 else "(空)"


def _friendly_auth_error(base_url: str, api_key: str, status: int) -> str:
    from urllib.parse import urlparse

    host = urlparse(base_url).netloc or base_url
    hint = ""
    if "deepseek.com" in host and api_key and not api_key.startswith("sk-"):
        hint = "（DeepSeek 官方 Key 均以 sk- 开头，当前 Key 格式不符，可能来自其他平台）"
    return (
        f"API Key 鉴权失败 (HTTP {status})：{host} 不认可当前 Key {_mask_key(api_key)}{hint}。"
        f"请在右上角「AI 引擎配置」中填写该平台有效的 Key 或切换到 Key 所属平台的 Base URL，"
        f"点击「实测调用模型服务」通过后保存即可。"
    )


def clear_auth_failures() -> None:
    _AUTH_FAILED.clear()


_PUBLIC_KEY_REQUIRED_HOSTS = (
    "api.deepseek.com",
    "api.openai.com",
    "api.anthropic.com",
    "dashscope.aliyuncs.com",
    "api.moonshot.cn",
    "open.bigmodel.cn",
    "ark.cn-beijing.volces.com",
)


def _fmt_callouts(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "无明显集中点位"
    return "、".join(f"{x['place']}({x['pct']}%)" for x in items[:3])


def _fmt_spots(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "暂无记录"
    return "、".join(f"{x['place']}({x['count']}次)" for x in items[:3])


def _serialize_player_for_prompt(p: Dict[str, Any]) -> str:
    s = p["stats"]
    weapons = "、".join(f"{w['weapon']}({w['pct']}%)" for w in p.get("top_weapons", [])[:3]) or "步枪为主"
    return (
        f"- 选手【{p['name']}】 | CT定位: {p['ct_role']} | T定位: {p['t_role']} | 标签: {', '.join(p.get('style_tags', [])) or '均衡型'}\n"
        f"  · 核心数据: Rating {s['rating']} | ADR {s['adr']} | K/D {s['kd']} | 爆头率 {s['hs_pct']}% | KAST {s['kast_pct']}%\n"
        f"  · 侵略与脱节: 首杀尝试率 {s['opening_attempt_rate']}% (首杀胜率 {s['opening_win_rate']}%) | "
        f"CT前压率 {s['ct_aggression_rate']}% | 阵亡未补枪(白给率) {s['untraded_death_rate']}% | 逆风强起率 {s['force_buy_rate']}%\n"
        f"  · CT分路占比: A区 {p['ct_lanes_pct']['A']}% / 中路 {p['ct_lanes_pct']['MID']}% / B区 {p['ct_lanes_pct']['B']}% "
        f"| 常驻报点: {_fmt_callouts(p.get('ct_top_callouts', []))}\n"
        f"  · T分路占比: A区 {p['t_lanes_pct']['A']}% / 中路 {p['t_lanes_pct']['MID']}% / B区 {p['t_lanes_pct']['B']}% "
        f"| 常走报点: {_fmt_callouts(p.get('t_top_callouts', []))}\n"
        f"  · 首杀高发点: {_fmt_spots(p.get('opening_kill_spots', []))} | 首死高发点: {_fmt_spots(p.get('opening_death_spots', []))}\n"
        f"  · 枪械与道具: 常用枪械[{weapons}] (AWP击杀占比 {s['awp_kill_share']}%) | "
        f"回合均道具 {s['utility_per_round']}颗 (烟{s['smokes_per_round']}/闪{s['flashes_per_round']}/火{s['molotovs_per_round']}, 均致盲敌人 {s['enemies_blinded_per_round']}次)"
    )


def build_scouting_prompt(data: Dict[str, Any], target_team_id: str = "TEAM_A") -> str:
    team_players = [p for p in data["players"] if p["team_id"] == target_team_id] or data["players"][:5]
    team_meta = data.get("teams", {}).get(target_team_id) or next(iter(data.get("teams", {}).values()), {})
    formations = "、".join(f"{f['formation']}({f['pct']}%)" for f in team_meta.get("ct_formations", []))

    players_block = "\n".join(_serialize_player_for_prompt(p) for p in team_players)
    return f"""你现在是顶级 CS2 职业战队的赛前数据分析师与战术指挥（IGL）。
请根据以下从完美世界对战平台历史 Demo 中提取出的对手结构化遥测数据，为我方撰写一份实战可直接照着指挥的《{data['map_cn_name']} 赛前对手球探与针对性战术简报 (Anti-Strat Report)》。

【比赛背景与宏观数据】
- 地图：{data['map_cn_name']} ({data['map_name']})
- 样本规模：{data['score_text']}
- 研究对象：{team_meta.get('team_name', target_team_id)}
- 对手 CT 常见默认阵型：{formations or '2A-1中-2B'}
- 对手 T 进攻主攻方向：A包点 {team_meta.get('t_attack_a_pct', 50)}% vs B包点 {team_meta.get('t_attack_b_pct', 50)}%（开局34秒内快攻提速占比：{team_meta.get('t_fast_execute_pct', 25)}%）
- 对手低经济局团队强起刚枪率：{team_meta.get('team_force_buy_rate', 30)}%

【对手五人详细地图习惯画像】
{players_block}

请严格按以下 5 个模块输出 Markdown 战术报告（拒绝空话，必须点名具体选手 ID、具体报点与数据支撑）：
1. **对手整体体系底牌速览**（阵型偏好、核心大腿是谁、最薄弱突破口是谁）
2. **我方做 T 进攻破局策略**（开局前 25 秒防谁前压架枪、主攻哪个薄弱包点、用哪几颗关键烟闪废掉对方主狙/大哥）
3. **我方做 CT 防守针对布置**（如何反制对方第一突破手与默认控图路线、如何抓死对方脱节单摸自由人）
4. **手枪局与经济局防翻盘预警**（根据对方强起率与沙鹰/冲锋枪偏好给出防刚枪预案）
5. **五名对手一句话临场口诀**（方便比赛热身时队长 30 秒内给队友快速播报）"""


def build_diagnosis_prompt(data: Dict[str, Any], focus_steamid: Optional[str] = None) -> str:
    players = data["players"]
    focus_player = next((p for p in players if p["steamid"] == focus_steamid), None) or players[0]
    my_team_id = focus_player["team_id"]
    teammates = [p for p in players if p["team_id"] == my_team_id and p["steamid"] != focus_player["steamid"]]
    opponents = [p for p in players if p["team_id"] != my_team_id]
    my_team_meta = data.get("teams", {}).get(my_team_id, {})

    teammates_block = "\n".join(_serialize_player_for_prompt(p) for p in teammates) or "（单人数据模式）"
    opp_block = "\n".join(_serialize_player_for_prompt(p) for p in opponents[:3]) or "（未包含对手明细）"

    return f"""你现在是专精 CS2 完美平台高分段的私人金牌复盘教练。
请根据以下从 `.dem` 录像中提取出的精确回合遥测数据，为主视角玩家【{focus_player['name']}】及其所在车队出具一份一针见血的《{data['map_cn_name']} 打法习惯诊断与上分改进处方》。

【对局信息与团队宏观表现】
- 地图：{data['map_cn_name']} ({data['map_name']}) | {data['score_text']}
- 我方 CT 常见阵型：{'、'.join(f"{x['formation']}({x['pct']}%)" for x in my_team_meta.get('ct_formations', []))}
- 我方 T 进攻方向偏好：A区 {my_team_meta.get('t_attack_a_pct', 50)}% / B区 {my_team_meta.get('t_attack_b_pct', 50)}%（快攻占比 {my_team_meta.get('t_fast_execute_pct', 20)}%）
- 我方逆风局强起率：{my_team_meta.get('team_force_buy_rate', 30)}%

【主视角玩家详细数据】
{_serialize_player_for_prompt(focus_player)}

【同队队友数据摘要】
{teammates_block}

【本场主要对手表现参考（用于定位我方被谁打穿）】
{opp_block}

请按以下 4 个模块输出深度复盘 Markdown（必须结合具体报点、CT/T 差异和百分比数据说话，语气专业犀利）：
1. **个人地图风格定位与亮点**（客观评价枪法、站位角色与贡献）
2. **致命坏习惯 TOP 3 深度剖析**（重点排查：固定点位无脑前压送首死、脱节白给未被补枪、道具利用率低、经济局乱强起等问题）
3. **车队协同漏洞与本场被针对复盘**（结合队友与对手首杀点位，还原为什么会丢分）
4. **下一场 {data['map_cn_name']} 立即可执行的 3 条改进清单**（给出具体到秒数、站位和道具的调整动作）"""


def generate_rule_based_report(
    data: Dict[str, Any],
    mode: str = "scouting",
    target_team_id: str = "TEAM_A",
    focus_steamid: Optional[str] = None,
) -> str:
    """内置规则战术引擎：无需外部 LLM Key，动态根据任意 Demo 解析指标生成高质量结构化报告。"""
    map_cn = data["map_cn_name"]

    if mode == "scouting":
        roster = [p for p in data["players"] if p["team_id"] == target_team_id] or data["players"][:5]
        team_meta = data.get("teams", {}).get(target_team_id) or next(iter(data.get("teams", {}).values()), {})

        carry = max(roster, key=lambda p: p["stats"]["rating"])
        weak_link = min(roster, key=lambda p: p["stats"]["rating"] + p["stats"]["opening_win_rate"] * 0.004)
        aggressor = max(roster, key=lambda p: p["stats"]["ct_aggression_rate"])
        awper = max(roster, key=lambda p: p["stats"]["awp_kill_share"])
        lurker = max(roster, key=lambda p: p["stats"]["untraded_death_rate"])
        util_guy = max(roster, key=lambda p: p["stats"]["utility_per_round"])

        top_formation = (team_meta.get("ct_formations") or [{"formation": "2A-1中-2B", "pct": 60.0}])[0]
        fav_site = "A包点" if team_meta.get("t_attack_a_pct", 50) >= team_meta.get("t_attack_b_pct", 50) else "B包点"
        fav_site_pct = max(team_meta.get("t_attack_a_pct", 50), team_meta.get("t_attack_b_pct", 50))

        weak_ct_spot = weak_link["ct_top_callouts"][0]["place"] if weak_link["ct_top_callouts"] else "包点死角"
        agg_spot = aggressor["ct_top_callouts"][0]["place"] if aggressor["ct_top_callouts"] else "前点"
        awp_spot = awper["ct_top_callouts"][0]["place"] if awper["ct_top_callouts"] else "中远距离架枪位"
        lurk_t_spot = lurker["t_top_callouts"][0]["place"] if lurker["t_top_callouts"] else "边路"

        bullet_lines = []
        for p in roster:
            s = p["stats"]
            ct_main = p["ct_top_callouts"][0]["place"] if p["ct_top_callouts"] else "机动"
            t_main = p["t_top_callouts"][0]["place"] if p["t_top_callouts"] else "跟大部队"
            bullet_lines.append(
                f"- **{p['name']}**（Rating `{s['rating']}`）：CT 常站 **{ct_main}**（前压率 `{s['ct_aggression_rate']}%`），"
                f"T 常走 **{t_main}**；{'手里常有大狙，切忌干拉！' if s['awp_kill_share'] >= 25 else ('枪硬爱主动找首杀，用闪光反清他！' if s['opening_attempt_rate'] >= 30 else ('容易单摸脱节白给，可双人抓死！' if s['untraded_death_rate'] >= 50 else '偏补枪辅助，优先击杀其身前突破手。'))}"
            )

        awp_note = (
            f"重点封锁主狙 **{awper['name']}**（AWP 击杀占比 `{awper['stats']['awp_kill_share']}%`），"
            f"其 CT 开局高频架点位于 **{awp_spot}**，务必先给烟/高闪再过点，严禁干拉对枪。"
            if awper["stats"]["awp_kill_share"] >= 20
            else f"对方全步枪体系为主，火力核心 **{carry['name']}** 常驻 **{awp_spot}**，建议用燃烧弹+瞬爆闪逼退其第一枪位。"
        )

        econ_note = (
            f"**高危强起预警**：该队逆风低经济局强起率高达 `{team_meta.get('team_force_buy_rate', 42)}%`！"
            f"赢下手枪局或重置局后，我方切忌单人贴近点冲锋送枪，务必抱团远距离架点防沙鹰/MP9 翻盘。"
            if team_meta.get("team_force_buy_rate", 30) >= 38
            else f"该队经济纪律较稳健（强起率 `{team_meta.get('team_force_buy_rate', 25)}%`），对方纯 Eco 局我方可大胆用冲锋枪前顶压缩空间刷经济。"
        )

        return f"""### 🎯 {map_cn} · 赛前对手球探与 Anti-Strat 简报
> 生成引擎：**内置战术规则引擎（基于 {data['total_rounds']} 回合 Demo 空间遥测动态推演）**

#### 1. 对手整体体系底牌速览
- **核心阵型惯性**：对手 CT 方有 **`{top_formation['pct']}%`** 的回合采用 **`{top_formation['formation']}`** 默认开局；T 方进攻明显偏向 **{fav_site}**（占比 **`{fav_site_pct}%`**，其中快攻提速占 `{team_meta.get('t_fast_execute_pct', 25)}%`）。
- **头号威胁大哥**：**{carry['name']}**（Rating `{carry['stats']['rating']}` / ADR `{carry['stats']['adr']}`，首杀胜率 `{carry['stats']['opening_win_rate']}%`），是全队打开局面的绝对核心。
- **最佳战术突破口**：**{weak_link['name']}**（Rating `{weak_link['stats']['rating']}`，首杀胜率仅 `{weak_link['stats']['opening_win_rate']}%`，白给率 `{weak_link['stats']['untraded_death_rate']}%`），其主防区域抗压能力明显偏弱。

#### 2. 我方做 T 进攻破局策略（重点！）
1. **开局前 22 秒架死前顶习惯**：数据显示 **{aggressor['name']}** 在 CT 方前压率高达 **`{aggressor['stats']['ct_aggression_rate']}%`**（高频出现在 **{agg_spot}**）。我方开局无需急于爆弹，先留 1~2 把长枪静音预瞄 **{agg_spot}** 等他主动送首杀，拿到 5v4 人数优势后再展开。
2. **封烟废掉核心火力点**：{awp_note}
3. **中期爆弹主攻薄弱侧**：**{weak_link['name']}** 在 CT 长期固守 **{weak_ct_spot}**，且其道具反清效率偏低（均致盲仅 `{weak_link['stats']['enemies_blinded_per_round']}` 次/局）。建议我方做默认骗出中路/强侧道具后，集中烟火套餐直接打穿 **{weak_ct_spot}**！

#### 3. 我方做 CT 防守针对布置
1. **重兵预判其主攻侧**：对方 T 方 **`{fav_site_pct}%`** 的下包集中在 **{fav_site}**，且 **{util_guy['name']}**（回合均投掷 `{util_guy['stats']['utility_per_round']}` 颗道具）一给爆弹往往代表真打，另一包点队友可提前一拍启动回防。
2. **抓单摸断后刷人数优势**：**{lurker['name']}** 常在 T 方单摸 **{lurk_t_spot}**，且阵亡未补枪（脱节白给率）高达 **`{lurker['stats']['untraded_death_rate']}%`**。我方可在中期安排双人静步同步清一次 **{lurk_t_spot}**，白拿人头且对方无法补枪。

#### 4. 手枪局与经济局防翻盘预警
- {econ_note}

#### 5. 五名对手临场 30 秒速记口诀
{chr(10).join(bullet_lines)}
"""

    # ==================== 模式 2：个人与车队习惯诊断复盘 ====================
    players = data["players"]
    me = next((p for p in players if p["steamid"] == focus_steamid), None) or players[0]
    s = me["stats"]
    my_team_id = me["team_id"]
    teammates = [p for p in players if p["team_id"] == my_team_id and p["steamid"] != me["steamid"]]
    opponents = [p for p in players if p["team_id"] != my_team_id]
    my_team_meta = data.get("teams", {}).get(my_team_id, {})

    ct_fav = me["ct_top_callouts"][0]["place"] if me["ct_top_callouts"] else "默认点位"
    t_fav = me["t_top_callouts"][0]["place"] if me["t_top_callouts"] else "默认分路"
    od_spot = me["opening_death_spots"][0]["place"] if me["opening_death_spots"] else ct_fav
    od_cnt = me["opening_death_spots"][0]["count"] if me["opening_death_spots"] else s["opening_deaths"]

    bad_habits: List[str] = []
    if s["ct_aggression_rate"] >= 35.0 and s["opening_win_rate"] < 48.0:
        bad_habits.append(
            f"**【习惯病灶 1：CT 开局高频惯性前顶送首死】** 你在 CT 方前压率高达 **`{s['ct_aggression_rate']}%`**，常驻 **{ct_fav}**，但首杀胜率仅有 **`{s['opening_win_rate']}%`**（在 **{od_spot}** 累计送出 `{od_cnt}` 次首死）。一旦前几次偷人得手或上头，后续回合很容易被对手提前预瞄或反清道具直接白给，导致全队频繁陷入 4v5 被动回防。"
        )
    if s["untraded_death_rate"] >= 48.0:
        bad_habits.append(
            f"**【习惯病灶 {len(bad_habits)+1}：走位与队友严重脱节（白给率过高）】** 你的阵亡未补枪率高达 **`{s['untraded_death_rate']}%`**（健康水平应低于 `38%`），KAST 仅为 **`{s['kast_pct']}%`**。无论在 **{t_fav}** 突破还是残局前压，你经常在队友闪光未到位或相隔两个身位以上时独自对枪阵亡，枪法数据再高也难以转化为胜率。"
        )
    if s["utility_per_round"] < 1.45 or s["enemies_blinded_per_round"] < 0.30:
        bad_habits.append(
            f"**【习惯病灶 {len(bad_habits)+1}：重枪法轻道具，高频带满道具阵亡】** 你每回合仅投掷 **`{s['utility_per_round']}`** 颗道具，回合均有效致盲敌人仅 **`{s['enemies_blinded_per_round']}`** 次。在 **{od_spot}** 与 **{t_fav}** 交火时习惯纯靠干拉拼爆头率（当前爆头率 `{s['hs_pct']}%`），缺少先给自助闪/灭火烟的肌肉记忆。"
        )
    if s["force_buy_rate"] >= 45.0:
        bad_habits.append(
            f"**【习惯病灶 {len(bad_habits)+1}：逆风局上头强起破坏团队经济链】** 在团队低经济回合你的强起率达到 **`{s['force_buy_rate']}%`**。频繁半甲沙鹰/微冲强起导致长枪局也配不齐烟闪雷火，放大了防区劣势。"
        )
    if not bad_habits:
        bad_habits.append(
            f"**【细节提升项：路线可预测性偏高】** 你在 CT 有 `{me['ct_top_callouts'][0]['pct'] if me['ct_top_callouts'] else 50}%` 回合固定出现在 **{ct_fav}**，T 方长期走 **{t_fav}**，高分段对手在中后期极易针对你的固定站位预留穿点与燃烧弹。"
        )

    opp_note = ""
    if opponents:
        nemesis = max(opponents, key=lambda p: p["stats"]["rating"])
        nem_spot = nemesis["opening_kill_spots"][0]["place"] if nemesis["opening_kill_spots"] else od_spot
        opp_note = (
            f"- **本场对手针对复盘**：对面核心 **{nemesis['name']}**（Rating `{nemesis['stats']['rating']}`，首杀胜率 `{nemesis['stats']['opening_win_rate']}%`）"
            f"正是摸透了你们在 **{nem_spot}** 爱提前对枪且缺乏双架补枪的习惯，单点连续拿到 `{nemesis['stats']['opening_kills']}` 次首杀，直接打崩了你们的半场经济。"
        )

    team_avg_untraded = (
        round(sum(p["stats"]["untraded_death_rate"] for p in [me] + teammates) / (1 + len(teammates)), 1)
        if teammates
        else s["untraded_death_rate"]
    )

    return f"""### 🩺 {map_cn} · 【{me['name']}】个人与车队打法习惯诊断书
> 生成引擎：**内置战术规则引擎（基于本场 {data['total_rounds']} 回合精确坐标与事件流诊断）**

#### 1. 个人地图风格画像与亮点
- **当前角色定位**：CT 方属于 **{me['ct_role']}**（主防 **{ct_fav}**），T 方担任 **{me['t_role']}**（主走 **{t_fav}**）。
- **核心优势**：场均伤害 **`{s['adr']}` ADR**、爆头率 **`{s['hs_pct']}%`**，开局首交火参与率 **`{s['opening_attempt_rate']}%`**，具备很强的正面对枪意愿与空间撕扯能力。

#### 2. 致命坏习惯深度剖析（核心失分点）
{chr(10).join(f"{i+1}. {h}" for i, h in enumerate(bad_habits[:3]))}

#### 3. 车队协同漏洞与丢分还原
- **全队补枪协同率偏低**：你们全队平均阵亡未补枪（白给率）达到 **`{team_avg_untraded}%`**，且 T 方进攻有 **`{max(my_team_meta.get('t_attack_a_pct', 50), my_team_meta.get('t_attack_b_pct', 50))}%`** 扎堆打同一包点，快攻提速仅占 `{my_team_meta.get('t_fast_execute_pct', 20)}%`——慢摸控图时单人掉点过多，导致残局人数劣势。
{opp_note}

#### 4. 下一场 {map_cn} 立即可执行的 3 条改进清单
1. **给 CT 前压加“冷却锁”**：在 **{ct_fav}** 每半场前顶偷人控制在 **3 回合以内**；其余长枪局改为「开局先铺烟/火拖过前 20 秒 → 退守交叉火力位等队友反清闪」，把你的首死数直接砍半。
2. **绑定双人补枪间距（3 秒法则）**：做 T 走 **{t_fav}** 突破时，强制呼叫道具手队友贴后身位跟闪，确保即便被架死也能在 3 秒内完成 1 换 1，将 KAST 从 `{s['kast_pct']}%` 提升至 `74%+`。
3. **死前清空关键道具**：养成接敌前先交出至少 1 颗防冲烟 + 1 颗反清闪的习惯，将回合均道具投掷量从 `{s['utility_per_round']}` 提升到 `1.8+` 颗。
"""


def _normalize_model_name(raw_model: str, base_url: str) -> str:
    """
    针对官方 api.deepseek.com 自动将常见误写别名 (如 deepseek-v4.1-flash)
    归一化为官方标准 Model ID `deepseek-flash` (底层对应 DeepSeek-V4.1-Flash)。
    """
    m = raw_model.strip()
    low = m.lower().replace(" ", "-")
    if "deepseek.com" in base_url.lower():
        if low in (
            "deepseek-v4.1-flash",
            "deepseek-4.1-flash",
            "deepseek-v4-flash",
            "v4.1-flash",
        ):
            return "deepseek-flash"
    return m


# ==================== 多厂商模型服务适配 ====================
# provider:
#   deepseek  -> DeepSeek 官方 (OpenAI Chat Completions 协议 + thinking 扩展)
#   openai    -> OpenAI 官方 (Chat Completions 协议 + reasoning_effort)
#   anthropic -> Anthropic Claude 官方 (Messages API: /v1/messages + x-api-key)
#   custom    -> 任意 OpenAI 兼容接口 (火山方舟 / 阿里百炼 / 硅基流动 / Ollama / vLLM / 内网网关)

VALID_PROVIDERS = ("deepseek", "openai", "anthropic", "custom")

PROVIDER_DEFAULTS: Dict[str, Dict[str, str]] = {
    "deepseek": {"base_url": "https://api.deepseek.com", "model": "deepseek-flash"},
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-6.1-sol"},
    "anthropic": {"base_url": "https://api.anthropic.com", "model": "claude-sonnet-5-5"},
    "custom": {"base_url": "http://127.0.0.1:11434/v1", "model": "qwen2.5:14b"},
}

ANTHROPIC_VERSION = "2023-06-01"
SYSTEM_PROMPT = (
    "你是精通 Counter-Strike 2 完美世界对战平台生态与职业战术体系的数据分析教练，"
    "擅长从 Demo 坐标与事件统计中挖掘每位选手在特定地图上的打法习惯与漏洞。"
)


def _infer_provider(base_url: str) -> str:
    u = base_url.lower()
    if "anthropic.com" in u:
        return "anthropic"
    if "api.openai.com" in u:
        return "openai"
    if "deepseek.com" in u:
        return "deepseek"
    return "custom"


def _resolve_llm_params(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """合并前端请求参数、项目 .env 与进程环境变量中的模型连接配置。"""
    env_vals = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}

    def _from_env(k: str) -> str:
        val = env_vals.get(k)
        if val is None or str(val).strip() == "":
            val = os.getenv(k, "")
        return str(val).strip()

    resolved_url = (
        (base_url or "").strip()
        or _from_env("LLM_BASE_URL")
        or _from_env("OPENAI_BASE_URL")
        or "https://api.deepseek.com"
    ).rstrip("/")

    raw_provider = ((provider or "").strip() or _from_env("LLM_PROVIDER")).lower()
    resolved_provider = raw_provider if raw_provider in VALID_PROVIDERS else _infer_provider(resolved_url)

    resolved_key = (
        (api_key or "").strip()
        or _from_env("LLM_API_KEY")
        or (_from_env("ANTHROPIC_API_KEY") if resolved_provider == "anthropic" else "")
        or (_from_env("OPENAI_API_KEY") if resolved_provider == "openai" else "")
        or (_from_env("DEEPSEEK_API_KEY") if resolved_provider == "deepseek" else "")
    )

    # 本地 Ollama 若未带 /v1 自动补齐 OpenAI 兼容前缀
    if ":11434" in resolved_url and not resolved_url.endswith(("/v1", "/chat/completions")):
        resolved_url = f"{resolved_url}/v1"

    raw_model = (
        (model or "").strip()
        or _from_env("LLM_MODEL")
        or PROVIDER_DEFAULTS[resolved_provider]["model"]
    )
    resolved_model = _normalize_model_name(raw_model, resolved_url)
    resolved_effort = (
        (reasoning_effort or "").strip() or _from_env("LLM_REASONING_EFFORT") or "low"
    ).lower()

    if resolved_provider == "anthropic":
        if resolved_url.endswith("/messages"):
            endpoint = resolved_url
        elif resolved_url.endswith("/v1"):
            endpoint = f"{resolved_url}/messages"
        else:
            endpoint = f"{resolved_url}/v1/messages"
    else:
        endpoint = (
            resolved_url
            if resolved_url.endswith("/chat/completions")
            else f"{resolved_url}/chat/completions"
        )

    url_lower = resolved_url.lower()
    requires_public_key = resolved_provider in ("deepseek", "openai", "anthropic") or any(
        h in url_lower for h in _PUBLIC_KEY_REQUIRED_HOSTS
    )
    # 只要提供了 API Key，或配置了无需鉴权的私有部署/内网/本机模型地址，均执行远程调用
    should_call = bool(resolved_key) or not requires_public_key

    return {
        "provider": resolved_provider,
        "api_key": resolved_key,
        "base_url": resolved_url,
        "endpoint": endpoint,
        "model": resolved_model,
        "reasoning_effort": resolved_effort,
        "should_call": should_call,
    }


def save_llm_env_config(
    base_url: str,
    model: str,
    api_key: str,
    reasoning_effort: str = "low",
    provider: str = "deepseek",
) -> None:
    """将模型服务配置同步持久化到服务端 .env，确保直接上传/命令行/跨页面刷新均能调用模型。"""
    if not ENV_FILE.exists():
        ENV_FILE.write_text("", encoding="utf-8")
    prov = provider if provider in VALID_PROVIDERS else _infer_provider(base_url or "")
    set_key(str(ENV_FILE), "LLM_PROVIDER", prov)
    set_key(str(ENV_FILE), "LLM_BASE_URL", (base_url or PROVIDER_DEFAULTS[prov]["base_url"]).strip())
    set_key(str(ENV_FILE), "LLM_MODEL", (model or PROVIDER_DEFAULTS[prov]["model"]).strip())
    set_key(str(ENV_FILE), "LLM_API_KEY", (api_key or "").strip())
    set_key(str(ENV_FILE), "LLM_REASONING_EFFORT", (reasoning_effort or "low").strip())
    clear_auth_failures()


def _build_request(
    cfg: Dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    max_tokens: Optional[int] = None,
    effort_override: Optional[str] = None,
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """按厂商协议构造请求头与请求体。"""
    provider = cfg["provider"]
    effort = (effort_override or cfg["reasoning_effort"] or "low").lower()

    if provider == "anthropic":
        headers = {
            "Content-Type": "application/json",
            "x-api-key": cfg["api_key"],
            "anthropic-version": ANTHROPIC_VERSION,
        }
        payload: Dict[str, Any] = {
            "model": cfg["model"],
            "max_tokens": max_tokens or 8192,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        return headers, payload

    headers = {"Content-Type": "application/json"}
    if cfg["api_key"]:
        headers["Authorization"] = f"Bearer {cfg['api_key']}"

    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    if provider == "deepseek" and cfg["model"] == "deepseek-flash":
        if effort in ("none", "disabled"):
            payload["thinking"] = {"type": "disabled"}
            payload["temperature"] = 0.4
        else:
            payload["thinking"] = {"type": "enabled"}
            if effort in ("low", "high", "max"):
                payload["reasoning_effort"] = effort
    elif provider == "openai":
        # OpenAI 推理型模型开启 reasoning_effort 时不允许传 temperature
        if effort in ("low", "medium", "high"):
            payload["reasoning_effort"] = effort
        if max_tokens:
            payload["max_completion_tokens"] = max_tokens
    else:
        payload["temperature"] = 0.4

    if max_tokens and provider != "openai":
        payload["max_tokens"] = max_tokens
    return headers, payload


def _parse_response(provider: str, body: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """统一解析不同厂商的返回结构，返回 (正文, 思考链)。"""
    if provider == "anthropic":
        text_parts: List[str] = []
        thinking_parts: List[str] = []
        for block in body.get("content") or []:
            btype = block.get("type")
            if btype == "text":
                text_parts.append(block.get("text") or "")
            elif btype == "thinking":
                thinking_parts.append(block.get("thinking") or "")
        return "".join(text_parts), ("\n".join(thinking_parts) or None)

    msg = (body.get("choices") or [{}])[0].get("message") or {}
    return (msg.get("content") or ""), (msg.get("reasoning_content") or None)


_OPTIONAL_PARAMS = ("reasoning_effort", "thinking", "temperature", "max_completion_tokens")


async def _post_llm(
    cfg: Dict[str, Any],
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout: float,
) -> httpx.Response:
    """发送请求；若因可选参数（如 reasoning_effort / temperature）不被该模型支持返回 400，则去掉后自动重试一次。"""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(cfg["endpoint"], headers=headers, json=payload)
        if resp.status_code == 400:
            err_text = resp.text.lower()
            stripped = {k: v for k, v in payload.items() if k not in _OPTIONAL_PARAMS}
            if stripped != payload and any(p in err_text for p in _OPTIONAL_PARAMS + ("unsupported", "not support")):
                print(
                    f"[LLM-CALL] 400 参数不兼容，去掉可选参数后重试 | model={cfg['model']}",
                    flush=True,
                )
                resp = await client.post(cfg["endpoint"], headers=headers, json=stripped)
        return resp


async def test_llm_connection(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """向目标模型服务发送一条真实连通性探针请求，验证网络、鉴权与后台调用日志记录。"""
    cfg = _resolve_llm_params(api_key, base_url, model, reasoning_effort, provider)
    if not cfg["should_call"]:
        raise ValueError("公有云模型服务需要填写有效的 API Key 后才能发起调用")

    headers, payload = _build_request(
        cfg,
        system_prompt="你是连通性测试助手。",
        user_prompt="请回复“CS2战术模型服务连通正常”这几个字。",
        max_tokens=64,
        effort_override="none" if cfg["provider"] == "deepseek" else None,
    )

    t0 = time.perf_counter()
    print(
        f"[LLM-TEST] POST {cfg['endpoint']} | provider={cfg['provider']} | model={cfg['model']}",
        flush=True,
    )
    resp = await _post_llm(cfg, headers, payload, timeout=30.0)
    latency_ms = int((time.perf_counter() - t0) * 1000)
    if resp.status_code in (401, 403):
        raise RuntimeError(_friendly_auth_error(cfg["base_url"], cfg["api_key"], resp.status_code))
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    content, reasoning = _parse_response(cfg["provider"], resp.json())
    _AUTH_FAILED.pop(_cfg_fingerprint(cfg["base_url"], cfg["api_key"]), None)
    return {
        "ok": True,
        "provider": cfg["provider"],
        "endpoint": cfg["endpoint"],
        "model": cfg["model"],
        "latency_ms": latency_ms,
        "reply": (content or reasoning or "").strip()[:120],
    }


async def run_ai_analysis(
    data: Dict[str, Any],
    mode: str = "scouting",
    target_team_id: str = "TEAM_A",
    focus_steamid: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    provider: Optional[str] = None,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """
    use_llm=True 且配置了外部大模型时，调用对应厂商的模型服务生成深度战术报告；
    use_llm=False（如内置示例）或未配置模型时，直接使用内置规则战术引擎生成报告，不发起任何远程请求。
    """
    prompt = (
        build_scouting_prompt(data, target_team_id=target_team_id)
        if mode == "scouting"
        else build_diagnosis_prompt(data, focus_steamid=focus_steamid)
    )

    def _rule_result(engine: str = "rule_engine", warning: Optional[str] = None) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "engine": engine,
            "report_markdown": generate_rule_based_report(
                data, mode=mode, target_team_id=target_team_id, focus_steamid=focus_steamid
            ),
            "prompt": prompt,
        }
        if warning:
            res["warning"] = warning
        return res

    if not use_llm:
        return _rule_result()

    cfg = _resolve_llm_params(api_key, base_url, model, reasoning_effort, provider)
    if not cfg["should_call"]:
        return _rule_result()

    fp = _cfg_fingerprint(cfg["base_url"], cfg["api_key"])
    if fp in _AUTH_FAILED:
        # 已知该 Key 鉴权失败：不再重复请求远端
        return _rule_result("rule_engine_fallback", _AUTH_FAILED[fp])

    headers, payload = _build_request(cfg, SYSTEM_PROMPT, prompt)

    t0 = time.perf_counter()
    print(
        f"[LLM-CALL] -> POST {cfg['endpoint']} | provider={cfg['provider']} | model={cfg['model']} | mode={mode}",
        flush=True,
    )
    try:
        resp = await _post_llm(cfg, headers, payload, timeout=180.0)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        if resp.status_code in (401, 403):
            friendly = _friendly_auth_error(cfg["base_url"], cfg["api_key"], resp.status_code)
            _AUTH_FAILED[fp] = friendly
            raise RuntimeError(friendly)
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:350]}")
        content, reasoning_text = _parse_response(cfg["provider"], resp.json())
        print(
            f"[LLM-CALL] <- 200 OK ({elapsed_ms}ms) | model={cfg['model']} | chars={len(content)}",
            flush=True,
        )
        return {
            "engine": f"llm ({cfg['model']})",
            "report_markdown": content,
            "reasoning_markdown": reasoning_text,
            "prompt": prompt,
        }
    except Exception as exc:
        print(f"[LLM-CALL] !! FAILED ({cfg['endpoint']}): {exc}", flush=True)
        warn_text = (
            _AUTH_FAILED[fp]
            if fp in _AUTH_FAILED
            else f"远程大模型服务 ({cfg['endpoint']} | {cfg['model']}) 调用失败：{exc}。已自动切换为内置战术规则引擎生成报告。"
        )
        return _rule_result("rule_engine_fallback", warn_text)
