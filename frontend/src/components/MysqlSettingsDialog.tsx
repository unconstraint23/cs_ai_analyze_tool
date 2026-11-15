import { CheckCircle2, Database, Loader2, ShieldAlert } from "lucide-react"
import { useEffect, useState } from "react"
import { saveMysqlConfig } from "@/api/client"
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
import { UvBeamButton, UvSectionIndex } from "@/components/ui/uiverse-primitives"
import type { DbStatusResponse } from "@/types/tactical"

interface MysqlSettingsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  status: DbStatusResponse | null
  onConfigured: (nextStatus: DbStatusResponse) => void
}

export function MysqlSettingsDialog({
  open,
  onOpenChange,
  status,
  onConfigured,
}: MysqlSettingsDialogProps) {
  const [host, setHost] = useState("127.0.0.1")
  const [port, setPort] = useState("3306")
  const [user, setUser] = useState("root")
  const [password, setPassword] = useState("")
  const [database, setDatabase] = useState("cs2_tactical")
  const [saving, setSaving] = useState(false)
  const [errMsg, setErrMsg] = useState<string | null>(null)

  useEffect(() => {
    if (open && status) {
      setHost(status.host || "127.0.0.1")
      setPort(String(status.port || 3306))
      setUser(status.user || "root")
      setDatabase(status.database || "cs2_tactical")
      setPassword("")
      setErrMsg(null)
    }
  }, [open, status])

  const handleConnect = async () => {
    setSaving(true)
    setErrMsg(null)
    try {
      const next = await saveMysqlConfig({
        host: host.trim() || "127.0.0.1",
        port: Number(port) || 3306,
        user: user.trim() || "root",
        // 若密码留空且之前已存过密码则传 undefined 保留原密码；若未存过密码则传空串测试
        password: password === "" && status?.has_password ? undefined : password,
        database: database.trim() || "cs2_tactical",
      })
      onConfigured(next)
      onOpenChange(false)
    } catch (err) {
      setErrMsg(err instanceof Error ? err.message : "MySQL 连接配置失败")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border-slate-800 bg-[#0b1018] sm:max-w-[520px]">
        <DialogHeader>
          <UvSectionIndex code="STORAGE" label="MYSQL PERSISTENCE ENGINE" />
          <DialogTitle className="mt-1 flex items-center gap-2 text-slate-50">
            <Database className="h-4 w-4 text-emerald-400" />
            MySQL 数据库连接与建表配置
          </DialogTitle>
          <DialogDescription className="text-slate-400">
            连接成功后系统将自动创建数据库{" "}
            <code className="text-cyan-300">cs2_tactical</code> 及三张表（
            <code className="text-slate-300">demo_sessions</code>、
            <code className="text-slate-300">demo_session_players</code>、
            <code className="text-slate-300">analysis_reports</code>），并将配置持久化写入{" "}
            <code className="text-amber-300">.env</code>。
          </DialogDescription>
        </DialogHeader>

        {/* 当前状态指示条 */}
        {status?.connected ? (
          <div className="flex items-start gap-2.5 rounded border border-emerald-500/35 bg-emerald-500/10 p-3 text-xs text-emerald-200">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
            <div>
              <p className="font-semibold">
                MySQL 已在线连通 ({status.user}@{status.host}:{status.port}/{status.database})
              </p>
              <p className="mt-0.5 text-[11px] text-emerald-300/80">
                当前库内已持久化 {status.sessions_count} 场真实 Demo · 共 {status.reports_count} 份 AI 报告
              </p>
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-2.5 rounded border border-amber-500/40 bg-amber-500/12 p-3 text-xs text-amber-200">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
            <div className="min-w-0">
              <p className="font-semibold">检测到本机 MySQL 需要填写密码鉴权</p>
              <p className="mt-0.5 break-words font-mono text-[11px] text-amber-300/85">
                {status?.error || "请填写下方 MySQL 密码，点击保存即可自动建库并同步已上传记录"}
              </p>
            </div>
          </div>
        )}

        <div className="space-y-3 py-1">
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2 space-y-1.5">
              <Label htmlFor="mysqlHost">MySQL Host</Label>
              <Input
                id="mysqlHost"
                value={host}
                onChange={(e) => setHost(e.target.value)}
                placeholder="127.0.0.1"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="mysqlPort">Port</Label>
              <Input
                id="mysqlPort"
                value={port}
                onChange={(e) => setPort(e.target.value)}
                placeholder="3306"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="mysqlUser">用户名 (User)</Label>
              <Input
                id="mysqlUser"
                value={user}
                onChange={(e) => setUser(e.target.value)}
                placeholder="root"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="mysqlDb">数据库名 (自动创建)</Label>
              <Input
                id="mysqlDb"
                value={database}
                onChange={(e) => setDatabase(e.target.value)}
                placeholder="cs2_tactical"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="mysqlPwd">
              MySQL 密码 (Password)
              {status?.has_password && (
                <span className="ml-1.5 text-[11px] text-emerald-400">
                  (已在 .env 保存密码，留空保持不变)
                </span>
              )}
            </Label>
            <Input
              id="mysqlPwd"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="输入本机 MySQL 密码..."
            />
          </div>
        </div>

        {errMsg && (
          <div className="rounded border border-rose-500/40 bg-rose-500/15 px-3 py-2 text-xs text-rose-200">
            {errMsg}
          </div>
        )}

        <DialogFooter className="gap-2 sm:gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="border-slate-700 bg-slate-900/70 text-xs"
          >
            关闭
          </Button>
          <UvBeamButton tone="cyan" disabled={saving} onClick={handleConnect}>
            {saving ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan-300" />
                正在连接并建表...
              </>
            ) : (
              <>
                <Database className="h-3.5 w-3.5 text-cyan-300" />
                连接 MySQL 并自动建库建表
              </>
            )}
          </UvBeamButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
