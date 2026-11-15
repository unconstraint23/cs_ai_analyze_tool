import * as React from "react"
import { cn } from "@/lib/utils"

/**
 * Uiverse HUD Panel — 带有四角战术准星折线与深色结构网格底座的面板容器
 */
export const UvHudPanel = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("uv-hud-panel rounded-md", className)}
    {...props}
  />
))
UvHudPanel.displayName = "UvHudPanel"

/**
 * Uiverse Spotlight Card — 鼠标实时追踪聚光灯高光卡片
 */
export interface UvSpotlightCardProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  activeTone?: "ct" | "t" | null
}

export const UvSpotlightCard = React.forwardRef<
  HTMLButtonElement,
  UvSpotlightCardProps
>(({ className, activeTone, onMouseMove, children, ...props }, ref) => {
  const handleMove = (e: React.MouseEvent<HTMLButtonElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    e.currentTarget.style.setProperty("--spot-x", `${e.clientX - rect.left}px`)
    e.currentTarget.style.setProperty("--spot-y", `${e.clientY - rect.top}px`)
    onMouseMove?.(e)
  }

  return (
    <button
      ref={ref}
      type="button"
      onMouseMove={handleMove}
      className={cn(
        "uv-spotlight-card rounded-md text-left",
        activeTone === "ct" && "uv-active-ct",
        activeTone === "t" && "uv-active-t",
        className
      )}
      {...props}
    >
      <div className="relative z-10">{children}</div>
    </button>
  )
})
UvSpotlightCard.displayName = "UvSpotlightCard"

/**
 * Uiverse Conic Beam Button — 流光边框战术主操作按钮
 */
export interface UvBeamButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  tone?: "cyan" | "amber"
}

export const UvBeamButton = React.forwardRef<
  HTMLButtonElement,
  UvBeamButtonProps
>(({ className, tone = "cyan", children, ...props }, ref) => (
  <button
    ref={ref}
    type="button"
    className={cn(
      "uv-beam-btn",
      tone === "amber" && "uv-beam-amber",
      className
    )}
    {...props}
  >
    <span className="uv-beam-btn-inner">{children}</span>
  </button>
))
UvBeamButton.displayName = "UvBeamButton"

/**
 * Uiverse Design Telemetry Section Index — 如 "§ 01 // ROSTER"
 */
export function UvSectionIndex({
  code,
  label,
  className,
}: {
  code: string
  label: string
  className?: string
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-sky-400/85",
        className
      )}
    >
      <span className="text-amber-400">§ {code}</span>
      <span className="text-slate-600">//</span>
      <span>{label}</span>
    </span>
  )
}
