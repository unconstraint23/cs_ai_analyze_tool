"""
FastAPI 后端服务：
- GET    /                          -> Web 战术分析工作台首页
- GET    /api/samples/{kind}        -> 加载内置高仿真样本 (scouting | diagnosis)
- POST   /api/parse-demos           -> 上传 1~N 个真实 CS2 .dem/.zip/.gz/.bz2 解析、调用大模型并持久化存入 MySQL
- POST   /api/parse-local           -> 直接读取本机磁盘上的 .dem 文件路径解析并存入 MySQL
- POST   /api/analyze               -> 运行方案一（对手球探）或方案二（个人与车队习惯诊断）AI 分析（若属真实会话同步入库）
- GET    /api/sessions              -> 查询 MySQL 中已保存的历史 Demo 分析记录列表
- GET    /api/sessions/{session_uid}-> 读取单条历史 Demo 完整遥测数据与全部历史 AI 报告
- DELETE /api/sessions/{session_uid}-> 删除指定历史 Demo 记录
- GET    /api/db/status             -> 查询 MySQL 连接健康度与库表统计
- POST   /api/db/config             -> 在线更新 MySQL 连接配置 (.env)、自动建库建表并同步缓存队列
- POST   /api/llm/config            -> 同步保存大模型配置至服务端 .env
- POST   /api/llm/test              -> 实测大模型接口连通性与延迟
"""

from __future__ import annotations

import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .ai_analyzer import run_ai_analysis, save_llm_env_config, test_llm_connection
from .db import (
    delete_session,
    find_existing_report,
    get_db_status,
    get_session_detail,
    init_db,
    list_sessions,
    save_report_to_existing_session,
    save_session_with_initial_report,
    update_mysql_config,
)
from .demo_extractor import merge_demo_analyses, parse_single_demo
from .sample_data import get_sample_diagnosis_inferno, get_sample_scouting_mirage

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST_DIR = ROOT_DIR / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    ok, err, synced = init_db()
    if ok:
        print(
            f"[MySQL] 已成功连接并初始化数据库表结构 (自动同步历史缓存 {synced} 条)",
            flush=True,
        )
    else:
        print(
            f"[MySQL] 启动时暂未连通 ({err}) —— 请在 .env 或网页右上角「MySQL存储」中填入密码完成连接。",
            flush=True,
        )
    yield


app = FastAPI(
    title="CS2 完美平台 Demo 地图打法习惯 & Anti-Strat AI 原型",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if (FRONTEND_DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST_DIR / "assets")), name="assets")


class LocalPathsRequest(BaseModel):
    paths: List[str]
    mode: str = "scouting"
    provider: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    reasoning_effort: Optional[str] = None


class AnalyzeRequest(BaseModel):
    data: Dict[str, Any]
    mode: str = "scouting"  # "scouting" | "diagnosis"
    target_team_id: str = "TEAM_A"
    focus_steamid: Optional[str] = None
    session_uid: Optional[str] = None
    use_llm: bool = True  # 内置示例传 False：仅用规则引擎，不调用模型服务
    force: bool = False  # True：忽略已存报告，强制重新调用模型生成
    provider: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    reasoning_effort: Optional[str] = None


class MysqlConfigRequest(BaseModel):
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: Optional[str] = None
    database: str = "cs2_tactical"


class LlmConfigRequest(BaseModel):
    provider: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-flash"
    api_key: str = ""
    reasoning_effort: str = "low"


@app.get("/")
async def index() -> FileResponse:
    index_file = FRONTEND_DIST_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(
            status_code=503,
            detail="前端尚未构建，请先在 frontend 目录执行 pnpm build，或访问 Vite 开发服 http://127.0.0.1:5173",
        )
    return FileResponse(str(index_file))


@app.get("/api/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/db/status")
async def db_status_endpoint() -> Dict[str, Any]:
    return get_db_status()


