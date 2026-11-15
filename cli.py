#!/usr/bin/env python3
"""
命令行快速体验与真实 Demo 解析入口：

示例 1（直接跑方案一：对手 Mirage 3场聚合球探报告）：
  ./.venv/bin/python cli.py --sample scouting

示例 2（直接跑方案二：个人与五黑车队 Inferno 赛后习惯诊断）：
  ./.venv/bin/python cli.py --sample diagnosis

示例 3（解析你本机从完美平台下载的真实 .dem 或 .zip 文件）：
  ./.venv/bin/python cli.py --demo ~/Downloads/pw_match1.dem ~/Downloads/pw_match2.dem --mode scouting
  ./.venv/bin/python cli.py --demo ~/Downloads/pw_match1.dem --mode diagnosis --player "你的游戏昵称"
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from backend.ai_analyzer import run_ai_analysis
from backend.demo_extractor import merge_demo_analyses, parse_single_demo
from backend.sample_data import get_sample_diagnosis_inferno, get_sample_scouting_mirage


async def _main() -> None:
    ap = argparse.ArgumentParser(description="CS2 完美平台 Demo 打法习惯 & Anti-Strat AI 分析器")
    ap.add_argument("--sample", choices=["scouting", "diagnosis"], help="运行内置高仿真样本数据")
    ap.add_argument("--demo", nargs="+", help="传入 1 个或多个真实 .dem / .zip 文件路径")
    ap.add_argument("--mode", choices=["scouting", "diagnosis"], default="scouting", help="分析模式：scouting(方案一球探) / diagnosis(方案二诊断)")
    ap.add_argument("--team", default="TEAM_A", choices=["TEAM_A", "TEAM_B"], help="方案一目标对手队伍 ID")
    ap.add_argument("--player", default="", help="方案二主视角玩家昵称或 SteamID（支持模糊匹配）")
    ap.add_argument("--export-json", default="", help="可选：将提取的结构化特征 JSON 保存到指定路径")
    ap.add_argument("--show-prompt", action="store_true", help="同时打印喂给大模型的完整结构化 Prompt")
    args = ap.parse_args()

    if args.demo:
        parsed = [parse_single_demo(Path(p).expanduser()) for p in args.demo]
        dataset = merge_demo_analyses(parsed)
        mode = args.mode
    elif args.sample == "diagnosis":
        dataset = get_sample_diagnosis_inferno()
        mode = "diagnosis"
    else:
        dataset = get_sample_scouting_mirage()
        mode = "scouting" if not args.sample else args.sample

    focus_sid = None
    if args.player:
        kw = args.player.lower()
        matched = next(
            (p for p in dataset["players"] if kw in p["name"].lower() or kw == str(p["steamid"]).lower()),
            None,
        )
        if matched:
            focus_sid = matched["steamid"]

    print("=" * 76)
    print(f"🗺️  地图: {dataset['map_cn_name']} | {dataset['score_text']}")
    print(f"👥 识别选手数: {len(dataset['players'])} 人 | 当前模式: {'方案一·赛前对手球探' if mode == 'scouting' else '方案二·个人与车队习惯诊断'}")
    print("=" * 76)
    for p in dataset["players"]:
        s = p["stats"]
        ct_spot = p["ct_top_callouts"][0]["place"] if p["ct_top_callouts"] else "-"
        t_spot = p["t_top_callouts"][0]["place"] if p["t_top_callouts"] else "-"
        print(
            f"[{p['team_id']}] {p['name']:<20} | Rating {s['rating']:<4} ADR {s['adr']:<5} "
            f"| CT常驻:{ct_spot:<9} (前压{s['ct_aggression_rate']}%) | T常走:{t_spot:<9} | 白给率:{s['untraded_death_rate']}%"
        )
    print("-" * 76)

    result = await run_ai_analysis(
        data=dataset,
        mode=mode,
        target_team_id=args.team,
        focus_steamid=focus_sid,
    )
    print(f"🤖 分析引擎: {result['engine']}\n")
    print(result["report_markdown"])

    if args.show_prompt:
        print("\n" + "=" * 76)
        print("📋 结构化 LLM Prompt 预览:")
        print("=" * 76)
        print(result["prompt"])

    if args.export_json:
        out_p = Path(args.export_json)
        out_p.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n✅ 已导出结构化遥测 JSON 至: {out_p}")


if __name__ == "__main__":
    asyncio.run(_main())
