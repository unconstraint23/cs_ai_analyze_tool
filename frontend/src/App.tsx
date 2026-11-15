import { RotateCcw } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"
import {
  deleteDemoSession,
  fetchDbStatus,
  fetchDemoSessionDetail,
  fetchDemoSessions,
  fetchSampleDataset,
  runTacticalAnalysis,
  saveBackendLlmConfig,
  uploadAndParseDemos,
} from "@/api/client"
import { AiReportPanel } from "@/components/AiReportPanel"
import { DemoHistoryDialog } from "@/components/DemoHistoryDialog"
import { ImportDemoDialog } from "@/components/ImportDemoDialog"
import { LlmSettingsDialog } from "@/components/LlmSettingsDialog"
import { MatchMacroBanner } from "@/components/MatchMacroBanner"
import { ModeControlBar } from "@/components/ModeControlBar"
import { MysqlSettingsDialog } from "@/components/MysqlSettingsDialog"
import { PlayerHabitDetailCard } from "@/components/PlayerHabitDetailCard"
import { PlayerRosterPanel } from "@/components/PlayerRosterPanel"
import { TacticalHeader } from "@/components/TacticalHeader"
import { TacticalRadarCard } from "@/components/TacticalRadarCard"
import { TooltipProvider } from "@/components/ui/tooltip"
import type {
  AnalysisMode,
  AnalysisResponse,
  DbStatusResponse,
  LlmSettings,
  MatchDataset,
  RadarScope,
  RadarSideFilter,
  SampleKind,
  SavedReportItem,
  SessionListItem,
} from "@/types/tactical"

const LLM_STORAGE_KEY = "cs2_pwa_ai_llm_cfg_v2"

const PUBLIC_CLOUD_HOSTS = [
  "api.deepseek.com",
  "api.openai.com",
  "api.anthropic.com",
  "dashscope.aliyuncs.com",
  "api.moonshot.cn",
  "open.bigmodel.cn",
  "ark.cn-beijing.volces.com",
]

const DEFAULT_LLM: LlmSettings = {
  provider: "deepseek",
  base_url: "https://api.deepseek.com",
  model: "deepseek-flash",
  api_key: "",
  reasoning_effort: "low",
}

function isCustomLlmConfigured(cfg: LlmSettings): boolean {
  if (cfg.api_key && cfg.api_key.trim().length > 0) return true
  const url = (cfg.base_url || "").trim().toLowerCase()
  if (!url) return false
  return !PUBLIC_CLOUD_HOSTS.some((host) => url.includes(host))
}

function loadStoredLlm(): LlmSettings {
  try {
    const raw = localStorage.getItem(LLM_STORAGE_KEY)
    if (!raw) return DEFAULT_LLM
    const parsed = { ...DEFAULT_LLM, ...JSON.parse(raw) } as LlmSettings
    if (!JSON.parse(raw).provider) {
      const u = (parsed.base_url || "").toLowerCase()
      parsed.provider = u.includes("anthropic.com")
        ? "anthropic"
        : u.includes("api.openai.com")
        ? "openai"
        : u.includes("deepseek.com")
        ? "deepseek"
        : "custom"
    }
    return parsed
  } catch {
    return DEFAULT_LLM
  }
}

