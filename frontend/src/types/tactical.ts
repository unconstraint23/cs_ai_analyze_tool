export type AnalysisMode = "scouting" | "diagnosis"
export type SampleKind = "scouting" | "diagnosis"
export type RadarScope = "player" | "team"
export type RadarSideFilter = "ALL" | "CT" | "T"

export interface MapLandmark {
  label: string
  x: number
  y: number
  zone: "A" | "MID" | "B" | "SPAWN" | string
}

export interface RadarPoint {
  x: number
  y: number
  side: "CT" | "T"
  kind: "position" | "opening_kill" | "opening_death"
  place: string
  round: number
}

export interface CalloutFreq {
  place: string
  pct: number
  count: number
}

export interface SpotCount {
  place: string
  count: number
}

export interface WeaponUsage {
  weapon: string
  kills: number
  pct: number
}

export interface PlayerStats {
  rating: number
  adr: number
  kd: number
  kills: number
  deaths: number
  assists: number
  hs_pct: number
  kast_pct: number
  opening_kills: number
  opening_deaths: number
  opening_attempt_rate: number
  opening_win_rate: number
  t_opening_attempt_rate: number
  ct_aggression_rate: number
  untraded_death_rate: number
  force_buy_rate: number
  awp_kill_share: number
  utility_per_round: number
  smokes_per_round: number
  flashes_per_round: number
  molotovs_per_round: number
  enemies_blinded_per_round: number
  flash_assists_plus_blind: number
  clutch_wins: number
}

export interface LanePct {
  A: number
  MID: number
  B: number
}

export interface PlayerProfile {
  steamid: string
  name: string
  team_id: string
  matches_played?: number
  rounds_played: number
  ct_rounds: number
  t_rounds: number
  ct_role: string
  t_role: string
  style_tags: string[]
  stats: PlayerStats
  ct_lanes_pct: LanePct
  t_lanes_pct: LanePct
  ct_top_callouts: CalloutFreq[]
  t_top_callouts: CalloutFreq[]
  top_weapons: WeaponUsage[]
  opening_kill_spots: SpotCount[]
  opening_death_spots: SpotCount[]
  radar_points: RadarPoint[]
}

export interface CtFormation {
  formation: string
  pct: number
}

export interface TeamMacro {
  team_id: string
  team_name: string
  ct_formations: CtFormation[]
  t_attack_a_pct: number
  t_attack_b_pct: number
  t_fast_execute_pct: number
  team_force_buy_rate: number
}

export interface MatchDataset {
  source_type: string
  demo_files: string[]
  matches_count: number
  map_name: string
  map_cn_name: string
  map_landmarks: MapLandmark[]
  total_rounds: number
  score_text: string
  teams: Record<string, TeamMacro>
  players: PlayerProfile[]
}

export interface AnalysisResponse {
  engine: string
  report_markdown: string
  reasoning_markdown?: string | null
  prompt: string
  warning?: string
  report_uid?: string
  storage_backend?: "mysql" | "local_pending_cache"
  from_cache?: boolean
}

export interface SamplePayload {
  dataset: MatchDataset
  analysis: AnalysisResponse
  recommended_mode?: AnalysisMode
  session_uid?: string | null
  mysql_session_id?: number | null
  report_uid?: string | null
  storage_backend?: "mysql" | "local_pending_cache"
  db_warning?: string | null
}

export type ReasoningEffort = "none" | "low" | "high"

/** deepseek / openai / anthropic 官方，custom = 任意 OpenAI 兼容接口（火山方舟、百炼、Ollama、内网网关等） */
export type LlmProvider = "deepseek" | "openai" | "anthropic" | "custom"

export interface LlmSettings {
  provider: LlmProvider
  base_url: string
  model: string
  api_key: string
  reasoning_effort?: ReasoningEffort
}

export interface LlmTestResponse {
  ok: boolean
  provider?: LlmProvider
  endpoint: string
  model: string
  latency_ms: number
  reply: string
}

export interface DbStatusResponse {
  connected: boolean
  storage_backend: "mysql" | "local_pending_cache"
  host: string
  port: number
  user: string
  database: string
  has_password: boolean
  sessions_count: number
  reports_count: number
  pending_sync_count: number
  synced_just_now?: number
  error?: string | null
}

export interface MysqlConfigInput {
  host: string
  port: number
  user: string
  password?: string
  database: string
}

export interface SessionListItem {
  mysql_id: number | null
  session_uid: string
  title: string
  map_name: string
  map_cn_name: string
  matches_count: number
  total_rounds: number
  score_text: string
  demo_files: string[]
  reports_count: number
  latest_engine: string
  storage_backend: "mysql" | "local_pending_cache"
  created_at: string
}

export interface SessionsListResponse {
  connected: boolean
  storage_backend: "mysql" | "local_pending_cache"
  error?: string | null
  items: SessionListItem[]
}

export interface SavedReportItem {
  mysql_id: number | null
  report_uid: string
  mode: AnalysisMode
  target_team_id: string
  focus_steamid: string | null
  focus_player_name: string | null
  engine: string
  created_at: string
  analysis: AnalysisResponse
}

export interface SessionDetailPayload {
  session_uid: string
  mysql_id: number | null
  title: string
  storage_backend: "mysql" | "local_pending_cache"
  created_at: string
  dataset: MatchDataset
  reports: SavedReportItem[]
  latest_report: SavedReportItem | null
}
