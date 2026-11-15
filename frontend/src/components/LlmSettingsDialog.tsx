import { Activity, CheckCircle2, KeyRound, Loader2 } from "lucide-react"
import { useEffect, useState } from "react"
import { testLlmService } from "@/api/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { UvBeamButton, UvSectionIndex } from "@/components/ui/uiverse-primitives"
import { cn } from "@/lib/utils"
import type { LlmProvider, LlmSettings, ReasoningEffort } from "@/types/tactical"

interface ProviderMeta {
  id: LlmProvider
  label: string
  sub: string
  baseUrl: string
  model: string
  modelOptions: string[]
  keyPlaceholder: string
  keyHint: string
}

/** 各厂商预设（Model ID 均可手动修改为控制台中可用的任意模型） */
export const PROVIDERS: ProviderMeta[] = [
  {
    id: "deepseek",
    label: "DeepSeek",
    sub: "官方",
    baseUrl: "https://api.deepseek.com",
    model: "deepseek-flash",
    modelOptions: ["deepseek-flash", "deepseek-chat", "deepseek-reasoner"],
    keyPlaceholder: "sk-...",
    keyHint: "DeepSeek 官方 Key 以 sk- 开头",
  },
  {
    id: "openai",
    label: "OpenAI",
    sub: "GPT",
    baseUrl: "https://api.openai.com/v1",
    model: "gpt-6.1-sol",
    modelOptions: ["gpt-6.1-sol", "gpt-6-astra", "gpt-6.1-terra", "gpt-6-luna", "o4-mini"],
    keyPlaceholder: "sk-proj-...",
    keyHint: "OpenAI Key 以 sk- 开头（项目 Key 为 sk-proj-）",
  },
  {
    id: "anthropic",
    label: "Anthropic",
    sub: "Claude",
    baseUrl: "https://api.anthropic.com",
    model: "claude-sonnet-5-5",
    modelOptions: ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5", "claude-fable-5-2"],
    keyPlaceholder: "sk-ant-...",
    keyHint: "Anthropic Key 以 sk-ant- 开头，走 Messages API (/v1/messages)",
  },
  {
    id: "custom",
    label: "OpenAI 兼容",
    sub: "自定义",
    baseUrl: "http://127.0.0.1:11434/v1",
    model: "qwen2.5:14b",
    modelOptions: [],
    keyPlaceholder: "可留空（本地/内网无鉴权服务）",
    keyHint: "火山方舟 / 阿里百炼 / 硅基流动 / Ollama / vLLM / 内网网关等",
  },
]

const CUSTOM_PRESETS: { label: string; url: string }[] = [
  { label: "本地 Ollama", url: "http://127.0.0.1:11434/v1" },
  { label: "火山方舟", url: "https://ark.cn-beijing.volces.com/api/v3" },
  { label: "阿里百炼", url: "https://dashscope.aliyuncs.com/compatible-mode/v1" },
  { label: "硅基流动", url: "https://api.siliconflow.cn/v1" },
]

interface LlmSettingsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  settings: LlmSettings
  onSave: (next: LlmSettings) => void
  onClear: () => void
}

