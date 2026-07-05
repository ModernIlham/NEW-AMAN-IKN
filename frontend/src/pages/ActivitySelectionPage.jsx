import React, { useState, useEffect, useRef, useCallback, lazy, Suspense } from "react";
import {
  Package, FileText,
  Plus, Trash2, Edit3, X, Camera, Settings, LogOut,
  ChevronRight, ChevronLeft, Loader2,
  Users, FileUp, BookOpen,
  CreditCard, Briefcase, FolderOpen, UserIcon,
  AlertTriangle, ShieldAlert, RotateCcw, Building2, Eye, Download,
  HardDrive, Upload, Shield, CheckCircle2, Database,
  Clock, PlayCircle, XCircle, Image as ImageIcon,
  ShieldCheck, Lock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import axios from "axios";
import { getApiError } from "@/lib/utils";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import { authMediaUrl } from "@/lib/mediaUrl";
import { compressImageFile } from "@/lib/imageCompression";
import { compressPdfFile } from "@/lib/pdfCompression";
import { useConfirm } from "@/components/ui/ConfirmDialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Lazy: dialog pengesahan hanya dimuat saat dibuka (pola dialog lazy lain)
const PengesahanDialog = lazy(() => import("@/components/assets/PengesahanDialog"));

// ============================================================================
// RESET ALL DIALOG - Hidden dangerous feature for admin only
// ============================================================================
function ResetAllDialog({ open, onClose, userId, onSuccess }) {
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
function RestoreDialog({ open, onClose, token, onSuccess }) {
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

// ============================================================================
// ACTIVITY SELECTION PAGE - First page after login
// ============================================================================
// Photo Lightbox - fetches full photos from single activity endpoint
function ActivityPhotoLightbox({ activityId, initialIndex = 0, onClose }) {
  const [photos, setPhotos] = useState([]);
  const [idx, setIdx] = useState(initialIndex);
  const [loading, setLoading] = useState(true);
  const API_URL = process.env.REACT_APP_BACKEND_URL;
  const closeBtnRef = useRef(null);
  const openerRef = useRef(null);

  // Focus the close button on open (this overlay is mounted/unmounted by the
  // parent), and restore focus to the opener when it unmounts.
  useEffect(() => {
    openerRef.current = document.activeElement;
    const t = setTimeout(() => closeBtnRef.current?.focus(), 0);
    return () => {
      clearTimeout(t);
      try { openerRef.current?.focus?.(); } catch { /* opener gone */ }
    };
  }, []);

  useEffect(() => {
    if (!activityId) return;
    setLoading(true);
    axios.get(`${API_URL}/api/inventory-activities/${activityId}`)
      .then(r => {
        const p = r.data?.photos || r.data?.photo_thumbnails || [];
        setPhotos(p);
        setIdx(Math.min(initialIndex, p.length - 1));
      })
      .catch(() => setPhotos([]))
      .finally(() => setLoading(false));
  }, [activityId, API_URL, initialIndex]);

  useEffect(() => {
    const handler = (e) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") setIdx(i => (i - 1 + photos.length) % photos.length);
      if (e.key === "ArrowRight") setIdx(i => (i + 1) % photos.length);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [photos.length, onClose]);

  if (!activityId) return null;

  return (
    <div role="dialog" aria-modal="true" aria-label="Pratinjau foto kegiatan" className="fixed inset-0 z-[100] bg-black/90 backdrop-blur-md flex items-center justify-center" onClick={onClose}>
      <button ref={closeBtnRef} aria-label="Tutup pratinjau foto" className="absolute top-4 right-4 z-10 w-9 h-9 rounded-full bg-white/10 hover:bg-white/25 text-white flex items-center justify-center" onClick={onClose}>
        <X className="w-5 h-5" />
      </button>
      <div className="relative flex items-center justify-center w-full max-w-4xl px-4" onClick={e => e.stopPropagation()}>
        {loading ? (
          <Loader2 className="w-10 h-10 text-white animate-spin" />
        ) : photos.length > 0 ? (
          <>
            <img src={photos[idx]} alt={`Foto ${idx + 1}`} className="max-h-[80vh] max-w-full object-contain rounded-lg shadow-2xl" />
            {photos.length > 1 && (
              <>
                <button className="absolute left-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-white/15 hover:bg-white/30 text-white flex items-center justify-center" onClick={() => setIdx(i => (i - 1 + photos.length) % photos.length)}>
                  <ChevronLeft className="w-6 h-6" />
                </button>
                <button className="absolute right-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-white/15 hover:bg-white/30 text-white flex items-center justify-center" onClick={() => setIdx(i => (i + 1) % photos.length)}>
                  <ChevronRight className="w-6 h-6" />
                </button>
                <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-black/50 text-white text-sm px-3 py-1 rounded-full">{idx + 1} / {photos.length}</div>
              </>
            )}
          </>
        ) : (
          <div className="text-white/50">Tidak ada foto</div>
        )}
      </div>
    </div>
  );
}

export default function ActivitySelectionPage({ user, onLogout, onSelectActivity, onShowInfo }) {
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editingActivity, setEditingActivity] = useState(null);
  const [showResetAll, setShowResetAll] = useState(false);
  const [showRestore, setShowRestore] = useState(false);
  const [backupLoading, setBackupLoading] = useState(false);
  // Lazy-load state: photos/documents aren't fetched until user clicks
  // the "Kelola" buttons inside the edit form. Tracks counts separately.
  const [photoCount, setPhotoCount] = useState(0);
  const [docCount, setDocCount] = useState(0);
  const [photosLoaded, setPhotosLoaded] = useState(false);
  const [docsLoaded, setDocsLoaded] = useState(false);
  const [loadingPhotos, setLoadingPhotos] = useState(false);
  const [loadingDocs, setLoadingDocs] = useState(false);
  // Status ribbon click → validation dialog
  const [completionDialog, setCompletionDialog] = useState(null); // { activity, data, loading }
  // Cached per-activity date-derived status (populated after first list load)
  const [statusCache, setStatusCache] = useState({}); // { [activityId]: {phase, status} }
  // Dialog pengesahan (finalisasi) kegiatan
  const [pengesahanActivity, setPengesahanActivity] = useState(null);

  const canManageActivities = user?.role === "admin" || user?.role === "operator";
  const isAdmin = user?.role === "admin";
  const { confirm, confirmDialog } = useConfirm();
  const [form, setForm] = useState({
    nomor_surat: '', nama_kegiatan: '', deskripsi: '',
    tanggal_mulai: '', tanggal_selesai: '',
    penanggung_jawab: '', penanggung_jawab_jabatan: '', penanggung_jawab_nip: '',
    photos: [], documents: [],
    tim_inti: [], tim_pembantu: [],
    tim_peneliti: [], tim_pendukung: [], kasatker_nama: '', kasatker_nip: '', kasatker_jabatan: '',
    alamat_satker: '', nomor_berita_acara: '', tanggal_berita_acara: '', kesimpulan: '',
    kode_satker: '', nama_satker: '', eselon1: [],
  });
  const [saving, setSaving] = useState(false);
  // Distinguishes a failed fetch (show retry) from a genuinely empty list.
  const [fetchError, setFetchError] = useState(null);
  // Inline required-field errors for the create/edit activity dialog.
  const [formErrors, setFormErrors] = useState({});
  const [satkerList, setSatkerList] = useState([]);
  const [selectedSatker, setSelectedSatker] = useState('all');
  const [photoLightbox, setPhotoLightbox] = useState(null); // { activityId, index }
  const satkerLookupTimer = useRef(null);

  const emptyForm = {
    nomor_surat: '', nama_kegiatan: '', deskripsi: '',
    tanggal_mulai: '', tanggal_selesai: '',
    penanggung_jawab: '', penanggung_jawab_jabatan: '', penanggung_jawab_nip: '',
    photos: [], documents: [],
    tim_inti: [], tim_pembantu: [],
    tim_peneliti: [], tim_pendukung: [], kasatker_nama: '', kasatker_nip: '', kasatker_jabatan: '',
    alamat_satker: '', nomor_berita_acara: '', tanggal_berita_acara: '', kesimpulan: '',
    kode_satker: '', nama_satker: '', eselon1: [],
  };

  const fetchActivities = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/inventory-activities`);
      setActivities(r.data);
      setFetchError(null);
    } catch (err) {
      console.error('Fetch activities error:', err);
      // Keep an error state so the UI shows a retry card instead of the
      // "no activities" empty state (which would falsely read as "you have none").
      setFetchError(getApiError(err, "Gagal memuat daftar kegiatan"));
    }
    setLoading(false);
  };

  const fetchSatkerList = async () => {
    try {
      const r = await axios.get(`${API}/satker-list`);
      setSatkerList(r.data || []);
    } catch { /* silent */ }
  };

  useEffect(() => { fetchActivities(); fetchSatkerList(); }, []);

  // Backup handler - start background backup job
  const handleBackup = async () => {
    setBackupLoading(true);
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${API}/backup/start`, {}, {
        headers: { Authorization: `Bearer ${token}` },
        timeout: 30000,
      });
      toast.success("Proses backup dimulai di background. Progress terlihat di panel bawah kanan.");
    } catch (err) {
      toast.error(getApiError(err, "Gagal memulai backup"));
    } finally {
      setBackupLoading(false);
    }
  };

  // Auto-fill satker: when kode_satker changes, lookup nama_satker + eselon1
  const handleKodeSatkerChange = useCallback((value) => {
    setForm(p => ({ ...p, kode_satker: value }));
    clearTimeout(satkerLookupTimer.current);
    if (value.trim().length >= 2) {
      satkerLookupTimer.current = setTimeout(async () => {
        try {
          const r = await axios.get(`${API}/satker-lookup`, { params: { kode: value.trim() } });
          if (r.data?.nama_satker) {
            setForm(p => ({ ...p, nama_satker: r.data.nama_satker, eselon1: r.data.eselon1 || [] }));
          }
        } catch { /* silent */ }
      }, 400);
    }
  }, []);

  // Auto-fill satker: when nama_satker changes, lookup kode_satker + eselon1
  const handleNamaSatkerChange = useCallback((value) => {
    setForm(p => ({ ...p, nama_satker: value }));
    clearTimeout(satkerLookupTimer.current);
    if (value.trim().length >= 3) {
      satkerLookupTimer.current = setTimeout(async () => {
        try {
          const r = await axios.get(`${API}/satker-lookup`, { params: { nama: value.trim() } });
          if (r.data?.kode_satker) {
            setForm(p => ({ ...p, kode_satker: r.data.kode_satker, eselon1: r.data.eselon1 || [] }));
          }
        } catch { /* silent */ }
      }, 400);
    }
  }, []);

  // Filter activities by selected satker
  const filteredActivities = selectedSatker === 'all'
    ? activities
    : activities.filter(a => a.kode_satker === selectedSatker);

  const handlePhotoUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    for (const file of files) {
      if (file.size > 15 * 1024 * 1024) { toast.error("Maks 15MB"); continue; }
      try {
        const compressed = await compressImageFile(file);
        setForm(p => ({ ...p, photos: [...(p.photos || []), compressed].slice(0, 10) }));
      } catch (err) {
        toast.error(`Gagal memproses ${file.name}: ${err.message || err}`);
      }
    }
  };

  const handleDocUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    for (const file of files) {
      // Allow up to 25MB raw; backend compression brings it down significantly.
      if (file.size > 25 * 1024 * 1024) {
        toast.error(`${file.name} terlalu besar (maks 25MB)`);
        continue;
      }
      const tId = toast.loading(`Mengompres ${file.name}...`);
      try {
        const { dataUrl, originalBytes, compressedBytes, method, savingsPercent, error } =
          await compressPdfFile(file);
        if (error) {
          toast.warning(`${file.name}: kompresi gagal, file asli digunakan`, { id: tId });
        } else if (savingsPercent > 0) {
          toast.success(
            `${file.name}: ${(originalBytes / 1024 / 1024).toFixed(1)}MB → ${(compressedBytes / 1024 / 1024).toFixed(1)}MB (-${savingsPercent}% via ${method})`,
            { id: tId }
          );
        } else {
          toast.success(`${file.name}: berhasil diunggah`, { id: tId });
        }
        setForm((p) => ({
          ...p,
          documents: [...(p.documents || []), { name: file.name, data: dataUrl }].slice(0, 5),
        }));
      } catch (err) {
        toast.error(`Gagal memproses ${file.name}: ${err.message || err}`, { id: tId });
      }
    }
  };

  // Required-field validation shared by create & edit. Returns { field: msg }.
  const validateActivityForm = () => {
    const errs = {};
    if (!form.nomor_surat.trim()) errs.nomor_surat = "Nomor surat wajib diisi";
    if (!form.nama_kegiatan.trim()) errs.nama_kegiatan = "Nama kegiatan wajib diisi";
    if (!form.kode_satker.trim()) errs.kode_satker = "Kode Satker wajib diisi";
    if (!form.nama_satker.trim()) errs.nama_satker = "Nama Satker wajib diisi";
    return errs;
  };

  const clearFormError = (name) => setFormErrors(prev => {
    if (!prev[name]) return prev;
    const next = { ...prev };
    delete next[name];
    return next;
  });

  // Scroll + focus the first missing field (top-to-bottom order) after render.
  const focusFirstActivityError = (errs) => {
    const first = ["nomor_surat", "nama_kegiatan", "kode_satker", "nama_satker"].find(f => errs[f]);
    if (!first) return;
    setTimeout(() => {
      const el = document.querySelector(`[name="activity-${first}"]`);
      if (el) { el.scrollIntoView({ behavior: "smooth", block: "center" }); try { el.focus({ preventScroll: true }); } catch { /* noop */ } }
    }, 50);
  };

  const handleCreate = async () => {
    const errs = validateActivityForm();
    if (Object.keys(errs).length > 0) {
      setFormErrors(errs);
      toast.error(`Lengkapi ${Object.keys(errs).length} field wajib`);
      focusFirstActivityError(errs);
      return;
    }
    setFormErrors({});
    setSaving(true);
    try {
      const payload = { ...form, asset_ids: [] };
      const r = await axios.post(`${API}/inventory-activities`, payload);
      toast.success("Kegiatan inventarisasi berhasil dibuat");
      fetchActivities();
      fetchSatkerList();
      setShowCreate(false);
      setForm({...emptyForm});
      if (r.data?.id) onSelectActivity(r.data);
    } catch (err) { toast.error(getApiError(err, "Gagal membuat kegiatan")); }
    finally { setSaving(false); }
  };

  const handleEdit = (e, act) => {
    e.stopPropagation();
    setEditingActivity(act);
    // IMPORTANT: do NOT populate photos/documents eagerly. The list endpoint
    // doesn't include them (only counts) so even if we tried we'd wipe DB data
    // on save. Initialize with null sentinel = "not loaded yet"; the lazy
    // buttons fetch them on demand. handleUpdate omits them if still null.
    setPhotoCount(act.photos_count || 0);
    setDocCount(act.documents_count || 0);
    setPhotosLoaded(false);
    setDocsLoaded(false);
    setForm({
      nomor_surat: act.nomor_surat || '', nama_kegiatan: act.nama_kegiatan || '',
      deskripsi: act.deskripsi || '', tanggal_mulai: act.tanggal_mulai || '',
      tanggal_selesai: act.tanggal_selesai || '',
      penanggung_jawab: act.penanggung_jawab || '',
      penanggung_jawab_jabatan: act.penanggung_jawab_jabatan || '',
      penanggung_jawab_nip: act.penanggung_jawab_nip || '',
      photos: null, documents: null,
      tim_inti: act.tim_inti || [], tim_pembantu: act.tim_pembantu || [],
      tim_peneliti: act.tim_peneliti || [], tim_pendukung: act.tim_pendukung || [], kasatker_nama: act.kasatker_nama || '',
      kasatker_nip: act.kasatker_nip || '', kasatker_jabatan: act.kasatker_jabatan || '',
      alamat_satker: act.alamat_satker || '', nomor_berita_acara: act.nomor_berita_acara || '',
      tanggal_berita_acara: act.tanggal_berita_acara || '', kesimpulan: act.kesimpulan || '',
      kode_satker: act.kode_satker || '', nama_satker: act.nama_satker || '',
      eselon1: act.eselon1 || [],
    });
    setFormErrors({});
    setShowCreate(true);
  };

  // Lazy-load photos when user clicks "Kelola Foto"
  const loadActivityPhotos = async () => {
    if (photosLoaded || loadingPhotos || !editingActivity) return;
    setLoadingPhotos(true);
    try {
      const r = await axios.get(`${API}/inventory-activities/${editingActivity.id}`);
      setForm(p => ({ ...p, photos: r.data?.photos || [] }));
      setPhotosLoaded(true);
    } catch (err) {
      toast.error(getApiError(err, "Gagal memuat foto kegiatan"));
    } finally {
      setLoadingPhotos(false);
    }
  };

  // Lazy-load documents when user clicks "Kelola Dokumen"
  const loadActivityDocs = async () => {
    if (docsLoaded || loadingDocs || !editingActivity) return;
    setLoadingDocs(true);
    try {
      const r = await axios.get(`${API}/inventory-activities/${editingActivity.id}`);
      setForm(p => ({ ...p, documents: r.data?.documents || [] }));
      setDocsLoaded(true);
    } catch (err) {
      toast.error(getApiError(err, "Gagal memuat dokumen kegiatan"));
    } finally {
      setLoadingDocs(false);
    }
  };

  const handleUpdate = async () => {
    const errs = validateActivityForm();
    if (Object.keys(errs).length > 0) {
      setFormErrors(errs);
      toast.error(`Lengkapi ${Object.keys(errs).length} field wajib`);
      focusFirstActivityError(errs);
      return;
    }
    setFormErrors({});
    setSaving(true);
    try {
      // Build payload: omit photos/documents when the user never opened them
      // (null sentinel). Sending null tells backend "keep existing DB values".
      const payload = { ...form, asset_ids: editingActivity.asset_ids || [] };
      if (!photosLoaded && form.photos === null) payload.photos = null;
      if (!docsLoaded && form.documents === null) payload.documents = null;
      await axios.put(`${API}/inventory-activities/${editingActivity.id}`, payload);
      toast.success("Kegiatan berhasil diperbarui");
      fetchActivities();
      fetchSatkerList();
      setShowCreate(false);
      setEditingActivity(null);
      setForm({...emptyForm});
      setPhotosLoaded(false); setDocsLoaded(false);
      setPhotoCount(0); setDocCount(0);
    } catch (err) { toast.error(getApiError(err, "Gagal memperbarui kegiatan")); }
    finally { setSaving(false); }
  };

  const handleDelete = async (e, act) => {
    e.stopPropagation();
    const id = typeof act === "object" ? act?.id : act;
    const name = typeof act === "object" ? (act?.nama_kegiatan || "").trim() : "";
    const ok = await confirm({
      title: "Hapus Kegiatan",
      description: `Kegiatan${name ? ` "${name}"` : ""} beserta SELURUH aset di dalamnya akan dihapus permanen. Tindakan ini tidak dapat dibatalkan.`,
      confirmLabel: "Hapus Kegiatan",
      variant: "danger",
      requireText: "HAPUS",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/inventory-activities/${id}`);
      toast.success("Kegiatan dihapus");
      fetchActivities();
    } catch { toast.error("Gagal hapus"); }
  };

  // Open PDF: prefer GridFS streaming endpoint; fallback to inline base64 (legacy).
  // We fetch as blob via axios (which carries the JWT from the global interceptor)
  // because the streaming endpoint is auth-protected — `window.open(url)` on the
  // raw URL would issue a fresh request WITHOUT Authorization and 401.
  const openPdfDoc = async (doc, activityId, idx) => {
    try {
      // GridFS-backed: fetch via axios (auth-aware) then open the blob URL
      if (doc && typeof doc === "object" && doc.gridfs_id && activityId != null && idx != null) {
        const tId = toast.loading("Memuat PDF...");
        try {
          const res = await axios.get(
            `${API}/inventory-activities/${activityId}/documents/${idx}`,
            { responseType: "blob", timeout: 60000 }
          );
          const blob = new Blob([res.data], { type: "application/pdf" });
          const url = URL.createObjectURL(blob);
          toast.dismiss(tId);
          const newWindow = window.open(url, "_blank");
          if (!newWindow) {
            const a = document.createElement("a");
            a.href = url;
            a.download = doc.name || "document.pdf";
            a.click();
          }
          setTimeout(() => URL.revokeObjectURL(url), 60000);
        } catch (err) {
          toast.dismiss(tId);
          const status = err?.response?.status;
          if (status === 401 || status === 403) {
            toast.error("Sesi habis. Silakan login ulang untuk melihat PDF.");
          } else if (err?.code === "ECONNABORTED") {
            toast.error("Waktu muat PDF habis. Coba lagi atau cek koneksi.");
          } else {
            toast.error(`Gagal memuat PDF${status ? ` (HTTP ${status})` : ""}`);
          }
        }
        return;
      }
      // Legacy inline base64
      const docData = typeof doc === "string" ? doc : doc?.data;
      if (!docData || typeof docData !== "string") { toast.error("Data PDF tidak valid"); return; }
      let dataUrl = docData;
      if (!docData.startsWith("data:")) dataUrl = `data:application/pdf;base64,${docData}`;
      const base64Match = dataUrl.match(/base64,(.+)/);
      if (!base64Match) { toast.error("Format PDF tidak valid"); return; }
      const binaryString = atob(base64Match[1]);
      const len = binaryString.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) bytes[i] = binaryString.charCodeAt(i);
      const blob = new Blob([bytes], { type: "application/pdf" });
      const url = URL.createObjectURL(blob);
      const newWindow = window.open(url, "_blank");
      if (!newWindow) {
        const a = document.createElement("a");
        a.href = url;
        a.download = (typeof doc === "object" && doc?.name) || "document.pdf";
        a.click();
      }
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      console.error("Error opening PDF:", err);
      toast.error("Gagal membuka PDF.");
    }
  };

  const handleCloseDialog = () => {
    setShowCreate(false);
    setEditingActivity(null);
    setForm({...emptyForm});
    setFormErrors({});
    setPhotosLoaded(false); setDocsLoaded(false);
    setPhotoCount(0); setDocCount(0);
  };

  // Compute date-based status phase for a kegiatan card.
  // 'belum_dimulai' (gray) → 'berlangsung' (blue) → 'selesai_tanggal' (amber, needs validation)
  const computeDatePhase = (act) => {
    const today = new Date().toISOString().slice(0, 10);
    const mulai = (act.tanggal_mulai || "").trim();
    const selesai = (act.tanggal_selesai || "").trim();
    if (!mulai || today < mulai) return "belum_dimulai";
    if (selesai && today > selesai) return "selesai_tanggal";
    return "berlangsung";
  };

  // Open completion-status dialog and call /completion-status endpoint
  const handleStatusRibbonClick = async (e, act) => {
    e.stopPropagation();
    setCompletionDialog({ activity: act, data: null, loading: true });
    try {
      const r = await axios.get(`${API}/inventory-activities/${act.id}/completion-status`);
      setCompletionDialog({ activity: act, data: r.data, loading: false });
      // Persist computed status into local cache so badge updates without
      // full list refetch
      setStatusCache(prev => ({ ...prev, [act.id]: r.data }));
    } catch (err) {
      toast.error(getApiError(err, "Gagal memvalidasi status kegiatan"));
      setCompletionDialog(null);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="bg-card border-b border-border px-4 py-3 sticky top-0 z-40 backdrop-blur-sm bg-card/95">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Klik logo = buka halaman Info/PRD aplikasi */}
            <div
              className={`w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-blue-500 flex items-center justify-center shadow-elev-1 ${onShowInfo ? "cursor-pointer" : ""}`}
              {...(onShowInfo ? {
                role: "button", tabIndex: 0, onClick: onShowInfo,
                onKeyDown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onShowInfo(); } },
                "aria-label": "Info aplikasi", title: "Info aplikasi",
              } : {})}
              data-testid="activity-page-logo"
            >
              <BookOpen className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-foreground font-['Manrope']">AMAN</h1>
              <p className="text-xs text-muted-foreground">Pilih Kegiatan Inventarisasi</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground hidden sm:block">{user?.name || user?.username}</span>
            <Button variant="outline" size="sm" onClick={onLogout} className="gap-1">
              <LogOut className="w-4 h-4" /><span className="hidden sm:inline">Keluar</span>
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto p-4 sm:p-6">
        {canManageActivities && (
          <Button
            onClick={() => { setEditingActivity(null); setForm({...emptyForm}); setFormErrors({}); setShowCreate(true); }}
            className="w-full mb-6 h-14 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-700 hover:to-blue-600 text-white text-lg font-semibold rounded-xl shadow-elev-2 hover:shadow-elev-3 transition-all duration-180 active:scale-[0.98]"
          >
            <Plus className="w-6 h-6 mr-2" />Buat Kegiatan Inventarisasi Baru
          </Button>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
          </div>
        ) : fetchError ? (
          /* Fetch gagal (jaringan/server) — bukan berarti belum ada kegiatan */
          <div className="text-center py-20 bg-card rounded-2xl border border-red-200 dark:border-red-800" data-testid="activities-fetch-error">
            <AlertTriangle className="w-16 h-16 mx-auto mb-4 text-red-400" />
            <h3 className="text-lg font-semibold text-foreground/80 mb-2">Gagal Memuat Kegiatan</h3>
            <p className="text-muted-foreground mb-4 px-4 break-words">{fetchError}</p>
            <Button variant="outline" onClick={fetchActivities} className="gap-1.5" data-testid="activities-retry-btn">
              <RotateCcw className="w-4 h-4" />Coba Lagi
            </Button>
          </div>
        ) : activities.length === 0 ? (
          <div className="text-center py-20 bg-card rounded-2xl border border-border">
            <FolderOpen className="w-16 h-16 mx-auto mb-4 text-muted-foreground" />
            <h3 className="text-lg font-semibold text-foreground/80 mb-2">Belum Ada Kegiatan</h3>
            <p className="text-muted-foreground mb-4">Buat kegiatan inventarisasi baru untuk memulai</p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Satker Filter + Report Buttons */}
            {satkerList.length > 0 && (
              <div className="flex items-center gap-3 flex-wrap" data-testid="satker-tabs">
                <Building2 className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                <select
                  value={selectedSatker}
                  onChange={e => setSelectedSatker(e.target.value)}
                  className="flex-1 max-w-xs h-9 px-3 rounded-lg border border-border bg-card text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 cursor-pointer"
                  data-testid="satker-filter-select"
                >
                  <option value="all">Semua Satker ({activities.length} kegiatan)</option>
                  {satkerList.map(s => (
                    <option key={s.kode_satker} value={s.kode_satker}>
                      {s.kode_satker} - {s.nama_satker} ({s.count} kegiatan)
                    </option>
                  ))}
                </select>
                {selectedSatker !== 'all' && (
                  <div className="flex items-center gap-1.5">
                    <Button
                      variant="outline" size="sm"
                      className="h-8 text-xs gap-1.5"
                      onClick={() => {
                        const act = filteredActivities[0];
                        if (act) window.open(authMediaUrl(`${process.env.REACT_APP_BACKEND_URL}/api/inventory-activities/${act.id}/laporan-satker-html`), '_blank');
                      }}
                      data-testid="btn-preview-laporan-satker"
                    >
                      <Eye className="w-3.5 h-3.5" />Preview Laporan
                    </Button>
                    <Button
                      variant="outline" size="sm"
                      className="h-8 text-xs gap-1.5"
                      onClick={async () => {
                        const act = filteredActivities[0];
                        if (!act) return;
                        try {
                          await downloadFileWithProgress(
                            `${API}/inventory-activities/${act.id}/laporan-satker-pdf`,
                            `Laporan_${selectedSatker}.pdf`,
                            { label: "Laporan Satker" }
                          );
                        } catch { /* toast error sudah ditangani helper */ }
                      }}
                      data-testid="btn-download-laporan-satker"
                    >
                      <Download className="w-3.5 h-3.5" />PDF
                    </Button>
                  </div>
                )}
              </div>
            )}

            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
              Daftar Kegiatan ({filteredActivities.length})
            </h2>
            {filteredActivities.length === 0 ? (
              <div className="text-center py-10 bg-card rounded-xl border border-border">
                <FolderOpen className="w-10 h-10 mx-auto mb-2 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">Tidak ada kegiatan untuk satker ini</p>
              </div>
            ) : filteredActivities.map(act => {
              const cached = statusCache[act.id];
              const datePhase = computeDatePhase(act);
              const isDisahkan = act.status_pengesahan === "disahkan";
              const computedStatus = isDisahkan ? "disahkan" : (cached?.computed_status || datePhase);
              const ribbonStyle = (
                computedStatus === "disahkan"
                  ? "bg-emerald-600 text-white"
                  : computedStatus === "selesai"
                  ? "bg-emerald-500 text-white"
                  : computedStatus === "belum_lengkap"
                  ? "bg-amber-500 text-white"
                  : computedStatus === "selesai_tanggal"
                  ? "bg-amber-500 text-white"
                  : computedStatus === "berlangsung"
                  ? "bg-blue-500 text-white"
                  : "bg-slate-400 text-white"
              );
              const ribbonIcon = (
                computedStatus === "disahkan"
                  ? <Lock className="w-3 h-3" />
                  : computedStatus === "selesai"
                  ? <CheckCircle2 className="w-3 h-3" />
                  : computedStatus === "belum_lengkap"
                  ? <AlertTriangle className="w-3 h-3" />
                  : computedStatus === "selesai_tanggal"
                  ? <Clock className="w-3 h-3" />
                  : computedStatus === "berlangsung"
                  ? <PlayCircle className="w-3 h-3" />
                  : <Clock className="w-3 h-3" />
              );
              const ribbonText = (
                computedStatus === "disahkan"
                  ? "Disahkan"
                  : computedStatus === "selesai"
                  ? "Selesai"
                  : computedStatus === "belum_lengkap"
                  ? "Belum Lengkap"
                  : computedStatus === "selesai_tanggal"
                  ? "Validasi"
                  : computedStatus === "berlangsung"
                  ? "On Going"
                  : "Belum Dimulai"
              );
              return (
              <div
                key={act.id}
                onClick={() => onSelectActivity(act)}
                className="bg-card rounded-xl border border-border p-4 hover:border-blue-300 hover:shadow-md transition-all cursor-pointer group relative overflow-hidden"
                data-testid={`activity-card-${act.id}`}
              >
                {/* Status Ribbon - clickable to validate completion */}
                <button
                  type="button"
                  onClick={(e) => {
                    if (isDisahkan) { e.stopPropagation(); setPengesahanActivity(act); return; }
                    handleStatusRibbonClick(e, act);
                  }}
                  className={`absolute top-0 left-0 ${ribbonStyle} text-[10px] font-semibold pl-3 pr-3 py-0.5 rounded-br-lg shadow flex items-center gap-1 min-h-0 min-w-0 leading-none hover:brightness-110 transition-all z-10 cursor-pointer`}
                  title={isDisahkan ? "Kegiatan telah disahkan — klik untuk detail pengesahan" : "Klik untuk validasi status kegiatan"}
                  data-testid={`activity-status-ribbon-${act.id}`}
                >
                  {ribbonIcon}<span>{ribbonText}</span>
                </button>
                <div className="absolute top-3 right-3 flex items-center gap-1 z-10">
                  {canManageActivities && (
                    <Button variant="ghost" size="sm" className="h-7 w-7 p-0 opacity-100 transition-opacity bg-card/80 hover:bg-emerald-50 dark:hover:bg-emerald-900/30 rounded-full shadow-sm" onClick={(e) => { e.stopPropagation(); setPengesahanActivity(act); }} title={isDisahkan ? "Detail Pengesahan" : "Pengesahan Kegiatan"} data-testid={`activity-pengesahan-btn-${act.id}`}>
                      {isDisahkan ? <Lock className="w-3.5 h-3.5 text-emerald-600" /> : <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />}
                    </Button>
                  )}
                  {canManageActivities && (<>
                    <Button variant="ghost" size="sm" className="h-7 w-7 p-0 opacity-100 transition-opacity bg-card/80 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-full shadow-sm" onClick={(e) => handleEdit(e, act)} title="Edit Kegiatan">
                      <Edit3 className="w-3.5 h-3.5 text-blue-500" />
                    </Button>
                    {!isDisahkan && (
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0 opacity-100 transition-opacity bg-card/80 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-full shadow-sm" onClick={(e) => handleDelete(e, act)} title="Hapus Kegiatan">
                        <Trash2 className="w-3.5 h-3.5 text-red-500" />
                      </Button>
                    )}
                  </>)}
                  <div className="w-6 h-6 flex items-center justify-center">
                    <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-blue-600 transition-colors" />
                  </div>
                </div>
                <div className="pr-24 sm:pr-20 pt-5">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    {act.ticket_number && (
                      <span className="text-xs font-mono font-semibold bg-slate-800 text-slate-100 dark:bg-slate-200 dark:text-slate-800 px-2 py-0.5 rounded" data-testid={`activity-ticket-${act.id}`}>{act.ticket_number}</span>
                    )}
                    <span className="text-xs font-mono bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 px-2 py-0.5 rounded">{act.nomor_surat}</span>
                    {act.kode_satker && (
                      <span className="text-xs font-mono bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 px-2 py-0.5 rounded flex items-center gap-1" data-testid={`activity-satker-${act.id}`}>
                        <Building2 className="w-3 h-3" />{act.kode_satker} - {act.nama_satker}
                      </span>
                    )}
                    <span className="text-xs text-muted-foreground">{act.tanggal_mulai} - {act.tanggal_selesai || 'Ongoing'}</span>
                  </div>
                  <h3 className="font-semibold text-foreground text-lg break-words">{act.nama_kegiatan}</h3>
                  {act.deskripsi && <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{act.deskripsi}</p>}
                  <div className="flex items-center gap-3 mt-3 text-sm flex-wrap">
                    <span className="flex items-center gap-1 text-muted-foreground"><Package className="w-4 h-4 flex-shrink-0" /><b>{act.total_assets || 0}</b> aset</span>
                    <span className="flex items-center gap-1 text-blue-600"><CreditCard className="w-4 h-4 flex-shrink-0" /><span className="truncate">Rp {(act.total_value || 0).toLocaleString('id-ID')}</span></span>
                    {act.penanggung_jawab && (
                      <span className="flex items-center gap-1 text-muted-foreground"><Briefcase className="w-4 h-4 flex-shrink-0" /><span className="truncate max-w-[100px] sm:max-w-none">{act.penanggung_jawab}</span></span>
                    )}
                  </div>
                  {/* Lightweight count badges - photos & docs are NOT eagerly loaded */}
                  {(act.photos_count > 0 || act.documents_count > 0) && (
                    <div className="flex items-center gap-2 mt-3 flex-wrap">
                      {act.photos_count > 0 && (
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); setPhotoLightbox({ activityId: act.id, index: 0 }); }}
                          className="flex items-center gap-1.5 bg-blue-50 dark:bg-blue-900/30 hover:bg-blue-100 dark:hover:bg-blue-900/50 border border-blue-200 dark:border-blue-700 rounded-lg px-2.5 py-1 transition-colors"
                          data-testid={`activity-photos-badge-${act.id}`}
                        >
                          <ImageIcon className="w-3.5 h-3.5 text-blue-600 dark:text-blue-300" />
                          <span className="text-xs font-medium text-blue-700 dark:text-blue-200">{act.photos_count} Foto</span>
                        </button>
                      )}
                      {act.documents_count > 0 && (
                        <span
                          className="flex items-center gap-1.5 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700 rounded-lg px-2.5 py-1"
                          data-testid={`activity-docs-badge-${act.id}`}
                        >
                          <FileText className="w-3.5 h-3.5 text-red-600 dark:text-red-300" />
                          <span className="text-xs font-medium text-red-700 dark:text-red-200">{act.documents_count} Dokumen</span>
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
              );
            })}
          </div>
        )}

        {isAdmin && (
          <div className="mt-12 mb-4">
            {/* Backup & Restore Section */}
            <div className="flex items-center justify-center gap-2 mb-3 flex-wrap">
              <button
                onClick={handleBackup}
                disabled={backupLoading}
                className="flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-blue-600 transition-all px-3 py-1.5 rounded-md hover:bg-blue-50 dark:hover:bg-blue-900/20 border border-border hover:border-blue-300 dark:hover:border-blue-700"
                data-testid="backup-btn"
              >
                {backupLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <HardDrive className="w-3 h-3" />}
                <span>{backupLoading ? 'Membuat Backup...' : 'Backup Sistem'}</span>
              </button>
              <button
                onClick={() => setShowRestore(true)}
                className="flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-emerald-600 transition-all px-3 py-1.5 rounded-md hover:bg-emerald-50 dark:hover:bg-emerald-900/20 border border-border hover:border-emerald-300 dark:hover:border-emerald-700"
                data-testid="restore-btn"
              >
                <Upload className="w-3 h-3" />
                <span>Pulihkan Data</span>
              </button>
            </div>
            {/* System Reset */}
            <div className="flex justify-center">
              <button onClick={() => setShowResetAll(true)} className="flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-red-500 transition-all opacity-50 hover:opacity-100 px-3 py-1.5 rounded-md hover:bg-red-50 dark:hover:bg-red-900/20 border border-transparent hover:border-red-200 dark:hover:border-red-800" title="System Reset">
                <Settings className="w-3 h-3" /><span>System Reset</span>
              </button>
            </div>
          </div>
        )}
      </main>

      {isAdmin && (
        <ResetAllDialog open={showResetAll} onClose={() => setShowResetAll(false)} userId={user?.id} onSuccess={() => fetchActivities()} />
      )}
      {isAdmin && (
        <RestoreDialog
          open={showRestore}
          onClose={() => setShowRestore(false)}
          token={localStorage.getItem('token')}
          onSuccess={() => { fetchActivities(); fetchSatkerList(); }}
        />
      )}

      <Dialog open={showCreate} onOpenChange={handleCloseDialog}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto overflow-x-hidden">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {editingActivity ? <Edit3 className="w-5 h-5 text-amber-600" /> : <Plus className="w-5 h-5 text-blue-600" />}
              {editingActivity ? 'Edit Kegiatan Inventarisasi' : 'Buat Kegiatan Inventarisasi Baru'}
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Isi detail kegiatan, satuan kerja, tim inventarisasi, dan unggah foto/dokumen pendukung jika diperlukan.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 w-full min-w-0 overflow-hidden">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>Nomor Surat *</Label>
                <Input name="activity-nomor_surat" value={form.nomor_surat} onChange={e => { setForm(p => ({...p, nomor_surat: e.target.value})); clearFormError('nomor_surat'); }} placeholder="INV/001/2024" className={formErrors.nomor_surat ? "border-red-500 focus-visible:ring-red-500" : ""} aria-invalid={!!formErrors.nomor_surat} />
                {formErrors.nomor_surat && <p className="text-[11px] text-red-600 dark:text-red-400">{formErrors.nomor_surat}</p>}
              </div>
              <div className="space-y-1">
                <Label>Nama Kegiatan *</Label>
                <Input name="activity-nama_kegiatan" value={form.nama_kegiatan} onChange={e => { setForm(p => ({...p, nama_kegiatan: e.target.value})); clearFormError('nama_kegiatan'); }} placeholder="Inventarisasi Aset Q1" className={formErrors.nama_kegiatan ? "border-red-500 focus-visible:ring-red-500" : ""} aria-invalid={!!formErrors.nama_kegiatan} />
                {formErrors.nama_kegiatan && <p className="text-[11px] text-red-600 dark:text-red-400">{formErrors.nama_kegiatan}</p>}
              </div>
              <div className="space-y-1"><Label>Tanggal Mulai</Label><Input type="date" value={form.tanggal_mulai} onChange={e => setForm(p => ({...p, tanggal_mulai: e.target.value}))} /></div>
              <div className="space-y-1"><Label>Tanggal Selesai</Label><Input type="date" value={form.tanggal_selesai} onChange={e => setForm(p => ({...p, tanggal_selesai: e.target.value}))} /></div>
              <div className="space-y-1 sm:col-span-2">
                <Label>Penanggung Jawab</Label>
                <div className="grid grid-cols-3 gap-2">
                  <Input value={form.penanggung_jawab} onChange={e => setForm(p => ({...p, penanggung_jawab: e.target.value}))} placeholder="Nama lengkap" className="text-xs" />
                  <Input value={form.penanggung_jawab_jabatan} onChange={e => setForm(p => ({...p, penanggung_jawab_jabatan: e.target.value}))} placeholder="Jabatan" className="text-xs" />
                  <Input value={form.penanggung_jawab_nip} onChange={e => setForm(p => ({...p, penanggung_jawab_nip: e.target.value}))} placeholder="NIP/NIK" className="text-xs" />
                </div>
              </div>
              <div className="space-y-1 sm:col-span-2"><Label>Deskripsi</Label><textarea className="w-full border border-border rounded-md p-2 text-sm min-h-[80px] bg-card text-foreground" value={form.deskripsi} onChange={e => setForm(p => ({...p, deskripsi: e.target.value}))} placeholder="Deskripsi kegiatan inventarisasi..." /></div>
            </div>

            {/* === TIM INVENTARISASI (Internal) === */}
            <div className="p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg space-y-3 border border-amber-200 dark:border-amber-700">
              <Label className="text-sm font-medium text-amber-800 dark:text-amber-300 flex items-center gap-1.5"><Users className="w-4 h-4" /> Tim Inventarisasi (Internal)</Label>

              {/* Tim Inti */}
              <div className="p-2.5 bg-white dark:bg-slate-800/50 rounded-md border border-amber-200 dark:border-amber-700/50 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-amber-700 dark:text-amber-300">Tim Inti (Pelaksana)</span>
                  <button type="button" onClick={() => setForm(p => ({...p, tim_inti: [...(p.tim_inti || []), {nama: '', jabatan: '', nip: '', unit: '', is_ketua: false}]}))} className="text-[10px] text-amber-600 dark:text-amber-400 hover:text-amber-800 flex items-center gap-0.5"><Plus className="w-3 h-3" /> Tambah</button>
                </div>
                {(form.tim_inti || []).length === 0 && <p className="text-[10px] text-amber-500 italic">Belum ada anggota tim inti.</p>}
                {(form.tim_inti || []).map((m, idx) => (
                  <div key={idx} className="space-y-1">
                    {idx === 0 && <div className="grid grid-cols-[60px_1fr_1fr_1fr_1fr_28px] gap-1"><span className="text-[9px] text-amber-600 dark:text-amber-400">Peran</span><span className="text-[9px] text-amber-600 dark:text-amber-400">Nama</span><span className="text-[9px] text-amber-600 dark:text-amber-400">Jabatan</span><span className="text-[9px] text-amber-600 dark:text-amber-400">NIP/NIK</span><span className="text-[9px] text-amber-600 dark:text-amber-400">Unit</span><span></span></div>}
                    <div className="grid grid-cols-[60px_1fr_1fr_1fr_1fr_28px] gap-1 items-center">
                      <select value={m.is_ketua ? 'ketua' : 'anggota'} onChange={e => { const arr = [...form.tim_inti]; arr[idx] = {...arr[idx], is_ketua: e.target.value === 'ketua'}; setForm(p => ({...p, tim_inti: arr})); }} className="h-7 text-[10px] rounded border border-border bg-card text-foreground px-1">
                        <option value="anggota">Anggota</option><option value="ketua">Ketua</option>
                      </select>
                      <Input value={m.nama} onChange={e => { const arr = [...form.tim_inti]; arr[idx] = {...arr[idx], nama: e.target.value}; setForm(p => ({...p, tim_inti: arr})); }} placeholder="Nama" className="h-7 text-xs" />
                      <Input value={m.jabatan} onChange={e => { const arr = [...form.tim_inti]; arr[idx] = {...arr[idx], jabatan: e.target.value}; setForm(p => ({...p, tim_inti: arr})); }} placeholder="Jabatan" className="h-7 text-xs" />
                      <Input value={m.nip} onChange={e => { const arr = [...form.tim_inti]; arr[idx] = {...arr[idx], nip: e.target.value}; setForm(p => ({...p, tim_inti: arr})); }} placeholder="NIP/NIK" className="h-7 text-xs" />
                      <Input value={m.unit} onChange={e => { const arr = [...form.tim_inti]; arr[idx] = {...arr[idx], unit: e.target.value}; setForm(p => ({...p, tim_inti: arr})); }} placeholder="Unit" className="h-7 text-xs" />
                      <button type="button" onClick={() => setForm(p => ({...p, tim_inti: p.tim_inti.filter((_, i) => i !== idx)}))} className="h-7 w-7 flex items-center justify-center text-red-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"><X className="w-3.5 h-3.5" /></button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Tim Pembantu */}
              <div className="p-2.5 bg-white dark:bg-slate-800/50 rounded-md border border-amber-200 dark:border-amber-700/50 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-amber-700 dark:text-amber-300">Tim Pembantu</span>
                  <button type="button" onClick={() => setForm(p => ({...p, tim_pembantu: [...(p.tim_pembantu || []), {nama: '', jabatan: '', nip: '', unit: '', is_ketua: false}]}))} className="text-[10px] text-amber-600 dark:text-amber-400 hover:text-amber-800 flex items-center gap-0.5"><Plus className="w-3 h-3" /> Tambah</button>
                </div>
                {(form.tim_pembantu || []).length === 0 && <p className="text-[10px] text-amber-500 italic">Belum ada anggota tim pembantu.</p>}
                {(form.tim_pembantu || []).map((m, idx) => (
                  <div key={idx} className="space-y-1">
                    {idx === 0 && <div className="grid grid-cols-[60px_1fr_1fr_1fr_1fr_28px] gap-1"><span className="text-[9px] text-amber-600 dark:text-amber-400">Peran</span><span className="text-[9px] text-amber-600 dark:text-amber-400">Nama</span><span className="text-[9px] text-amber-600 dark:text-amber-400">Jabatan</span><span className="text-[9px] text-amber-600 dark:text-amber-400">NIP/NIK</span><span className="text-[9px] text-amber-600 dark:text-amber-400">Unit</span><span></span></div>}
                    <div className="grid grid-cols-[60px_1fr_1fr_1fr_1fr_28px] gap-1 items-center">
                      <select value={m.is_ketua ? 'ketua' : 'anggota'} onChange={e => { const arr = [...form.tim_pembantu]; arr[idx] = {...arr[idx], is_ketua: e.target.value === 'ketua'}; setForm(p => ({...p, tim_pembantu: arr})); }} className="h-7 text-[10px] rounded border border-border bg-card text-foreground px-1">
                        <option value="anggota">Anggota</option><option value="ketua">Ketua</option>
                      </select>
                      <Input value={m.nama} onChange={e => { const arr = [...form.tim_pembantu]; arr[idx] = {...arr[idx], nama: e.target.value}; setForm(p => ({...p, tim_pembantu: arr})); }} placeholder="Nama" className="h-7 text-xs" />
                      <Input value={m.jabatan} onChange={e => { const arr = [...form.tim_pembantu]; arr[idx] = {...arr[idx], jabatan: e.target.value}; setForm(p => ({...p, tim_pembantu: arr})); }} placeholder="Jabatan" className="h-7 text-xs" />
                      <Input value={m.nip} onChange={e => { const arr = [...form.tim_pembantu]; arr[idx] = {...arr[idx], nip: e.target.value}; setForm(p => ({...p, tim_pembantu: arr})); }} placeholder="NIP/NIK" className="h-7 text-xs" />
                      <Input value={m.unit} onChange={e => { const arr = [...form.tim_pembantu]; arr[idx] = {...arr[idx], unit: e.target.value}; setForm(p => ({...p, tim_pembantu: arr})); }} placeholder="Unit" className="h-7 text-xs" />
                      <button type="button" onClick={() => setForm(p => ({...p, tim_pembantu: p.tim_pembantu.filter((_, i) => i !== idx)}))} className="h-7 w-7 flex items-center justify-center text-red-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"><X className="w-3.5 h-3.5" /></button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* === TIM EKSTERNAL === */}
            {/* Tim Peneliti */}
            <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg space-y-2 border border-blue-200 dark:border-blue-700">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium text-blue-800 dark:text-blue-300 flex items-center gap-1.5"><Users className="w-4 h-4" /> Tim Peneliti (Eksternal)</Label>
                <button type="button" onClick={() => setForm(p => ({...p, tim_peneliti: [...(p.tim_peneliti || []), {nama: '', jabatan: '', nip: ''}]}))} className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-200 flex items-center gap-1"><Plus className="w-3 h-3" /> Tambah Anggota</button>
              </div>
              {(form.tim_peneliti || []).length === 0 && <p className="text-xs text-blue-500 dark:text-blue-400 italic">Belum ada anggota tim peneliti.</p>}
              {(form.tim_peneliti || []).map((member, idx) => (
                <div key={idx} className="space-y-1">
                  {idx === 0 && <div className="grid grid-cols-[1fr_1fr_1fr_28px] gap-2"><span className="text-[10px] text-blue-600 dark:text-blue-400">Nama</span><span className="text-[10px] text-blue-600 dark:text-blue-400">Jabatan</span><span className="text-[10px] text-blue-600 dark:text-blue-400">NIP</span><span></span></div>}
                  <div className="grid grid-cols-[1fr_1fr_1fr_28px] gap-2 items-center">
                    <Input value={member.nama} onChange={e => { const arr = [...form.tim_peneliti]; arr[idx] = {...arr[idx], nama: e.target.value}; setForm(p => ({...p, tim_peneliti: arr})); }} placeholder="Nama lengkap" className="h-7 text-xs" />
                    <Input value={member.jabatan} onChange={e => { const arr = [...form.tim_peneliti]; arr[idx] = {...arr[idx], jabatan: e.target.value}; setForm(p => ({...p, tim_peneliti: arr})); }} placeholder="Jabatan" className="h-7 text-xs" />
                    <Input value={member.nip} onChange={e => { const arr = [...form.tim_peneliti]; arr[idx] = {...arr[idx], nip: e.target.value}; setForm(p => ({...p, tim_peneliti: arr})); }} placeholder="NIP" className="h-7 text-xs" />
                    <button type="button" onClick={() => setForm(p => ({...p, tim_peneliti: p.tim_peneliti.filter((_, i) => i !== idx)}))} className="h-7 w-7 flex items-center justify-center text-red-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"><X className="w-3.5 h-3.5" /></button>
                  </div>
                </div>
              ))}
            </div>

            {/* Tim Pendukung */}
            <div className="p-3 bg-violet-50 dark:bg-violet-900/20 rounded-lg space-y-2 border border-violet-200 dark:border-violet-700">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium text-violet-800 dark:text-violet-300 flex items-center gap-1.5"><Users className="w-4 h-4" /> Tim Pendukung (Eksternal)</Label>
                <button type="button" onClick={() => setForm(p => ({...p, tim_pendukung: [...(p.tim_pendukung || []), {nama: '', jabatan: '', nip: '', dari_pihak: ''}]}))} className="text-xs text-violet-600 dark:text-violet-400 hover:text-violet-800 dark:hover:text-violet-200 flex items-center gap-1" data-testid="add-tim-pendukung-btn"><Plus className="w-3 h-3" /> Tambah Anggota</button>
              </div>
              {(form.tim_pendukung || []).length === 0 && <p className="text-xs text-violet-500 dark:text-violet-400 italic">Belum ada anggota tim pendukung.</p>}
              {(form.tim_pendukung || []).map((member, idx) => (
                <div key={idx} className="space-y-1">
                  {idx === 0 && <div className="grid grid-cols-[1fr_1fr_1fr_1fr_28px] gap-2"><span className="text-[10px] text-violet-600 dark:text-violet-400">Nama</span><span className="text-[10px] text-violet-600 dark:text-violet-400">Jabatan</span><span className="text-[10px] text-violet-600 dark:text-violet-400">NIP</span><span className="text-[10px] text-violet-600 dark:text-violet-400">Dari Pihak</span><span></span></div>}
                  <div className="grid grid-cols-[1fr_1fr_1fr_1fr_28px] gap-2 items-center">
                    <Input value={member.nama} onChange={e => { const arr = [...form.tim_pendukung]; arr[idx] = {...arr[idx], nama: e.target.value}; setForm(p => ({...p, tim_pendukung: arr})); }} placeholder="Nama lengkap" className="h-7 text-xs" />
                    <Input value={member.jabatan} onChange={e => { const arr = [...form.tim_pendukung]; arr[idx] = {...arr[idx], jabatan: e.target.value}; setForm(p => ({...p, tim_pendukung: arr})); }} placeholder="Jabatan" className="h-7 text-xs" />
                    <Input value={member.nip} onChange={e => { const arr = [...form.tim_pendukung]; arr[idx] = {...arr[idx], nip: e.target.value}; setForm(p => ({...p, tim_pendukung: arr})); }} placeholder="NIP" className="h-7 text-xs" />
                    <Input value={member.dari_pihak || ''} onChange={e => { const arr = [...form.tim_pendukung]; arr[idx] = {...arr[idx], dari_pihak: e.target.value}; setForm(p => ({...p, tim_pendukung: arr})); }} placeholder="Dari pihak mana" className="h-7 text-xs" />
                    <button type="button" onClick={() => setForm(p => ({...p, tim_pendukung: p.tim_pendukung.filter((_, i) => i !== idx)}))} className="h-7 w-7 flex items-center justify-center text-red-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"><X className="w-3.5 h-3.5" /></button>
                  </div>
                </div>
              ))}
            </div>

            {/* Data Satker */}
            <div className="p-3 bg-emerald-50 dark:bg-emerald-900/20 rounded-lg space-y-2 border border-emerald-200 dark:border-emerald-700">
              <Label className="text-sm font-medium text-emerald-800 dark:text-emerald-300 flex items-center gap-1.5"><Building2 className="w-4 h-4" /> Data Satuan Kerja</Label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <div className="space-y-0.5">
                  <Label className="text-[10px] text-emerald-600 dark:text-emerald-400">Kode Satker <span className="text-red-500">*</span></Label>
                  <Input name="activity-kode_satker" value={form.kode_satker} onChange={e => { handleKodeSatkerChange(e.target.value); clearFormError('kode_satker'); }} placeholder="Contoh: 001234" className={`h-7 text-xs${formErrors.kode_satker ? ' border-red-500 focus-visible:ring-red-500' : ''}`} aria-invalid={!!formErrors.kode_satker} data-testid="input-kode-satker" />
                  {formErrors.kode_satker && <p className="text-[11px] text-red-600 dark:text-red-400">{formErrors.kode_satker}</p>}
                </div>
                <div className="space-y-0.5">
                  <Label className="text-[10px] text-emerald-600 dark:text-emerald-400">Nama Satker <span className="text-red-500">*</span></Label>
                  <Input name="activity-nama_satker" value={form.nama_satker} onChange={e => { handleNamaSatkerChange(e.target.value); clearFormError('nama_satker'); }} placeholder="Contoh: Kantor Wilayah Jakarta" className={`h-7 text-xs${formErrors.nama_satker ? ' border-red-500 focus-visible:ring-red-500' : ''}`} aria-invalid={!!formErrors.nama_satker} data-testid="input-nama-satker" />
                  {formErrors.nama_satker && <p className="text-[11px] text-red-600 dark:text-red-400">{formErrors.nama_satker}</p>}
                </div>
                <div className="space-y-0.5"><Label className="text-[10px] text-emerald-600 dark:text-emerald-400">Nama Kasatker</Label><Input value={form.kasatker_nama} onChange={e => setForm(p => ({...p, kasatker_nama: e.target.value}))} placeholder="Nama Kepala Satker" className="h-7 text-xs" /></div>
                <div className="space-y-0.5"><Label className="text-[10px] text-emerald-600 dark:text-emerald-400">NIP Kasatker</Label><Input value={form.kasatker_nip} onChange={e => setForm(p => ({...p, kasatker_nip: e.target.value}))} placeholder="NIP" className="h-7 text-xs" /></div>
                <div className="space-y-0.5"><Label className="text-[10px] text-emerald-600 dark:text-emerald-400">Jabatan</Label><Input value={form.kasatker_jabatan} onChange={e => setForm(p => ({...p, kasatker_jabatan: e.target.value}))} placeholder="Jabatan Kasatker" className="h-7 text-xs" /></div>
                <div className="space-y-0.5"><Label className="text-[10px] text-emerald-600 dark:text-emerald-400">Alamat Satker</Label><Input value={form.alamat_satker} onChange={e => setForm(p => ({...p, alamat_satker: e.target.value}))} placeholder="Alamat lengkap" className="h-7 text-xs" /></div>
              </div>
              {/* Eselon I with nested Eselon II */}
              <div className="mt-2 pt-2 border-t border-emerald-200 dark:border-emerald-700 space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-[10px] font-medium text-emerald-700 dark:text-emerald-300">Eselon I</Label>
                  <button type="button" onClick={() => setForm(p => ({...p, eselon1: [...(p.eselon1 || []), {nama: '', eselon2: []}]}))} className="text-[10px] text-emerald-600 dark:text-emerald-400 hover:text-emerald-800 dark:hover:text-emerald-200 flex items-center gap-0.5" data-testid="add-eselon1-btn">
                    <Plus className="w-3 h-3" /> Tambah Eselon I
                  </button>
                </div>
                {(form.eselon1 || []).length === 0 && <p className="text-[10px] text-emerald-500 dark:text-emerald-400 italic">Belum ada data Eselon I.</p>}
                {(form.eselon1 || []).map((es, idx) => {
                  const esObj = typeof es === 'object' ? es : {nama: es, eselon2: []};
                  return (
                    <div key={idx} className="border border-emerald-200 dark:border-emerald-600 rounded-lg p-2 space-y-1.5 bg-emerald-25 dark:bg-emerald-900/10">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[10px] text-emerald-600 font-bold w-4 text-center flex-shrink-0">{idx + 1}.</span>
                        <Input
                          value={esObj.nama}
                          onChange={e => { const arr = [...(form.eselon1 || [])]; arr[idx] = {...esObj, nama: e.target.value}; setForm(p => ({...p, eselon1: arr})); }}
                          placeholder="Nama Eselon I"
                          className="h-7 text-xs flex-1"
                          data-testid={`eselon1-input-${idx}`}
                        />
                        <button type="button" onClick={() => setForm(p => ({...p, eselon1: (p.eselon1 || []).filter((_, i) => i !== idx)}))} className="h-7 w-7 flex items-center justify-center text-red-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded flex-shrink-0" data-testid={`remove-eselon1-${idx}`}>
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      {/* Eselon II list under this Eselon I */}
                      <div className="ml-5 space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="text-[9px] text-emerald-500 dark:text-emerald-400 font-medium">Eselon II</span>
                          <button type="button" onClick={() => { const arr = [...(form.eselon1 || [])]; const obj = {...esObj, eselon2: [...(esObj.eselon2 || []), '']}; arr[idx] = obj; setForm(p => ({...p, eselon1: arr})); }} className="text-[9px] text-emerald-500 hover:text-emerald-700 flex items-center gap-0.5" data-testid={`add-eselon2-btn-${idx}`}>
                            <Plus className="w-2.5 h-2.5" /> Tambah
                          </button>
                        </div>
                        {(esObj.eselon2 || []).map((e2, j) => (
                          <div key={j} className="flex items-center gap-1">
                            <span className="text-[9px] text-emerald-400 w-6 text-right flex-shrink-0">{idx+1}.{j+1}</span>
                            <Input
                              value={e2}
                              onChange={e => { const arr = [...(form.eselon1 || [])]; const e2arr = [...(esObj.eselon2 || [])]; e2arr[j] = e.target.value; arr[idx] = {...esObj, eselon2: e2arr}; setForm(p => ({...p, eselon1: arr})); }}
                              placeholder="Nama Eselon II"
                              className="h-6 text-[11px] flex-1"
                              data-testid={`eselon2-input-${idx}-${j}`}
                            />
                            <button type="button" onClick={() => { const arr = [...(form.eselon1 || [])]; arr[idx] = {...esObj, eselon2: (esObj.eselon2 || []).filter((_, k) => k !== j)}; setForm(p => ({...p, eselon1: arr})); }} className="h-6 w-6 flex items-center justify-center text-red-400 hover:text-red-600 rounded flex-shrink-0" data-testid={`remove-eselon2-${idx}-${j}`}>
                              <X className="w-3 h-3" />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Berita Acara */}
            <div className="p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg space-y-2 border border-amber-200 dark:border-amber-700">
              <Label className="text-sm font-medium text-amber-800 dark:text-amber-300 flex items-center gap-1.5"><BookOpen className="w-4 h-4" /> Data Berita Acara</Label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <div className="space-y-0.5"><Label className="text-[10px] text-amber-600 dark:text-amber-400">Nomor Berita Acara</Label><Input value={form.nomor_berita_acara} onChange={e => setForm(p => ({...p, nomor_berita_acara: e.target.value}))} placeholder="BA-001/2024" className="h-7 text-xs" /></div>
                <div className="space-y-0.5"><Label className="text-[10px] text-amber-600 dark:text-amber-400">Tanggal Berita Acara</Label><Input type="date" value={form.tanggal_berita_acara} onChange={e => setForm(p => ({...p, tanggal_berita_acara: e.target.value}))} className="h-7 text-xs" /></div>
              </div>
              <div className="space-y-0.5"><Label className="text-[10px] text-amber-600 dark:text-amber-400">Kesimpulan Penelitian</Label><textarea value={form.kesimpulan} onChange={e => setForm(p => ({...p, kesimpulan: e.target.value}))} className="w-full border border-border rounded-md p-1.5 text-xs min-h-[50px] resize-none bg-card text-foreground" placeholder="Kesimpulan hasil penelitian tim internal..." /></div>
            </div>

            {/* Photo Upload — lazy-loaded in edit mode to avoid huge payload */}
            <div className="space-y-2 min-w-0 overflow-hidden">
              <Label>Foto Kegiatan ({editingActivity && !photosLoaded ? `${photoCount}/10 — belum dimuat` : `${(form.photos || []).length}/10`})</Label>
              {editingActivity && !photosLoaded ? (
                <button
                  type="button"
                  onClick={loadActivityPhotos}
                  disabled={loadingPhotos}
                  className="w-full flex items-center justify-center gap-2 text-sm text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 dark:hover:bg-blue-900/40 rounded-lg p-3 cursor-pointer border-2 border-dashed border-blue-200 dark:border-blue-700 disabled:opacity-50"
                  data-testid="lazy-load-photos-btn"
                >
                  {loadingPhotos ? <Loader2 className="w-5 h-5 animate-spin" /> : <ImageIcon className="w-5 h-5 flex-shrink-0" />}
                  {loadingPhotos ? 'Memuat foto...' : photoCount > 0 ? `Kelola Foto (${photoCount}/10)` : `Kelola Foto (0/10)`}
                </button>
              ) : (
                <>
                  {(form.photos || []).length < 10 && (
                    <label className="flex items-center justify-center gap-2 text-sm text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 dark:hover:bg-blue-900/40 rounded-lg p-3 cursor-pointer border-2 border-dashed border-blue-200 dark:border-blue-700">
                      <Camera className="w-5 h-5 flex-shrink-0" />Upload Foto
                      <input type="file" accept="image/*" multiple className="hidden" onChange={handlePhotoUpload} data-testid="upload-photo-input" />
                    </label>
                  )}
                  {(form.photos || []).length >= 10 && (
                    <p className="text-xs text-amber-600 dark:text-amber-400 italic">Maksimal 10 foto tercapai. Hapus foto untuk menambahkan baru.</p>
                  )}
                  {(form.photos || []).length > 0 && (
                    <div className="flex gap-2 flex-wrap overflow-hidden">
                      {(form.photos || []).map((p, i) => (
                        <div key={i} className="relative group">
                          <img src={p} alt="" className="w-16 h-16 object-cover rounded-lg border" />
                          <button type="button" onClick={() => setForm(prev => ({...prev, photos: (prev.photos || []).filter((_, j) => j !== i)}))} className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"><X className="w-3 h-3" /></button>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Document Upload — lazy-loaded in edit mode */}
            <div className="space-y-2 min-w-0 overflow-hidden">
              <Label>Dokumen Inventarisasi ({editingActivity && !docsLoaded ? `${docCount}/5 — belum dimuat` : `${(form.documents || []).length}/5`})</Label>
              {editingActivity && !docsLoaded ? (
                <button
                  type="button"
                  onClick={loadActivityDocs}
                  disabled={loadingDocs}
                  className="w-full flex items-center justify-center gap-2 text-sm text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/20 hover:bg-emerald-100 dark:hover:bg-emerald-900/40 rounded-lg p-3 cursor-pointer border-2 border-dashed border-emerald-200 dark:border-emerald-700 disabled:opacity-50"
                  data-testid="lazy-load-docs-btn"
                >
                  {loadingDocs ? <Loader2 className="w-5 h-5 animate-spin" /> : <FileText className="w-5 h-5 flex-shrink-0" />}
                  {loadingDocs ? 'Memuat dokumen...' : docCount > 0 ? `Kelola Dokumen (${docCount}/5)` : `Kelola Dokumen (0/5)`}
                </button>
              ) : (
                <>
                  {(form.documents || []).length < 5 && (
                    <label className="flex items-center justify-center gap-2 text-sm text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/20 hover:bg-emerald-100 dark:hover:bg-emerald-900/40 rounded-lg p-3 cursor-pointer border-2 border-dashed border-emerald-200 dark:border-emerald-700">
                      <FileUp className="w-5 h-5 flex-shrink-0" />Upload Dokumen (PDF)
                      <input type="file" accept=".pdf" multiple className="hidden" onChange={handleDocUpload} data-testid="upload-doc-input" />
                    </label>
                  )}
                  {(form.documents || []).length >= 5 && (
                    <p className="text-xs text-amber-600 dark:text-amber-400 italic">Maksimal 5 dokumen tercapai. Hapus dokumen untuk menambahkan baru.</p>
                  )}
                  {(form.documents || []).length > 0 && (
                    <div className="space-y-1 min-w-0 overflow-hidden">
                      {(form.documents || []).map((doc, i) => (
                        <div key={i} className="flex items-center gap-2 bg-muted rounded-lg px-3 py-2 min-w-0 max-w-full overflow-hidden">
                          <FileText className="w-4 h-4 text-red-600 flex-shrink-0" />
                          <span className="text-sm text-foreground/80 flex-1 min-w-0 truncate block" title={doc.name}>{doc.name}</span>
                          <button type="button" onClick={() => openPdfDoc(doc, editingActivity?.id, i)} className="text-xs text-blue-600 hover:text-blue-800 underline flex-shrink-0">Lihat</button>
                          <button type="button" onClick={() => setForm(prev => ({...prev, documents: (prev.documents || []).filter((_, j) => j !== i)}))} className="text-red-400 hover:text-red-600 flex-shrink-0"><X className="w-4 h-4" /></button>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>

            <Button
              onClick={editingActivity ? handleUpdate : handleCreate}
              disabled={saving}
              className={`w-full ${editingActivity ? 'bg-amber-600 hover:bg-amber-700' : 'bg-blue-600 hover:bg-blue-700'} text-white`}
            >
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              {editingActivity ? 'Simpan Perubahan' : 'Buat Kegiatan'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Photo Lightbox */}
      {photoLightbox && (
        <ActivityPhotoLightbox
          activityId={photoLightbox.activityId}
          initialIndex={photoLightbox.index}
          onClose={() => setPhotoLightbox(null)}
        />
      )}

      {confirmDialog}

      {/* Pengesahan (finalisasi) kegiatan — lazy loaded */}
      <Suspense fallback={null}>
        {pengesahanActivity && (
          <PengesahanDialog
            open={!!pengesahanActivity}
            activity={pengesahanActivity}
            isAdmin={isAdmin}
            onClose={() => setPengesahanActivity(null)}
            onSahkanSuccess={() => { fetchActivities(); }}
          />
        )}
      </Suspense>

      {/* Completion Status Validation Dialog */}
      <Dialog open={!!completionDialog} onOpenChange={(o) => { if (!o) setCompletionDialog(null); }}>
        <DialogContent className="max-w-md" data-testid="completion-status-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              Validasi Status Kegiatan
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Hasil validasi otomatis berdasarkan tanggal kegiatan, status inventarisasi aset, dan kelengkapan foto bukti.
            </DialogDescription>
          </DialogHeader>
          {completionDialog?.loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
              <span className="ml-3 text-sm text-muted-foreground">Memvalidasi...</span>
            </div>
          ) : completionDialog?.data && (
            (() => {
              const d = completionDialog.data;
              const status = d.computed_status;
              const cfg = (
                status === "selesai"
                  ? { color: "emerald", label: "Selesai", icon: CheckCircle2, msg: "Semua aset telah diinventarisasi dan berfoto. Kegiatan dinyatakan selesai." }
                  : status === "belum_lengkap"
                  ? { color: "amber", label: "Belum Lengkap", icon: AlertTriangle, msg: "Tanggal kegiatan sudah berakhir, namun ada aset yang belum lengkap." }
                  : status === "berlangsung"
                  ? { color: "blue", label: "On Going", icon: PlayCircle, msg: "Kegiatan sedang berlangsung." }
                  : { color: "slate", label: "Belum Dimulai", icon: Clock, msg: "Tanggal mulai kegiatan belum tiba." }
              );
              const colorClasses = {
                emerald: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-700",
                amber: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-700",
                blue: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700",
                slate: "bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-900/30 dark:text-slate-300 dark:border-slate-700",
              };
              const Icon = cfg.icon;
              return (
                <div className="space-y-3">
                  <div className={`flex items-start gap-3 p-3 rounded-lg border ${colorClasses[cfg.color]}`}>
                    <Icon className="w-5 h-5 flex-shrink-0 mt-0.5" />
                    <div>
                      <div className="font-semibold text-sm">{cfg.label}</div>
                      <p className="text-xs mt-1">{cfg.msg}</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="p-2 rounded-lg bg-muted">
                      <div className="text-lg font-bold text-foreground">{d.total_assets}</div>
                      <div className="text-[10px] text-muted-foreground uppercase">Total Aset</div>
                    </div>
                    <div className={`p-2 rounded-lg ${d.pending_inventory_count === 0 ? 'bg-emerald-50 dark:bg-emerald-900/30' : 'bg-amber-50 dark:bg-amber-900/30'}`}>
                      <div className={`text-lg font-bold ${d.pending_inventory_count === 0 ? 'text-emerald-700 dark:text-emerald-300' : 'text-amber-700 dark:text-amber-300'}`}>{d.pending_inventory_count}</div>
                      <div className="text-[10px] text-muted-foreground uppercase">Belum Diinv.</div>
                    </div>
                    <div className={`p-2 rounded-lg ${d.no_photo_count === 0 ? 'bg-emerald-50 dark:bg-emerald-900/30' : 'bg-amber-50 dark:bg-amber-900/30'}`}>
                      <div className={`text-lg font-bold ${d.no_photo_count === 0 ? 'text-emerald-700 dark:text-emerald-300' : 'text-amber-700 dark:text-amber-300'}`}>{d.no_photo_count}</div>
                      <div className="text-[10px] text-muted-foreground uppercase">Belum Berfoto</div>
                    </div>
                  </div>
                  {(d.pending_inventory_count > 0 || d.no_photo_count > 0) && (
                    <div className="text-xs text-muted-foreground space-y-1 p-2 bg-muted/50 rounded">
                      {d.pending_inventory_count > 0 && <p>• {d.pending_inventory_count} aset masih berstatus "Belum Diinventarisasi"</p>}
                      {d.no_photo_count > 0 && <p>• {d.no_photo_count} aset belum memiliki foto bukti</p>}
                    </div>
                  )}
                  <div className="flex gap-2">
                    <Button variant="outline" className="flex-1" onClick={() => setCompletionDialog(null)} data-testid="completion-close-btn">Tutup</Button>
                    {completionDialog?.activity && (
                      <Button className="flex-1 bg-blue-600 hover:bg-blue-700 text-white" onClick={() => { onSelectActivity(completionDialog.activity); setCompletionDialog(null); }} data-testid="completion-open-activity-btn">
                        Buka Kegiatan
                      </Button>
                    )}
                  </div>
                </div>
              );
            })()
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