@app.post("/api/db/config")
async def db_config_endpoint(req: MysqlConfigRequest) -> Dict[str, Any]:
    try:
        return update_mysql_config(
            host=req.host,
            port=req.port,
            user=req.user,
            password=req.password,
            database=req.database,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/llm/config")
async def llm_config_endpoint(req: LlmConfigRequest) -> Dict[str, Any]:
    save_llm_env_config(
        base_url=req.base_url,
        model=req.model,
        api_key=req.api_key,
        reasoning_effort=req.reasoning_effort,
        provider=req.provider,
    )
    return {"status": "saved"}


@app.post("/api/llm/test")
async def llm_test_endpoint(req: LlmConfigRequest) -> Dict[str, Any]:
    try:
        return await test_llm_connection(
            api_key=req.api_key,
            base_url=req.base_url,
            model=req.model,
            reasoning_effort=req.reasoning_effort,
            provider=req.provider,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/sessions")
async def list_sessions_endpoint() -> Dict[str, Any]:
    return list_sessions()


@app.get("/api/sessions/{session_uid}")
async def get_session_endpoint(session_uid: str) -> Dict[str, Any]:
    detail = get_session_detail(session_uid)
    if not detail:
        raise HTTPException(status_code=404, detail=f"未找到历史分析记录: {session_uid}")
    return detail


@app.delete("/api/sessions/{session_uid}")
async def delete_session_endpoint(session_uid: str) -> Dict[str, Any]:
    deleted = delete_session(session_uid)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"未找到要删除的记录: {session_uid}")
    return {"deleted": True, "session_uid": session_uid}


@app.get("/api/samples/{kind}")
async def get_sample(kind: str) -> Dict[str, Any]:
    if kind == "scouting":
        dataset = get_sample_scouting_mirage()
        analysis = await run_ai_analysis(
            dataset, mode="scouting", target_team_id="TEAM_A", use_llm=False
        )
        return {"dataset": dataset, "analysis": analysis, "recommended_mode": "scouting"}
    if kind == "diagnosis":
        dataset = get_sample_diagnosis_inferno()
        first_sid = dataset["players"][0]["steamid"]
        analysis = await run_ai_analysis(
            dataset, mode="diagnosis", focus_steamid=first_sid, use_llm=False
        )
        return {"dataset": dataset, "analysis": analysis, "recommended_mode": "diagnosis"}
    raise HTTPException(status_code=404, detail=f"未知示例类型: {kind}")


@app.post("/api/parse-demos")
async def parse_uploaded_demos(
    files: List[UploadFile] = File(...),
    mode: str = Form("scouting"),
    target_team_id: Optional[str] = Form(None),
    focus_steamid: Optional[str] = Form(None),
    provider: Optional[str] = Form(None),
    api_key: Optional[str] = Form(None),
    base_url: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    reasoning_effort: Optional[str] = Form(None),
) -> Dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个 .dem 或 .zip 文件")

    parsed_list: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="cs2_upload_") as tmp_dir:
        tmp_root = Path(tmp_dir)
        for uf in files:
            safe_name = Path(uf.filename or "match.dem").name
            dst = tmp_root / safe_name
            with open(dst, "wb") as out_f:
                shutil.copyfileobj(uf.file, out_f)
            try:
                parsed_list.append(parse_single_demo(dst))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"解析 {safe_name} 失败: {exc}") from exc

    merged = merge_demo_analyses(parsed_list)
    effective_mode = mode if mode in ("scouting", "diagnosis") else "scouting"
    teams_dict = merged.get("teams") or {}
    effective_team = (
        target_team_id
        if (target_team_id and target_team_id in teams_dict)
        else next(iter(teams_dict.keys()), "TEAM_A")
    )
    players_list = merged.get("players") or []
    effective_sid = (
        focus_steamid
        if (focus_steamid and any(p.get("steamid") == focus_steamid for p in players_list))
        else (players_list[0]["steamid"] if players_list else None)
    )

    # 直接带着前端/环境配置的模型参数发起真实大模型推理
    analysis = await run_ai_analysis(
        merged,
        mode=effective_mode,
        target_team_id=effective_team,
        focus_steamid=effective_sid,
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
        reasoning_effort=reasoning_effort,
    )

    # 将解析出的完整遥测数据集 + 10名选手画像 + AI 报告一并持久化至 MySQL
    saved_meta = save_session_with_initial_report(
        dataset=merged,
        analysis=analysis,
        mode=effective_mode,
        target_team_id=effective_team,
        focus_steamid=effective_sid,
    )

    return {
        "dataset": merged,
        "analysis": analysis,
        "recommended_mode": effective_mode,
        "session_uid": saved_meta["session_uid"],
        "mysql_session_id": saved_meta["mysql_session_id"],
        "report_uid": saved_meta["report_uid"],
        "storage_backend": saved_meta["storage_backend"],
        "db_warning": saved_meta["db_warning"],
    }


