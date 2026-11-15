"""
MySQL 数据库持久化层 (基于 PyMySQL)：
用于存储玩家上传的真实 CS2 `.dem` 解析遥测数据集、10 名选手地图打法习惯明细以及 AI 生成的战术分析报告。

核心表结构 (默认库名 `cs2_tactical`, 自动建库建表):
1. `demo_sessions`        — 上传的 Demo 场次/同地图多场聚合批次主表
2. `demo_session_players` — 每场 10 名选手的地图习惯核心遥测指标明细表 (支持直接 SQL 检索)
3. `analysis_reports`     — 关联该场次的所有 AI 战术报告 (支持切换对手球探 / 不同选手诊断多份报告共存)

容错机制：
当本机 MySQL 尚未填入密码导致鉴权未通过时，自动暂存至本地待同步缓存队列 (`data/mysql_pending_cache.json`)，
确保前端切换示例后上传记录不丢失；一旦在 `.env` 或前端配置弹窗填入正确 MySQL 密码，立即自动建库并将待同步记录刷入 MySQL。
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymysql
from dotenv import dotenv_values, load_dotenv, set_key
from pymysql.cursors import DictCursor

logger = logging.getLogger("cs2_tactical.db")

ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT_DIR / ".env"
DATA_DIR = ROOT_DIR / "data"
FALLBACK_CACHE_FILE = DATA_DIR / "mysql_pending_cache.json"

load_dotenv(ENV_FILE, override=False)

_VALID_DB_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")

DDL_DEMO_SESSIONS = """
CREATE TABLE IF NOT EXISTS `demo_sessions` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `session_uid` VARCHAR(64) NOT NULL,
    `title` VARCHAR(255) NOT NULL,
    `map_name` VARCHAR(64) NOT NULL,
    `map_cn_name` VARCHAR(128) NOT NULL,
    `matches_count` INT NOT NULL DEFAULT 1,
    `total_rounds` INT NOT NULL DEFAULT 0,
    `score_text` VARCHAR(255) NOT NULL DEFAULT '',
    `demo_files_json` JSON NOT NULL,
    `dataset_json` LONGTEXT NOT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_session_uid` (`session_uid`),
    KEY `idx_map_created` (`map_name`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

DDL_DEMO_SESSION_PLAYERS = """
CREATE TABLE IF NOT EXISTS `demo_session_players` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `session_id` BIGINT UNSIGNED NOT NULL,
    `steamid` VARCHAR(32) NOT NULL,
    `player_name` VARCHAR(128) NOT NULL,
    `team_id` VARCHAR(32) NOT NULL,
    `ct_role` VARCHAR(64) NOT NULL DEFAULT '',
    `t_role` VARCHAR(64) NOT NULL DEFAULT '',
    `rating` DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    `adr` DECIMAL(6,1) NOT NULL DEFAULT 0.0,
    `kd` DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    `hs_pct` DECIMAL(5,1) NOT NULL DEFAULT 0.0,
    `kast_pct` DECIMAL(5,1) NOT NULL DEFAULT 0.0,
    `opening_attempt_rate` DECIMAL(5,1) NOT NULL DEFAULT 0.0,
    `opening_win_rate` DECIMAL(5,1) NOT NULL DEFAULT 0.0,
    `ct_aggression_rate` DECIMAL(5,1) NOT NULL DEFAULT 0.0,
    `untraded_death_rate` DECIMAL(5,1) NOT NULL DEFAULT 0.0,
    `awp_kill_share` DECIMAL(5,1) NOT NULL DEFAULT 0.0,
    `utility_per_round` DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    `style_tags_json` JSON NULL,
    `ct_top_callouts_json` JSON NULL,
    `t_top_callouts_json` JSON NULL,
    PRIMARY KEY (`id`),
    KEY `idx_session_id` (`session_id`),
    KEY `idx_steamid` (`steamid`),
    CONSTRAINT `fk_dsp_session` FOREIGN KEY (`session_id`)
        REFERENCES `demo_sessions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

