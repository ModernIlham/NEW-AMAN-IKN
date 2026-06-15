import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  HardDrive, Upload, Download, X, Loader2, CheckCircle2,
  AlertTriangle, ChevronDown, ChevronUp, Clock,
} from "lucide-react";
import axios from "axios";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * BackgroundTaskBar - Non-intrusive floating progress widget.
 * Polls /api/backup/active for running/completed backup/restore jobs.
 * Shows at bottom-right of screen, minimizable, auto-downloads completed backups.
 */
export default function BackgroundTaskBar({ isAdmin }) {
  const [job, setJob] = useState(null);
  const [minimized, setMinimized] = useState(false);
  const [dismissed, setDismissed] = useState(new Set());
  const [downloaded, setDownloaded] = useState(new Set());
  const [downloading, setDownloading] = useState(false);
  const pollRef = useRef(null);
  const autoDownloadRef = useRef(new Set());

  const getToken = () => localStorage.getItem("token");
  // Once we see a 401 we stop polling until the token changes. This prevents
  // the console from being spammed with `/api/backup/active 401` errors while
  // on pages like the activity list (which the user reported seeing on prod).
  const authFailedRef = useRef(false);

  /**
   * Trigger a native browser download via a hidden <a>. This bypasses the
   * axios/blob roundtrip (which could silently fail for large backup zips on
   * deployed environments because the whole file had to fit in JS memory and
   * the ingress proxy was ending the stream before axios finished buffering).
   * The token is sent as a query-param because plain anchor navigation can't
   * attach an Authorization header — the backend endpoint now accepts both.
   */
  const triggerNativeDownload = useCallback((jobId, filename) => {
    const token = getToken();
    if (!token) {
      toast.error("Sesi berakhir. Silakan login ulang.");
      return false;
    }
    try {
      const url = `${API}/backup/download/${jobId}?token=${encodeURIComponent(token)}`;
      const a = document.createElement("a");
      a.href = url;
      a.download = filename || `backup_${jobId}.zip`;
      a.rel = "noopener";
      a.style.display = "none";
      document.body.appendChild(a);
      a.click();
      // Give the browser a moment before removing the element
      setTimeout(() => a.remove(), 500);
      return true;
    } catch (e) {
      console.error("[backup] native download failed", e);
      return false;
    }
  }, []);

  const pollProgress = useCallback(async () => {
    if (!isAdmin) return;
    const token = getToken();
    if (!token) return; // no credentials yet — don't even fire the request
    if (authFailedRef.current) return;
    try {
      const r = await axios.get(`${API}/backup/active`, {
        headers: { Authorization: `Bearer ${token}` },
        timeout: 10000,
      });
      const data = r.data;
      if (data.status === "idle" || dismissed.has(data.job_id)) {
        setJob(null);
        return;
      }
      setJob(data);

      // Auto-download completed backup using native browser download
      // (guaranteed to work for large files, no memory ceiling).
      if (data.type === "backup" && data.status === "completed" && !autoDownloadRef.current.has(data.job_id)) {
        autoDownloadRef.current.add(data.job_id);
        const ok = triggerNativeDownload(data.job_id, data.filename);
        if (ok) {
          setDownloaded(prev => new Set([...prev, data.job_id]));
          toast.success("Backup siap — file sedang diunduh otomatis.");
        }
      }
    } catch (err) {
      // Silent fail on poll — but if auth is bad, stop polling to avoid
      // console spam and wasted network.
      if (err?.response?.status === 401 || err?.response?.status === 403) {
        authFailedRef.current = true;
      }
    }
  }, [isAdmin, dismissed, triggerNativeDownload]);

  // Reset the auth-failed flag whenever the stored token changes so a fresh
  // login resumes polling automatically.
  useEffect(() => {
    const onStorage = (e) => {
      if (e.key === "token") {
        authFailedRef.current = false;
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  // Polling interval: fast when running, slow otherwise
  useEffect(() => {
    if (!isAdmin) return;
    pollProgress();
    const interval = job?.status === "running" || job?.status === "queued" ? 1500 : 5000;
    pollRef.current = setInterval(pollProgress, interval);
    return () => clearInterval(pollRef.current);
  }, [isAdmin, pollProgress, job?.status]);

  const handleDismiss = async () => {
    if (!job?.job_id) return;
    setDismissed(prev => new Set([...prev, job.job_id]));
    setJob(null);
    try {
      await axios.post(`${API}/backup/dismiss/${job.job_id}`, {}, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
    } catch { /* silent */ }
  };

  const handleManualDownload = async () => {
    if (!job?.job_id || job.type !== "backup") return;
    if (downloading) return;
    setDownloading(true);
    try {
      // Probe the file with a tiny ranged GET so we can surface a clear
      // message if it has already been cleaned up (after 1h) or if auth is
      // stale. Without this the button appeared to do nothing when the file
      // had expired on the server — user reported the button being
      // unresponsive.
      try {
        await axios.get(`${API}/backup/download/${job.job_id}`, {
          headers: {
            Authorization: `Bearer ${getToken()}`,
            Range: "bytes=0-0",
          },
          responseType: "blob",
          timeout: 15000,
        });
      } catch (err) {
        const status = err?.response?.status;
        if (status === 404) {
          toast.error("File backup sudah kedaluwarsa. Silakan buat backup baru.");
          return;
        }
        if (status === 401 || status === 403) {
          toast.error("Sesi berakhir atau bukan admin. Silakan login ulang.");
          return;
        }
        // Any other probe error — don't block, fall through to actual download.
      }

      const ok = triggerNativeDownload(job.job_id, job.filename);
      if (ok) {
        setDownloaded(prev => new Set([...prev, job.job_id]));
        toast.success("Mengunduh backup…");
      } else {
        toast.error("Gagal memulai unduhan. Coba lagi.");
      }
    } finally {
      // Release the button after a short delay so the user sees feedback
      setTimeout(() => setDownloading(false), 1000);
    }
  };

  if (!isAdmin || !job) return null;

  const isRunning = job.status === "running" || job.status === "queued";
  const isCompleted = job.status === "completed";
  const isFailed = job.status === "failed";
  const isBackup = job.type === "backup";
  const isRestore = job.type === "restore";

  // Color schemes
  const colors = isCompleted
    ? "border-emerald-500/40 bg-emerald-950/95 shadow-emerald-900/30"
    : isFailed
    ? "border-red-500/40 bg-red-950/95 shadow-red-900/30"
    : "border-blue-500/40 bg-[#0f1729]/95 shadow-blue-900/30";

  const iconColor = isCompleted ? "text-emerald-400" : isFailed ? "text-red-400" : "text-blue-400";
  const progressBarColor = isCompleted ? "bg-emerald-500" : isFailed ? "bg-red-500" : "bg-blue-500";
  const Icon = isBackup ? HardDrive : Upload;

  if (minimized) {
    return (
      <div
        className={`fixed bottom-4 right-4 z-[90] flex items-center gap-2 px-3 py-2 rounded-full border ${colors} backdrop-blur-md cursor-pointer transition-all hover:scale-105`}
        onClick={() => setMinimized(false)}
        data-testid="bg-task-minimized"
      >
        {isRunning && <Loader2 className={`w-4 h-4 animate-spin ${iconColor}`} />}
        {isCompleted && <CheckCircle2 className={`w-4 h-4 ${iconColor}`} />}
        {isFailed && <AlertTriangle className={`w-4 h-4 ${iconColor}`} />}
        <span className="text-xs text-white font-medium">
          {isBackup ? "Backup" : "Restore"} {job.progress || 0}%
        </span>
        <ChevronUp className="w-3 h-3 text-gray-400" />
      </div>
    );
  }

  return (
    <div
      className={`fixed bottom-4 right-4 z-[90] w-80 rounded-xl border ${colors} backdrop-blur-md shadow-xl transition-all`}
      data-testid="bg-task-bar"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-white/5">
        <div className="flex items-center gap-2">
          <Icon className={`w-4 h-4 ${iconColor}`} />
          <span className="text-sm font-semibold text-white">
            {isBackup ? "Backup Sistem" : "Restore Data"}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setMinimized(true)}
            className="w-6 h-6 flex items-center justify-center rounded hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
            data-testid="bg-task-minimize"
          >
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
          {!isRunning && (
            <button
              onClick={handleDismiss}
              className="w-6 h-6 flex items-center justify-center rounded hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
              data-testid="bg-task-dismiss"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="px-3 py-3 space-y-2.5">
        {/* Progress bar */}
        <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ease-out ${progressBarColor} ${isRunning ? "animate-pulse" : ""}`}
            style={{ width: `${job.progress || 0}%` }}
          />
        </div>

        {/* Status text */}
        <div className="flex items-center justify-between">
          <p className="text-xs text-gray-300 truncate flex-1 mr-2">
            {job.message || "Memproses..."}
          </p>
          <span className={`text-xs font-bold tabular-nums ${iconColor}`}>
            {job.progress || 0}%
          </span>
        </div>

        {/* Completed: stats + download */}
        {isCompleted && isBackup && (
          <div className="space-y-2">
            {job.stats && (
              <div className="grid grid-cols-3 gap-1">
                {Object.entries(job.stats).slice(0, 6).map(([k, v]) => (
                  <div key={k} className="text-center px-1 py-1 rounded bg-white/5">
                    <div className="text-[10px] text-gray-500 truncate">{k}</div>
                    <div className="text-xs text-white font-mono">{v}</div>
                  </div>
                ))}
              </div>
            )}
            {job.file_size && (
              <p className="text-[10px] text-gray-500 text-center">
                Ukuran: {(job.file_size / 1024 / 1024).toFixed(2)} MB
              </p>
            )}
            <button
              onClick={handleManualDownload}
              disabled={downloading}
              className="w-full flex items-center justify-center gap-1.5 text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-800 disabled:cursor-not-allowed rounded-lg py-1.5 transition-colors"
              data-testid="bg-task-download"
            >
              {downloading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Download className="w-3.5 h-3.5" />
              )}
              {downloading
                ? "Mengunduh…"
                : (downloaded.has(job.job_id) ? "Download Ulang" : "Download Backup")}
            </button>
          </div>
        )}

        {/* Completed: restore stats */}
        {isCompleted && isRestore && (
          <div className="space-y-2">
            {job.restore_stats && (
              <div className="grid grid-cols-3 gap-1">
                {Object.entries(job.restore_stats).slice(0, 6).map(([k, v]) => (
                  <div key={k} className="text-center px-1 py-1 rounded bg-white/5">
                    <div className="text-[10px] text-gray-500 truncate">{k}</div>
                    <div className="text-xs text-white font-mono">{v}</div>
                  </div>
                ))}
              </div>
            )}
            {job.backup_metadata?.created_at && (
              <p className="text-[10px] text-gray-500 text-center">
                Sumber: {new Date(job.backup_metadata.created_at).toLocaleString("id-ID")} oleh {job.backup_metadata.created_by}
              </p>
            )}
          </div>
        )}

        {/* Failed */}
        {isFailed && job.error && (
          <div className="bg-red-900/30 border border-red-800/30 rounded-lg px-2 py-1.5">
            <p className="text-[10px] text-red-300 break-words">{job.error}</p>
          </div>
        )}

        {/* Timer for running jobs */}
        {isRunning && job.started_at && (
          <div className="flex items-center gap-1 text-[10px] text-gray-500">
            <Clock className="w-3 h-3" />
            <span>Dimulai: {new Date(job.started_at).toLocaleTimeString("id-ID")}</span>
          </div>
        )}
      </div>
    </div>
  );
}
