import React, { useState, useRef } from "react";
import { Upload, FileText, FileSpreadsheet, Loader2, CheckCircle2, AlertTriangle } from "lucide-react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "../ui/dialog";
import { toast } from "sonner";
import axios from "axios";
import { getApiError } from "../../lib/utils";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function ImportDialog({ open, onClose, onSuccess, activityId, preloadFile }) {
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState(null);
  const fileRef = useRef(null);

  // Process a file (shared between file input and drag-drop preload)
  const processFile = async (file) => {
    if (!file) return;
    if (!activityId) { toast.error("Tidak ada kegiatan inventarisasi yang dipilih"); return; }
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['csv', 'xlsx', 'xls'].includes(ext)) { toast.error("Format: CSV / Excel (.xlsx)"); return; }
    setImporting(true); setResult(null);
    const fd = new FormData(); fd.append("file", file);
    try {
      const res = await axios.post(`${API}/import?activity_id=${activityId}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      setResult(res.data);
      if (res.data.success) { toast.success(res.data.message); onSuccess(); }
    } catch (err) {
      const detail = getApiError(err, "Gagal import");
      setResult({ success: false, message: detail, errors: [detail], duplicates: [] });
    } finally { setImporting(false); }
  };

  const handleFileSelect = async e => {
    processFile(e.target.files?.[0]);
  };

  // Auto-process preloaded file from drag & drop
  const preloadProcessed = useRef(false);
  React.useEffect(() => {
    if (preloadFile && open && !preloadProcessed.current) {
      preloadProcessed.current = true;
      processFile(preloadFile);
    }
    if (!open) preloadProcessed.current = false;
  }, [preloadFile, open]);
  
  const handleForceUpdate = async () => {
    if (!fileRef.current?.files?.[0]) { toast.error("Pilih file kembali"); return; }
    if (!activityId) { toast.error("Tidak ada kegiatan inventarisasi yang dipilih"); return; }
    setImporting(true);
    const fd = new FormData(); fd.append("file", fileRef.current.files[0]);
    try {
      const res = await axios.post(`${API}/import?force_update=true&activity_id=${activityId}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      setResult(res.data);
      if (res.data.success) { toast.success(res.data.message); onSuccess(); }
    } catch (err) { toast.error(getApiError(err, "Gagal import")); }
    finally { setImporting(false); }
  };
  
  const dlCSV = async () => { try { const r = await axios.get(`${API}/templates/csv`, { responseType: 'blob' }); const u = URL.createObjectURL(new Blob([r.data])); const a = document.createElement('a'); a.href = u; a.download = 'template_import_aset.csv'; a.click(); toast.success("Template CSV didownload"); } catch { toast.error("Gagal download"); } };
  const dlXlsx = async () => { try { const r = await axios.get(`${API}/templates/xlsx`, { responseType: 'blob' }); const u = URL.createObjectURL(new Blob([r.data])); const a = document.createElement('a'); a.href = u; a.download = 'template_import_aset.xlsx'; a.click(); toast.success("Template Excel didownload"); } catch { toast.error("Gagal download"); } };
  
  const reset = () => { setResult(null); setImporting(false); if (fileRef.current) fileRef.current.value = ""; onClose(); };
  
  return (
    <Dialog open={open} onOpenChange={reset}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto" aria-describedby="import-dialog-desc">
        <DialogHeader><DialogTitle className="flex items-center gap-2"><Upload className="w-5 h-5 text-blue-600" />Import Data Aset</DialogTitle></DialogHeader>
        <div className="space-y-3" id="import-dialog-desc">
          <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3 space-y-2">
            <p className="text-sm font-medium text-blue-800 dark:text-blue-300">Download Template</p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={dlCSV} className="flex-1 text-xs" data-testid="import-dl-csv"><FileText className="w-3.5 h-3.5 mr-1" />CSV</Button>
              <Button variant="outline" size="sm" onClick={dlXlsx} className="flex-1 text-xs" data-testid="import-dl-xlsx"><FileSpreadsheet className="w-3.5 h-3.5 mr-1" />Excel (Dropdown)</Button>
            </div>
          </div>
          <div className="bg-amber-50 dark:bg-amber-900/20 rounded-lg p-2.5">
            <p className="text-xs font-medium text-amber-800 dark:text-amber-300 mb-1">Aturan Validasi</p>
            <ul className="text-[11px] text-amber-700 dark:text-amber-400 space-y-0.5 list-disc list-inside">
              <li><b>asset_code</b>: 10 digit angka (wajib)</li>
              <li><b>asset_name, category</b>: wajib diisi</li>
              <li><b>kode_register</b>: 32 karakter hex</li>
              <li><b>nomor_spm</b>: format 02847T/621001/2024</li>
              <li><b>condition/status</b>: sesuai dropdown</li>
              <li><b>Tidak boleh duplikat</b>: Kode Aset + NUP dan Kode Register harus unik dalam 1 file</li>
            </ul>
          </div>
          <div className="space-y-1.5">
            <Label>Pilih File (CSV / Excel)</Label>
            {preloadFile && (
              <div className="flex items-center gap-2 text-xs text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 px-2 py-1.5 rounded" data-testid="import-preload-info">
                <FileSpreadsheet className="w-3.5 h-3.5" />
                <span>File: <b>{preloadFile.name}</b> (drag & drop)</span>
              </div>
            )}
            <Input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" onChange={handleFileSelect} disabled={importing} data-testid="import-file-input" />
            {importing && <div className="flex items-center gap-2 text-sm text-blue-600"><Loader2 className="w-4 h-4 animate-spin" />Memproses...</div>}
          </div>
          {result && (
            <div className={`rounded-lg p-3 ${result.success ? 'bg-emerald-50 dark:bg-emerald-900/20' : 'bg-red-50 dark:bg-red-900/20'}`} data-testid="import-result">
              <div className="flex items-start gap-2">
                {result.success ? <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400 flex-shrink-0" /> : <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0" />}
                <p className={`text-sm font-medium ${result.success ? 'text-emerald-800 dark:text-emerald-300' : 'text-red-800 dark:text-red-300'}`}>{result.message}</p>
              </div>
              {result.errors?.length > 0 && (
                <div className="bg-card rounded p-2 mt-2 max-h-40 overflow-y-auto">
                  <p className="text-xs font-medium text-red-700 dark:text-red-400 mb-1">Detail Kesalahan:</p>
                  {result.errors.map((e, i) => <p key={i} className="text-xs text-red-600 dark:text-red-400 py-0.5 border-b border-red-100 dark:border-red-800 last:border-0">{e}</p>)}
                </div>
              )}
              {result.duplicates?.length > 0 && (
                <div className="bg-card rounded p-2 mt-2">
                  <p className="text-xs font-medium text-amber-700 dark:text-amber-400 mb-1">Data Duplikat:</p>
                  <div className="max-h-32 overflow-y-auto space-y-1">
                    {result.duplicates.map((d, i) => (
                      <div key={i} className="text-xs p-1 bg-amber-50 dark:bg-amber-900/20 rounded">Baris {d.row}: <b>{d.asset_code}</b> - {d.asset_name}</div>
                    ))}
                  </div>
                  <div className="flex gap-2 mt-2">
                    <Button size="sm" variant="outline" onClick={reset} className="flex-1 text-xs">Batalkan</Button>
                    <Button size="sm" onClick={handleForceUpdate} disabled={importing} className="flex-1 text-xs bg-amber-600 hover:bg-amber-700 text-white">
                      {importing && <Loader2 className="w-3 h-3 animate-spin mr-1" />}Update Data Lama
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default ImportDialog;