DDL_ANALYSIS_REPORTS = """
CREATE TABLE IF NOT EXISTS `analysis_reports` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `report_uid` VARCHAR(64) NOT NULL,
    `session_id` BIGINT UNSIGNED NOT NULL,
    `mode` VARCHAR(32) NOT NULL,
    `target_team_id` VARCHAR(32) NOT NULL DEFAULT 'TEAM_A',
    `focus_steamid` VARCHAR(32) NULL,
    `focus_player_name` VARCHAR(128) NULL,
    `engine` VARCHAR(128) NOT NULL,
    `report_markdown` LONGTEXT NOT NULL,
    `reasoning_markdown` LONGTEXT NULL,
    `prompt_text` LONGTEXT NOT NULL,
    `warning_text` TEXT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_report_uid` (`report_uid`),
    KEY `idx_session_created` (`session_id`, `created_at`),
    CONSTRAINT `fk_ar_session` FOREIGN KEY (`session_id`)
        REFERENCES `demo_sessions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


def get_mysql_config() -> Dict[str, Any]:
    """实时合并 .env 与环境变量中的 MySQL 连接参数（修改 .env 无需重启即可生效）。"""
    file_vals = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}

    def _pick(key: str, default: str) -> str:
        val = file_vals.get(key)
        if val is None:
            val = os.getenv(key, default)
        return str(val).strip()

    enabled_str = _pick("MYSQL_ENABLED", "true").lower()
    db_name = _pick("MYSQL_DATABASE", "cs2_tactical") or "cs2_tactical"
    if not _VALID_DB_NAME_RE.match(db_name):
        db_name = "cs2_tactical"

    try:
        port = int(_pick("MYSQL_PORT", "3306") or "3306")
    except ValueError:
        port = 3306

    return {
        "enabled": enabled_str not in ("0", "false", "no", "off"),
        "host": _pick("MYSQL_HOST", "127.0.0.1") or "127.0.0.1",
        "port": port,
        "user": _pick("MYSQL_USER", "root") or "root",
        "password": file_vals.get("MYSQL_PASSWORD")
        if file_vals.get("MYSQL_PASSWORD") is not None
        else os.getenv("MYSQL_PASSWORD", ""),
        "database": db_name,
    }


def _fmt_dt(val: Any) -> str:
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return str(val or "")


def _connect_server(cfg: Optional[Dict[str, Any]] = None, with_db: bool = True) -> pymysql.Connection:
    c = cfg or get_mysql_config()
    if not c["enabled"]:
        raise RuntimeError("MySQL 存储已在配置中关闭 (MYSQL_ENABLED=false)")
    kwargs: Dict[str, Any] = {
        "host": c["host"],
        "port": c["port"],
        "user": c["user"],
        "password": c["password"],
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": True,
        "connect_timeout": 4,
        "read_timeout": 30,
        "write_timeout": 30,
    }
    if with_db:
        kwargs["database"] = c["database"]
    return pymysql.connect(**kwargs)


# ==================== 本地待同步缓存兜底 (未填 MySQL 密码前防丢数据) ====================


def _load_fallback_store() -> Dict[str, Any]:
    if not FALLBACK_CACHE_FILE.exists():
        return {"sessions": []}
    try:
        return json.loads(FALLBACK_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"sessions": []}


def _save_fallback_store(store: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FALLBACK_CACHE_FILE.write_text(
        json.dumps(store, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _insert_session_into_conn(
    conn: pymysql.Connection,
    session_uid: str,
    title: str,
    dataset: Dict[str, Any],
    created_at_str: Optional[str] = None,
) -> int:
    demo_files = dataset.get("demo_files") or []
    players = dataset.get("players") or []

    with conn.cursor() as cur:
        cur.execute(
            "SELECT `id` FROM `demo_sessions` WHERE `session_uid` = %s LIMIT 1",
            (session_uid,),
        )
        existing = cur.fetchone()
        if existing:
            return int(existing["id"])

        if created_at_str:
            cur.execute(
                """
                INSERT INTO `demo_sessions`
                (`session_uid`, `title`, `map_name`, `map_cn_name`, `matches_count`,
                 `total_rounds`, `score_text`, `demo_files_json`, `dataset_json`, `created_at`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session_uid,
                    title,
                    dataset.get("map_name", "unknown"),
                    dataset.get("map_cn_name", "未知地图"),
                    int(dataset.get("matches_count", 1)),
                    int(dataset.get("total_rounds", 0)),
                    str(dataset.get("score_text", ""))[:250],
                    json.dumps(demo_files, ensure_ascii=False),
                    json.dumps(dataset, ensure_ascii=False),
                    created_at_str,
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO `demo_sessions`
                (`session_uid`, `title`, `map_name`, `map_cn_name`, `matches_count`,
                 `total_rounds`, `score_text`, `demo_files_json`, `dataset_json`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session_uid,
                    title,
                    dataset.get("map_name", "unknown"),
                    dataset.get("map_cn_name", "未知地图"),
                    int(dataset.get("matches_count", 1)),
                    int(dataset.get("total_rounds", 0)),
                    str(dataset.get("score_text", ""))[:250],
                    json.dumps(demo_files, ensure_ascii=False),
                    json.dumps(dataset, ensure_ascii=False),
                ),
            )
        session_db_id = int(cur.lastrowid)

        for p in players:
            st = p.get("stats") or {}
            cur.execute(
                """
                INSERT INTO `demo_session_players`
                (`session_id`, `steamid`, `player_name`, `team_id`, `ct_role`, `t_role`,
                 `rating`, `adr`, `kd`, `hs_pct`, `kast_pct`,
                 `opening_attempt_rate`, `opening_win_rate`, `ct_aggression_rate`,
                 `untraded_death_rate`, `awp_kill_share`, `utility_per_round`,
                 `style_tags_json`, `ct_top_callouts_json`, `t_top_callouts_json`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session_db_id,
                    str(p.get("steamid", ""))[:32],
                    str(p.get("name", "Player"))[:128],
                    str(p.get("team_id", "TEAM_A"))[:32],
                    str(p.get("ct_role", ""))[:64],
                    str(p.get("t_role", ""))[:64],
                    float(st.get("rating", 0.0)),
                    float(st.get("adr", 0.0)),
                    float(st.get("kd", 0.0)),
                    float(st.get("hs_pct", 0.0)),
                    float(st.get("kast_pct", 0.0)),
                    float(st.get("opening_attempt_rate", 0.0)),
                    float(st.get("opening_win_rate", 0.0)),
                    float(st.get("ct_aggression_rate", 0.0)),
                    float(st.get("untraded_death_rate", 0.0)),
                    float(st.get("awp_kill_share", 0.0)),
                    float(st.get("utility_per_round", 0.0)),
                    json.dumps(p.get("style_tags") or [], ensure_ascii=False),
                    json.dumps(p.get("ct_top_callouts") or [], ensure_ascii=False),
                    json.dumps(p.get("t_top_callouts") or [], ensure_ascii=False),
                ),
            )

    return session_db_id


def _insert_report_into_conn(
    conn: pymysql.Connection,
    session_db_id: int,
    report_uid: str,
    mode: str,
    target_team_id: str,
    focus_steamid: Optional[str],
    focus_player_name: Optional[str],
    analysis: Dict[str, Any],
    created_at_str: Optional[str] = None,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT `id` FROM `analysis_reports` WHERE `report_uid` = %s LIMIT 1",
            (report_uid,),
        )
        existing = cur.fetchone()
        if existing:
            return int(existing["id"])

        if created_at_str:
            cur.execute(
                """
                INSERT INTO `analysis_reports`
                (`report_uid`, `session_id`, `mode`, `target_team_id`, `focus_steamid`,
                 `focus_player_name`, `engine`, `report_markdown`, `reasoning_markdown`,
                 `prompt_text`, `warning_text`, `created_at`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    report_uid,
                    session_db_id,
                    mode[:32],
                    (target_team_id or "TEAM_A")[:32],
                    (focus_steamid or None),
                    (focus_player_name or None),
                    str(analysis.get("engine", "rule_engine"))[:128],
                    str(analysis.get("report_markdown", "")),
                    analysis.get("reasoning_markdown"),
                    str(analysis.get("prompt", "")),
                    analysis.get("warning"),
                    created_at_str,
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO `analysis_reports`
                (`report_uid`, `session_id`, `mode`, `target_team_id`, `focus_steamid`,
                 `focus_player_name`, `engine`, `report_markdown`, `reasoning_markdown`,
                 `prompt_text`, `warning_text`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    report_uid,
                    session_db_id,
                    mode[:32],
                    (target_team_id or "TEAM_A")[:32],
                    (focus_steamid or None),
                    (focus_player_name or None),
                    str(analysis.get("engine", "rule_engine"))[:128],
                    str(analysis.get("report_markdown", "")),
                    analysis.get("reasoning_markdown"),
                    str(analysis.get("prompt", "")),
                    analysis.get("warning"),
                ),
            )
        return int(cur.lastrowid)


def _sync_fallback_to_mysql(conn: pymysql.Connection) -> int:
    """当 MySQL 连通后，将之前暂存在本地缓存队列中的会话与报告全部同步写入 MySQL。"""
    store = _load_fallback_store()
    pending_sessions = store.get("sessions") or []
    if not pending_sessions:
        return 0

    synced_count = 0
    for item in pending_sessions:
        s_uid = item["session_uid"]
        s_id = _insert_session_into_conn(
            conn=conn,
            session_uid=s_uid,
            title=item["title"],
            dataset=item["dataset"],
            created_at_str=item.get("created_at"),
        )
        for rep in item.get("reports") or []:
            _insert_report_into_conn(
                conn=conn,
                session_db_id=s_id,
                report_uid=rep["report_uid"],
                mode=rep["mode"],
                target_team_id=rep.get("target_team_id", "TEAM_A"),
                focus_steamid=rep.get("focus_steamid"),
                focus_player_name=rep.get("focus_player_name"),
                analysis=rep["analysis"],
                created_at_str=rep.get("created_at"),
            )
        synced_count += 1

    _save_fallback_store({"sessions": []})
    logger.info("[MySQL] 已自动将 %d 条待同步 Demo 记录刷入 MySQL", synced_count)
    return synced_count


def init_db(cfg_override: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str], int]:
    """
    初始化 MySQL 数据库 (`cs2_tactical`) 与三张核心业务表，并同步待入库队列。
    返回: (connected, error_message, synced_pending_count)
    """
    cfg = cfg_override or get_mysql_config()
    if not cfg["enabled"]:
        return False, "MySQL 已禁用 (MYSQL_ENABLED=false)", 0

    try:
        conn = _connect_server(cfg, with_db=False)
        try:
            db_name = cfg["database"]
            with conn.cursor() as cur:
                cur.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                    "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                )
                cur.execute(f"USE `{db_name}`;")
                cur.execute(DDL_DEMO_SESSIONS)
                cur.execute(DDL_DEMO_SESSION_PLAYERS)
                cur.execute(DDL_ANALYSIS_REPORTS)
            synced = _sync_fallback_to_mysql(conn)
            return True, None, synced
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("[MySQL] 连接或初始化失败: %s", exc)
        return False, str(exc), 0


