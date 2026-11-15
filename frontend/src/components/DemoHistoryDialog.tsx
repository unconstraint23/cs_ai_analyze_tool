import {
  Clock,
  Database,
  FileText,
  FolderClock,
  Loader2,
  Play,
  Trash2,
} from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { UvSectionIndex } from "@/components/ui/uiverse-primitives"
import { cn } from "@/lib/utils"
import type { DbStatusResponse, SessionListItem } from "@/types/tactical"

interface DemoHistoryDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  sessions: SessionListItem[]
  activeSessionUid: string | null
  dbStatus: DbStatusResponse | null
  onSelectSession: (sessionUid: string) => Promise<void>
  onDeleteSession: (sessionUid: string) => Promise<void>
  onOpenMysqlSettings: () => void
}

export function DemoHistoryDialog({
  open,
  onOpenChange,
  sessions,
  activeSessionUid,
  dbStatus,
  onSelectSession,
  onDeleteSession,
  onOpenMysqlSettings,
}: DemoHistoryDialogProps) {
  const [loadingUid, setLoadingUid] = useState<string | null>(null)
  const [deletingUid, setDeletingUid] = useState<string | null>(null)

  const handleLoad = async (uid: string) => {
    setLoadingUid(uid)
    try {
      await onSelectSession(uid)
      onOpenChange(false)
    } finally {
      setLoadingUid(null)
    }
  }

  const handleDelete = async (uid: string) => {
    setDeletingUid(uid)
    try {
      await onDeleteSession(uid)
    } finally {
      setDeletingUid(null)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border-slate-800 bg-[#0b1018] sm:max-w-[660px]">
        <DialogHeader>
          <UvSectionIndex code="ARCHIVE" label="DEMO TELEMETRY & AI REPORT REPOSITORY" />
          <DialogTitle className="mt-1 flex items-center justify-between gap-2 pr-6 text-slate-50">
            <span className="flex items-center gap-2">
              <FolderClock className="h-4 w-4 text-cyan-400" />
              已上传真实 Demo 历史分析记录库
            </span>
            <button
              type="button"
              onClick={() => {
                onOpenChange(false)
                onOpenMysqlSettings()
              }}
              className={cn(
                "inline-flex items-center gap-1.5 rounded border px-2.5 py-1 font-mono text-[10px] font-medium transition-colors",
                dbStatus?.connected
                  ? "border-emerald-500/40 bg-emerald-500/12 text-emerald-300 hover:bg-emerald-500/20"
                  : "border-amber-500/45 bg-amber-500/15 text-amber-200 hover:bg-amber-500/25"
              )}
            >
              <Database className="h-3 w-3" />
              {dbStatus?.connected
                ? `MySQL: ${dbStatus.database}`
                : "MySQL 未鉴权 · 点击配置密码同步入库"}
            </button>
          </DialogTitle>
          <DialogDescription className="text-slate-400">
            所有上传解析过的真实 <code className="text-cyan-300">.dem</code> 空间遥测数据与生成的 AI 报告均保存在此处，切换内置案例或刷新网页后随时一键切回。
          </DialogDescription>
        </DialogHeader>

        {sessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-md border border-dashed border-slate-800 bg-slate-950/60 py-12 text-center">
            <FolderClock className="mb-2.5 h-8 w-8 text-slate-600" />
            <p className="text-sm font-medium text-slate-300">暂无已上传的真实 Demo 记录</p>
            <p className="mt-1 text-xs text-slate-500">
              点击顶部「导入真实完美 Demo」上传录像后，遥测数据与 AI 战术报告将自动持久化归档
            </p>
          </div>
        ) : (
          <ScrollArea className="max-h-[420px] pr-2">
            <div className="space-y-2.5">
              {sessions.map((item) => {
                const isActive = item.session_uid === activeSessionUid
                const isLlm = item.latest_engine.toLowerCase().startsWith("llm")
                return (
                  <div
                    key={item.session_uid}
                    className={cn(
                      "flex flex-wrap items-center justify-between gap-3 rounded-md border p-3.5 transition-all",
                      isActive
                        ? "border-cyan-400/65 bg-cyan-500/10 shadow-[0_0_20px_-6px_rgba(0,212,255,0.35)]"
                        : "border-slate-800/90 bg-slate-950/75 hover:border-slate-700"
                    )}
                  >
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        {item.mysql_id ? (
                          <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-emerald-300">
                            MySQL #{item.mysql_id}
                          </span>
                        ) : (
                          <span className="rounded bg-amber-500/15 px-1.5 py-0.5 font-mono text-[10px] text-amber-300">
                            待同步入库
                          </span>
                        )}
                        <span className="truncate text-sm font-semibold text-slate-100">
                          {item.title}
                        </span>
                        {isActive && (
                          <span className="rounded border border-cyan-400/50 bg-cyan-500/20 px-1.5 py-0.5 font-mono text-[10px] text-cyan-200">
                            当前查看中
                          </span>
                        )}
                      </div>

                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] text-slate-400">
                        <span>{item.score_text}</span>
                        <span>·</span>
                        <span className="inline-flex items-center gap-1">
                          <FileText className="h-3 w-3 text-cyan-400" />
                          {item.reports_count} 份报告
                        </span>
                        <span>·</span>
                        <span
                          className={cn(
                            isLlm ? "text-emerald-300" : "text-slate-400"
                          )}
                        >
                          {item.latest_engine}
                        </span>
                        {item.created_at && (
                          <>
                            <span>·</span>
                            <span className="inline-flex items-center gap-1 text-slate-500">
                              <Clock className="h-3 w-3" />
                              {item.created_at}
                            </span>
                          </>
                        )}
                      </div>
                    </div>

                    <div className="flex shrink-0 items-center gap-2">
                      <Button
                        size="sm"
                        variant={isActive ? "secondary" : "outline"}
                        disabled={loadingUid === item.session_uid}
                        onClick={() => handleLoad(item.session_uid)}
                        className="h-8 border-cyan-500/40 bg-cyan-500/12 text-xs text-cyan-200 hover:bg-cyan-500/25"
                      >
                        {loadingUid === item.session_uid ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Play className="h-3 w-3 fill-current" />
                        )}
                        {isActive ? "重新载入" : "查看报告与雷达"}
                      </Button>

                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={deletingUid === item.session_uid}
                        onClick={() => handleDelete(item.session_uid)}
                        className="h-8 w-8 p-0 text-slate-500 hover:bg-rose-500/15 hover:text-rose-400"
                        title="删除此条记录"
                      >
                        {deletingUid === item.session_uid ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="h-3.5 w-3.5" />
                        )}
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  )
}
