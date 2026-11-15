import { AlertTriangle, Bot, FileCode2, History } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { UvHudPanel, UvSectionIndex } from "@/components/ui/uiverse-primitives"
import { cn } from "@/lib/utils"
import type { AnalysisResponse, SavedReportItem } from "@/types/tactical"

interface AiReportPanelProps {
  analysis: AnalysisResponse | null
  isAnalyzing: boolean
  savedReports?: SavedReportItem[]
  activeReportUid?: string | null
  onSelectSavedReport?: (rep: SavedReportItem) => void
}

export function AiReportPanel({
  analysis,
  isAnalyzing,
  savedReports = [],
  activeReportUid,
  onSelectSavedReport,
}: AiReportPanelProps) {
  const engineLabel =
    !analysis?.engine || analysis.engine === "rule_engine"
      ? "RULE_ENGINE // LOCAL"
      : analysis.engine === "rule_engine_fallback"
      ? "RULE_ENGINE // FALLBACK"
      : analysis.engine.toUpperCase()

  return (
    <UvHudPanel className="flex flex-col overflow-hidden">
      <Tabs defaultValue="report" className="flex flex-col">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/90 bg-slate-950/65 px-4 py-3">
          <div className="space-y-1">
            <UvSectionIndex code="04" label="TACTICAL INTELLIGENCE BRIEFING" />
            <div>
              <TabsList className="h-7 border border-slate-800 bg-slate-900/90 p-0.5">
                <TabsTrigger value="report" className="h-6 gap-1.5 px-2.5 text-xs">
                  <Bot className="h-3.5 w-3.5 text-cyan-400" />
                  AI 战术简报与处方
                </TabsTrigger>
                <TabsTrigger value="prompt" className="h-6 gap-1.5 px-2.5 text-xs">
                  <FileCode2 className="h-3.5 w-3.5 text-amber-400" />
                  原始遥测 Prompt
                </TabsTrigger>
              </TabsList>
            </div>
          </div>

          <span className="inline-flex items-center gap-1.5 rounded border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 font-mono text-[10px] font-semibold tracking-wider text-cyan-300">
            <i className="uv-live-dot" />
            {isAnalyzing ? "COMPUTING..." : engineLabel}
          </span>
        </div>

        {/* 若当前真实 Demo 已持久化多份历史分析报告，支持毫秒级一键切换查看 */}
        {savedReports.length > 0 && onSelectSavedReport && (
          <div className="flex flex-wrap items-center gap-1.5 border-b border-slate-800/75 bg-slate-950/45 px-4 py-2">
            <span className="inline-flex shrink-0 items-center gap-1 font-mono text-[10px] text-slate-400">
              <History className="h-3 w-3 text-emerald-400" />
              本场已存报告:
            </span>
            {savedReports.map((rep) => {
              const selected = rep.report_uid === activeReportUid
              const label =
                rep.mode === "scouting"
                  ? `球探 (${rep.target_team_id})`
                  : `诊断 (${rep.focus_player_name || "个人"})`
              return (
                <button
                  key={rep.report_uid}
                  type="button"
                  onClick={() => onSelectSavedReport(rep)}
                  className={cn(
                    "shrink-0 rounded border px-2 py-0.5 font-mono text-[10px] transition-colors",
                    selected
                      ? "border-emerald-400/60 bg-emerald-500/15 text-emerald-200"
                      : "border-slate-800 bg-slate-900/80 text-slate-400 hover:border-slate-600 hover:text-slate-200"
                  )}
                >
                  {label} · {rep.engine.startsWith("llm") ? "LLM" : "规则"}
                </button>
              )
            })}
          </div>
        )}

        {analysis?.warning && (
          <div className="mx-4 mt-3 flex items-start gap-2 rounded border border-amber-500/40 bg-amber-500/15 px-3 py-2 text-xs text-amber-200">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
            <span>{analysis.warning}</span>
          </div>
        )}

        <TabsContent value="report" className="m-0">
          <ScrollArea className="h-[calc(100vh-240px)] min-h-[540px]">
            <div className="p-5">
              {analysis?.reasoning_markdown && (
                <details className="mb-4 rounded border border-cyan-500/25 bg-slate-950/75 px-3.5 py-2.5 text-xs">
                  <summary className="cursor-pointer select-none font-mono text-[11px] font-semibold text-cyan-300">
                    🧠 查看 DeepSeek-V4.1-Flash 战术思考链 (Reasoning Process)
                  </summary>
                  <pre className="mt-2 whitespace-pre-wrap break-words border-t border-slate-800/80 pt-2 font-mono text-[11.5px] leading-relaxed text-slate-400">
                    {analysis.reasoning_markdown}
                  </pre>
                </details>
              )}

              <div className="tactical-markdown">
                {analysis?.report_markdown ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {analysis.report_markdown}
                  </ReactMarkdown>
                ) : (
                  <p className="font-mono text-xs text-slate-400">
                    // INITIALIZING TACTICAL ANALYSIS STREAM...
                  </p>
                )}
              </div>
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="prompt" className="m-0">
          <ScrollArea className="h-[calc(100vh-240px)] min-h-[540px]">
            <pre className="whitespace-pre-wrap break-words bg-slate-950/60 p-4 font-mono text-xs leading-relaxed text-slate-300">
              {analysis?.prompt || ""}
            </pre>
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </UvHudPanel>
  )
}