def get_db_status() -> Dict[str, Any]:
    """检查当前 MySQL 连接健康度、表记录数以及本地待同步数。"""
    cfg = get_mysql_config()
    pending_cnt = len(_load_fallback_store().get("sessions") or [])

    connected, err, synced = init_db(cfg)
    if connected:
        try:
            conn = _connect_server(cfg, with_db=True)
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) AS cnt FROM `demo_sessions`")
                    sessions_cnt = int((cur.fetchone() or {}).get("cnt", 0))
                    cur.execute("SELECT COUNT(*) AS cnt FROM `analysis_reports`")
                    reports_cnt = int((cur.fetchone() or {}).get("cnt", 0))
                return {
                    "connected": True,
                    "storage_backend": "mysql",
                    "host": cfg["host"],
                    "port": cfg["port"],
                    "user": cfg["user"],
                    "database": cfg["database"],
                    "has_password": bool(cfg["password"]),
                    "sessions_count": sessions_cnt,
                    "reports_count": reports_cnt,
                    "pending_sync_count": 0,
                    "synced_just_now": synced,
                    "error": None,
                }
            finally:
                conn.close()
        except Exception as exc:
            err = str(exc)

    return {
        "connected": False,
        "storage_backend": "local_pending_cache",
        "host": cfg["host"],
        "port": cfg["port"],
        "user": cfg["user"],
        "database": cfg["database"],
        "has_password": bool(cfg["password"]),
        "sessions_count": pending_cnt,
        "reports_count": sum(
            len(s.get("reports") or []) for s in (_load_fallback_store().get("sessions") or [])
        ),
        "pending_sync_count": pending_cnt,
        "synced_just_now": 0,
        "error": err,
    }


