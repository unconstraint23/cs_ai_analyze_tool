# DESIGN.md — CS2 Tactical Telemetry & Anti-Strat System
> Inspired by **Uiverse Design (`uiverse.io/design`)** Dark Structural Telemetry & Uiverse Open-Source Micro-Interaction Elements.

## 1. Visual Theme & Atmosphere
- **Archetype**: Dark Structural Telemetry / Esports Command Deck.
- **Core Philosophy**: Eliminate generic SaaS rounded gradients ("AI slop"). Use matte obsidian/graphite surfaces, architectural 1px structural grid lines, HUD corner reticles (`┌ ┐ └ ┘`), monospace coordinate indices (`§ 01 // ROSTER`), and high-contrast Counter-Strike faction signals (**CT Ice Cyan** vs **T Amber Gold**).
- **Atmosphere**: Tactile, utilitarian, high-precision intelligence console built for IGLs, coaches, and competitive CS2 players.

## 2. Color Tokens (`uiverse-system.css`)
- **Canvas & Surfaces**:
  - `--uv-canvas`: `#07090d` (Deep obsidian stage with subtle 28px architectural coordinate grid)
  - `--uv-surface`: `#0c1017` (Primary structural module base)
  - `--uv-elevated`: `#121822` (Interactive card & control surface)
- **Structural Lines**:
  - `--uv-hairline`: `rgba(148, 163, 184, 0.14)`
  - `--uv-hairline-strong`: `rgba(56, 189, 248, 0.42)`
- **Tactical Signal Accents**:
  - `--uv-ct`: `#00d4ff` (CT Defense / Spatial Hold / Primary Telemetry Signal)
  - `--uv-t`: `#ff9e00` (T Offense / Entry Route / Counter-Strike Signature Amber)
  - `--uv-ok`: `#10f5a0` (Opening Kill / High Rating / Advantage)
  - `--uv-danger`: `#ff3b5c` (Opening Death / Untraded "白给" Risk)

## 3. Typography & Data Readouts
- **Section Indices**: Uppercase monospace section markers (`§ 01 // ROSTER TELEMETRY`, `§ 02 // 2D RADAR [64T]`, `§ 03 // AI BRIEFING`).
- **Numeric Telemetry**: Always apply `font-mono tabular-nums` to Ratings, ADR, percentages, coordinates, and round counts.
- **Chinese Typography**: Crisp `-apple-system / PingFang SC` with generous line-height (`1.68`) in AI briefing reports for instant scanability during match prep.

## 4. Signature Uiverse Micro-Interactions
1. **Conic Beam CTA (`uv-beam-btn`)**: Rotating conic-gradient border beam on primary tactical triggers ("生成 AI 战术分析", "导入真实完美 Demo").
2. **HUD Corner Reticle & Cursor Spotlight (`uv-hud-card` / `uv-player-tile`)**: Precision 6px L-bracket corners + subtle mouse-tracking radial spotlight glow.
3. **Radar Sweep & Target Ping (`uv-radar-sweep`, `uv-ping-dot`)**: Subtle 360-degree scanning sweep over the 2D CS2 map schematic and pulsing rings on opening kills/deaths.
4. **Live Status Beacon (`uv-beacon`)**: Pulsing status LED indicating active telemetry engine state.