@app.post("/api/parse-local")
async def parse_local_demos(req: LocalPathsRequest) -> Dict[str, Any]:
    clean_paths = [Path(p.strip()).expanduser() for p in req.paths if p.strip()]
    if not clean_paths:
        raise HTTPException(status_code=400, detail="请输入至少一个本地 .dem 或 .zip 文件路径")

    parsed_list: List[Dict[str, Any]] = []
    for p in clean_paths:
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"找不到本地文件: {p}")
        if p.is_dir():
            dem_files = sorted(list(p.glob("*.dem")) + list(p.glob("*.zip")))
            if not dem_files:
                raise HTTPException(status_code=400, detail=f"文件夹 {p} 中没有找到 .dem 或 .zip 文件")
            for df in dem_files[:8]:
                parsed_list.append(parse_single_demo(df))
        else:
            try:
                parsed_list.append(parse_single_demo(p))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"解析 {p.name} 失败: {exc}") from exc

    merged = merge_demo_analyses(parsed_list)
    effective_mode = req.mode if req.mode in ("scouting", "diagnosis") else "scouting"
    effective_team = next(iter((merged.get("teams") or {}).keys()), "TEAM_A")
    effective_sid = merged["players"][0]["steamid"] if merged.get("players") else None

    analysis = await run_ai_analysis(
        merged,
        mode=effective_mode,
        target_team_id=effective_team,
        focus_steamid=effective_sid,
        provider=req.provider,
        api_key=req.api_key,
        base_url=req.base_url,
        model=req.model,
        reasoning_effort=req.reasoning_effort,
    )

    saved_meta = save_session_with_initial_report(
        dataset=merged,
        analysis=analysis,
        mode=effective_mode,
        target_team_id=effective_team,
        focus_steamid=effective_sid,
    )

    return {
        "dataset": merged,
        "analysis": analysis,
        "recommended_mode": effective_mode,
        "session_uid": saved_meta["session_uid"],
        "mysql_session_id": saved_meta["mysql_session_id"],
        "report_uid": saved_meta["report_uid"],
        "storage_backend": saved_meta["storage_backend"],
        "db_warning": saved_meta["db_warning"],
    }


@app.post("/api/analyze")
async def analyze_endpoint(req: AnalyzeRequest) -> Dict[str, Any]:
    if req.mode not in ("scouting", "diagnosis"):
        raise HTTPException(status_code=400, detail="mode 必须为 scouting 或 diagnosis")

    # 已存报告复用：同一场 Demo 同一分析维度已分析过则直接返回，不再重复调用模型服务
    if req.session_uid and req.use_llm and not req.force:
        cached = find_existing_report(
            session_uid=req.session_uid,
            mode=req.mode,
            target_team_id=req.target_team_id,
            focus_steamid=req.focus_steamid,
        )
        if cached:
            cached["from_cache"] = True
            return cached

    analysis = await run_ai_analysis(
        data=req.data,
        mode=req.mode,
        target_team_id=req.target_team_id,
        focus_steamid=req.focus_steamid,
        use_llm=req.use_llm,
        provider=req.provider,
        api_key=req.api_key,
        base_url=req.base_url,
        model=req.model,
        reasoning_effort=req.reasoning_effort,
    )
    if req.session_uid and req.use_llm:
        saved_rep = save_report_to_existing_session(
            session_uid=req.session_uid,
            dataset=req.data,
            analysis=analysis,
            mode=req.mode,
            target_team_id=req.target_team_id,
            focus_steamid=req.focus_steamid,
        )
        if saved_rep:
            analysis["report_uid"] = saved_rep["report_uid"]
            analysis["storage_backend"] = saved_rep["storage_backend"]
    return analysis