def update_mysql_config(
    host: str,
    port: int,
    user: str,
    password: Optional[str],
    database: str,
) -> Dict[str, Any]:
    """验证并保存 MySQL 连接配置到项目根目录 `.env`，同时自动建库建表并同步历史队列。"""
    clean_db = database.strip() or "cs2_tactical"
    if not _VALID_DB_NAME_RE.match(clean_db):
        raise ValueError("数据库名称仅允许字母、数字与下划线")

    current = get_mysql_config()
    resolved_pwd = current["password"] if password is None else password

    candidate = {
        "enabled": True,
        "host": host.strip() or "127.0.0.1",
        "port": int(port or 3306),
        "user": user.strip() or "root",
        "password": resolved_pwd,
        "database": clean_db,
    }

    # 先实测连接并建库建表，验证通过后再落盘 .env
    ok, err, synced = init_db(candidate)
    if not ok:
        raise RuntimeError(f"MySQL 连接验证失败：{err}")

    if not ENV_FILE.exists():
        ENV_FILE.write_text("", encoding="utf-8")

    set_key(str(ENV_FILE), "MYSQL_ENABLED", "true")
    set_key(str(ENV_FILE), "MYSQL_HOST", candidate["host"])
    set_key(str(ENV_FILE), "MYSQL_PORT", str(candidate["port"]))
    set_key(str(ENV_FILE), "MYSQL_USER", candidate["user"])
    set_key(str(ENV_FILE), "MYSQL_PASSWORD", candidate["password"])
    set_key(str(ENV_FILE), "MYSQL_DATABASE", candidate["database"])

    status = get_db_status()
    status["synced_just_now"] = synced
    return status


