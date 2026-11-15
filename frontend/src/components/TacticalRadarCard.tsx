import { useState } from "react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { UvHudPanel, UvSectionIndex } from "@/components/ui/uiverse-primitives"
import type {
  MatchDataset,
  PlayerProfile,
  RadarScope,
  RadarSideFilter,
} from "@/types/tactical"

interface TacticalRadarCardProps {
  dataset: MatchDataset
  player: PlayerProfile
  radarScope: RadarScope
  radarSide: RadarSideFilter
  onChangeScope: (scope: RadarScope) => void
  onChangeSide: (side: RadarSideFilter) => void
}

const ZONE_STROKE: Record<string, string> = {
  A: "#00d4ff",
  MID: "#a78bfa",
  B: "#ff9e00",
  SPAWN: "#64748b",
}

export function TacticalRadarCard({
  dataset,
  player,
  radarScope,
  radarSide,
  onChangeScope,
  onChangeSide,
}: TacticalRadarCardProps) {
  const [hoverInfo, setHoverInfo] = useState<{
    text: string
    coord: string
    x: number
    y: number
  } | null>(null)

  const sourcePlayers =
    radarScope === "team"
      ? dataset.players.filter((p) => p.team_id === player.team_id)
      : [player]

  const titleTarget =
    radarScope === "player"
      ? player.name
      : dataset.teams?.[player.team_id]?.team_name || player.team_id

  return (
    <UvHudPanel className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/90 bg-slate-950/65 px-4 py-3">
        <div>
          <UvSectionIndex code="02" label="SPATIAL RADAR [64-TICK]" />
          <h2 className="mt-0.5 text-sm font-bold text-slate-100">
            2D 站位与首杀雷达 · <span className="text-cyan-300">{titleTarget}</span>
          </h2>
        </div>

        <div className="flex items-center gap-2">
          <Select
            value={radarScope}
            onValueChange={(v) => onChangeScope(v as RadarScope)}
          >
            <SelectTrigger className="h-7 w-[138px] border-slate-700/80 bg-slate-950 text-[11px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="player">仅当前选中选手</SelectItem>
              <SelectItem value="team">当前整支队伍叠加</SelectItem>
            </SelectContent>
          </Select>

          <Select
            value={radarSide}
            onValueChange={(v) => onChangeSide(v as RadarSideFilter)}
          >
            <SelectTrigger className="h-7 w-[124px] border-slate-700/80 bg-slate-950 text-[11px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">CT + T 全部</SelectItem>
              <SelectItem value="CT">仅看 CT 防守</SelectItem>
              <SelectItem value="T">仅看 T 进攻</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="bg-[#06090f] p-3">
        <div className="relative mx-auto max-w-[395px]">
          <svg
            viewBox="0 0 100 100"
            className="aspect-square w-full rounded border border-slate-800/95 bg-[radial-gradient(circle_at_center,#101b2d_0%,#05080d_100%)]"
            onMouseLeave={() => setHoverInfo(null)}
          >
            <defs>
              <linearGradient id="uvSweepGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#00d4ff" stopOpacity="0.18" />
                <stop offset="100%" stopColor="#00d4ff" stopOpacity="0" />
              </linearGradient>
            </defs>

            {/* 同心校准环与十字刻度网格 */}
            {[20, 40, 60, 80].map((v) => (
              <g key={v}>
                <line
                  x1={v}
                  y1={0}
                  x2={v}
                  y2={100}
                  stroke="#182234"
                  strokeWidth="0.28"
                />
                <line
                  x1={0}
                  y1={v}
                  x2={100}
                  y2={v}
                  stroke="#182234"
                  strokeWidth="0.28"
                />
              </g>
            ))}
            <circle
              cx={50}
              cy={50}
              r={24}
              fill="none"
              stroke="#19273c"
              strokeDasharray="1.5 1.5"
              strokeWidth="0.3"
            />
            <circle
              cx={50}
              cy={50}
              r={42}
              fill="none"
              stroke="#162235"
              strokeWidth="0.3"
            />

            {/* Uiverse 动态雷达扫描扇区 */}
            <g className="uv-radar-sweep-cone">
              <path
                d="M 50 50 L 50 4 A 46 46 0 0 1 83 18 Z"
                fill="url(#uvSweepGrad)"
              />
              <line
                x1={50}
                y1={50}
                x2={50}
                y2={4}
                stroke="#00d4ff"
                strokeOpacity="0.35"
                strokeWidth="0.35"
              />
            </g>

            {/* 地图报点战术盒 */}
            {(dataset.map_landmarks || []).map((lm) => {
              const stroke = ZONE_STROKE[lm.zone] || "#64748b"
              return (
                <g key={`${lm.label}-${lm.x}-${lm.y}`}>
                  <rect
                    x={lm.x - 8.6}
                    y={lm.y - 3.2}
                    width={17.2}
                    height={5.5}
                    rx={0.9}
                    fill="rgba(9, 14, 23, 0.88)"
                    stroke={stroke}
                    strokeOpacity={0.5}
                    strokeWidth={0.35}
                  />
                  <text
                    x={lm.x}
                    y={lm.y + 0.55}
                    textAnchor="middle"
                    fill="#dce7f5"
                    fontSize="2.22"
                    fontWeight={600}
                  >
                    {lm.label}
                  </text>
                </g>
              )
            })}

            {/* 选手空间采样点与首杀/首死脉冲信标 */}
            {sourcePlayers.flatMap((sp) =>
              (sp.radar_points || [])
                .filter((pt) => radarSide === "ALL" || pt.side === radarSide)
                .map((pt, idx) => {
                  const key = `${sp.steamid}-${idx}`
                  const tipBase = `${sp.name} · ${pt.side} · ${pt.place} (R${pt.round})`
                  const coordText = `GRID [${pt.x.toFixed(0)}, ${pt.y.toFixed(0)}]`

                  if (pt.kind === "opening_kill") {
                    return (
                      <g
                        key={key}
                        className="cursor-pointer"
                        onMouseEnter={() =>
                          setHoverInfo({
                            text: `★ 首杀得手 · ${tipBase}`,
                            coord: coordText,
                            x: pt.x,
                            y: pt.y,
                          })
                        }
                      >
                        <circle
                          cx={pt.x}
                          cy={pt.y}
                          r={3.2}
                          fill="none"
                          stroke="#10f5a0"
                          className="uv-kill-ring"
                        />
                        <circle
                          cx={pt.x}
                          cy={pt.y}
                          r={1.7}
                          fill="#10f5a0"
                          stroke="#052e1c"
                          strokeWidth={0.4}
                        />
                      </g>
                    )
                  }

                  if (pt.kind === "opening_death") {
                    return (
                      <g
                        key={key}
                        className="cursor-pointer"
                        onMouseEnter={() =>
                          setHoverInfo({
                            text: `✕ 首死白给 · ${tipBase}`,
                            coord: coordText,
                            x: pt.x,
                            y: pt.y,
                          })
                        }
                      >
                        <circle cx={pt.x} cy={pt.y} r={2.4} fill="rgba(255,59,92,0.14)" />
                        <line
                          x1={pt.x - 1.5}
                          y1={pt.y - 1.5}
                          x2={pt.x + 1.5}
                          y2={pt.y + 1.5}
                          stroke="#ff3b5c"
                          strokeWidth={0.85}
                        />
                        <line
                          x1={pt.x + 1.5}
                          y1={pt.y - 1.5}
                          x2={pt.x - 1.5}
                          y2={pt.y + 1.5}
                          stroke="#ff3b5c"
                          strokeWidth={0.85}
                        />
                      </g>
                    )
                  }

                  return (
                    <circle
                      key={key}
                      cx={pt.x}
                      cy={pt.y}
                      r={1.3}
                      fill={
                        pt.side === "CT"
                          ? "rgba(0, 212, 255, 0.86)"
                          : "rgba(255, 158, 0, 0.86)"
                      }
                      className="cursor-pointer"
                      onMouseEnter={() =>
                        setHoverInfo({
                          text: tipBase,
                          coord: coordText,
                          x: pt.x,
                          y: pt.y,
                        })
                      }
                    />
                  )
                })
            )}
          </svg>

          {hoverInfo && (
            <div
              className="pointer-events-none absolute z-20 rounded border border-cyan-400/70 bg-slate-950/95 px-2.5 py-1.5 text-[11px] text-slate-100 shadow-xl"
              style={{
                left: `${Math.min(68, Math.max(4, hoverInfo.x))}%`,
                top: `${Math.max(4, hoverInfo.y - 11)}%`,
              }}
            >
              <div className="font-medium">{hoverInfo.text}</div>
              <div className="font-mono text-[9.5px] text-cyan-400">
                {hoverInfo.coord}
              </div>
            </div>
          )}
        </div>

        {/* 图例 */}
        <div className="mt-2.5 flex flex-wrap items-center justify-center gap-4 font-mono text-[10.5px] text-slate-400">
          <span className="flex items-center gap-1.5">
            <i className="h-2 w-2 rounded-full bg-[#00d4ff] shadow-[0_0_6px_#00d4ff]" />
            CT默认(+14s)
          </span>
          <span className="flex items-center gap-1.5">
            <i className="h-2 w-2 rounded-full bg-[#ff9e00] shadow-[0_0_6px_#ff9e00]" />
            T路线(+14s)
          </span>
          <span className="flex items-center gap-1.5">
            <i className="h-2 w-2 rounded-full bg-[#10f5a0] shadow-[0_0_6px_#10f5a0]" />
            首杀点(★)
          </span>
          <span className="flex items-center gap-1.5">
            <i className="h-2 w-2 rounded-full bg-[#ff3b5c] shadow-[0_0_6px_#ff3b5c]" />
            首死白给(✕)
          </span>
        </div>
      </div>
    </UvHudPanel>
  )
}
