import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { getApiError } from "../../lib/utils";
import { ChevronDown, ChevronUp, BarChart3, Loader2 } from "lucide-react";

import SummaryCards from "./rekapitulasi/SummaryCards";
import ConditionBreakdown from "./rekapitulasi/ConditionBreakdown";
import InventoryProgress from "./rekapitulasi/InventoryProgress";
import TidakDitemukanBreakdown from "./rekapitulasi/TidakDitemukanBreakdown";
import ReportDownloads from "./rekapitulasi/ReportDownloads";

const API = (process.env.REACT_APP_BACKEND_URL || "http://localhost:8001") + "/api";

function RekapitulasiPanel({ activityId, isOpen, onToggle }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState("");
  const [showSettings, setShowSettings] = useState(false);

  const fetchData = useCallback(async () => {
    if (!activityId || !isOpen) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/inventory-activities/${activityId}/rekapitulasi`);
      setData(r.data);
    } catch (err) {
      console.error("Failed to fetch rekapitulasi:", err);
    } finally {
      setLoading(false);
    }
  }, [activityId, isOpen]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleDownloadPDF = async (type) => {
    setDownloading(type);
    try {
      const endpoints = {
        "berita-acara": "berita-acara-pdf", "sptjm": "sptjm-pdf",
        "surat-koreksi": "surat-koreksi-pdf", "rhi": "rhi-pdf",
        "bahi": "bahi-pdf", "sp-hasil": "sp-hasil-pdf",
        "sp-pelaksanaan": "sp-pelaksanaan-pdf", "lhi": "lhi-pdf",
        "executive-summary": "executive-summary-pdf"
      };
      const filenames = {
        "berita-acara": "Berita_Acara", "sptjm": "SPTJM",
        "surat-koreksi": "Surat_Koreksi", "rhi": "RHI",
        "bahi": "BAHI", "sp-hasil": "SP_Hasil",
        "sp-pelaksanaan": "SP_Pelaksanaan", "lhi": "LHI_Lengkap",
        "executive-summary": "Laporan_Eksekutif"
      };
      const endpoint = endpoints[type];
      if (!endpoint) return;
      const r = await axios.get(`${API}/inventory-activities/${activityId}/${endpoint}`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([r.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `${filenames[type] || type}_${activityId.substring(0, 8)}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`${filenames[type] || type} berhasil diunduh`);
    } catch (err) {
      toast.error("Gagal download: " + getApiError(err, err.message));
    } finally {
      setDownloading("");
    }
  };

  const handleDownloadDBHI = async (type, label) => {
    setDownloading(type);
    try {
      const r = await axios.get(`${API}/inventory-activities/${activityId}/dbhi/${type}`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([r.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `DBHI_${label.replace(/\s/g, "_")}_${activityId.substring(0, 8)}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`DBHI ${label} berhasil diunduh`);
    } catch (err) {
      toast.error("Gagal download DBHI: " + getApiError(err, err.message));
    } finally {
      setDownloading("");
    }
  };

  const total = data?.total_bmn_diteliti || 0;

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden mb-2 print:hidden" data-testid="rekapitulasi-panel">
      {/* Toggle Header */}
      <button onClick={onToggle} className="w-full flex items-center justify-between px-4 py-2 hover:bg-muted transition-colors">
        <div className="flex items-center gap-2 text-sm font-medium text-foreground">
          <BarChart3 className="w-4 h-4 text-blue-600" />
          <span>Rekapitulasi Inventarisasi</span>
          {data && !loading && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">{total} BMN</span>
          )}
        </div>
        {isOpen ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
      </button>

      {/* Content */}
      {isOpen && (
        <div className="border-t border-border px-4 py-3 space-y-3">
          {loading ? (
            <div className="flex items-center justify-center py-4 gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
              <span className="text-sm text-muted-foreground">Memuat rekapitulasi...</span>
            </div>
          ) : !data || total === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">Belum ada data aset untuk direkapitulasi.</p>
          ) : (
            <>
              <SummaryCards data={data} total={total} />
              <ConditionBreakdown ditemukan={data.ditemukan} />
              <InventoryProgress data={data} total={total} />
              <TidakDitemukanBreakdown tidakDitemukan={data.tidak_ditemukan} subBreakdown={data.sub_breakdown} />
              <ReportDownloads
                data={data}
                activityId={activityId}
                downloading={downloading}
                showSettings={showSettings}
                setShowSettings={setShowSettings}
                onDownloadPDF={handleDownloadPDF}
                onDownloadDBHI={handleDownloadDBHI}
              />
            </>
          )}
        </div>
      )}
    </div>
  );
}

RekapitulasiPanel.displayName = "RekapitulasiPanel";
export default RekapitulasiPanel;
