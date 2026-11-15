import { Flame, MapPin, Shield, Swords, Zap } from "lucide-react"
import type { MatchDataset } from "@/types/tactical"

interface MatchMacroBannerProps {
  dataset: MatchDataset | null
  targetTeamId: string
}

export function MatchMacroBanner({ dataset, targetTeamId }: MatchMacroBannerProps) {
  if (!dataset) return null

  const teams = dataset.teams || {}
  const firstKey = Object.keys(teams)[0]
  const activeMacro = teams[targetTeamId] || (firstKey ? teams[firstKey] : undefined)
  const topFormation = activeMacro?.ct_formations?.[0]
    ? `${activeMacro.ct_formations[0].formation} (${activeMacro.ct_formations[0].pct}%)`
    : "2A-1中-2B"

  return (
    <div className="border-b border-slate-800/80 bg-[#080b11]/95">
      <div className="mx-auto flex max-w-[1720px] flex-wrap items-center justify-between gap-3 px-5 py-2 text-xs">
        <div className="flex flex-wrap items-center gap-3">
          <span className="inline-flex items-center gap-1.5 rounded border border-cyan-500/35 bg-cyan-500/10 px-2.5 py-0.5 font-mono text-[11px] font-bold text-cyan-300">
            <MapPin className="h-3 w-3" />
            {dataset.map_cn_name}
          </span>
          <span className="font-medium text-slate-200">{dataset.score_text}</span>
          <span className="font-mono text-[11px] text-slate-500">
            // {dataset.players.length} PROFILES LOADED
          </span>
        </div>

        {/* 结构化遥测数据格 */}
        <div className="flex flex-wrap items-center divide-x divide-slate-800 rounded border border-slate-800/90 bg-slate-950/80 font-mono text-[11px]">
          <div className="flex items-center gap-1.5 px-3 py-1">
            <Shield className="h-3.5 w-3.5 text-cyan-400" />
            <span className="text-slate-400">CT阵型:</span>
            <strong className="tabular-nums text-slate-100">{topFormation}</strong>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1">
            <Swords className="h-3.5 w-3.5 text-amber-400" />
            <span className="text-slate-400">T主攻:</span>
            <strong className="tabular-nums text-slate-100">
              A {activeMacro?.t_attack_a_pct ?? 50}% / B {activeMacro?.t_attack_b_pct ?? 50}%
            </strong>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1">
            <Zap className="h-3.5 w-3.5 text-emerald-400" />
            <span className="text-slate-400">提速占比:</span>
            <strong className="tabular-nums text-slate-100">
              {activeMacro?.t_fast_execute_pct ?? 25}%
            </strong>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1">
            <Flame className="h-3.5 w-3.5 text-rose-400" />
            <span className="text-slate-400">逆风强起:</span>
            <strong className="tabular-nums text-slate-100">
              {activeMacro?.team_force_buy_rate ?? 30}%
            </strong>
          </div>
        </div>
      </div>
    </div>
  )
}
