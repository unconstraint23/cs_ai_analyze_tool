import {
  Crosshair,
  Database,
  FolderClock,
  FolderUp,
  Radar,
  Settings2,
  Stethoscope,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { UvBeamButton } from "@/components/ui/uiverse-primitives"
import { cn } from "@/lib/utils"
import type { DbStatusResponse, SampleKind } from "@/types/tactical"

interface TacticalHeaderProps {
  activeSample: SampleKind | null
  activeSessionUid: string | null
  sessionsCount: number
  dbStatus: DbStatusResponse | null
  isLoadingSample: boolean
  hasCustomLlm: boolean
  onSelectSample: (kind: SampleKind) => void
  onOpenHistory: () => void
  onOpenMysqlSettings: () => void
  onOpenImport: () => void
  onOpenSettings: () => void
}

export function TacticalHeader({
  activeSample,
  activeSessionUid,
  sessionsCount,
  dbStatus,
  isLoadingSample,
  hasCustomLlm,
  onSelectSample,
  onOpenHistory,
  onOpenMysqlSettings,
  onOpenImport,
  onOpenSettings,
}: TacticalHeaderProps) {
  const mysqlConnected = Boolean(dbStatus?.connected)

  return (
    <header className="sticky top-0 z-30 border-b border-slate-800/85 bg-[#070a10]/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-[1720px] flex-wrap items-center justify-between gap-3 px-5 py-2.5">
        {/* 左侧品牌与实时遥测信标 */}
        <div className="flex items-center gap-3.5">
          <div className="relative flex h-9 w-9 items-center justify-center rounded border border-cyan-400/40 bg-cyan-500/10 text-cyan-300 shadow-[0_0_18px_-4px_rgba(0,212,255,0.45)]">
            <Crosshair className="h-4 w-4" />
            <span className="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 bg-amber-400" />
          </div>

          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-[15px] font-bold tracking-tight text-slate-50">
                CS2 完美平台战术习惯 &amp; Anti-Strat 情报台
              </h1>
              <span className="inline-flex items-center gap-1.5 rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-widest text-emerald-300">
                <i className="uv-live-dot" />
                SYS.LIVE // 64-TICK
              </span>
            </div>
            <p className="font-mono text-[11px] text-slate-400">
              PWA DEMO TELEMETRY ENGINE · 支持多场 <span className="text-cyan-300">.dem/.zip</span> 空间聚合、MySQL 归档与 AI 破局推演
            </p>
          </div>
        </div>

        {/* 右侧 Uiverse 交互按钮组 */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={isLoadingSample}
            onClick={() => onSelectSample("scouting")}
            className={cn(
              "uv-pill-switch inline-flex h-8 items-center gap-1.5 rounded px-2.5 text-xs font-medium",
              activeSample === "scouting"
                ? "border-cyan-400/70 bg-cyan-500/15 text-cyan-200 shadow-[0_0_14px_-4px_rgba(0,212,255,0.45)]"
                : "text-slate-300 hover:border-slate-600 hover:text-white"
            )}
          >
            <Radar className="h-3.5 w-3.5 text-cyan-400" />
            <span>示例一：球探</span>
            <span className="font-mono text-[10px] text-cyan-300/80">[MIRAGE×3]</span>
          </button>

          <button
            type="button"
            disabled={isLoadingSample}
            onClick={() => onSelectSample("diagnosis")}
            className={cn(
              "uv-pill-switch inline-flex h-8 items-center gap-1.5 rounded px-2.5 text-xs font-medium",
              activeSample === "diagnosis"
                ? "border-amber-400/70 bg-amber-500/15 text-amber-200 shadow-[0_0_14px_-4px_rgba(255,158,0,0.45)]"
                : "text-slate-300 hover:border-slate-600 hover:text-white"
            )}
          >
            <Stethoscope className="h-3.5 w-3.5 text-amber-400" />
            <span>示例二：诊断</span>
            <span className="font-mono text-[10px] text-amber-300/80">[INFERNO]</span>
          </button>

          {/* 历史上传 Demo 库入口（切换案例后可一键切回自己的真实 Demo 报告） */}
          <button
            type="button"
            onClick={onOpenHistory}
            className={cn(
              "uv-pill-switch inline-flex h-8 items-center gap-1.5 rounded px-2.5 text-xs font-medium",
              activeSessionUid
                ? "border-emerald-400/75 bg-emerald-500/15 text-emerald-200 shadow-[0_0_14px_-4px_rgba(16,245,160,0.45)]"
                : "text-slate-200 hover:border-cyan-400/60 hover:text-white"
            )}
          >
            <FolderClock className="h-3.5 w-3.5 text-emerald-400" />
            <span>我的 Demo 记录</span>
            <span className="rounded bg-slate-800/90 px-1.5 py-0.5 font-mono text-[10px] text-emerald-300">
              {sessionsCount}
            </span>
          </button>

          <UvBeamButton tone="cyan" onClick={onOpenImport}>
            <FolderUp className="h-3.5 w-3.5 text-cyan-300" />
            导入完美 Demo
          </UvBeamButton>

          {/* MySQL 状态与配置按钮 */}
          <Button
            variant="outline"
            size="sm"
            onClick={onOpenMysqlSettings}
            title={
              mysqlConnected
                ? `MySQL 已连接 (${dbStatus?.database})`
                : "点击配置本机 MySQL 数据库密码"
            }
            className={cn(
              "h-[34px] text-xs",
              mysqlConnected
                ? "border-slate-700/80 bg-slate-900/70 hover:border-emerald-400/50"
                : "border-amber-500/50 bg-amber-500/10 text-amber-200 hover:border-amber-400"
            )}
          >
            <Database
              className={cn(
                "h-3.5 w-3.5",
                mysqlConnected ? "text-emerald-400" : "text-amber-400"
              )}
            />
            {mysqlConnected ? "MySQL 已连" : "MySQL 配置"}
            <span
              className={cn(
                "ml-0.5 h-2 w-2 rounded-full",
                mysqlConnected
                  ? "bg-emerald-400 shadow-[0_0_8px_#10f5a0]"
                  : "bg-amber-400 shadow-[0_0_8px_#ff9e00]"
              )}
            />
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={onOpenSettings}
            className="h-[34px] border-slate-700/80 bg-slate-900/70 text-xs hover:border-cyan-400/50"
          >
            <Settings2 className="h-3.5 w-3.5 text-slate-300" />
            AI 引擎配置
            {hasCustomLlm && (
              <span className="ml-0.5 h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#10f5a0]" />
            )}
          </Button>
        </div>
      </div>
    </header>
  )
}
