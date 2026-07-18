import React, { useState, useEffect, useRef } from "react";
import {
  X, AlertTriangle, ShieldAlert, RotateCcw, Loader2, Upload, HardDrive,
  Shield, CheckCircle2, Database, FileText,
} from "lucide-react";
import { toast } from "sonner";
import axios from "axios";
import { getApiError } from "@/lib/utils";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Dialog RESTORE & RESET dipindah dari ActivitySelectionPage ke komponen
// bersama (#407): satu rumah untuk siklus data (Pengaturan > Sistem) —
// tidak ada lagi pintu ganda yang membingungkan alur.

// ============================================================================
// RESET ALL DIALOG - Hidden dangerous feature for admin only
// ============================================================================
export function ResetAllDialog({ open, onClose, userId, onSuccess }) {
  const [confirmText, setConfirmText] = useState('');
  const [resetting, setResetting] = useState(false);
  const [step, setStep] = useState(1);
  const inputRef = useRef(null);
  const dialogRef = useRef(null);
  const openerRef = useRef(null);

  const CONFIRM_WORD = "HAPUS SEMUA";
  const isConfirmed = confirmText === CONFIRM_WORD;

  useEffect(() => {
    if (open) {
      setConfirmText('');
      setStep(1);
      setResetting(false);
    }
  }, [open]);

  // Focus management: on open capture the opener + focus the first focusable
  // inside the dialog; on close restore focus to the opener.
  useEffect(() => {
    if (open) {
      openerRef.current = document.activeElement;
      const t = setTimeout(() => {
        const el = dialogRef.current?.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
        el?.focus();
      }, 50);
      return () => clearTimeout(t);
    }
    try { openerRef.current?.focus?.(); } catch { /* opener gone */ }
    openerRef.current = null;
  }, [open]);

  useEffect(() => {
    if (step === 2 && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [step]);

  const handleReset = async () => {
    if (!isConfirmed || resetting) return;
    setResetting(true);
    try {
      const r = await axios.delete(`${API}/system/reset-all`, {
        data: { admin_id: userId, confirmation: CONFIRM_WORD }
      });
      toast.success("Sistem berhasil direset. Semua data telah dihapus.");
      onClose();
      if (onSuccess) onSuccess(r.data);
    } catch (err) {
      toast.error(getApiError(err, "Gagal mereset sistem"));
    } finally {
      setResetting(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') onClose();
    if (e.key === 'Enter' && isConfirmed && !resetting) handleReset();
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center" onKeyDown={handleKeyDown}>
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={onClose} />
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-label="Reset seluruh sistem" className="relative w-full max-w-md mx-4 bg-[#1a1a2e] border border-red-900/50 rounded-xl shadow-2xl shadow-red-900/20 overflow-hidden">
        <div className="h-1 bg-gradient-to-r from-red-600 via-red-500 to-red-600" />
        {step === 1 ? (
          <div className="p-6">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center">
                  <ShieldAlert className="w-5 h-5 text-red-400" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white">Zona Berbahaya</h2>
                  <p className="text-xs text-red-400">Tindakan Tidak Dapat Dibatalkan</p>
                </div>
              </div>
              <button onClick={onClose} className="text-gray-500 hover:text-gray-300 transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="bg-red-950/40 border border-red-900/30 rounded-lg p-4 mb-4">
              <div className="flex gap-3">
                <AlertTriangle className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-gray-300 space-y-2">
                  <p className="font-semibold text-red-300">Anda akan menghapus SELURUH data dalam sistem!</p>
                  <p>Tindakan ini akan menghapus secara permanen:</p>
                  <ul className="list-disc list-inside text-red-300/80 space-y-1 ml-1">
                    <li>Semua <b>kegiatan inventarisasi</b></li>
                    <li>Semua <b>data aset</b> beserta foto & dokumen</li>
                    <li>Semua <b>kategori aset</b></li>
                    <li>Semua <b>log audit</b></li>
                  </ul>
                  <p className="text-yellow-400/90 font-medium mt-2">
                    Data yang dihapus TIDAK DAPAT dipulihkan kembali.
                  </p>
                </div>
              </div>
            </div>
            <div className="flex gap-3">
              <button onClick={() => setStep(2)} className="flex-1 flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700 text-white font-medium py-2.5 px-4 rounded-lg transition-colors">
                <AlertTriangle className="w-4 h-4" />Saya Mengerti, Lanjutkan
              </button>
              <button onClick={onClose} className="flex items-center justify-center gap-1 bg-gray-700 hover:bg-gray-600 text-gray-300 font-medium py-2.5 px-4 rounded-lg transition-colors">
                Batal<span className="text-[10px] bg-gray-600 rounded px-1.5 py-0.5 ml-1">Esc</span>
              </button>
            </div>
          </div>
        ) : (
          <div className="p-6">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center animate-pulse">
                  <RotateCcw className="w-5 h-5 text-red-400" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white">Reset Seluruh Sistem</h2>
                  <p className="text-xs text-red-400">Konfirmasi Akhir</p>
                </div>
              </div>
              <button onClick={onClose} className="text-gray-500 hover:text-gray-300 transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-sm text-gray-400 mb-4">
              Menghapus seluruh data akan membuat sistem kembali bersih seperti baru. Tindakan ini bersifat permanen dan tidak dapat dibatalkan.
            </p>
            <p className="text-sm text-gray-300 mb-2">
              Ketik <span className="font-mono font-bold bg-red-900/40 text-red-300 px-2 py-0.5 rounded border border-red-800/50 select-all">{CONFIRM_WORD}</span> untuk konfirmasi.
            </p>
            <input
              ref={inputRef}
              type="text"
              value={confirmText}
              onChange={e => setConfirmText(e.target.value)}
              className="w-full bg-[#0d0d1a] border border-gray-700 focus:border-red-500 focus:ring-1 focus:ring-red-500/30 rounded-lg px-4 py-3 text-white placeholder-gray-600 text-sm outline-none transition-colors mb-4"
              autoComplete="off"
              spellCheck="false"
            />
            <div className="flex gap-3">
              <button
                onClick={handleReset}
                disabled={!isConfirmed || resetting}
                className={`flex-1 flex items-center justify-center gap-2 font-medium py-2.5 px-4 rounded-lg transition-all ${
                  isConfirmed && !resetting ? 'bg-red-600 hover:bg-red-700 text-white cursor-pointer' : 'bg-red-900/30 text-red-800 cursor-not-allowed'
                }`}
              >
                {resetting ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
                {resetting ? 'Mereset...' : 'Reset Semua Data'}
              </button>
              <button onClick={onClose} disabled={resetting} className="flex items-center justify-center gap-1 bg-gray-700 hover:bg-gray-600 text-gray-300 font-medium py-2.5 px-4 rounded-lg transition-colors">
                Batal<span className="text-[10px] bg-gray-600 rounded px-1.5 py-0.5 ml-1">Esc</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// RESTORE DIALOG - Upload backup and start background restore
// ============================================================================
export function RestoreDialog({ open, onClose, token, onSuccess }) {
  const [step, setStep] = useState(1);
  const [file, setFile] = useState(null);
  const [confirmText, setConfirmText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef(null);
  const fileRef = useRef(null);
  const dialogRef = useRef(null);
  const openerRef = useRef(null);

  const CONFIRM_WORD = "PULIHKAN DATA";
  const isConfirmed = confirmText === CONFIRM_WORD;

  useEffect(() => {
    if (open) {
      setStep(1); setFile(null); setConfirmText(''); setSubmitting(false);
    }
  }, [open]);

  // Focus management: capture opener + autofocus first focusable on open,
  // restore focus to the opener on close.
  useEffect(() => {
    if (open) {
      openerRef.current = document.activeElement;
      const t = setTimeout(() => {
        const el = dialogRef.current?.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
        el?.focus();
      }, 50);
      return () => clearTimeout(t);
    }
    try { openerRef.current?.focus?.(); } catch { /* opener gone */ }
    openerRef.current = null;
  }, [open]);

  useEffect(() => {
    if (step === 2 && inputRef.current) setTimeout(() => inputRef.current?.focus(), 100);
  }, [step]);

  const handleKeyDown = (e) => {
    if (e.key === 'Escape' && !submitting) onClose();
  };

  const handleFileSelect = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!f.name.endsWith('.zip')) { toast.error("File harus berformat .zip"); return; }
    setFile(f);
  };

  const handleRestore = async () => {
    if (!isConfirmed || !file || submitting) return;
    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      await axios.post(`${API}/backup/restore/start`, formData, {
        headers: { 'Content-Type': 'multipart/form-data', 'Authorization': `Bearer ${token}` },
        timeout: 120000,
      });
      toast.success("Proses restore dimulai di background. Anda bisa melanjutkan aktivitas.");
      onClose();
      if (onSuccess) onSuccess();
    } catch (err) {
      toast.error(getApiError(err, "Gagal memulai restore"));
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center" onKeyDown={handleKeyDown}>
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={submitting ? undefined : onClose} />
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-label="Pulihkan data sistem" className="relative w-full max-w-md mx-4 bg-[#1a1a2e] border border-blue-900/50 rounded-xl shadow-2xl shadow-blue-900/20 overflow-hidden">
        <div className="h-1 bg-gradient-to-r from-blue-600 via-cyan-500 to-blue-600" />

        {step === 1 && (
          <div className="p-6">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center">
                  <Upload className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white">Pulihkan Data Sistem</h2>
                  <p className="text-xs text-blue-400">Upload file backup (.zip)</p>
                </div>
              </div>
              <button onClick={onClose} className="text-gray-500 hover:text-gray-300 transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="bg-blue-950/40 border border-blue-900/30 rounded-lg p-4 mb-4">
              <div className="flex gap-3">
                <AlertTriangle className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-gray-300 space-y-2">
                  <p className="font-semibold text-yellow-300">Perhatian!</p>
                  <p>Proses restore akan:</p>
                  <ul className="list-disc list-inside text-blue-300/80 space-y-1 ml-1">
                    <li><b>Berjalan di background</b> — Anda tetap bisa menggunakan aplikasi</li>
                    <li><b>Membuat safety backup</b> data saat ini sebelum restore</li>
                    <li><b>Menimpa seluruh data</b> dengan data dari file backup</li>
                  </ul>
                  <p className="text-yellow-400/90 font-medium mt-2">
                    Jika restore gagal, data otomatis dikembalikan ke kondisi semula.
                  </p>
                </div>
              </div>
            </div>

            <div
              className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-all mb-4 ${file ? 'border-blue-500 bg-blue-950/30' : 'border-gray-600 hover:border-blue-500 hover:bg-blue-950/20'}`}
              onClick={() => fileRef.current?.click()}
              data-testid="restore-file-dropzone"
            >
              <input ref={fileRef} type="file" accept=".zip" className="hidden" onChange={handleFileSelect} />
              {file ? (
                <div className="flex items-center justify-center gap-3">
                  <Database className="w-6 h-6 text-blue-400" />
                  <div className="text-left">
                    <p className="text-sm text-white font-medium">{file.name}</p>
                    <p className="text-xs text-gray-400">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                  </div>
                  <button onClick={(e) => { e.stopPropagation(); setFile(null); }} className="ml-2 text-gray-500 hover:text-red-400"><X className="w-4 h-4" /></button>
                </div>
              ) : (
                <><Upload className="w-8 h-8 text-gray-500 mx-auto mb-2" /><p className="text-sm text-gray-400">Klik untuk pilih file backup (.zip)</p></>
              )}
            </div>

            <div className="flex gap-3">
              <button onClick={() => file && setStep(2)} disabled={!file} className={`flex-1 flex items-center justify-center gap-2 font-medium py-2.5 px-4 rounded-lg transition-all ${file ? 'bg-blue-600 hover:bg-blue-700 text-white cursor-pointer' : 'bg-blue-900/30 text-blue-800 cursor-not-allowed'}`} data-testid="restore-next-btn">
                <Shield className="w-4 h-4" />Lanjutkan
              </button>
              <button onClick={onClose} className="flex items-center justify-center gap-1 bg-gray-700 hover:bg-gray-600 text-gray-300 font-medium py-2.5 px-4 rounded-lg transition-colors">Batal</button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="p-6">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center">
                  <Shield className="w-5 h-5 text-amber-400" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white">Konfirmasi Restore</h2>
                  <p className="text-xs text-amber-400">Proses akan berjalan di background</p>
                </div>
              </div>
              {!submitting && (
                <button onClick={onClose} className="text-gray-500 hover:text-gray-300 transition-colors"><X className="w-5 h-5" /></button>
              )}
            </div>

            <div className="bg-amber-950/30 border border-amber-800/30 rounded-lg p-3 mb-4">
              <p className="text-xs text-gray-400">File: <span className="text-white font-medium">{file?.name}</span></p>
              <p className="text-xs text-gray-400">Ukuran: <span className="text-white font-medium">{file ? (file.size / 1024 / 1024).toFixed(2) : 0} MB</span></p>
            </div>

            <p className="text-sm text-gray-300 mb-2">
              Ketik <span className="font-mono font-bold bg-amber-900/40 text-amber-300 px-2 py-0.5 rounded border border-amber-800/50 select-all">{CONFIRM_WORD}</span> untuk konfirmasi.
            </p>
            <input
              ref={inputRef} type="text" value={confirmText}
              onChange={e => setConfirmText(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && isConfirmed && !submitting) handleRestore(); }}
              className="w-full bg-[#0d0d1a] border border-gray-700 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 rounded-lg px-4 py-3 text-white placeholder-gray-600 text-sm outline-none transition-colors mb-4"
              placeholder="Ketik di sini..." autoComplete="off" spellCheck="false" data-testid="restore-confirm-input"
            />
            <div className="flex gap-3">
              <button
                onClick={handleRestore} disabled={!isConfirmed || submitting}
                className={`flex-1 flex items-center justify-center gap-2 font-medium py-2.5 px-4 rounded-lg transition-all ${isConfirmed && !submitting ? 'bg-blue-600 hover:bg-blue-700 text-white cursor-pointer' : 'bg-blue-900/30 text-blue-800 cursor-not-allowed'}`}
                data-testid="restore-confirm-btn"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                {submitting ? 'Mengunggah...' : 'Pulihkan Data'}
              </button>
              <button onClick={onClose} disabled={submitting} className="flex items-center justify-center gap-1 bg-gray-700 hover:bg-gray-600 text-gray-300 font-medium py-2.5 px-4 rounded-lg transition-colors">Batal</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

