import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  ShieldCheck, Loader2, FileText, Upload, Trash2, Lock,
  CheckCircle2, AlertTriangle, X, Eye,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import axios from "axios";
import { getApiError } from "@/lib/utils";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const MAX_PDF_MB = 20;

const formatTanggal = (iso) => {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleDateString("id-ID", {
      day: "2-digit", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
};

// Syarat pengesahan — key mengikuti payload GET /pengesahan-status.
// Baris hijau bila count 0, merah bila masih ada aset yang belum memenuhi.
const REQUIREMENTS = [
  { key: "belum_diinventarisasi", ok: "Semua aset sudah diinventarisasi", fail: (n) => `${n} aset belum diinventarisasi` },
  { key: "tanpa_foto", ok: "Semua aset memiliki foto", fail: (n) => `${n} aset tanpa foto` },
  { key: "kategori_dummy", ok: "Tidak ada aset kategori dummy", fail: (n) => `${n} aset masih berkategori dummy` },
  { key: "tanpa_kode_register", ok: "Semua aset memiliki kode register", fail: (n) => `${n} aset tanpa kode register` },
  { key: "tanpa_eselon", ok: "Semua aset memiliki Eselon I/II", fail: (n) => `${n} aset tanpa Eselon I/II` },
  { key: "tanpa_lokasi", ok: "Semua aset memiliki lokasi", fail: (n) => `${n} aset tanpa lokasi` },
  { key: "tanpa_pengguna", ok: "Semua aset memiliki pengguna", fail: (n) => `${n} aset tanpa pengguna` },
];

/**
 * Dialog Pengesahan Kegiatan:
 *  1. Cek kelayakan (semua aset terinventarisasi + berfoto) via
 *     GET /inventory-activities/{id}/pengesahan-status
 *  2. Unggah dokumen pengesahan (PDF bertanda tangan, wajib >= 1)
 *  3. Sahkan → kegiatan terkunci + riwayat aset dicatat (kartu inventarisasi)
 *
 * Lazy-loaded oleh ActivitySelectionPage.
 */
export default function PengesahanDialog({ open, activity, isAdmin, onClose, onSahkanSuccess }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [sahkanStep, setSahkanStep] = useState(false); // konfirmasi akhir
  const [sahkanLoading, setSahkanLoading] = useState(false);
  const fileRef = useRef(null);

  const fetchStatus = useCallback(async () => {
    if (!activity?.id) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/inventory-activities/${activity.id}/pengesahan-status`);
      setStatus(r.data);
    } catch (err) {
      toast.error(getApiError(err, "Gagal memuat status pengesahan"));
      onClose?.();
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activity?.id]);

  useEffect(() => {
    if (open) { setSahkanStep(false); fetchStatus(); }
    else setStatus(null);
  }, [open, fetchStatus]);

  const disahkan = status?.status === "disahkan";
  const dokumen = status?.dokumen || [];
  const canSahkan = !!status?.eligible && dokumen.length > 0 && !disahkan;

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) { toast.error("Dokumen harus berformat PDF"); return; }
    if (file.size > MAX_PDF_MB * 1024 * 1024) { toast.error(`Ukuran dokumen maksimal ${MAX_PDF_MB}MB`); return; }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const token = localStorage.getItem("token");
      await axios.post(`${API}/inventory-activities/${activity.id}/pengesahan-dokumen`, formData, {
        headers: { "Content-Type": "multipart/form-data", Authorization: `Bearer ${token}` },
        timeout: 120000,
      });
      toast.success(`Dokumen "${file.name}" berhasil diunggah`);
      fetchStatus();
    } catch (err) {
      toast.error(getApiError(err, "Gagal mengunggah dokumen"));
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDoc = async (doc) => {
    if (!window.confirm(`Hapus dokumen "${doc.name}"?`)) return;
    try {
      const token = localStorage.getItem("token");
      await axios.delete(`${API}/inventory-activities/${activity.id}/pengesahan-dokumen/${doc.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success("Dokumen dihapus");
      fetchStatus();
    } catch (err) {
      toast.error(getApiError(err, "Gagal menghapus dokumen"));
    }
  };

  const handleViewDoc = (doc) => {
    window.open(`${API}/inventory-activities/${activity.id}/pengesahan-dokumen/${doc.id}`, "_blank");
  };

  const handleSahkan = async () => {
    if (sahkanLoading) return;
    setSahkanLoading(true);
    try {
      const token = localStorage.getItem("token");
      const r = await axios.post(`${API}/inventory-activities/${activity.id}/sahkan`, {}, {
        headers: { Authorization: `Bearer ${token}` },
        timeout: 120000,
      });
      toast.success(r.data?.message || "Kegiatan berhasil disahkan");
      setSahkanStep(false);
      fetchStatus();
      onSahkanSuccess?.(r.data);
    } catch (err) {
      toast.error(getApiError(err, "Gagal mengesahkan kegiatan"));
    } finally {
      setSahkanLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose?.(); }}>
      <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto" data-testid="pengesahan-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {disahkan ? <Lock className="w-5 h-5 text-emerald-600" /> : <ShieldCheck className="w-5 h-5 text-blue-600" />}
            Pengesahan Kegiatan
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground">
            {disahkan
              ? "Kegiatan telah disahkan dan seluruh data aset terkunci."
              : "Sahkan kegiatan setelah semua aset terinventarisasi, berfoto, berdata lengkap (kode register, eselon, lokasi, pengguna, tanpa kategori dummy), dan dokumen pengesahan bertanda tangan diunggah."}
          </DialogDescription>
        </DialogHeader>

        {loading || !status ? (
          <div className="flex items-center justify-center py-10 gap-2 text-muted-foreground">
            <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
            <span className="text-sm">Memuat status...</span>
          </div>
        ) : (
          <div className="space-y-3">
            {/* Tiket + status */}
            <div className={`flex items-start gap-3 p-3 rounded-lg border ${
              disahkan
                ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-700"
                : status.eligible
                ? "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700"
                : "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-700"
            }`}>
              {disahkan ? <CheckCircle2 className="w-5 h-5 flex-shrink-0 mt-0.5" />
                : status.eligible ? <ShieldCheck className="w-5 h-5 flex-shrink-0 mt-0.5" />
                : <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />}
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-sm">
                    {disahkan ? "Disahkan" : status.eligible ? "Siap Disahkan" : "Belum Memenuhi Syarat"}
                  </span>
                  {status.ticket_number && (
                    <span className="text-[11px] font-mono font-bold bg-card/70 px-1.5 py-0.5 rounded border border-current/20" data-testid="pengesahan-ticket">
                      {status.ticket_number}
                    </span>
                  )}
                </div>
                {disahkan && (
                  <p className="text-xs mt-1">
                    Disahkan {formatTanggal(status.disahkan_at)} oleh <b>{status.disahkan_by || "-"}</b>
                  </p>
                )}
              </div>
            </div>

            {/* Syarat pengesahan — baris hijau/merah per kriteria */}
            <div className="rounded-lg border border-border overflow-hidden" data-testid="pengesahan-requirements">
              <div className="flex items-center justify-between px-2.5 py-1.5 bg-muted">
                <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Syarat Pengesahan</span>
                <span className="text-[11px] font-bold text-foreground tabular-nums">{status.total} aset</span>
              </div>
              <div className="divide-y divide-border">
                {status.total === 0 && (
                  <div className="flex items-center gap-2 px-2.5 py-1.5 bg-red-50 dark:bg-red-900/20">
                    <AlertTriangle className="w-3.5 h-3.5 text-red-600 dark:text-red-400 flex-shrink-0" />
                    <span className="text-xs text-red-700 dark:text-red-300">Kegiatan belum memiliki aset</span>
                  </div>
                )}
                {REQUIREMENTS.map((req) => {
                  const n = Number(status[req.key] || 0);
                  const ok = n === 0;
                  return (
                    <div
                      key={req.key}
                      className={`flex items-center gap-2 px-2.5 py-1.5 ${ok ? "bg-emerald-50/60 dark:bg-emerald-900/15" : "bg-red-50 dark:bg-red-900/20"}`}
                      data-testid={`pengesahan-req-${req.key}`}
                    >
                      {ok
                        ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
                        : <X className="w-3.5 h-3.5 text-red-600 dark:text-red-400 flex-shrink-0" />}
                      <span className={`text-xs ${ok ? "text-emerald-700 dark:text-emerald-300" : "text-red-700 dark:text-red-300 font-medium"}`}>
                        {ok ? req.ok : req.fail(n)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Dokumen pengesahan */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-red-500" />
                  Dokumen Pengesahan ({dokumen.length})
                </span>
                {!disahkan && isAdmin && (
                  <button
                    type="button"
                    onClick={() => fileRef.current?.click()}
                    disabled={uploading}
                    className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 flex items-center gap-1 disabled:opacity-50"
                    data-testid="pengesahan-upload-btn"
                  >
                    {uploading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Upload className="w-3 h-3" />}
                    {uploading ? "Mengunggah..." : "Unggah PDF"}
                  </button>
                )}
              </div>
              <input ref={fileRef} type="file" accept=".pdf" className="hidden" onChange={handleUpload} data-testid="pengesahan-file-input" />
              {dokumen.length === 0 ? (
                <p className="text-[11px] text-muted-foreground italic px-1">
                  Belum ada dokumen. Unggah PDF hasil pengesahan yang telah ditandatangani (maks {MAX_PDF_MB}MB, wajib minimal 1).
                </p>
              ) : (
                <div className="space-y-1">
                  {dokumen.map((doc) => (
                    <div key={doc.id} className="flex items-center gap-2 bg-muted rounded-lg px-2.5 py-1.5 min-w-0">
                      <FileText className="w-4 h-4 text-red-600 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-foreground/90 truncate" title={doc.name}>{doc.name}</p>
                        <p className="text-[10px] text-muted-foreground truncate">
                          {(doc.size / 1024 / 1024).toFixed(2)} MB • {doc.uploaded_by || "-"}
                        </p>
                      </div>
                      <button type="button" onClick={() => handleViewDoc(doc)} className="text-blue-600 hover:text-blue-800 flex-shrink-0" title="Lihat dokumen">
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                      {!disahkan && isAdmin && (
                        <button type="button" onClick={() => handleDeleteDoc(doc)} className="text-red-400 hover:text-red-600 flex-shrink-0" title="Hapus dokumen">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Aksi */}
            {disahkan ? (
              <Button variant="outline" className="w-full" onClick={onClose}>Tutup</Button>
            ) : !isAdmin ? (
              <p className="text-[11px] text-muted-foreground text-center">Hanya admin yang dapat mengesahkan kegiatan.</p>
            ) : sahkanStep ? (
              <div className="space-y-2 p-3 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20">
                <p className="text-xs text-red-700 dark:text-red-300 font-medium">
                  Setelah disahkan, seluruh data aset kegiatan ini <b>terkunci permanen</b> (tidak bisa ditambah, diubah, atau dihapus) dan riwayat pengesahan dicatat ke kartu inventarisasi. Lanjutkan?
                </p>
                <div className="flex gap-2">
                  <Button
                    className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white"
                    onClick={handleSahkan}
                    disabled={sahkanLoading}
                    data-testid="pengesahan-confirm-btn"
                  >
                    {sahkanLoading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <ShieldCheck className="w-4 h-4 mr-1" />}
                    {sahkanLoading ? "Mengesahkan..." : "Ya, Sahkan"}
                  </Button>
                  <Button variant="outline" onClick={() => setSahkanStep(false)} disabled={sahkanLoading}>
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            ) : (
              <Button
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-50"
                disabled={!canSahkan}
                onClick={() => setSahkanStep(true)}
                title={!status.eligible ? "Lengkapi semua syarat pengesahan terlebih dahulu" : dokumen.length === 0 ? "Unggah minimal 1 dokumen pengesahan" : ""}
                data-testid="pengesahan-sahkan-btn"
              >
                <ShieldCheck className="w-4 h-4 mr-1.5" />
                Sahkan Kegiatan
              </Button>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
