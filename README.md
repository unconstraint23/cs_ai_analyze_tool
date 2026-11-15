# CS2 完美平台战术习惯 & Anti-Strat AI 分析原型

> 架构设计文档见 [ARCHITECTURE.md](./ARCHITECTURE.md)，UI 视觉规范见 [DESIGN.md](./DESIGN.md)。

针对 **完美世界竞技平台（PWA）** 玩家与车队打造的 **双场景 `.dem` 录像空间遥测 + AI 打法习惯分析系统**（前端基于 **React 18 + TypeScript + Tailwind CSS + shadcn/ui** 构建）：

1. **方案一：赛前对手球探报告 (`scouting` / Anti-Strat)**
   - 适用场景：完美周末联赛、全国高校赛、企业赛、约战训练赛。
   - 输入对手近期 **1～N 场同地图 `.dem`（或 `.zip`）录像**，自动按 `SteamID` 聚合对手 5 人的 **CT 默认阵型、常驻报点、前压偷人率、主狙架点位、薄弱防守点、低经济强起习惯**，生成可直接照着指挥的针对性破局简报。
2. **方案二：个人与固定车队打法习惯诊断 (`diagnosis` / Self & Team Coach)**
   - 适用场景：天梯单排 / 五黑赛后复盘。
   - 对局结算后下载本场 `.dem`，一键定位你和队友在当前地图的**开局高频送首死点位、脱节白给率（5秒内无队友补枪）、道具浪费率、被对手针对的战术漏洞**，并给出下一场可执行改进清单。

---

## 快速启动

### 方式 A：一键启动完整版（FastAPI + 已构建 React 产物）

```bash
./start.sh
```

浏览器打开 `http://127.0.0.1:8765`。

### 方式 B：前后端分离热更新开发模式（Vite HMR + FastAPI）

```bash
# 终端 1：启动 FastAPI 后端 (端口 8765)
./.venv/bin/uvicorn backend.app:app --reload --host 127.0.0.1 --port 8765

# 终端 2：启动 React + TS + shadcn/ui 前端开发服 (端口 5173，已代理 /api -> 8765)
cd frontend
pnpm dev
```

浏览器打开 `http://127.0.0.1:5173`。

---

## 命令行 CLI 运行

```bash
./.venv/bin/python cli.py --sample scouting
./.venv/bin/python cli.py --sample diagnosis
./.venv/bin/python cli.py --demo ~/Downloads/pw_mirage_1.dem ~/Downloads/pw_mirage_2.dem --mode scouting
```

---

## 技术栈与目录结构

- **前端 (`frontend/`)**：Vite + React 18 + TypeScript + Tailwind CSS + **shadcn/ui**（Radix UI Primitives + CVA + Lucide Icons + `components.json`）+ `react-markdown`
  - `frontend/src/components/ui/` — 标准 shadcn/ui 基础组件 (`button`, `card`, `badge`, `tabs`, `dialog`, `select`, `input`, `textarea`, `label`, `scroll-area`, `progress`, `separator`, `tooltip`)
  - `frontend/src/components/` — 业务面板组件（顶部导航、模式控制栏、2D 交互式 SVG 战术雷达、选手画像列表、量化习惯卡片、AI 报告与导入配置弹窗）
- **后端 (`backend/`)**：FastAPI + `demoparser2` (Rust 底层 CS2 录像解析) + `pymysql` (MySQL 持久化) + `httpx`
  - `backend/map_knowledge.py` — CS2 官方地图 3D 世界坐标转 2D 雷达坐标投影 + 中文报点消歧库
  - `backend/demo_extractor.py` — 毫秒级关键 Tick 采样与多场 `.dem` 聚合引擎
  - `backend/ai_analyzer.py` — 双模式 LLM 提示词工程（原生适配 `deepseek-flash` / DeepSeek-V4.1-Flash 思考链）+ 零依赖动态战术规则引擎
  - `backend/db.py` — MySQL 自动建库建表与持久化存储层（`cs2_tactical` 库下包含 `demo_sessions`、`demo_session_players`、`analysis_reports` 三张表）

---

## MySQL 与模型配置 (`.env`)

可在项目根目录 `.env` 中配置（或直接在网页顶部点击 **「MySQL 配置」** / **「AI 引擎配置」** 在线保存，无需重启后端）：

```env
MYSQL_ENABLED=true
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=你的本机MySQL密码
MYSQL_DATABASE=cs2_tactical

LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_API_KEY=sk-...
LLM_REASONING_EFFORT=low
```
