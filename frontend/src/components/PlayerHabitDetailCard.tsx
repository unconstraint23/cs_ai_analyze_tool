import { Crosshair, Flame, Shield, Skull } from "lucide-react"
import { Progress } from "@/components/ui/progress"
import { UvHudPanel, UvSectionIndex } from "@/components/ui/uiverse-primitives"
import type { PlayerProfile } from "@/types/tactical"

interface PlayerHabitDetailCardProps {
  player: PlayerProfile
}

export function PlayerHabitDetailCard({ player }: PlayerHabitDetailCardProps) {
  const s = player.stats
  const ctL = player.ct_lanes_pct
  const tL = player.t_lanes_pct

  const weaponsText =
    player.top_weapons?.map((w) => `${w.weapon.toUpperCase()} ${w.pct}%`).join(" · ") ||
    "RIFLE BALANCED"

  return (
    <UvHudPanel className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/90 bg-slate-950/65 px-4 py-3">
        <div>
          <UvSectionIndex code="03" label="HABIT VECTOR MATRIX" />
          <h2 className="mt-0.5 text-sm font-bold text-slate-100">
            {player.name} · 个人地图习惯拆解
          </h2>
        </div>
        <span className="rounded border border-slate-800 bg-slate-900/90 px-2 py-0.5 font-mono text-[10.5px] tabular-nums text-slate-300">
          {player.rounds_played} RDS · {weaponsText}
        </span>
      </div>

      <div className="space-y-4 p-4">
        {/* CT / T 分路堆叠条 */}
        <div className="space-y-2.5">
          <div>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="font-medium text-cyan-300">
                CT 防守分路偏好 · {player.ct_role}
              </span>
              <span className="font-mono text-[11px] tabular-nums text-slate-400">
                前压率 <strong className="text-cyan-200">{s.ct_aggression_rate}%</strong>
              </span>
            </div>
            <div className="flex h-[18px] w-full overflow-hidden rounded border border-slate-800 font-mono text-[10px] font-bold tabular-nums">
              <div
                style={{ width: `${Math.max(ctL.A, 8)}%` }}
                className="flex items-center justify-center bg-cyan-600/90 text-white"
              >
                A {ctL.A}%
              </div>
              <div
                style={{ width: `${Math.max(ctL.MID, 8)}%` }}
                className="flex items-center justify-center border-x border-slate-950/60 bg-indigo-500/90 text-white"
              >
                MID {ctL.MID}%
              </div>
              <div
                style={{ width: `${Math.max(ctL.B, 8)}%` }}
                className="flex items-center justify-center bg-amber-500/95 text-slate-950"
              >
                B {ctL.B}%
              </div>
            </div>
          </div>

          <div>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="font-medium text-amber-300">
                T 进攻路线偏好 · {player.t_role}
              </span>
              <span className="font-mono text-[11px] tabular-nums text-slate-400">
                T首杀尝试{" "}
                <strong className="text-amber-200">{s.t_opening_attempt_rate}%</strong>
              </span>
            </div>
            <div className="flex h-[18px] w-full overflow-hidden rounded border border-slate-800 font-mono text-[10px] font-bold tabular-nums">
              <div
                style={{ width: `${Math.max(tL.A, 8)}%` }}
                className="flex items-center justify-center bg-cyan-600/90 text-white"
              >
                A {tL.A}%
              </div>
              <div
                style={{ width: `${Math.max(tL.MID, 8)}%` }}
                className="flex items-center justify-center border-x border-slate-950/60 bg-indigo-500/90 text-white"
              >
                MID {tL.MID}%
              </div>
              <div
                style={{ width: `${Math.max(tL.B, 8)}%` }}
                className="flex items-center justify-center bg-amber-500/95 text-slate-950"
              >
                B {tL.B}%
              </div>
            </div>
          </div>
        </div>

        {/* 关键指标分段遥测条 */}
        <div className="grid grid-cols-2 gap-3 rounded border border-slate-800/90 bg-slate-950/75 p-3 text-xs">
          <div className="space-y-1.5">
            <div className="flex justify-between">
              <span className="text-slate-400">KAST 团队贡献率</span>
              <strong className="font-mono tabular-nums text-emerald-300">
                {s.kast_pct}%
              </strong>
            </div>
            <Progress
              value={s.kast_pct}
              className="h-1.5 bg-slate-800"
              indicatorClassName="bg-[#10f5a0]"
            />
          </div>

          <div className="space-y-1.5">
            <div className="flex justify-between">
              <span className="text-slate-400">阵亡未补枪 (白给率)</span>
              <strong className="font-mono tabular-nums text-rose-400">
                {s.untraded_death_rate}%
              </strong>
            </div>
            <Progress
              value={s.untraded_death_rate}
              className="h-1.5 bg-slate-800"
              indicatorClassName="bg-[#ff3b5c]"
            />
          </div>

          <div className="space-y-1.5">
            <div className="flex justify-between">
              <span className="text-slate-400">低经济强起刚枪率</span>
              <strong className="font-mono tabular-nums text-amber-300">
                {s.force_buy_rate}%
              </strong>
            </div>
            <Progress
              value={s.force_buy_rate}
              className="h-1.5 bg-slate-800"
              indicatorClassName="bg-[#ff9e00]"
            />
          </div>

          <div className="space-y-1.5">
            <div className="flex justify-between">
              <span className="text-slate-400">道具投掷 / 致盲效率</span>
              <strong className="font-mono tabular-nums text-cyan-300">
                {s.utility_per_round}颗 · 盲{s.enemies_blinded_per_round}/局
              </strong>
            </div>
            <Progress
              value={Math.min(100, s.utility_per_round * 40)}
              className="h-1.5 bg-slate-800"
              indicatorClassName="bg-[#00d4ff]"
            />
          </div>
        </div>

        {/* 四象限报点热区矩阵 */}
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          <div className="rounded border border-slate-800/85 bg-slate-950/60 p-2.5 text-xs">
            <div className="mb-1.5 flex items-center gap-1.5 font-mono text-[11px] font-bold text-cyan-300">
              <Shield className="h-3.5 w-3.5" />
              CT 常驻报点 TOP
            </div>
            <div className="space-y-1">
              {player.ct_top_callouts.length > 0 ? (
                player.ct_top_callouts.map((c) => (
                  <div key={c.place} className="flex justify-between text-slate-300">
                    <span>{c.place}</span>
                    <strong className="font-mono tabular-nums text-slate-100">
                      {c.pct}% ({c.count})
                    </strong>
                  </div>
                ))
              ) : (
                <div className="text-slate-500">暂无集中报点</div>
              )}
            </div>
          </div>

          <div className="rounded border border-slate-800/85 bg-slate-950/60 p-2.5 text-xs">
            <div className="mb-1.5 flex items-center gap-1.5 font-mono text-[11px] font-bold text-amber-300">
              <Flame className="h-3.5 w-3.5" />
              T 进攻路线 TOP
            </div>
            <div className="space-y-1">
              {player.t_top_callouts.length > 0 ? (
                player.t_top_callouts.map((c) => (
                  <div key={c.place} className="flex justify-between text-slate-300">
                    <span>{c.place}</span>
                    <strong className="font-mono tabular-nums text-slate-100">
                      {c.pct}% ({c.count})
                    </strong>
                  </div>
                ))
              ) : (
                <div className="text-slate-500">暂无集中路线</div>
              )}
            </div>
          </div>

          <div className="rounded border border-slate-800/85 bg-slate-950/60 p-2.5 text-xs">
            <div className="mb-1.5 flex items-center gap-1.5 font-mono text-[11px] font-bold text-emerald-300">
              <Crosshair className="h-3.5 w-3.5" />
              首杀得手热区 ({s.opening_kills}次)
            </div>
            <div className="space-y-1">
              {player.opening_kill_spots.length > 0 ? (
                player.opening_kill_spots.map((c) => (
                  <div key={c.place} className="flex justify-between text-slate-300">
                    <span>{c.place}</span>
                    <strong className="font-mono tabular-nums text-emerald-300">
                      {c.count} 次
                    </strong>
                  </div>
                ))
              ) : (
                <div className="text-slate-500">暂无记录</div>
              )}
            </div>
          </div>

          <div className="rounded border border-slate-800/85 bg-slate-950/60 p-2.5 text-xs">
            <div className="mb-1.5 flex items-center gap-1.5 font-mono text-[11px] font-bold text-rose-400">
              <Skull className="h-3.5 w-3.5" />
              首死白给热区 ({s.opening_deaths}次)
            </div>
            <div className="space-y-1">
              {player.opening_death_spots.length > 0 ? (
                player.opening_death_spots.map((c) => (
                  <div key={c.place} className="flex justify-between text-slate-300">
                    <span>{c.place}</span>
                    <strong className="font-mono tabular-nums text-rose-400">
                      {c.count} 次
                    </strong>
                  </div>
                ))
              ) : (
                <div className="text-slate-500">暂无记录</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </UvHudPanel>
  )
}