def _build_session_title(dataset: Dict[str, Any]) -> str:
    map_cn = dataset.get("map_cn_name") or dataset.get("map_name") or "CS2 对局"
    files = dataset.get("demo_files") or []
    matches_cnt = int(dataset.get("matches_count", 1))
    if matches_cnt > 1:
        return f"{map_cn} · {matches_cnt}场聚合 ({files[0] if files else 'demos'})"
    if files:
        return f"{map_cn} · {files[0]}"
    return f"{map_cn} · {dataset.get('total_rounds', 0)}回合"


def _resolve_focus_player_name(dataset: Dict[str, Any], focus_steamid: Optional[str]) -> Optional[str]:
    if not focus_steamid:
        return None
    for p in dataset.get("players") or []:
        if p.get("steamid") == focus_steamid:
            return str(p.get("name") or "")
    return None


def save_session_with_initial_report(
    dataset: Dict[str, Any],
    analysis: Dict[str, Any],
    mode: str,
    target_team_id: str,
    focus_steamid: Optional[str],
) -> Dict[str, Any]:
    """
    上传解析新 Demo 后，将完整遥测数据集 + 首份 AI 分析报告持久化写入 MySQL。
    若 MySQL 当前未鉴权，自动写入本地待同步缓存并在返回状态中提示用户。
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session_uid = f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    report_uid = f"rep_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    title = _build_session_title(dataset)
    focus_name = _resolve_focus_player_name(dataset, focus_steamid)

    ok, err, _ = init_db()
    if ok:
        conn = _connect_server(with_db=True)
        try:
            s_id = _insert_session_into_conn(conn, session_uid, title, dataset)
            r_id = _insert_report_into_conn(
                conn=conn,
                session_db_id=s_id,
                report_uid=report_uid,
                mode=mode,
                target_team_id=target_team_id,
                focus_steamid=focus_steamid,
                focus_player_name=focus_name,
                analysis=analysis,
            )
            logger.info(
                "[MySQL] 已保存 Demo 会话 id=%d (%s) 与 AI 报告 id=%d (%s)",
                s_id,
                session_uid,
                r_id,
                analysis.get("engine"),
            )
            return {
                "session_uid": session_uid,
                "mysql_session_id": s_id,
                "report_uid": report_uid,
                "mysql_report_id": r_id,
                "storage_backend": "mysql",
                "db_warning": None,
            }
        finally:
            conn.close()

    # MySQL 暂未连通时写入本地待同步缓存，保证前端历史记录立即可切回查看
    store = _load_fallback_store()
    sessions = store.get("sessions") or []
    sessions.insert(
        0,
        {
            "session_uid": session_uid,
            "title": title,
            "map_name": dataset.get("map_name", "unknown"),
            "map_cn_name": dataset.get("map_cn_name", "未知地图"),
            "matches_count": int(dataset.get("matches_count", 1)),
            "total_rounds": int(dataset.get("total_rounds", 0)),
            "score_text": str(dataset.get("score_text", "")),
            "demo_files": dataset.get("demo_files") or [],
            "dataset": dataset,
            "created_at": now_str,
            "reports": [
                {
                    "report_uid": report_uid,
                    "mode": mode,
                    "target_team_id": target_team_id,
                    "focus_steamid": focus_steamid,
                    "focus_player_name": focus_name,
                    "engine": str(analysis.get("engine", "rule_engine")),
                    "analysis": analysis,
                    "created_at": now_str,
                }
            ],
        },
    )
    store["sessions"] = sessions
    _save_fallback_store(store)
    return {
        "session_uid": session_uid,
        "mysql_session_id": None,
        "report_uid": report_uid,
        "mysql_report_id": None,
        "storage_backend": "local_pending_cache",
        "db_warning": f"MySQL 尚未连通 ({err})，已暂存至本地历史记录；配置 MySQL 密码后将自动同步入库。",
    }


def save_report_to_existing_session(
    session_uid: str,
    dataset: Dict[str, Any],
    analysis: Dict[str, Any],
    mode: str,
    target_team_id: str,
    focus_steamid: Optional[str],
) -> Optional[Dict[str, Any]]:
    """当用户在已上传的真实 Demo 上切换模式/切换选手重新触发 AI 分析时，将新生成的报告追加持久化至 MySQL。"""
    if not session_uid:
        return None

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_uid = f"rep_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    focus_name = _resolve_focus_player_name(dataset, focus_steamid)

    ok, _, _ = init_db()
    if ok:
        conn = _connect_server(with_db=True)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT `id` FROM `demo_sessions` WHERE `session_uid` = %s LIMIT 1",
                    (session_uid,),
                )
                row = cur.fetchone()
            if row:
                s_id = int(row["id"])
                r_id = _insert_report_into_conn(
                    conn=conn,
                    session_db_id=s_id,
                    report_uid=report_uid,
                    mode=mode,
                    target_team_id=target_team_id,
                    focus_steamid=focus_steamid,
                    focus_player_name=focus_name,
                    analysis=analysis,
                )
                return {
                    "report_uid": report_uid,
                    "mysql_report_id": r_id,
                    "storage_backend": "mysql",
                }
        finally:
            conn.close()

    # 若位于本地待同步队列中则追加进去
    store = _load_fallback_store()
    for item in store.get("sessions") or []:
        if item.get("session_uid") == session_uid:
            reps = item.setdefault("reports", [])
            reps.insert(
                0,
                {
                    "report_uid": report_uid,
                    "mode": mode,
                    "target_team_id": target_team_id,
                    "focus_steamid": focus_steamid,
                    "focus_player_name": focus_name,
                    "engine": str(analysis.get("engine", "rule_engine")),
                    "analysis": analysis,
                    "created_at": now_str,
                },
            )
            _save_fallback_store(store)
            return {
                "report_uid": report_uid,
                "mysql_report_id": None,
                "storage_backend": "local_pending_cache",
            }
    return None


def find_existing_report(
    session_uid: str,
    mode: str,
    target_team_id: str,
    focus_steamid: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    查找该 Demo 会话下是否已经存在相同分析维度的报告：
    - scouting：同 mode + 同 target_team_id
    - diagnosis：同 mode + 同 focus_steamid
    命中时直接复用，避免重复调用大模型服务。
    """
    if not session_uid:
        return None

    def _matches(r_mode: str, r_team: Optional[str], r_sid: Optional[str]) -> bool:
        if r_mode != mode:
            return False
        if mode == "scouting":
            return (r_team or "TEAM_A") == (target_team_id or "TEAM_A")
        return (r_sid or None) == (focus_steamid or None)

    ok, _, _ = init_db()
    if ok:
        conn = _connect_server(with_db=True)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT r.* FROM `analysis_reports` r
                    JOIN `demo_sessions` s ON s.`id` = r.`session_id`
                    WHERE s.`session_uid` = %s AND r.`mode` = %s
                    ORDER BY r.`id` DESC
                    """,
                    (session_uid, mode),
                )
                rows = cur.fetchall() or []
            for r in rows:
                if _matches(r["mode"], r.get("target_team_id"), r.get("focus_steamid")):
                    rep: Dict[str, Any] = {
                        "engine": r["engine"],
                        "report_markdown": r["report_markdown"],
                        "reasoning_markdown": r.get("reasoning_markdown"),
                        "prompt": r["prompt_text"],
                        "report_uid": r["report_uid"],
                        "storage_backend": "mysql",
                    }
                    if r.get("warning_text"):
                        rep["warning"] = r["warning_text"]
                    return rep
        finally:
            conn.close()

    for s in _load_fallback_store().get("sessions") or []:
        if s.get("session_uid") != session_uid:
            continue
        for r in s.get("reports") or []:
            if _matches(r.get("mode", ""), r.get("target_team_id"), r.get("focus_steamid")):
                rep = dict(r["analysis"])
                rep["report_uid"] = r["report_uid"]
                rep["storage_backend"] = "local_pending_cache"
                return rep
    return None


def list_sessions(limit: int = 50) -> Dict[str, Any]:
    """查询历史上传的真实 Demo 列表（按时间倒序）。"""
    ok, err, _ = init_db()
    if ok:
        conn = _connect_server(with_db=True)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        s.`id` AS `mysql_id`,
                        s.`session_uid`,
                        s.`title`,
                        s.`map_name`,
                        s.`map_cn_name`,
                        s.`matches_count`,
                        s.`total_rounds`,
                        s.`score_text`,
                        s.`demo_files_json`,
                        s.`created_at`,
                        COUNT(r.`id`) AS `reports_count`,
                        (
                            SELECT r2.`engine`
                            FROM `analysis_reports` r2
                            WHERE r2.`session_id` = s.`id`
                            ORDER BY r2.`id` DESC
                            LIMIT 1
                        ) AS `latest_engine`
                    FROM `demo_sessions` s
                    LEFT JOIN `analysis_reports` r ON r.`session_id` = s.`id`
                    GROUP BY s.`id`
                    ORDER BY s.`id` DESC
                    LIMIT %s
                    """,
                    (int(limit),),
                )
                rows = cur.fetchall() or []

            items = []
            for r in rows:
                raw_files = r.get("demo_files_json")
                if isinstance(raw_files, str):
                    try:
                        files = json.loads(raw_files)
                    except Exception:
                        files = []
                else:
                    files = raw_files or []
                items.append(
                    {
                        "mysql_id": int(r["mysql_id"]),
                        "session_uid": r["session_uid"],
                        "title": r["title"],
                        "map_name": r["map_name"],
                        "map_cn_name": r["map_cn_name"],
                        "matches_count": int(r["matches_count"]),
                        "total_rounds": int(r["total_rounds"]),
                        "score_text": r["score_text"],
                        "demo_files": files,
                        "reports_count": int(r.get("reports_count") or 0),
                        "latest_engine": r.get("latest_engine") or "rule_engine",
                        "storage_backend": "mysql",
                        "created_at": _fmt_dt(r.get("created_at")),
                    }
                )
            return {"connected": True, "storage_backend": "mysql", "error": None, "items": items}
        finally:
            conn.close()

    store = _load_fallback_store()
    items = []
    for s in (store.get("sessions") or [])[:limit]:
        reps = s.get("reports") or []
        items.append(
            {
                "mysql_id": None,
                "session_uid": s["session_uid"],
                "title": s["title"],
                "map_name": s.get("map_name", "unknown"),
                "map_cn_name": s.get("map_cn_name", "未知地图"),
                "matches_count": int(s.get("matches_count", 1)),
                "total_rounds": int(s.get("total_rounds", 0)),
                "score_text": s.get("score_text", ""),
                "demo_files": s.get("demo_files") or [],
                "reports_count": len(reps),
                "latest_engine": reps[0].get("engine", "rule_engine") if reps else "rule_engine",
                "storage_backend": "local_pending_cache",
                "created_at": s.get("created_at", ""),
            }
        )
    return {
        "connected": False,
        "storage_backend": "local_pending_cache",
        "error": err,
        "items": items,
    }


