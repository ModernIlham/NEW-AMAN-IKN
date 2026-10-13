import React, { memo, useState } from "react";
import { Check, X, Plus, FileUp, FileText, ClipboardList, Trash2 } from "lucide-react";
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

    // SATU salinan kerja untuk SELURUH loop, bukan `[...checklist]` baru tiap
    // iterasi. `checklist` adalah prop yang nilainya BEKU selama callback ini
    // berjalan — ia tidak ikut berubah walau onChange sudah dipanggil. Dulu
    // tiap iterasi menyalin daftar yang sama (tanpa hasil iterasi sebelumnya)
    // lalu memanggil onChange, sehingga memilih 3 foto sekaligus hanya
    // menyisakan yang TERAKHIR — dua lainnya lenyap tanpa satu pesan pun, dan
    // batas "maks 3 foto" pun dihitung dari cacah yang basi.
    let kerja = [...checklist];
    let berubah = false;

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
          if ((kerja[idx].documents || []).length >= 1) { toast.error("Maksimal 1 dokumen PDF"); continue; }
          kerja[idx] = { ...kerja[idx], documents: [...(kerja[idx].documents || []), { name: file.name, data }] };
          berubah = true;
        } else if (file.type.startsWith('image/')) {
          // Images: compress client-side (10x smaller payload)
          data = await compressImageFile(file);
          if ((kerja[idx].photos || []).length >= 3) { toast.error("Maksimal 3 foto per item"); continue; }
          kerja[idx] = { ...kerja[idx], photos: [...(kerja[idx].photos || []), data] };
          berubah = true;
          toast.success(`${file.name} berhasil diupload`);
        }
      } catch (err) {
        toast.error(`Gagal memproses ${file.name}: ${err.message || err}`);
      }
    }
    // Satu kali di akhir, membawa SEMUA berkas yang lolos. Berkas yang gagal
    // atau melebihi batas tetap dilewati satu per satu di atas — yang berhasil
    // tidak ikut jadi korbannya.
    if (berubah) onChange(kerja);
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
    <div className="space-y-3 min-w-0" data-testid="document-checklist">
      <div className="space-y-2">
        <Label className="flex items-start gap-2 text-sm leading-snug"><ClipboardList className="w-4 h-4 shrink-0 text-blue-600 mt-0.5" />Kelengkapan Dokumen & Peralatan</Label>
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="text-muted-foreground bg-muted px-2 py-1 rounded-md whitespace-nowrap">{checkedCount} dari {checklist.length} lengkap</span>
          {totalFiles > 0 && <span className="text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/30 px-2 py-1 rounded-md whitespace-nowrap">{totalFiles} file</span>}
        </div>
      </div>
      <div className="space-y-2">
        {checklist.map((item, idx) => {
          const hasFiles = (item.photos?.length || 0) + (item.documents?.length || 0) > 0;
          return (
            <div key={idx} className={`rounded-lg transition-colors ${item.checked ? 'bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-700' : 'bg-card border border-border'}`}>
              <div className="flex items-center gap-1 px-2 py-1">
                <button type="button" onClick={() => toggleItem(idx)} aria-pressed={item.checked}
                  aria-label={`Kelengkapan ${item.name}`} className="flex min-h-11 min-w-0 flex-1 items-center gap-2 text-left rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  <span className={`w-5 h-5 rounded border flex items-center justify-center shrink-0 ${item.checked ? 'bg-emerald-600 border-emerald-600 text-white' : 'border-input bg-background'}`}>
                    {item.checked && <Check className="w-3.5 h-3.5" />}
                  </span>
                  <span className={`text-sm min-w-0 break-words ${item.checked ? 'text-emerald-700 dark:text-emerald-400 font-medium' : 'text-foreground'}`}>{item.name}</span>
                </button>
                {hasFiles && <span className="text-[11px] shrink-0 whitespace-nowrap text-muted-foreground">{(item.photos?.length || 0) + (item.documents?.length || 0)} file</span>}
                {!DEFAULT_DOC_ITEMS.includes(item.name) && (
                  <button type="button" onClick={() => removeItem(idx)} aria-label={`Hapus item ${item.name}`} title={`Hapus item ${item.name}`} className="w-11 h-11 shrink-0 rounded-md flex items-center justify-center text-muted-foreground hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/20"><Trash2 className="w-4 h-4" /></button>
                )}
              </div>
              {(item.checked || hasFiles) && (
                <div className="px-3 pb-3 space-y-3">
                  {item.checked ? <div className="space-y-1.5">
                    <label className="flex-1">
                      <input type="file" accept="image/*,.pdf" multiple className="sr-only peer" aria-label={`Tambah foto atau PDF ${item.name}`} onChange={e => handleFileUpload(idx, e)} />
                      <div className="flex min-h-11 items-center justify-center gap-2 text-xs text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 hover:bg-blue-100 dark:hover:bg-blue-900/50 rounded-md px-2 py-2 cursor-pointer transition-colors border border-blue-200 dark:border-blue-700 border-dashed peer-focus-visible:ring-2 peer-focus-visible:ring-ring">
                        <FileUp className="w-4 h-4 shrink-0" />Tambah foto / PDF
                      </div>
                    </label>
                    <p className="text-[11px] leading-snug text-muted-foreground">Maks. 3 foto dan 1 PDF per item.</p>
                  </div> : <p className="text-[11px] text-muted-foreground">File tetap tersimpan. Centang item untuk menambah file.</p>}
                  
                  {/* File preview section - IMPROVED */}
                  {hasFiles && (
                    <div className="space-y-3">
                      
                      {/* Photos */}
                      {(item.photos?.length || 0) > 0 && (
                        <div className="space-y-1">
                          <div className="text-xs text-muted-foreground">Foto ({item.photos.length}/3)</div>
                          <div className="grid grid-cols-3 gap-2">
                            {item.photos.map((photo, pi) => {
                              const src = photoSrcFor(item, photo, pi);
                              const previewSrc = isExistingPhoto(photo) && assetId
                                ? authMediaUrl(`${API}/assets/${assetId}/checklist/${idx}/photos/${existingPhotoIdx(photo)}?v=${assetVersion}`)
                                : src;
                              return (
                                <div key={pi} className="min-w-0 rounded-lg border border-border bg-card overflow-hidden">
                                  <button type="button" aria-label={`Lihat foto ${pi + 1} ${item.name}`} className="block w-full aspect-square focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring" onClick={() => setPreviewImg(previewSrc)}>
                                    <img src={src} alt={`${item.name} foto ${pi+1}`} className="w-full h-full aspect-square object-cover" />
                                  </button>
                                  <button type="button" onClick={() => removeFile(idx, 'photo', pi)}
                                    aria-label={`Hapus foto ${pi + 1} ${item.name}`} className="flex w-full min-h-11 items-center justify-center gap-1 text-[11px] text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20">
                                    <Trash2 className="w-3.5 h-3.5 shrink-0" />Hapus
                                  </button>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                      
                      {/* Documents */}
                      {(item.documents?.length || 0) > 0 && (
                        <div className="space-y-1">
                          <div className="text-xs text-muted-foreground">Dokumen PDF</div>
                          {item.documents.map((doc, di) => (
                            <div key={di} className="rounded-lg bg-card border border-border p-2">
                              <div className="flex items-start gap-2">
                                <FileText className="w-4 h-4 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
                                <span className="text-xs leading-relaxed min-w-0 break-words [overflow-wrap:anywhere]" title={doc.name}>{doc.name}</span>
                              </div>
                              <div className="flex items-center gap-2 mt-1">
                              <button
                                type="button"
                                onClick={() => openPdf(doc, idx, di)}
                                aria-label={`Lihat PDF ${doc.name}`} className="min-h-11 flex-1 rounded-md text-xs text-blue-700 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20"
                                data-testid={`checklist-doc-view-${idx}-${di}`}
                              >
                                Lihat PDF
                              </button>
                              <button type="button" aria-label={`Hapus PDF ${doc.name}`} onClick={() => removeFile(idx, 'doc', di)} className="min-h-11 flex-1 rounded-md flex items-center justify-center gap-1.5 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20">
                                <Trash2 className="w-3.5 h-3.5" />Hapus
                              </button>
                              </div>
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
      <div className="flex gap-2 items-stretch">
        <Input aria-label="Nama item kelengkapan baru" placeholder="Tambah item lain…" value={customItem} onChange={e => setCustomItem(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), addCustom())} className="h-11 min-w-0 flex-1 text-sm" />
        <Button type="button" variant="outline" onClick={addCustom} disabled={!customItem.trim()} className="h-11 shrink-0 px-3 text-xs" aria-label="Tambah item kelengkapan"><Plus className="w-4 h-4" />Tambah</Button>
      </div>
      
      {/* Image Preview Modal */}
      {previewImg && (
        <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4" onClick={() => setPreviewImg(null)}>
          <div className="relative max-w-3xl max-h-[90vh]">
            <img src={previewImg} alt="Preview" className="max-w-full max-h-[85vh] object-contain rounded-lg" />
            <button 
              type="button" aria-label="Tutup pratinjau foto" onClick={() => setPreviewImg(null)}
              className="absolute top-2 right-2 w-11 h-11 bg-card text-foreground rounded-full flex items-center justify-center shadow-lg hover:bg-muted"
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