export default function App() {
  const [dataset, setDataset] = useState<MatchDataset | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null)
  const [activeSample, setActiveSample] = useState<SampleKind | null>(null)
  const [activeSessionUid, setActiveSessionUid] = useState<string | null>(null)
  const [savedReports, setSavedReports] = useState<SavedReportItem[]>([])
  const [activeReportUid, setActiveReportUid] = useState<string | null>(null)

  const [sessions, setSessions] = useState<SessionListItem[]>([])
  const [dbStatus, setDbStatus] = useState<DbStatusResponse | null>(null)

  const [mode, setMode] = useState<AnalysisMode>("scouting")
  const [targetTeamId, setTargetTeamId] = useState<string>("TEAM_A")
  const [selectedSteamId, setSelectedSteamId] = useState<string | null>(null)
  const [radarScope, setRadarScope] = useState<RadarScope>("player")
  const [radarSide, setRadarSide] = useState<RadarSideFilter>("ALL")

  const [isLoadingSample, setIsLoadingSample] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [mysqlOpen, setMysqlOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [llmSettings, setLlmSettings] = useState<LlmSettings>(loadStoredLlm)
  const [toastMsg, setToastMsg] = useState<string | null>(null)

  const bootedRef = useRef(false)
  /** 已生成报告的内存缓存：key = 作用域(会话/示例) | 模式 | 球队或选手 */
  const analysisCacheRef = useRef<Map<string, AnalysisResponse>>(new Map())
  /** 正在请求中的 key，防止重复点击并发触发多次模型调用 */
  const inflightRef = useRef<Set<string>>(new Set())

  const buildCacheKey = (
    scope: string,
    m: AnalysisMode,
    teamId: string,
    sid: string | null
  ) => `${scope}|${m}|${m === "scouting" ? teamId : sid || ""}`

  const notify = useCallback((msg: string) => {
    setToastMsg(msg)
  }, [])

  useEffect(() => {
    if (!toastMsg) return
    const timer = setTimeout(() => setToastMsg(null), 3500)
    return () => clearTimeout(timer)
  }, [toastMsg])

  const refreshDbAndHistory = useCallback(async () => {
    try {
      const [statusRes, listRes] = await Promise.all([
        fetchDbStatus(),
        fetchDemoSessions(),
      ])
      setDbStatus(statusRes)
      setSessions(listRes.items)
      return listRes.items
    } catch {
      return []
    }
  }, [])

  const applySessionDetail = useCallback(
    async (sessionUid: string) => {
      const detail = await fetchDemoSessionDetail(sessionUid)
      const firstSid = detail.dataset.players[0]?.steamid || null
      const firstTeam = Object.keys(detail.dataset.teams || {})[0] || "TEAM_A"
      const latest = detail.latest_report

      setActiveSample(null)
      setActiveSessionUid(detail.session_uid)
      setDataset(detail.dataset)
      setSavedReports(detail.reports)
      // 已存报告全部写入内存缓存（倒序遍历保证同维度下最新的一份生效）
      ;[...detail.reports].reverse().forEach((r) => {
        analysisCacheRef.current.set(
          buildCacheKey(detail.session_uid, r.mode, r.target_team_id, r.focus_steamid),
          { ...r.analysis, report_uid: r.report_uid }
        )
      })

      if (latest) {
        setAnalysis(latest.analysis)
        setActiveReportUid(latest.report_uid)
        setMode(latest.mode)
        setTargetTeamId(latest.target_team_id || firstTeam)
        setSelectedSteamId(latest.focus_steamid || firstSid)
      } else {
        setActiveReportUid(null)
        setTargetTeamId(firstTeam)
        setSelectedSteamId(firstSid)
      }
    },
    []
  )

  const executeAnalysis = useCallback(
    async (
      ds: MatchDataset,
      nextMode: AnalysisMode,
      nextTeamId: string,
      nextFocusSid: string | null,
      opts?: {
        sessionUid?: string | null
        llm?: LlmSettings
        /** 显式重新生成：跳过所有缓存 */
        force?: boolean
      }
    ) => {
      const targetUid =
        opts?.sessionUid !== undefined ? opts.sessionUid : activeSessionUid
      // 只有真实上传的 Demo 会话才调用模型服务；内置示例一律走规则引擎（假数据）
      const useLlm = Boolean(targetUid)
      const scope = targetUid || `sample:${activeSample ?? "none"}`
      const key = buildCacheKey(scope, nextMode, nextTeamId, nextFocusSid)

      if (!opts?.force) {
        const cached = analysisCacheRef.current.get(key)
        if (cached) {
          setAnalysis(cached)
          setActiveReportUid(cached.report_uid || null)
          return
        }
      }
      if (inflightRef.current.has(key)) return
      inflightRef.current.add(key)

      setIsAnalyzing(true)
      try {
        const res = await runTacticalAnalysis({
          data: ds,
          mode: nextMode,
          target_team_id: nextTeamId,
          focus_steamid: nextFocusSid,
          session_uid: targetUid,
          use_llm: useLlm,
          force: opts?.force,
          llm: opts?.llm ?? llmSettings,
        })
        analysisCacheRef.current.set(key, res)
        setAnalysis(res)
        setActiveReportUid(res.report_uid || null)
        // 仅当真的新生成并入库了报告时才刷新已存报告列表
        if (targetUid && useLlm && !res.from_cache) {
          const detail = await fetchDemoSessionDetail(targetUid)
          setSavedReports(detail.reports)
          void refreshDbAndHistory()
        }
      } catch (err) {
        notify(err instanceof Error ? err.message : "战术推演请求失败")
      } finally {
        inflightRef.current.delete(key)
        setIsAnalyzing(false)
      }
    },
    [activeSample, activeSessionUid, llmSettings, notify, refreshDbAndHistory]
  )

  const handleLoadSample = useCallback(
    async (kind: SampleKind) => {
      setIsLoadingSample(true)
      try {
        const payload = await fetchSampleDataset(kind)
        const nextMode = payload.recommended_mode || kind
        const firstSid = payload.dataset.players[0]?.steamid || null
        const firstTeam = Object.keys(payload.dataset.teams || {})[0] || "TEAM_A"

        setActiveSessionUid(null)
        setSavedReports([])
        setActiveReportUid(null)
        setActiveSample(kind)
        setDataset(payload.dataset)
        setAnalysis(payload.analysis)
        setMode(nextMode)
        setTargetTeamId(firstTeam)
        setSelectedSteamId(firstSid)
        // 示例数据只用内置规则引擎生成的假报告，不调用模型服务
        analysisCacheRef.current.set(
          buildCacheKey(`sample:${kind}`, nextMode, firstTeam, firstSid),
          payload.analysis
        )
      } catch (err) {
        notify(err instanceof Error ? err.message : "加载样本失败")
      } finally {
        setIsLoadingSample(false)
      }
    },
    [notify]
  )

  // 初始化：优先恢复最近上传的真实 Demo 记录；若无上传记录则加载内置示例一
  useEffect(() => {
    if (bootedRef.current) return
    bootedRef.current = true
    void (async () => {
      const storedLlm = loadStoredLlm()
      if (isCustomLlmConfigured(storedLlm)) {
        void saveBackendLlmConfig(storedLlm).catch(() => {})
      }
      const items = await refreshDbAndHistory()
      if (items.length > 0) {
        try {
          await applySessionDetail(items[0].session_uid)
          return
        } catch {
          // fallback to sample
        }
      }
      await handleLoadSample("scouting")
    })()
  }, [applySessionDetail, handleLoadSample, refreshDbAndHistory])

  const handleChangeMode = (nextMode: AnalysisMode) => {
    setMode(nextMode)
    if (dataset) void executeAnalysis(dataset, nextMode, targetTeamId, selectedSteamId)
  }

  const handleChangeTargetTeam = (teamId: string) => {
    setTargetTeamId(teamId)
    if (dataset && mode === "scouting") {
      void executeAnalysis(dataset, mode, teamId, selectedSteamId)
    }
  }

  const handleSelectPlayer = (steamId: string) => {
    setSelectedSteamId(steamId)
    if (dataset && mode === "diagnosis") {
      void executeAnalysis(dataset, mode, targetTeamId, steamId)
    }
  }

  const handleSelectSavedReport = (rep: SavedReportItem) => {
    setAnalysis(rep.analysis)
    setActiveReportUid(rep.report_uid)
    setMode(rep.mode)
    if (rep.target_team_id) setTargetTeamId(rep.target_team_id)
    if (rep.focus_steamid) setSelectedSteamId(rep.focus_steamid)
  }

  const handleUploadFiles = async (
    files: File[],
    onProgress?: (pct: number) => void
  ) => {
    const payload = await uploadAndParseDemos(files, {
      mode,
      target_team_id: targetTeamId,
      focus_steamid: selectedSteamId,
      llm: llmSettings,
      onUploadProgress: onProgress,
    })

    await refreshDbAndHistory()

    if (payload.session_uid) {
      await applySessionDetail(payload.session_uid)
    } else {
      const firstSid = payload.dataset.players[0]?.steamid || null
      const firstTeam = Object.keys(payload.dataset.teams || {})[0] || "TEAM_A"
      setActiveSample(null)
      setDataset(payload.dataset)
      setAnalysis(payload.analysis)
      setTargetTeamId(firstTeam)
      setSelectedSteamId(firstSid)
    }

    if (payload.db_warning) {
      notify(
        `已解析 ${payload.dataset.matches_count} 场 Demo（暂存本地记录，点击顶部「MySQL 配置」填入密码即可入库）`
      )
    } else {
      notify(
        `已解析 ${payload.dataset.matches_count} 场 Demo 并持久化存入 MySQL！`
      )
    }
  }

  const handleSelectHistorySession = async (sessionUid: string) => {
    await applySessionDetail(sessionUid)
    notify("已切回历史上传 Demo 分析报告")
  }

  const handleDeleteHistorySession = async (sessionUid: string) => {
    await deleteDemoSession(sessionUid)
    const remaining = await refreshDbAndHistory()
    notify("已从记录库中删除该场 Demo")
    if (activeSessionUid === sessionUid) {
      if (remaining.length > 0) {
        await applySessionDetail(remaining[0].session_uid)
      } else {
        await handleLoadSample("scouting")
      }
    }
  }

  const handleMysqlConfigured = (nextStatus: DbStatusResponse) => {
    setDbStatus(nextStatus)
    void refreshDbAndHistory()
    const syncNote =
      nextStatus.synced_just_now && nextStatus.synced_just_now > 0
        ? `，并自动同步了 ${nextStatus.synced_just_now} 条待入库记录`
        : ""
    notify(`MySQL (${nextStatus.database}) 连接成功${syncNote}！`)
  }

  const handleSaveSettings = (next: LlmSettings) => {
    localStorage.setItem(LLM_STORAGE_KEY, JSON.stringify(next))
    setLlmSettings(next)
    void saveBackendLlmConfig(next).catch(() => {})
    if (dataset && activeSessionUid && isCustomLlmConfigured(next)) {
      notify(`已保存模型服务 (${next.model})，正在为当前 Demo 重新生成报告...`)
      void executeAnalysis(dataset, mode, targetTeamId, selectedSteamId, {
        sessionUid: activeSessionUid,
        llm: next,
        force: true,
      })
    } else {
      notify(`已保存模型配置 (${next.provider} · ${next.model})`)
    }
  }

  const handleClearSettings = () => {
    localStorage.removeItem(LLM_STORAGE_KEY)
    setLlmSettings(DEFAULT_LLM)
    void saveBackendLlmConfig(DEFAULT_LLM).catch(() => {})
    notify("已恢复内置规则引擎（后续新分析不再调用模型服务）")
  }

  const handleCopyPrompt = async () => {
    if (!analysis?.prompt) return
    await navigator.clipboard.writeText(analysis.prompt)
    notify("已复制完整结构化 AI Prompt 到剪贴板！")
  }

  const currentPlayer =
    dataset?.players.find((p) => p.steamid === selectedSteamId) ||
    dataset?.players[0] ||
    null

  const latestUploadedSession = sessions[0] || null

  return (
    <TooltipProvider>
      <div className="uv-grid-stage min-h-screen text-foreground">
        <TacticalHeader
          activeSample={activeSample}
          activeSessionUid={activeSessionUid}
          sessionsCount={sessions.length}
          dbStatus={dbStatus}
          isLoadingSample={isLoadingSample}
          hasCustomLlm={isCustomLlmConfigured(llmSettings)}
          onSelectSample={handleLoadSample}
          onOpenHistory={() => setHistoryOpen(true)}
          onOpenMysqlSettings={() => setMysqlOpen(true)}
          onOpenImport={() => setImportOpen(true)}
          onOpenSettings={() => setSettingsOpen(true)}
        />

        {/* 当处于内置示例模式且已有上传过的真实 Demo 时，顶部提供醒目的一键切回条 */}
        {activeSample !== null && latestUploadedSession && (
          <div className="border-b border-emerald-500/25 bg-emerald-500/10 px-5 py-1.5">
            <div className="mx-auto flex max-w-[1680px] flex-wrap items-center justify-between gap-2 text-xs">
              <span className="text-emerald-200">
                当前正在浏览内置演示案例 · 你最近上传的真实录像{" "}
                <strong className="font-mono text-emerald-100">
                  「{latestUploadedSession.title}」
                </strong>{" "}
                已归档保存（共 {sessions.length} 条记录）
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() =>
                    void handleSelectHistorySession(
                      latestUploadedSession.session_uid
                    )
                  }
                  className="inline-flex items-center gap-1.5 rounded border border-emerald-400/50 bg-emerald-500/20 px-2.5 py-0.5 font-medium text-emerald-100 hover:bg-emerald-500/30"
                >
                  <RotateCcw className="h-3 w-3" />
                  一键切回我的真实 Demo 报告
                </button>
              </div>
            </div>
          </div>
        )}

        <ModeControlBar
          dataset={dataset}
          mode={mode}
          targetTeamId={targetTeamId}
          selectedSteamId={selectedSteamId}
          isAnalyzing={isAnalyzing}
          onChangeMode={handleChangeMode}
          onChangeTargetTeam={handleChangeTargetTeam}
          onChangeFocusPlayer={handleSelectPlayer}
          onRunAnalyze={() =>
            dataset &&
            executeAnalysis(dataset, mode, targetTeamId, selectedSteamId, {
              force: true,
            })
          }
          onCopyPrompt={handleCopyPrompt}
        />

        <MatchMacroBanner dataset={dataset} targetTeamId={targetTeamId} />

        {/* 三栏响应式工作台 */}
        <main className="mx-auto grid max-w-[1680px] grid-cols-1 gap-4 px-5 py-4 xl:grid-cols-12">
          <div className="xl:col-span-3">
            <PlayerRosterPanel
              dataset={dataset}
              selectedSteamId={selectedSteamId}
              onSelectPlayer={handleSelectPlayer}
            />
          </div>

          <div className="space-y-4 xl:col-span-4">
            {dataset && currentPlayer && (
              <>
                <TacticalRadarCard
                  dataset={dataset}
                  player={currentPlayer}
                  radarScope={radarScope}
                  radarSide={radarSide}
                  onChangeScope={setRadarScope}
                  onChangeSide={setRadarSide}
                />
                <PlayerHabitDetailCard player={currentPlayer} />
              </>
            )}
          </div>

          <div className="xl:col-span-5">
            <AiReportPanel
              analysis={analysis}
              isAnalyzing={isAnalyzing}
              savedReports={savedReports}
              activeReportUid={activeReportUid}
              onSelectSavedReport={handleSelectSavedReport}
            />
          </div>
        </main>

        <ImportDemoDialog
          open={importOpen}
          onOpenChange={setImportOpen}
          onUploadFiles={handleUploadFiles}
        />

        <DemoHistoryDialog
          open={historyOpen}
          onOpenChange={setHistoryOpen}
          sessions={sessions}
          activeSessionUid={activeSessionUid}
          dbStatus={dbStatus}
          onSelectSession={handleSelectHistorySession}
          onDeleteSession={handleDeleteHistorySession}
          onOpenMysqlSettings={() => setMysqlOpen(true)}
        />

        <MysqlSettingsDialog
          open={mysqlOpen}
          onOpenChange={setMysqlOpen}
          status={dbStatus}
          onConfigured={handleMysqlConfigured}
        />

        <LlmSettingsDialog
          open={settingsOpen}
          onOpenChange={setSettingsOpen}
          settings={llmSettings}
          onSave={handleSaveSettings}
          onClear={handleClearSettings}
        />

        {toastMsg && (
          <div className="fixed bottom-5 right-5 z-50 rounded-lg border border-sky-400/50 bg-slate-900/95 px-4 py-2.5 text-xs font-medium text-sky-100 shadow-xl animate-in fade-in slide-in-from-bottom-2">
            {toastMsg}
          </div>
        )}
      </div>
    </TooltipProvider>
  )
}
