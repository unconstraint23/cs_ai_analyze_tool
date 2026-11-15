"""端到端自检测试：验证样本流、双模式 AI 分析流、多场 Demo 聚合器、LLM 参数解析与持久化历史记录路由。"""

from __future__ import annotations

import asyncio
from copy import deepcopy

import httpx

from backend.ai_analyzer import _build_request, _parse_response, _resolve_llm_params
from backend.app import app
from backend.db import save_session_with_initial_report
from backend.demo_extractor import merge_demo_analyses
from backend.sample_data import get_sample_diagnosis_inferno, get_sample_scouting_mirage


async def run_tests() -> None:
    # 1. 验证 LLM 配置归一化与自建/云端触发判定
    p_ds = _resolve_llm_params(
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        model="deepseek-v4.1-flash",
    )
    assert p_ds["model"] == "deepseek-flash"
    assert p_ds["should_call"] is True

    p_lan = _resolve_llm_params(
        api_key="",
        base_url="http://192.168.1.88:8000/v1",
        model="deepseek-v4.1-flash",
    )
    assert p_lan["should_call"] is True
    assert p_lan["endpoint"] == "http://192.168.1.88:8000/v1/chat/completions"

    # Anthropic Messages API 适配
    p_ant = _resolve_llm_params(
        api_key="sk-ant-test", base_url="https://api.anthropic.com", model="claude-sonnet-5-5", provider="anthropic"
    )
    assert p_ant["endpoint"] == "https://api.anthropic.com/v1/messages"
    h_ant, body_ant = _build_request(p_ant, "sys", "user")
    assert h_ant["x-api-key"] == "sk-ant-test" and "anthropic-version" in h_ant
    assert body_ant["system"] == "sys" and body_ant["messages"][0]["role"] == "user"
    txt, think = _parse_response(
        "anthropic",
        {"content": [{"type": "thinking", "thinking": "T"}, {"type": "text", "text": "OK"}]},
    )
    assert txt == "OK" and think == "T"

    # OpenAI 适配
    p_oai = _resolve_llm_params(api_key="sk-x", base_url="https://api.openai.com/v1", model="o4-mini", provider="openai")
    assert p_oai["endpoint"] == "https://api.openai.com/v1/chat/completions"
    _, body_oai = _build_request(p_oai, "sys", "user")
    assert "temperature" not in body_oai and body_oai["reasoning_effort"] == "low"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        r_index = await client.get("/")
        assert r_index.status_code == 200

        r_health = await client.get("/api/health")
        assert r_health.status_code == 200

        r_db = await client.get("/api/db/status")
        assert r_db.status_code == 200
        assert "connected" in r_db.json()

        r_scout = await client.get("/api/samples/scouting")
        assert r_scout.status_code == 200
        scout_json = r_scout.json()
        assert scout_json["dataset"]["map_name"] == "de_mirage"
        assert len(scout_json["dataset"]["players"]) == 5
        assert "Anti-Strat" in scout_json["analysis"]["report_markdown"]
        assert scout_json["analysis"]["engine"] == "rule_engine"  # 示例不调用模型

        r_diag = await client.get("/api/samples/diagnosis")
        assert r_diag.status_code == 200
        diag_json = r_diag.json()
        assert diag_json["dataset"]["map_name"] == "de_inferno"
        assert len(diag_json["dataset"]["players"]) == 7
        assert "诊断书" in diag_json["analysis"]["report_markdown"]

        # 2. 验证真实上传后的持久化归档与历史回看、追加报告及删除闭环
        saved = save_session_with_initial_report(
            dataset=diag_json["dataset"],
            analysis=diag_json["analysis"],
            mode="scouting",
            target_team_id="TEAM_A",
            focus_steamid=diag_json["dataset"]["players"][0]["steamid"],
        )
        s_uid = saved["session_uid"]

        r_list = await client.get("/api/sessions")
        assert r_list.status_code == 200
        assert any(item["session_uid"] == s_uid for item in r_list.json()["items"])

        # 在该会话下切换选手追加生成第二份诊断报告并自动持久化
        second_sid = diag_json["dataset"]["players"][1]["steamid"]
        r_analyze = await client.post(
            "/api/analyze",
            json={
                "data": diag_json["dataset"],
                "mode": "diagnosis",
                "focus_steamid": second_sid,
                "session_uid": s_uid,
            },
        )
        assert r_analyze.status_code == 200
        assert diag_json["dataset"]["players"][1]["name"] in r_analyze.json()["report_markdown"]

        # 同一维度再次请求：直接复用已存报告，不再调用模型
        r_again = await client.post(
            "/api/analyze",
            json={
                "data": diag_json["dataset"],
                "mode": "diagnosis",
                "focus_steamid": second_sid,
                "session_uid": s_uid,
            },
        )
        assert r_again.json().get("from_cache") is True

        # 示例模式 use_llm=False：始终规则引擎
        r_sample = await client.post(
            "/api/analyze",
            json={"data": diag_json["dataset"], "mode": "diagnosis", "focus_steamid": second_sid, "use_llm": False},
        )
        assert r_sample.json()["engine"] == "rule_engine"

        r_detail = await client.get(f"/api/sessions/{s_uid}")
        assert r_detail.status_code == 200
        detail_json = r_detail.json()
        assert len(detail_json["reports"]) == 2

        r_del = await client.delete(f"/api/sessions/{s_uid}")
        assert r_del.status_code == 200

    # 3. 验证多场同图 Demo 聚合逻辑
    d1 = deepcopy(get_sample_diagnosis_inferno())
    d2 = deepcopy(get_sample_diagnosis_inferno())
    merged = merge_demo_analyses([d1, d2])
    assert merged["matches_count"] == 2
    assert merged["total_rounds"] == 48
    assert merged["players"][0]["rounds_played"] == 48

    print("✅ ALL INTEGRATION TESTS PASSED!")


if __name__ == "__main__":
    asyncio.run(run_tests())