def get_session_detail(session_uid: str) -> Optional[Dict[str, Any]]:
    """按 session_uid 读取完整 Demo 遥测数据集与全部历史 AI 报告。"""
    ok, _, _ = init_db()
    if ok:
        conn = _connect_server(with_db=True)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM `demo_sessions` WHERE `session_uid` = %s LIMIT 1",
                    (session_uid,),
                )
                s_row = cur.fetchone()
                if s_row:
                    s_id = int(s_row["id"])
                    cur.execute(
                        """
                        SELECT * FROM `analysis_reports`
                        WHERE `session_id` = %s
                        ORDER BY `id` DESC
                        """,
                        (s_id,),
                    )
                    r_rows = cur.fetchall() or []

                    dataset = json.loads(s_row["dataset_json"])
                    reports = []
                    for r in r_rows:
                        rep_analysis: Dict[str, Any] = {
                            "engine": r["engine"],
                            "report_markdown": r["report_markdown"],
                            "reasoning_markdown": r.get("reasoning_markdown"),
                            "prompt": r["prompt_text"],
                        }
                        if r.get("warning_text"):
                            rep_analysis["warning"] = r["warning_text"]
                        reports.append(
                            {
                                "mysql_id": int(r["id"]),
                                "report_uid": r["report_uid"],
                                "mode": r["mode"],
                                "target_team_id": r["target_team_id"],
                                "focus_steamid": r.get("focus_steamid"),
                                "focus_player_name": r.get("focus_player_name"),
                                "engine": r["engine"],
                                "created_at": _fmt_dt(r.get("created_at")),
                                "analysis": rep_analysis,
                            }
                        )

                    latest_rep = reports[0] if reports else None
                    return {
                        "session_uid": s_row["session_uid"],
                        "mysql_id": s_id,
                        "title": s_row["title"],
                        "storage_backend": "mysql",
                        "created_at": _fmt_dt(s_row.get("created_at")),
                        "dataset": dataset,
                        "reports": reports,
                        "latest_report": latest_rep,
                    }
        finally:
            conn.close()

    store = _load_fallback_store()
    for s in store.get("sessions") or []:
        if s.get("session_uid") == session_uid:
            reports = []
            for r in s.get("reports") or []:
                reports.append(
                    {
                        "mysql_id": None,
                        "report_uid": r["report_uid"],
                        "mode": r["mode"],
                        "target_team_id": r.get("target_team_id", "TEAM_A"),
                        "focus_steamid": r.get("focus_steamid"),
                        "focus_player_name": r.get("focus_player_name"),
                        "engine": r.get("engine", "rule_engine"),
                        "created_at": r.get("created_at", ""),
                        "analysis": r["analysis"],
                    }
                )
            return {
                "session_uid": s["session_uid"],
                "mysql_id": None,
                "title": s["title"],
                "storage_backend": "local_pending_cache",
                "created_at": s.get("created_at", ""),
                "dataset": s["dataset"],
                "reports": reports,
                "latest_report": reports[0] if reports else None,
            }
    return None


def delete_session(session_uid: str) -> bool:
    """删除指定的历史 Demo 会话及其级联的选手记录与 AI 报告。"""
    deleted = False
    ok, _, _ = init_db()
    if ok:
        conn = _connect_server(with_db=True)
        try:
            with conn.cursor() as cur:
                affected = cur.execute(
                    "DELETE FROM `demo_sessions` WHERE `session_uid` = %s",
                    (session_uid,),
                )
                if affected > 0:
                    deleted = True
        finally:
            conn.close()

    store = _load_fallback_store()
    before = len(store.get("sessions") or [])
    remaining = [s for s in (store.get("sessions") or []) if s.get("session_uid") != session_uid]
    if len(remaining) != before:
        store["sessions"] = remaining
        _save_fallback_store(store)
        deleted = True

    return deleted
