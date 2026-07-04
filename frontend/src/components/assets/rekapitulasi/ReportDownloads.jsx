import React, { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { getApiError } from "../../../lib/utils";
import {
  Download, BarChart3, BookOpen, FileText, Shield, FileWarning,
  CheckCircle2, XCircle, AlertTriangle, Settings, Loader2,
  Package, Check
} from "lucide-react";
import ReportSettingsEditor from "../ReportSettingsEditor";

const API = (process.env.REACT_APP_BACKEND_URL || "http://localhost:8001") + "/api";

const dbhiItems = [
  { type: "kondisi-baik", label: "Kondisi Baik", icon: CheckCircle2,
    activeClass: "bg-emerald-50 border-emerald-200 text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-900/30 dark:border-emerald-700 dark:text-emerald-300 dark:hover:bg-emerald-900/50",
    badgeClass: "bg-emerald-100 dark:bg-emerald-800/50",
    path: d => d.ditemukan?.kondisi_baik?.count },
  { type: "kondisi-rusak-ringan", label: "Rusak Ringan", icon: AlertTriangle,
    activeClass: "bg-amber-50 border-amber-200 text-amber-700 hover:bg-amber-100 dark:bg-amber-900/30 dark:border-amber-700 dark:text-amber-300 dark:hover:bg-amber-900/50",
    badgeClass: "bg-amber-100 dark:bg-amber-800/50",
    path: d => d.ditemukan?.kondisi_rusak_ringan?.count },
  { type: "kondisi-rusak-berat", label: "Rusak Berat", icon: XCircle,
    activeClass: "bg-red-50 border-red-200 text-red-700 hover:bg-red-100 dark:bg-red-900/30 dark:border-red-700 dark:text-red-300 dark:hover:bg-red-900/50",
    badgeClass: "bg-red-100 dark:bg-red-800/50",
    path: d => d.ditemukan?.kondisi_rusak_berat?.count },
  { type: "berlebih", label: "Berlebih", icon: FileWarning,
    activeClass: "bg-purple-50 border-purple-200 text-purple-700 hover:bg-purple-100 dark:bg-purple-900/30 dark:border-purple-700 dark:text-purple-300 dark:hover:bg-purple-900/50",
    badgeClass: "bg-purple-100 dark:bg-purple-800/50",
    path: d => d.berlebih?.count },
  { type: "tidak-ditemukan", label: "Tidak Ditemukan", icon: XCircle,
    activeClass: "bg-rose-50 border-rose-200 text-rose-700 hover:bg-rose-100 dark:bg-rose-900/30 dark:border-rose-700 dark:text-rose-300 dark:hover:bg-rose-900/50",
    badgeClass: "bg-rose-100 dark:bg-rose-800/50",
    path: d => d.tidak_ditemukan?.count },
  { type: "sengketa", label: "Sengketa", icon: Shield,
    activeClass: "bg-muted border-border text-foreground hover:bg-muted",
    badgeClass: "bg-muted",
    path: d => d.sengketa?.count },
];

const officialReports = [
  { key: "rhi", label: "RHI (Rekapitulasi)", icon: BarChart3,
    btn: "bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 dark:bg-indigo-700 dark:hover:bg-indigo-600 dark:disabled:bg-indigo-900/50 dark:disabled:text-indigo-400" },
  { key: "bahi", label: "BAHI (Berita Acara)", icon: BookOpen,
    btn: "bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 dark:bg-blue-700 dark:hover:bg-blue-600 dark:disabled:bg-blue-900/50 dark:disabled:text-blue-400" },
  { key: "sp-hasil", label: "SP Hasil", icon: Shield,
    btn: "bg-teal-600 hover:bg-teal-700 disabled:bg-teal-300 dark:bg-teal-700 dark:hover:bg-teal-600 dark:disabled:bg-teal-900/50 dark:disabled:text-teal-400" },
  { key: "sp-pelaksanaan", label: "SP Pelaksanaan", icon: FileText,
    btn: "bg-cyan-600 hover:bg-cyan-700 disabled:bg-cyan-300 dark:bg-cyan-700 dark:hover:bg-cyan-600 dark:disabled:bg-cyan-900/50 dark:disabled:text-cyan-400" },
];

const supportingDocs = [
  { key: "berita-acara", label: "BA Tidak Ditemukan", icon: BookOpen },
  { key: "sptjm", label: "SPTJM", icon: Shield },
  { key: "surat-koreksi", label: "Surat Koreksi", icon: FileWarning },
];

// Kolom tambahan opsional untuk kolom "Kondisi & Status" pada Data Aset eksekutif
const detailFieldOptions = [
  { key: "spm", label: "SPM" },
  { key: "perolehan", label: "Perolehan" },
  { key: "kontrak", label: "Kontrak" },
  { key: "bast", label: "BAST" },
  { key: "supplier", label: "Supplier" },
  { key: "serial", label: "S/N" },
];

const allBatchItems = [
  { key: "cover", label: "Sampul LHI", group: "lhi" },
  { key: "rhi", label: "RHI", group: "resmi" },
  { key: "bahi", label: "BAHI", group: "resmi" },
  { key: "sp-hasil", label: "SP Hasil", group: "resmi" },
  { key: "sp-pelaksanaan", label: "SP Pelaksanaan", group: "resmi" },
  { key: "dbhi-kondisi-baik", label: "DBHI Kondisi Baik", group: "dbhi" },
  { key: "dbhi-kondisi-rusak-ringan", label: "DBHI Rusak Ringan", group: "dbhi" },
  { key: "dbhi-kondisi-rusak-berat", label: "DBHI Rusak Berat", group: "dbhi" },
  { key: "dbhi-berlebih", label: "DBHI Berlebih", group: "dbhi" },
  { key: "dbhi-tidak-ditemukan", label: "DBHI Tidak Ditemukan", group: "dbhi" },
  { key: "dbhi-sengketa", label: "DBHI Sengketa", group: "dbhi" },
  { key: "berita-acara", label: "BA Tidak Ditemukan", group: "pendukung" },
  { key: "sptjm", label: "SPTJM", group: "pendukung" },
  { key: "surat-koreksi", label: "Surat Koreksi", group: "pendukung" },
  { key: "executive-summary", label: "Laporan Eksekutif", group: "pendukung" },
];

const batchGroupColors = {
  lhi: {
    active: "bg-amber-100 border-amber-300 text-amber-800 dark:bg-amber-900/40 dark:border-amber-600 dark:text-amber-300",
    inactive: "bg-card border-border text-muted-foreground hover:bg-muted",
  },
  resmi: {
    active: "bg-blue-100 border-blue-300 text-blue-800 dark:bg-blue-900/40 dark:border-blue-600 dark:text-blue-300",
    inactive: "bg-card border-border text-muted-foreground hover:bg-muted",
  },
  dbhi: {
    active: "bg-emerald-100 border-emerald-300 text-emerald-800 dark:bg-emerald-900/40 dark:border-emerald-600 dark:text-emerald-300",
    inactive: "bg-card border-border text-muted-foreground hover:bg-muted",
  },
  pendukung: {
    active: "bg-muted border-slate-400 text-foreground dark:border-slate-500",
    inactive: "bg-card border-border text-muted-foreground hover:bg-muted",
  },
};

export default function ReportDownloads({
  data, activityId, downloading, showSettings, setShowSettings,
  onDownloadPDF, onDownloadDBHI
}) {
  const [batchMode, setBatchMode] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [batchDownloading, setBatchDownloading] = useState(false);
  const [dataInfo, setDataInfo] = useState(null);
  const [dataDownloading, setDataDownloading] = useState(null);
  const [groupedDownloading, setGroupedDownloading] = useState(false);
  const [detailFields, setDetailFields] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("exec_detail_fields") || "[]");
      return new Set(Array.isArray(saved) ? saved : []);
    } catch { return new Set(); }
  });

  // Fetch data page info when component mounts
  useEffect(() => {
    if (!activityId) return;
    axios.get(`${API}/inventory-activities/${activityId}/executive-data-info`)
      .then(r => setDataInfo(r.data))
      .catch(() => setDataInfo(null));
  }, [activityId]);

  const toggleDetailField = (key) => {
    setDetailFields(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      localStorage.setItem("exec_detail_fields", JSON.stringify(Array.from(next)));
      return next;
    });
  };

  const detailFieldsParam = detailFields.size > 0
    ? `&detail_fields=${Array.from(detailFields).join(",")}`
    : "";

  const handleDownloadDataPage = async (pageNum, startIdx, endIdx) => {
    setDataDownloading(pageNum);
    try {
      const r = await axios.get(
        `${API}/inventory-activities/${activityId}/executive-data-pdf?page=${pageNum}${detailFieldsParam}`,
        { responseType: "blob" }
      );
      const url = window.URL.createObjectURL(new Blob([r.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `Data_Aset_${startIdx}-${endIdx}_${activityId.substring(0, 8)}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`Data Aset ${startIdx}-${endIdx} berhasil diunduh`);
    } catch (err) {
      toast.error("Gagal download: " + getApiError(err, err.message));
    } finally {
      setDataDownloading(null);
    }
  };

  const handleDownloadGrouped = async () => {
    setGroupedDownloading(true);
    try {
      const r = await axios.get(
        `${API}/inventory-activities/${activityId}/executive-grouped-pdf`,
        { responseType: "blob" }
      );
      const url = window.URL.createObjectURL(new Blob([r.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "Laporan_Eksekutif_Barang_Serupa.pdf");
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Laporan Eksekutif per Barang Serupa berhasil diunduh");
    } catch (err) {
      toast.error("Gagal download: " + getApiError(err, err.message));
    } finally {
      setGroupedDownloading(false);
    }
  };

  const toggleSelect = (key) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const selectAll = () => setSelected(new Set(allBatchItems.map(i => i.key)));
  const selectNone = () => setSelected(new Set());

  const handleBatchDownload = async () => {
    if (selected.size === 0) { toast.error("Pilih minimal satu laporan"); return; }
    setBatchDownloading(true);
    try {
      const r = await axios.post(
        `${API}/inventory-activities/${activityId}/batch-pdf-zip`,
        { types: Array.from(selected) },
        { responseType: "blob" }
      );
      const url = window.URL.createObjectURL(new Blob([r.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `Laporan_Batch_${activityId.substring(0, 8)}.zip`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`${selected.size} laporan berhasil diunduh sebagai ZIP`);
      setBatchMode(false);
      setSelected(new Set());
    } catch (err) {
      toast.error("Gagal download batch: " + getApiError(err, err.message));
    } finally {
      setBatchDownloading(false);
    }
  };

  return (
    <>
      {/* LHI Section */}
      <div className="border-t border-border pt-3 space-y-2">
        <div className="flex gap-2">
          <button data-testid="download-lhi" onClick={() => onDownloadPDF("lhi")} disabled={!!downloading}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-indigo-600 via-blue-600 to-cyan-600 hover:from-indigo-700 hover:via-blue-700 hover:to-cyan-700 disabled:from-indigo-300 disabled:via-blue-300 disabled:to-cyan-300 dark:from-indigo-700 dark:via-blue-700 dark:to-cyan-700 dark:hover:from-indigo-600 dark:hover:via-blue-600 dark:hover:to-cyan-600 text-white rounded-lg text-sm font-semibold transition-all shadow-sm">
            {downloading === "lhi" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            Download LHI Lengkap
          </button>
          <button data-testid="toggle-settings-btn" onClick={() => setShowSettings(p => !p)}
            className={`flex items-center gap-1 px-3 py-2 rounded-lg text-xs font-medium transition-all border ${
              showSettings
                ? "bg-slate-700 text-white border-slate-700 dark:bg-slate-600 dark:border-slate-500"
                : "bg-card border-border text-muted-foreground hover:bg-muted"
            }`}>
            <Settings className="w-3.5 h-3.5" /> Sampul
          </button>
        </div>
        <p className="text-[10px] text-muted-foreground text-center">Sampul + BAHI + RHI + 6 DBHI + SP Hasil + SP Pelaksanaan</p>
        {showSettings && <ReportSettingsEditor onClose={() => setShowSettings(false)} />}
      </div>

      {/* DBHI Buttons */}
      <div className="border-t border-border pt-3">
        <p className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1.5">
          <Download className="w-3.5 h-3.5" /> DBHI - Daftar Barang Hasil Inventarisasi
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
          {dbhiItems.map(({ type, label, icon: Icon, activeClass, badgeClass, path }) => {
            const count = path(data) || 0;
            return (
              <button key={type} data-testid={`dbhi-download-${type}`}
                onClick={() => onDownloadDBHI(type, label)}
                disabled={!!downloading || count <= 0}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all border ${
                  count > 0 ? activeClass : "bg-muted border-border text-muted-foreground cursor-not-allowed"
                }`}>
                {downloading === type ? <Loader2 className="w-3 h-3 animate-spin" /> : <Icon className="w-3 h-3" />}
                <span className="truncate">{label}</span>
                <span className={`ml-auto text-[10px] px-1 rounded ${count > 0 ? badgeClass : 'bg-muted'}`}>{count}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Official Reports */}
      <div className="border-t border-border pt-3">
        <p className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1.5">
          <FileText className="w-3.5 h-3.5" /> Laporan Resmi Inventarisasi
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 mb-2">
          {officialReports.map(({ key, label, icon: Icon, btn }) => (
            <button key={key} data-testid={`download-${key}`} onClick={() => onDownloadPDF(key)} disabled={!!downloading}
              className={`flex items-center gap-1.5 px-2.5 py-2 ${btn} text-white rounded-lg text-[11px] font-medium transition-colors`}>
              {downloading === key ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Icon className="w-3.5 h-3.5" />}
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Executive Summary Section */}
      <div className="border-t border-border pt-3">
        <p className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1.5">
          <BarChart3 className="w-3.5 h-3.5" /> Laporan Eksekutif Inventarisasi BMN
        </p>
        <div className="space-y-1.5">
          <button data-testid="download-executive-summary" onClick={() => onDownloadPDF("executive-summary")} disabled={!!downloading}
            className="w-full flex items-center justify-center gap-2 px-3 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 disabled:from-emerald-300 disabled:to-teal-300 dark:from-emerald-700 dark:to-teal-700 dark:hover:from-emerald-600 dark:hover:to-teal-600 text-white rounded-lg text-xs font-semibold transition-all shadow-sm">
            {downloading === "executive-summary" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            Ringkasan Eksekutif (Distribusi, Analisis, Tim)
          </button>
          <button data-testid="download-executive-grouped" onClick={handleDownloadGrouped} disabled={!!downloading || groupedDownloading}
            className="w-full flex items-center justify-center gap-2 px-3 py-2.5 bg-gradient-to-r from-sky-600 to-cyan-600 hover:from-sky-700 hover:to-cyan-700 disabled:from-sky-300 disabled:to-cyan-300 dark:from-sky-700 dark:to-cyan-700 dark:hover:from-sky-600 dark:hover:to-cyan-600 text-white rounded-lg text-xs font-semibold transition-all shadow-sm">
            {groupedDownloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            Eksekutif per Barang Serupa (PDF)
          </button>
          {dataInfo && dataInfo.total_assets > 0 && (
            <div className="flex flex-wrap items-center gap-1" data-testid="exec-detail-fields">
              <span className="text-[10px] text-muted-foreground mr-0.5">Kolom tambahan:</span>
              {detailFieldOptions.map(({ key, label }) => (
                <label key={key} data-testid={`detail-field-${key}`}
                  className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] cursor-pointer transition-colors border ${
                    detailFields.has(key)
                      ? "bg-teal-100 border-teal-300 text-teal-800 dark:bg-teal-900/40 dark:border-teal-600 dark:text-teal-300"
                      : "bg-card border-border text-muted-foreground hover:bg-muted"
                  }`}>
                  <input type="checkbox" checked={detailFields.has(key)} onChange={() => toggleDetailField(key)} className="hidden" />
                  {detailFields.has(key) && <Check className="w-2.5 h-2.5" />}
                  {label}
                </label>
              ))}
            </div>
          )}
          {dataInfo && dataInfo.total_assets > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
              {dataInfo.pages.map(p => (
                <button key={p.page} data-testid={`download-data-page-${p.page}`}
                  onClick={() => handleDownloadDataPage(p.page, p.start, p.end)}
                  disabled={!!downloading || dataDownloading !== null}
                  className="flex items-center gap-1.5 px-2.5 py-2 bg-teal-50 border border-teal-200 text-teal-700 hover:bg-teal-100 dark:bg-teal-900/30 dark:border-teal-700 dark:text-teal-300 dark:hover:bg-teal-900/50 rounded-lg text-[11px] font-medium transition-colors">
                  {dataDownloading === p.page ? <Loader2 className="w-3 h-3 animate-spin" /> : <FileText className="w-3 h-3" />}
                  Data Aset {p.start}-{p.end}
                  <span className="ml-auto text-[10px] px-1 rounded bg-teal-100 dark:bg-teal-800/50">{p.count}</span>
                </button>
              ))}
            </div>
          )}
          {dataInfo && dataInfo.total_assets === 0 && (
            <p className="text-[10px] text-muted-foreground text-center">Belum ada data aset</p>
          )}
        </div>
      </div>

      {/* Supporting Documents */}
      <div className="border-t border-border pt-3">
        <p className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1.5">
          <FileText className="w-3.5 h-3.5" /> Dokumen Pendukung Lainnya
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {supportingDocs.map(({ key, label, icon: Icon }) => (
            <button key={key} onClick={() => onDownloadPDF(key)} disabled={!!downloading}
              className="flex items-center gap-2 px-3 py-2 bg-slate-600 hover:bg-slate-700 disabled:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 dark:disabled:bg-slate-800/50 dark:disabled:text-slate-500 text-white rounded-lg text-xs font-medium transition-colors">
              {downloading === key ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Icon className="w-3.5 h-3.5" />}
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Batch Download ZIP */}
      <div className="border-t border-border pt-3">
        <button
          data-testid="toggle-batch-mode"
          onClick={() => setBatchMode(p => !p)}
          className={`w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold transition-all border ${
            batchMode
              ? "bg-amber-50 border-amber-300 text-amber-700 dark:bg-amber-900/30 dark:border-amber-600 dark:text-amber-300"
              : "bg-card border-border text-muted-foreground hover:bg-muted"
          }`}
        >
          <Package className="w-4 h-4" />
          {batchMode ? "Tutup Batch Download" : "Batch Download (ZIP)"}
        </button>

        {batchMode && (
          <div className="mt-2 bg-amber-50/50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg p-3 space-y-2" data-testid="batch-download-panel">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-amber-800 dark:text-amber-300">Pilih laporan yang ingin diunduh:</p>
              <div className="flex gap-2">
                <button onClick={selectAll} className="text-[10px] text-amber-700 dark:text-amber-400 hover:text-amber-900 dark:hover:text-amber-200 underline">Pilih Semua</button>
                <button onClick={selectNone} className="text-[10px] text-muted-foreground hover:text-foreground underline">Hapus Semua</button>
              </div>
            </div>

            {["lhi", "resmi", "dbhi", "pendukung"].map(group => {
              const groupLabels = { lhi: "Umum", resmi: "Laporan Resmi", dbhi: "DBHI", pendukung: "Pendukung" };
              const items = allBatchItems.filter(i => i.group === group);
              const colors = batchGroupColors[group];
              return (
                <div key={group} className="space-y-1">
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">{groupLabels[group]}</p>
                  <div className="flex flex-wrap gap-1">
                    {items.map(({ key, label }) => (
                      <label key={key} className={`flex items-center gap-1.5 px-2 py-1 rounded text-[11px] cursor-pointer transition-colors border ${
                        selected.has(key) ? colors.active : colors.inactive
                      }`}>
                        <input type="checkbox" checked={selected.has(key)} onChange={() => toggleSelect(key)} className="hidden" />
                        {selected.has(key) && <Check className="w-3 h-3" />}
                        {label}
                      </label>
                    ))}
                  </div>
                </div>
              );
            })}

            <button
              data-testid="batch-download-btn"
              onClick={handleBatchDownload}
              disabled={batchDownloading || selected.size === 0}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-amber-600 hover:bg-amber-700 disabled:bg-amber-300 dark:bg-amber-700 dark:hover:bg-amber-600 dark:disabled:bg-amber-900/50 dark:disabled:text-amber-400 text-white rounded-lg text-xs font-semibold transition-colors"
            >
              {batchDownloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Package className="w-4 h-4" />}
              Download {selected.size} Laporan sebagai ZIP
            </button>
          </div>
        )}
      </div>
    </>
  );
}
