import {
  FileArchive,
  FileCheck2,
  FolderOpen,
  Loader2,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react"
import { useRef, useState, type DragEvent } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Progress } from "@/components/ui/progress"
import { ScrollArea } from "@/components/ui/scroll-area"
import { UvBeamButton, UvSectionIndex } from "@/components/ui/uiverse-primitives"
import { cn } from "@/lib/utils"

interface ImportDemoDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onUploadFiles: (
    files: File[],
    onProgress?: (pct: number) => void
  ) => Promise<void>
}

const VALID_EXT_REGEX = /\.(dem|zip|gz|bz2)$/i

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function ImportDemoDialog({
  open,
  onOpenChange,
  onUploadFiles,
}: ImportDemoDialogProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [files, setFiles] = useState<File[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [uploadPct, setUploadPct] = useState<number>(0)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const appendValidFiles = (incoming: FileList | File[]) => {
    const arr = Array.from(incoming)
    if (arr.length === 0) return

    const invalid = arr.filter((f) => !VALID_EXT_REGEX.test(f.name))
    const valid = arr.filter((f) => VALID_EXT_REGEX.test(f.name))

    if (invalid.length > 0) {
      setErrorMsg(
        `已忽略不支持的文件：${invalid.map((f) => f.name).join("、")}（仅支持 .dem / .zip / .gz / .bz2）`
      )
    } else {
      setErrorMsg(null)
    }

    if (valid.length > 0) {
      setFiles((prev) => {
        const map = new Map(
          prev.map((f) => [`${f.name}-${f.size}-${f.lastModified}`, f])
        )
        for (const vf of valid) {
          map.set(`${vf.name}-${vf.size}-${vf.lastModified}`, vf)
        }
        return Array.from(map.values())
      })
    }
  }

  const handleDragEnter = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    if (!loading) setIsDragging(true)
  }

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    if (!loading && !isDragging) setIsDragging(true)
  }

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.currentTarget.contains(e.relatedTarget as Node)) return
    setIsDragging(false)
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
    if (loading) return
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      appendValidFiles(e.dataTransfer.files)
    }
  }

  const handleRemoveFile = (targetIndex: number) => {
    setFiles((prev) => prev.filter((_, idx) => idx !== targetIndex))
  }

  const handleSubmit = async () => {
    if (files.length === 0) {
      setErrorMsg("请先拖拽或点击选择至少一个 .dem / .zip 录像文件")
      return
    }
    setLoading(true)
    setUploadPct(0)
    setErrorMsg(null)
    try {
      await onUploadFiles(files, (pct) => setUploadPct(pct))
      setFiles([])
      onOpenChange(false)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "上传解析失败")
    } finally {
      setLoading(false)
      setUploadPct(0)
    }
  }

  const totalSize = files.reduce((acc, f) => acc + f.size, 0)

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!loading) onOpenChange(next)
      }}
    >
      <DialogContent className="border-slate-800 bg-[#0b1018] sm:max-w-[560px]">
        <DialogHeader>
          <UvSectionIndex code="UPLOAD" label="DEMO TELEMETRY INGESTION" />
          <DialogTitle className="mt-1 flex items-center gap-2 text-slate-50">
            上传完美世界对战平台 CS2 Demo 录像
          </DialogTitle>
          <DialogDescription className="text-slate-400">
            支持拖拽或选择 1～N 个同地图{" "}
            <code className="text-cyan-300">.dem</code>、
            <code className="text-cyan-300">.zip</code>、
            <code className="text-cyan-300">.dem.gz</code>、
            <code className="text-cyan-300">.dem.bz2</code> 文件。上传多场录像将自动按{" "}
            <code className="text-amber-300">SteamID</code> 聚合选手打法习惯。
          </DialogDescription>
        </DialogHeader>

        {/* 隐藏的原生文件选择器 */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".dem,.zip,.gz,.bz2"
          className="hidden"
          onChange={(e) => {
            if (e.target.files) {
              appendValidFiles(e.target.files)
            }
            // 清空 value 以便重复选择同名文件也能触发
            e.target.value = ""
          }}
        />

        {/* Uiverse HUD 拖拽上传与点击选择区 */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => !loading && fileInputRef.current?.click()}
          onKeyDown={(e) => {
            if ((e.key === "Enter" || e.key === " ") && !loading) {
              e.preventDefault()
              fileInputRef.current?.click()
            }
          }}
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={cn(
            "group relative flex cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed px-6 py-7 text-center transition-all",
            isDragging
              ? "border-cyan-400 bg-cyan-500/12 shadow-[0_0_28px_-6px_rgba(0,212,255,0.45)]"
              : "border-slate-700/80 bg-slate-950/65 hover:border-cyan-400/60 hover:bg-slate-900/70",
            loading && "pointer-events-none opacity-60"
          )}
        >
          <div
            className={cn(
              "mb-3 flex h-12 w-12 items-center justify-center rounded-lg border transition-transform duration-200",
              isDragging
                ? "scale-110 border-cyan-400 bg-cyan-500/20 text-cyan-300"
                : "border-slate-700 bg-slate-900 text-cyan-400 group-hover:-translate-y-0.5 group-hover:border-cyan-400/50"
            )}
          >
            <UploadCloud className="h-6 w-6" />
          </div>

          <p className="text-sm font-semibold text-slate-100">
            {isDragging ? "松开鼠标立即添加录像文件" : "将 .dem / .zip 录像文件拖拽到此处"}
          </p>
          <p className="mt-1 text-xs text-slate-400">
            支持一次框选多个文件，或分多次拖入叠加
          </p>

          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={loading}
            onClick={(e) => {
              e.stopPropagation()
              fileInputRef.current?.click()
            }}
            className="mt-3.5 border-cyan-500/40 bg-cyan-500/10 text-xs text-cyan-200 hover:bg-cyan-500/20"
          >
            <FolderOpen className="h-3.5 w-3.5 text-cyan-300" />
            选择指定文件
          </Button>
        </div>

        {/* 已选待上传文件队列 */}
        {files.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-mono text-[11px] text-slate-300">
                已选择 <strong className="text-cyan-300">{files.length}</strong> 个文件 · 共{" "}
                <strong className="tabular-nums text-slate-100">
                  {formatBytes(totalSize)}
                </strong>
              </span>
              <button
                type="button"
                disabled={loading}
                onClick={() => setFiles([])}
                className="inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-rose-400 disabled:opacity-50"
              >
                <Trash2 className="h-3 w-3" />
                清空列表
              </button>
            </div>

            <ScrollArea className="max-h-[156px] rounded border border-slate-800/90 bg-slate-950/80">
              <div className="divide-y divide-slate-800/70">
                {files.map((file, idx) => {
                  const isArchive = /\.(zip|gz|bz2)$/i.test(file.name)
                  return (
                    <div
                      key={`${file.name}-${file.size}-${file.lastModified}`}
                      className="flex items-center justify-between gap-3 px-3 py-2 text-xs"
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        {isArchive ? (
                          <FileArchive className="h-4 w-4 shrink-0 text-amber-400" />
                        ) : (
                          <FileCheck2 className="h-4 w-4 shrink-0 text-cyan-400" />
                        )}
                        <span className="truncate font-medium text-slate-200">
                          {file.name}
                        </span>
                      </div>

                      <div className="flex shrink-0 items-center gap-2.5">
                        <span className="font-mono text-[11px] tabular-nums text-slate-400">
                          {formatBytes(file.size)}
                        </span>
                        <button
                          type="button"
                          disabled={loading}
                          onClick={() => handleRemoveFile(idx)}
                          className="rounded p-0.5 text-slate-500 hover:bg-slate-800 hover:text-rose-400 disabled:opacity-40"
                          title="移除此文件"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            </ScrollArea>
          </div>
        )}

        {/* 上传与解析实时进度条 */}
        {loading && (
          <div className="space-y-1.5 rounded border border-cyan-500/30 bg-cyan-500/10 p-3 text-xs">
            <div className="flex items-center justify-between font-mono text-[11px]">
              <span className="flex items-center gap-1.5 text-cyan-200">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan-400" />
                {uploadPct < 100
                  ? "正在传输录像文件至本地解析引擎..."
                  : "传输完成，Rust demoparser2 正在提取 64-Tick 空间特征..."}
              </span>
              <strong className="tabular-nums text-cyan-300">{uploadPct}%</strong>
            </div>
            <Progress
              value={uploadPct}
              className="h-1.5 bg-slate-900"
              indicatorClassName="bg-[#00d4ff]"
            />
          </div>
        )}

        {errorMsg && (
          <div className="rounded border border-rose-500/40 bg-rose-500/15 px-3 py-2 text-xs text-rose-200">
            {errorMsg}
          </div>
        )}

        <DialogFooter className="gap-2 sm:gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={loading}
            onClick={() => onOpenChange(false)}
            className="border-slate-700 bg-slate-900/70 text-xs"
          >
            取消
          </Button>
          <UvBeamButton
            tone="cyan"
            disabled={loading || files.length === 0}
            onClick={handleSubmit}
          >
            {loading ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan-300" />
                上传并解析中...
              </>
            ) : (
              <>
                <UploadCloud className="h-3.5 w-3.5 text-cyan-300" />
                开始上传并解析 {files.length > 0 ? `(${files.length})` : ""}
              </>
            )}
          </UvBeamButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
