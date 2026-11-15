import type {
  AnalysisMode,
  AnalysisResponse,
  DbStatusResponse,
  LlmSettings,
  LlmTestResponse,
  MatchDataset,
  MysqlConfigInput,
  SampleKind,
  SamplePayload,
  SessionDetailPayload,
  SessionsListResponse,
} from "@/types/tactical"

/**
 * 开发环境下 (端口 5173) 浏览器直接跨域请求本机 FastAPI (8765)，
 * 避免受限沙箱环境下 Vite Node 进程内部发起反向代理连接触发 EPERM；
 * 生产托管环境下 (端口 8765 同源) 自动使用相对路径 ""。
 */
const API_BASE: string =
  import.meta.env.VITE_API_BASE ??
  (typeof window !== "undefined" && window.location.port === "5173"
    ? `${window.location.protocol}//${window.location.hostname}:8765`
    : "")

async function handleJson<T>(resp: Response): Promise<T> {
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    const detail = (data as { detail?: string })?.detail || `请求失败 (${resp.status})`
    throw new Error(detail)
  }
  return data as T
}

export async function fetchSampleDataset(kind: SampleKind): Promise<SamplePayload> {
  const resp = await fetch(`${API_BASE}/api/samples/${kind}`)
  return handleJson<SamplePayload>(resp)
}

export function uploadAndParseDemos(
  files: FileList | File[],
  options?: {
    mode?: AnalysisMode
    target_team_id?: string
    focus_steamid?: string | null
    llm?: Partial<LlmSettings>
    onUploadProgress?: (pct: number) => void
  }
): Promise<SamplePayload> {
  return new Promise((resolve, reject) => {
    const form = new FormData()
    Array.from(files).forEach((f) => form.append("files", f))

    if (options?.mode) form.append("mode", options.mode)
    if (options?.target_team_id) form.append("target_team_id", options.target_team_id)
    if (options?.focus_steamid) form.append("focus_steamid", options.focus_steamid)
    if (options?.llm?.provider) form.append("provider", options.llm.provider)
    if (options?.llm?.api_key) form.append("api_key", options.llm.api_key)
    if (options?.llm?.base_url) form.append("base_url", options.llm.base_url)
    if (options?.llm?.model) form.append("model", options.llm.model)
    if (options?.llm?.reasoning_effort) {
      form.append("reasoning_effort", options.llm.reasoning_effort)
    }

    const xhr = new XMLHttpRequest()
    xhr.open("POST", `${API_BASE}/api/parse-demos`)

    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable && options?.onUploadProgress) {
        const pct = Math.round((ev.loaded / ev.total) * 100)
        options.onUploadProgress(pct)
      }
    }

    xhr.onload = () => {
      let body: unknown = {}
      try {
        body = JSON.parse(xhr.responseText || "{}")
      } catch {
        body = {}
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as SamplePayload)
      } else {
        const detail =
          (body as { detail?: string })?.detail || `上传解析失败 (${xhr.status})`
        reject(new Error(detail))
      }
    }

    xhr.onerror = () => {
      reject(new Error("网络请求失败，请确认后端 FastAPI 服务 (8765端口) 正在运行"))
    }

    xhr.send(form)
  })
}

export async function runTacticalAnalysis(params: {
  data: MatchDataset
  mode: AnalysisMode
  target_team_id: string
  focus_steamid: string | null
  session_uid?: string | null
  /** false = 仅用内置规则引擎（内置示例），不调用模型服务 */
  use_llm?: boolean
  /** true = 忽略已存报告，强制重新调用模型 */
  force?: boolean
  llm?: Partial<LlmSettings>
}): Promise<AnalysisResponse> {
  const resp = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      data: params.data,
      mode: params.mode,
      target_team_id: params.target_team_id,
      focus_steamid: params.focus_steamid,
      session_uid: params.session_uid || null,
      use_llm: params.use_llm ?? true,
      force: params.force ?? false,
      provider: params.llm?.provider || null,
      api_key: params.llm?.api_key || null,
      base_url: params.llm?.base_url || null,
      model: params.llm?.model || null,
      reasoning_effort: params.llm?.reasoning_effort || "low",
    }),
  })
  return handleJson<AnalysisResponse>(resp)
}

export async function fetchDbStatus(): Promise<DbStatusResponse> {
  const resp = await fetch(`${API_BASE}/api/db/status`)
  return handleJson<DbStatusResponse>(resp)
}

export async function saveMysqlConfig(cfg: MysqlConfigInput): Promise<DbStatusResponse> {
  const resp = await fetch(`${API_BASE}/api/db/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cfg),
  })
  return handleJson<DbStatusResponse>(resp)
}

export async function saveBackendLlmConfig(llm: LlmSettings): Promise<void> {
  const resp = await fetch(`${API_BASE}/api/llm/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      provider: llm.provider,
      base_url: llm.base_url,
      model: llm.model,
      api_key: llm.api_key,
      reasoning_effort: llm.reasoning_effort || "low",
    }),
  })
  await handleJson<{ status: string }>(resp)
}

export async function testLlmService(llm: LlmSettings): Promise<LlmTestResponse> {
  const resp = await fetch(`${API_BASE}/api/llm/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      provider: llm.provider,
      base_url: llm.base_url,
      model: llm.model,
      api_key: llm.api_key,
      reasoning_effort: llm.reasoning_effort || "low",
    }),
  })
  return handleJson<LlmTestResponse>(resp)
}

export async function fetchDemoSessions(): Promise<SessionsListResponse> {
  const resp = await fetch(`${API_BASE}/api/sessions`)
  return handleJson<SessionsListResponse>(resp)
}

export async function fetchDemoSessionDetail(
  sessionUid: string
): Promise<SessionDetailPayload> {
  const resp = await fetch(`${API_BASE}/api/sessions/${encodeURIComponent(sessionUid)}`)
  return handleJson<SessionDetailPayload>(resp)
}

export async function deleteDemoSession(sessionUid: string): Promise<void> {
  const resp = await fetch(
    `${API_BASE}/api/sessions/${encodeURIComponent(sessionUid)}`,
    { method: "DELETE" }
  )
  await handleJson<{ deleted: boolean }>(resp)
}
