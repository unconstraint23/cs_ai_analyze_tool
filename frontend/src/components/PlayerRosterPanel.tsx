import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  UvHudPanel,
  UvSectionIndex,
  UvSpotlightCard,
} from "@/components/ui/uiverse-primitives"
import { cn } from "@/lib/utils"
import type { MatchDataset, PlayerProfile } from "@/types/tactical"

interface PlayerRosterPanelProps {
  dataset: MatchDataset | null
  selectedSteamId: string | null
  onSelectPlayer: (steamId: string) => void
}

function getTagVariant(tag: string): "destructive" | "t" | "ct" | "indigo" {
  if (tag.includes("白给") || tag.includes("首死")) return "destructive"
  if (tag.includes("前压") || tag.includes("突破") || tag.includes("强起")) return "t"
  if (tag.includes("狙") || tag.includes("枪男")) return "ct"
  return "indigo"
}

function getRatingVariant(rating: number): "emerald" | "ct" | "destructive" {
  if (rating >= 1.12) return "emerald"
  if (rating >= 0.95) return "ct"
  return "destructive"
}

export function PlayerRosterPanel({
  dataset,
  selectedSteamId,
  onSelectPlayer,
}: PlayerRosterPanelProps) {
  if (!dataset) return null

  const grouped: Record<string, PlayerProfile[]> = {}
  for (const p of dataset.players) {
    if (!grouped[p.team_id]) grouped[p.team_id] = []
    grouped[p.team_id].push(p)
  }

  return (
    <UvHudPanel className="flex flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-800/90 bg-slate-950/65 px-4 py-3">
        <div>
          <UvSectionIndex code="01" label="ROSTER TELEMETRY" />
          <h2 className="mt-0.5 text-sm font-bold text-slate-100">
            对局选手画像档案
          </h2>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500">
          SELECT TARGET
        </span>
      </div>

      <ScrollArea className="h-[calc(100vh-225px)] min-h-[540px]">
        <div className="space-y-3.5 p-3">
          {Object.entries(grouped).map(([teamId, players]) => {
            const teamTitle = dataset.teams?.[teamId]?.team_name || teamId
            const isTeamA = teamId === "TEAM_A"
            return (
              <div key={teamId} className="space-y-2">
                <div className="flex items-center gap-2 px-1">
                  <span
                    className={cn(
                      "h-2 w-2 rounded-xs",
                      isTeamA ? "bg-cyan-400" : "bg-amber-400"
                    )}
                  />
                  <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-slate-300">
                    {teamTitle}
                  </span>
                </div>

                {players.map((p) => {
                  const s = p.stats
                  const selected = p.steamid === selectedSteamId
                  return (
                    <UvSpotlightCard
                      key={p.steamid}
                      activeTone={selected ? (isTeamA ? "ct" : "t") : null}
                      onClick={() => onSelectPlayer(p.steamid)}
                      className="w-full p-3"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm font-bold text-slate-50">
                          {p.name}
                        </span>
                        <Badge
                          variant={getRatingVariant(s.rating)}
                          className="shrink-0 font-mono tabular-nums"
                        >
                          R {s.rating.toFixed(2)}
                        </Badge>
                      </div>

                      <div className="mt-1 text-[11px] text-slate-400">
                        <span className="font-mono font-semibold text-cyan-300">CT</span>{" "}
                        {p.ct_role}
                        <span className="mx-1.5 text-slate-600">/</span>
                        <span className="font-mono font-semibold text-amber-300">T</span>{" "}
                        {p.t_role}
                      </div>

                      {p.style_tags.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {p.style_tags.map((tag) => (
                            <Badge
                              key={tag}
                              variant={getTagVariant(tag)}
                              className="rounded px-1.5 py-0 text-[10px] font-medium"
                            >
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      )}

                      <div className="mt-2.5 grid grid-cols-4 divide-x divide-slate-800/90 rounded border border-slate-800/80 bg-slate-950/65 py-1.5 text-center font-mono text-[11px] tabular-nums">
                        <div>
                          <span className="block text-[9px] uppercase text-slate-500">
                            ADR
                          </span>
                          <strong className="text-slate-100">{s.adr}</strong>
                        </div>
                        <div>
                          <span className="block text-[9px] uppercase text-slate-500">
                            CT前压
                          </span>
                          <strong className="text-cyan-200">
                            {s.ct_aggression_rate}%
                          </strong>
                        </div>
                        <div>
                          <span className="block text-[9px] uppercase text-slate-500">
                            首杀胜率
                          </span>
                          <strong className="text-slate-100">
                            {s.opening_win_rate}%
                          </strong>
                        </div>
                        <div>
                          <span className="block text-[9px] uppercase text-slate-500">
                            白给率
                          </span>
                          <strong
                            className={
                              s.untraded_death_rate >= 50
                                ? "text-rose-400"
                                : "text-slate-100"
                            }
                          >
                            {s.untraded_death_rate}%
                          </strong>
                        </div>
                      </div>
                    </UvSpotlightCard>
                  )
                })}
              </div>
            )
          })}
        </div>
      </ScrollArea>
    </UvHudPanel>
  )
}
