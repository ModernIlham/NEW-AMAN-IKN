import React, { memo, useState } from "react";
import { Check, X, Plus, FileUp, FileText, ClipboardList } from "lucide-react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { toast } from "sonner";
import { compressImageFile } from "../../lib/imageCompression";
import { compressPdfFile } from "../../lib/pdfCompression";
import { authMediaUrl } from "../../lib/mediaUrl";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Default document items
const DEFAULT_DOC_ITEMS = [
  "Buku Manual", "Charger/Adapter", "Kabel USB", "Kartu Garansi", "CD Driver"
];

// ============================================================================
// DOCUMENT CHECKLIST WITH FILE UPLOAD - IMPROVED
// ============================================================================
//
// Photos & documents stored on existing assets are NOT shipped inline in the
// `/checklist-full` JSON payload (would balloon the response to many MB). The
// frontend instead receives:
//   - photos: ["__existing__:<origIdx>", "__existing__:<origIdx>", ...]
//   - photo_thumbnails: tiny base64 thumbs from the server
//   - documents: [{name, idx}]
// and renders photos via streaming URLs and PDFs via a streaming "Lihat" link.
// New uploads still use base64 data URLs in the same array slots.
//
// `assetVersion` is appended as a ?v= cache-buster to every streaming URL:
// the endpoints send long-lived Cache-Control/ETag headers, and any edit
// bumps the asset version (OCC) so a fresh URL bypasses the stale cache.
const DocumentChecklist = memo(({ checklist, onChange, assetId, assetVersion = 1 }) => {
  const [customItem, setCustomItem] = useState("");
  const [previewImg, setPreviewImg] = useState(null);

  const isExistingPhoto = (p) => typeof p === "string" && p.startsWith("__existing__:");
  const existingPhotoIdx = (p) => {
    const n = parseInt(String(p).split(":", 2)[1], 10);
    return Number.isFinite(n) ? n : -1;
  };
  const isExistingDoc = (d) =>
    !!d && typeof d.data === "string" && d.data.startsWith("__existing__:");
  const existingDocIdx = (d) => {
    const n = parseInt(String(d?.data || "").split(":", 2)[1], 10);
    return Number.isFinite(n) ? n : -1;
  };
  const photoSrcFor = (item, photo, photoIdx) => {
    if (isExistingPhoto(photo)) {
      // Prefer the inline thumbnail (already loaded with /checklist-full) for
      // fast rendering. Fall back to the streaming endpoint if no thumb.
      const thumbs = item.photo_thumbnails || [];
      const origIdx = existingPhotoIdx(photo);
      if (origIdx >= 0 && origIdx < thumbs.length && thumbs[origIdx]) {
        return thumbs[origIdx];
      }
      const itemIdx = checklist.indexOf(item);
      if (assetId && itemIdx >= 0 && origIdx >= 0) {
        return authMediaUrl(`${API}/assets/${assetId}/checklist/${itemIdx}/photos/${origIdx}?v=${assetVersion}`);
      }
      return "";
    }
    return photo;
  };

  const toggleItem = idx => { const u = [...checklist]; u[idx] = { ...u[idx], checked: !u[idx].checked }; onChange(u); };
  
  const handleFileUpload = async (idx, e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;

    for (const file of files) {
      if (file.size > 25 * 1024 * 1024) { toast.error(`${file.name} terlalu besar (maks 25MB)`); continue; }
      try {
        let data;
        if (file.type === 'application/pdf') {
          // PDFs: compress via backend (iLoveAPI → WhipDoc fallback)
          const tId = toast.loading(`Mengompres ${file.name}...`);
          const { dataUrl, originalBytes, compressedBytes, method, savingsPercent, error } =
            await compressPdfFile(file);
          data = dataUrl;
          if (error) {
            toast.warning(`${file.name}: kompresi gagal, file asli digunakan`, { id: tId });
          } else if (savingsPercent > 0) {
            toast.success(
              `${file.name}: ${(originalBytes/1024/1024).toFixed(1)}MB → ${(compressedBytes/1024/1024).toFixed(1)}MB (-${savingsPercent}% via ${method})`,
              { id: tId }
            );
          } else {
            toast.success(`${file.name} berhasil diupload`, { id: tId });
          }
          const u = [...checklist];
          if ((u[idx].documents || []).length >= 1) { toast.error("Maksimal 1 dokumen PDF"); continue; }
          u[idx] = { ...u[idx], documents: [...(u[idx].documents || []), { name: file.name, data }] };
          onChange(u);
        } else if (file.type.startsWith('image/')) {
          // Images: compress client-side (10x smaller payload)
          data = await compressImageFile(file);
          const u = [...checklist];
          if ((u[idx].photos || []).length >= 3) { toast.error("Maksimal 3 foto per item"); continue; }
          u[idx] = { ...u[idx], photos: [...(u[idx].photos || []), data] };
          onChange(u);
          toast.success(`${file.name} berhasil diupload`);
        }
      } catch (err) {
        toast.error(`Gagal memproses ${file.name}: ${err.message || err}`);
      }
    }
    e.target.value = "";
  };
  
  const removeFile = (idx, type, fileIdx) => {
    const u = [...checklist];
    if (type === 'photo') { u[idx] = { ...u[idx], photos: (u[idx].photos || []).filter((_, i) => i !== fileIdx) }; }
    else { u[idx] = { ...u[idx], documents: (u[idx].documents || []).filter((_, i) => i !== fileIdx) }; }
    onChange(u);
  };
  
  const openPdf = (doc, itemIdx, docIdx) => {
    try {
      // Existing PDF (loaded from server) — open the streaming endpoint in a
      // new tab. The browser handles auth (cookies/header are not needed since
      // the asset endpoints are public on this deployment) and cache.
      if (isExistingDoc(doc) && assetId) {
        const origIdx = existingDocIdx(doc);
        if (origIdx < 0) {
          toast.error("Indeks dokumen tidak valid");
          return;
        }
        const url = authMediaUrl(`${API}/assets/${assetId}/checklist/${itemIdx}/documents/${origIdx}?v=${assetVersion}`);
        const w = window.open(url, "_blank");
        if (!w) {
          toast.error("Popup diblokir. Izinkan popup untuk melihat PDF.");
        }
        return;
      }

      // New upload (still inline base64) — fall back to the original blob path.
      const pdfData = doc?.data;
      if (!pdfData || typeof pdfData !== "string") {
        toast.error("Data PDF tidak valid");
        return;
      }
      let dataUrl = pdfData;
      if (!pdfData.startsWith("data:")) {
        dataUrl = `data:application/pdf;base64,${pdfData}`;
      }
      const base64Match = dataUrl.match(/base64,(.+)/);
      if (!base64Match) {
        toast.error("Format PDF tidak valid");
        return;
      }
      const base64Data = base64Match[1];
      const binaryString = atob(base64Data);
      const len = binaryString.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) bytes[i] = binaryString.charCodeAt(i);
      const blob = new Blob([bytes], { type: "application/pdf" });
      const url = URL.createObjectURL(blob);
      const newWindow = window.open(url, "_blank");
      if (!newWindow) {
        toast.error("Popup diblokir. Izinkan popup untuk melihat PDF.");
        const a = document.createElement("a");
        a.href = url;
        a.download = doc?.name || "document.pdf";
        a.click();
      }
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      console.error("Error opening PDF:", err);
      toast.error("Gagal membuka PDF. File mungkin rusak.");
    }
  };
  
  const addCustom = () => {
    if (!customItem.trim()) return;
    if (checklist.some(i => i.name.toLowerCase() === customItem.trim().toLowerCase())) { toast.error("Item sudah ada"); return; }
    onChange([...checklist, { name: customItem.trim(), checked: false, notes: "", photos: [], documents: [] }]);
    setCustomItem("");
  };
  
  const removeItem = idx => onChange(checklist.filter((_, i) => i !== idx));
  const checkedCount = checklist.filter(i => i.checked).length;
  const totalFiles = checklist.reduce((sum, item) => sum + (item.photos?.length || 0) + (item.documents?.length || 0), 0);
  
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label className="flex items-center gap-1.5"><ClipboardList className="w-4 h-4 text-blue-600" />Kelengkapan Dokumen & Peralatan</Label>
        <div className="flex gap-1">
          <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">{checkedCount}/{checklist.length}</span>
          {totalFiles > 0 && <span className="text-xs text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/30 px-2 py-0.5 rounded-full">{totalFiles} file</span>}
        </div>
      </div>
      <div className="bg-muted rounded-lg p-2 space-y-1.5 max-h-[400px] overflow-y-auto">
        {checklist.map((item, idx) => {
          const hasFiles = (item.photos?.length || 0) + (item.documents?.length || 0) > 0;
          return (
            <div key={idx} className={`rounded-lg transition-colors ${item.checked ? 'bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-700' : 'bg-card border border-border'}`}>
              <div className="flex items-center gap-2 p-2">
                <button type="button" onClick={() => toggleItem(idx)}
                  className={`w-5 h-5 rounded border flex items-center justify-center flex-shrink-0 ${item.checked ? 'bg-emerald-500 border-emerald-500 text-white' : 'border-border hover:border-blue-400'}`}>
                  {item.checked && <Check className="w-3 h-3" />}
                </button>
                <span className={`text-sm flex-1 ${item.checked ? 'text-emerald-700 dark:text-emerald-400 font-medium' : 'text-foreground'}`}>{item.name}</span>
                {hasFiles && <span className="text-[10px] text-emerald-600 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-900/40 px-1.5 py-0.5 rounded">{(item.photos?.length || 0) + (item.documents?.length || 0)} file</span>}
                {!DEFAULT_DOC_ITEMS.includes(item.name) && (
                  <button type="button" onClick={() => removeItem(idx)} className="text-red-400 hover:text-red-600"><X className="w-3.5 h-3.5" /></button>
                )}
              </div>
              {item.checked && (
                <div className="px-2 pb-2 space-y-2">
                  <div className="flex gap-1.5">
                    <label className="flex-1">
                      <input type="file" accept="image/*,.pdf" multiple className="hidden" onChange={e => handleFileUpload(idx, e)} />
                      <div className="flex items-center justify-center gap-1 text-xs text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 hover:bg-blue-100 dark:hover:bg-blue-900/50 rounded px-2 py-1.5 cursor-pointer transition-colors border border-blue-200 dark:border-blue-700 border-dashed">
                        <FileUp className="w-3.5 h-3.5" />Upload Foto/Dokumen
                      </div>
                    </label>
                  </div>
                  <div className="text-[10px] text-muted-foreground">Maks 3 foto + 1 PDF per item</div>
                  
                  {/* File preview section - IMPROVED */}
                  {hasFiles && (
                    <div className="bg-card rounded-lg p-2 border border-border space-y-2">
                      <div className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">File Terupload:</div>
                      
                      {/* Photos */}
                      {(item.photos?.length || 0) > 0 && (
                        <div className="space-y-1">
                          <div className="text-[10px] text-muted-foreground">Foto ({item.photos.length}/3):</div>
                          <div className="flex gap-2 flex-wrap">
                            {item.photos.map((photo, pi) => {
                              const src = photoSrcFor(item, photo, pi);
                              const previewSrc = isExistingPhoto(photo) && assetId
                                ? authMediaUrl(`${API}/assets/${assetId}/checklist/${idx}/photos/${existingPhotoIdx(photo)}?v=${assetVersion}`)
                                : src;
                              return (
                                <div key={pi} className="relative group">
                                  <img
                                    src={src}
                                    alt={`${item.name} foto ${pi+1}`}
                                    className="w-14 h-14 sm:w-16 sm:h-16 object-cover rounded-lg border-2 border-border cursor-pointer hover:border-blue-400 transition-colors"
                                    onClick={() => setPreviewImg(previewSrc)}
                                  />
                                  <button type="button" onClick={() => removeFile(idx, 'photo', pi)}
                                    className="absolute -top-1 -right-1 w-4 h-4 sm:w-5 sm:h-5 bg-red-500 text-white rounded-full flex items-center justify-center shadow-md hover:bg-red-600 transition-colors">
                                    <X className="w-2.5 h-2.5 sm:w-3 sm:h-3" />
                                  </button>
                                  <div className="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-[8px] text-center py-0.5 rounded-b-lg">
                                    Foto {pi+1}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                      
                      {/* Documents */}
                      {(item.documents?.length || 0) > 0 && (
                        <div className="space-y-1">
                          <div className="text-[10px] text-muted-foreground">Dokumen PDF:</div>
                          {item.documents.map((doc, di) => (
                            <div key={di} className="flex items-center gap-2 bg-red-50 dark:bg-red-900/20 rounded-lg px-2 py-1.5 border border-red-200 dark:border-red-700">
                              <FileText className="w-4 h-4 text-red-600 dark:text-red-400 flex-shrink-0" />
                              <span className="text-xs text-red-700 dark:text-red-400 flex-1 min-w-0 truncate max-w-[120px] sm:max-w-[180px]" title={doc.name}>{doc.name}</span>
                              <button
                                type="button"
                                onClick={() => openPdf(doc, idx, di)}
                                className="text-[10px] text-blue-600 hover:text-blue-800 underline"
                                data-testid={`checklist-doc-view-${idx}-${di}`}
                              >
                                Lihat
                              </button>
                              <button type="button" onClick={() => removeFile(idx, 'doc', di)} className="text-red-400 hover:text-red-600">
                                <X className="w-4 h-4" />
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="flex gap-1.5">
        <Input placeholder="Tambah item lain..." value={customItem} onChange={e => setCustomItem(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), addCustom())} className="h-8 text-sm" />
        <Button type="button" variant="outline" size="sm" onClick={addCustom} className="h-8 px-2"><Plus className="w-3.5 h-3.5" /></Button>
      </div>
      
      {/* Image Preview Modal */}
      {previewImg && (
        <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4" onClick={() => setPreviewImg(null)}>
          <div className="relative max-w-3xl max-h-[90vh]">
            <img src={previewImg} alt="Preview" className="max-w-full max-h-[85vh] object-contain rounded-lg" />
            <button 
              onClick={() => setPreviewImg(null)}
              className="absolute -top-3 -right-3 w-8 h-8 bg-card text-foreground rounded-full flex items-center justify-center shadow-lg hover:bg-muted"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
});
DocumentChecklist.displayName = "DocumentChecklist";

export { DocumentChecklist, DEFAULT_DOC_ITEMS };