export function LlmSettingsDialog({
  open,
  onOpenChange,
  settings,
  onSave,
  onClear,
}: LlmSettingsDialogProps) {
  const [provider, setProvider] = useState<LlmProvider>(settings.provider || "deepseek")
  const [baseUrl, setBaseUrl] = useState(settings.base_url)
  const [model, setModel] = useState(settings.model)
  const [apiKey, setApiKey] = useState(settings.api_key)
  const [effort, setEffort] = useState<ReasoningEffort>(settings.reasoning_effort || "low")
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => {
    if (open) {
      setProvider(settings.provider || "deepseek")
      setBaseUrl(settings.base_url || "https://api.deepseek.com")
      setModel(settings.model || "deepseek-flash")
      setApiKey(settings.api_key || "")
      setEffort(settings.reasoning_effort || "low")
      setTestResult(null)
    }
  }, [open, settings])

  const meta = PROVIDERS.find((p) => p.id === provider) || PROVIDERS[0]

  const switchProvider = (next: LlmProvider) => {
    if (next === provider) return
    const nextMeta = PROVIDERS.find((p) => p.id === next) || PROVIDERS[0]
    setProvider(next)
    setBaseUrl(nextMeta.baseUrl)
    setModel(nextMeta.model)
    // 切换厂商时清空 Key，避免把 A 厂商的 Key 发到 B 厂商
    setApiKey(next === settings.provider ? settings.api_key : "")
    setTestResult(null)
  }

  const buildCurrentSettings = (): LlmSettings => ({
    provider,
    base_url: baseUrl.trim() || meta.baseUrl,
    model: model.trim() || meta.model,
    api_key: apiKey.trim(),
    reasoning_effort: effort,
  })

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await testLlmService(buildCurrentSettings())
      setTestResult({
        ok: true,
        text: `连通成功 (${res.latency_ms}ms) · 已真实请求 ${res.endpoint} (${res.model}) · 回复: "${res.reply}"`,
      })
    } catch (err) {
      setTestResult({
        ok: false,
        text: err instanceof Error ? err.message : "模型连通性测试失败",
      })
    } finally {
      setTesting(false)
    }
  }

  const handleSave = () => {
    onSave(buildCurrentSettings())
    onOpenChange(false)
  }

  const handleClear = () => {
    onClear()
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border-slate-800 bg-[#0b1018] sm:max-w-[560px]">
        <DialogHeader>
          <UvSectionIndex code="ENGINE" label="LLM INFERENCE CONFIG" />
          <DialogTitle className="mt-1 flex items-center gap-2 text-slate-50">
            <KeyRound className="h-4 w-4 text-cyan-400" />
            配置 AI 战术推理模型
          </DialogTitle>
          <DialogDescription className="text-slate-400">
            支持 DeepSeek、OpenAI、Anthropic Claude 官方接口，以及任意 OpenAI 兼容服务。保存后同步写入服务端{" "}
            <code className="text-amber-300">.env</code>。内置示例始终使用规则引擎，不会调用模型。
          </DialogDescription>
        </DialogHeader>

        {/* 厂商分段切换 */}
        <div className="grid grid-cols-4 gap-1.5">
          {PROVIDERS.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => switchProvider(p.id)}
              className={cn(
                "flex flex-col items-center rounded border px-2 py-1.5 text-[11px] transition-colors",
                provider === p.id
                  ? "border-cyan-400/70 bg-cyan-500/15 text-cyan-100 shadow-[0_0_14px_-4px_rgba(0,212,255,0.45)]"
                  : "border-slate-700 bg-slate-900 text-slate-300 hover:border-slate-500"
              )}
            >
              <span className="font-semibold">{p.label}</span>
              <span className="font-mono text-[10px] text-slate-400">{p.sub}</span>
            </button>
          ))}
        </div>

        {provider === "custom" && (
          <div className="flex flex-wrap gap-1.5">
            {CUSTOM_PRESETS.map((cp) => (
              <button
                key={cp.label}
                type="button"
                onClick={() => setBaseUrl(cp.url)}
                className="rounded border border-slate-700 bg-slate-900 px-2 py-0.5 text-[10.5px] text-slate-300 hover:border-slate-500"
              >
                {cp.label}
              </button>
            ))}
          </div>
        )}

        <div className="space-y-3 py-1">
          <div className="space-y-1.5">
            <Label htmlFor="cfgBaseUrl">API Base URL</Label>
            <Input
              id="cfgBaseUrl"
              placeholder={meta.baseUrl}
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="cfgModel">Model ID</Label>
              <Input
                id="cfgModel"
                list="cfgModelOptions"
                placeholder={meta.model}
                value={model}
                onChange={(e) => setModel(e.target.value)}
              />
              <datalist id="cfgModelOptions">
                {meta.modelOptions.map((m) => (
                  <option key={m} value={m} />
                ))}
              </datalist>
            </div>

            <div className="space-y-1.5">
              <Label>思考 / 推理强度</Label>
              <Select
                value={effort}
                onValueChange={(v) => setEffort(v as ReasoningEffort)}
                disabled={provider === "anthropic" || provider === "custom"}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">低 (low · 推荐)</SelectItem>
                  <SelectItem value="high">高 (high)</SelectItem>
                  <SelectItem value="none">关闭 (none)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="cfgKey">API Key</Label>
            <Input
              id="cfgKey"
              type="password"
              placeholder={meta.keyPlaceholder}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
            <p className="font-mono text-[10.5px] text-slate-500">{meta.keyHint}</p>
          </div>
        </div>

        {testResult && (
          <div
            className={
              testResult.ok
                ? "flex items-start gap-2 rounded border border-emerald-500/40 bg-emerald-500/12 px-3 py-2 text-xs text-emerald-200"
                : "rounded border border-rose-500/40 bg-rose-500/15 px-3 py-2 text-xs text-rose-200"
            }
          >
            {testResult.ok && <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />}
            <span className="break-words font-mono text-[11px]">{testResult.text}</span>
          </div>
        )}

        <DialogFooter className="flex-wrap gap-2 sm:justify-between">
          <Button
            type="button"
            variant="outline"
            disabled={testing}
            onClick={handleTest}
            className="border-cyan-500/40 bg-cyan-500/10 text-xs text-cyan-200 hover:bg-cyan-500/20"
          >
            {testing ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Activity className="h-3.5 w-3.5 text-cyan-300" />
            )}
            实测调用模型服务
          </Button>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={handleClear}
              className="border-slate-700 bg-slate-900/70 text-xs"
            >
              恢复规则引擎
            </Button>
            <UvBeamButton tone="cyan" onClick={handleSave}>
              保存模型配置
            </UvBeamButton>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
