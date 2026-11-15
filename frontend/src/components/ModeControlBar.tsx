import { Check, Copy, Loader2, ShieldAlert, Sparkles, UserCheck } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { UvBeamButton, UvSpotlightCard } from "@/components/ui/uiverse-primitives"
import { cn } from "@/lib/utils"
import type { AnalysisMode, MatchDataset } from "@/types/tactical"

interface ModeControlBarProps {
  dataset: MatchDataset | null
  mode: AnalysisMode
  targetTeamId: string
  selectedSteamId: string | null
  isAnalyzing: boolean
  onChangeMode: (mode: AnalysisMode) => void
  onChangeTargetTeam: (teamId: string) => void
  onChangeFocusPlayer: (steamId: string) => void
  onRunAnalyze: () => void
  onCopyPrompt: () => Promise<void>
}

export function ModeControlBar({
  dataset,
  mode,
  targetTeamId,
  selectedSteamId,
  isAnalyzing,
  onChangeMode,
  onChangeTargetTeam,
  onChangeFocusPlayer,
  onRunAnalyze,
  onCopyPrompt,
}: ModeControlBarProps) {
  const [copied, setCopied] = useState(false)
  const teams = dataset?.teams || {}
  const teamKeys = Object.keys(teams)

  const handleCopy = async () => {
    await onCopyPrompt()
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <section className="border-b border-slate-800/85 bg-[#0a0e16]/90">
      <div className="mx-auto flex max-w-[1720px] flex-wrap items-center justify-between gap-3 px-5 py-2.5">
        {/* Uiverse Spotlight 双模式战术切换卡 */}
        <div className="flex flex-wrap items-center gap-2.5">
          <UvSpotlightCard
            activeTone={mode === "scouting" ? "ct" : null}
            onClick={() => onChangeMode("scouting")}
            className="px-3.5 py-2"
          >
            <div className="flex items-center gap-2.5">
              <ShieldAlert
                className={cn(
                  "h-4 w-4 shrink-0",
                  mode === "scouting" ? "text-cyan-400" : "text-slate-500"
                )}
              />
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10px] tracking-widest text-cyan-400/80">
                    MODE // 01
                  </span>
                  <span
                    className={cn(
                      "text-xs font-bold",
                      mode === "scouting" ? "text-cyan-200" : "text-slate-200"
                    )}
                  >
                    赛前对手球探报告 (Anti-Strat)
                  </span>
                </div>
                <div className="text-[11px] text-slate-400">
                  摸透对手 5 人常驻报点、CT前压偷人、主狙架点与防守突破口
                </div>
              </div>
            </div>
          </UvSpotlightCard>

          <UvSpotlightCard
            activeTone={mode === "diagnosis" ? "t" : null}
            onClick={() => onChangeMode("diagnosis")}
            className="px-3.5 py-2"
          >
            <div className="flex items-center gap-2.5">
              <UserCheck
                className={cn(
                  "h-4 w-4 shrink-0",
                  mode === "diagnosis" ? "text-amber-400" : "text-slate-500"
                )}
              />
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10px] tracking-widest text-amber-400/80">
                    MODE // 02
                  </span>
                  <span
                    className={cn(
                      "text-xs font-bold",
                      mode === "diagnosis" ? "text-amber-200" : "text-slate-200"
                    )}
                  >
                    个人与车队打法习惯诊断
                  </span>
                </div>
                <div className="text-[11px] text-slate-400">
                  定位开局高频送首死点位、5秒脱节白给率、道具浪费与被针对复盘
                </div>
              </div>
            </div>
          </UvSpotlightCard>
        </div>

        {/* 右侧目标选择器与流光触发器 */}
        <div className="flex flex-wrap items-center gap-2.5">
          {mode === "scouting" ? (
            <div className="flex items-center gap-2">
              <span className="font-mono text-[11px] uppercase tracking-wider text-slate-400 whitespace-nowrap">
                TARGET TEAM:
              </span>
              <Select value={targetTeamId} onValueChange={onChangeTargetTeam}>
                <SelectTrigger className="h-[34px] w-[245px] border-slate-700/80 bg-slate-950/80">
                  <SelectValue placeholder="选择队伍" />
                </SelectTrigger>
                <SelectContent>
                  {teamKeys.map((tid) => (
                    <SelectItem key={tid} value={tid}>
                      {teams[tid]?.team_name || tid}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span className="font-mono text-[11px] uppercase tracking-wider text-slate-400 whitespace-nowrap">
                POV PLAYER:
              </span>
              <Select
                value={selectedSteamId || ""}
                onValueChange={onChangeFocusPlayer}
              >
                <SelectTrigger className="h-[34px] w-[255px] border-slate-700/80 bg-slate-950/80">
                  <SelectValue placeholder="选择选手" />
                </SelectTrigger>
                <SelectContent>
                  {(dataset?.players || []).map((p) => (
                    <SelectItem key={p.steamid} value={p.steamid}>
                      [{p.team_id}] {p.name} (R {p.stats.rating.toFixed(2)})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <UvBeamButton
            tone="amber"
            disabled={isAnalyzing || !dataset}
            onClick={onRunAnalyze}
          >
            {isAnalyzing ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-300" />
                正在推演情报...
              </>
            ) : (
              <>
                <Sparkles className="h-3.5 w-3.5 text-amber-300" />
                生成 AI 战术分析
              </>
            )}
          </UvBeamButton>

          <Button
            variant="outline"
            size="sm"
            disabled={!dataset}
            onClick={handleCopy}
            className="h-[34px] border-slate-700/80 bg-slate-900/70 text-xs hover:border-cyan-400/50"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-emerald-400" />
                已复制 Prompt
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5 text-slate-300" />
                复制 AI Prompt
              </>
            )}
          </Button>
        </div>
      </div>
    </section>
  )
}
