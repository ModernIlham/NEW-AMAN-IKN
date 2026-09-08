import React, { memo, useState, useCallback, useEffect, useMemo, useRef } from "react";
import { Plus, Upload, Trash2, ChevronLeft, ChevronRight, XCircle, FolderOpen, FileUp } from "lucide-react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import Lipatan from "../ui/Lipatan";
import { toast } from "sonner";
import axios from "axios";
import { getApiError } from "../../lib/utils";
import { useConfirm } from "../ui/ConfirmDialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const CATEGORY_PAGE_SIZE = 50;
const MAKS_IMPOR_KATEGORI = 10 * 1024 * 1024;

/**
 * Tinggi BAKU seluruh kendali di dialog ini: 44px di layar sentuh, 32px mulai
 * `lg`. Satu nilai, dipakai input maupun tombol.
 *
 * Permintaan pemilik: *"bagian halaman kelola kategori aset sederhanakan dan
 * seragamkan agar terlihat rapi dan proporsional."* Yang membuatnya tak
 * proporsional bukan tombolnya yang kebesaran, melainkan tingginya yang tak
 * seragam: aturan tap-target global (`index.css`, ≤1023px) memaksa SETIAP
 * `button` menjadi 44×44, sementara input di sebelahnya tetap `h-8` = 32px.
 * Tombol "+" karenanya berdiri satu setengah kali lebih tinggi daripada dua
 * kotak isian di kirinya.
 *
 * Yang diperbaiki tingginya kendali lain, BUKAN tombolnya — mengecilkan tombol
 * di layar sentuh melanggar aturan yang sama, dan kotak isian pun memang layak
 * 44px oleh jari.
 */
const TINGGI_KENDALI = "h-11 lg:h-8";

/** 12488 → "12.488". Angka lima digit tanpa pemisah dibaca dengan berhenti. */
const angka = (n) => Number(n || 0).toLocaleString("id-ID");

const CategoryManagerDialog = memo(({ open, onClose, categories, onCategoriesChanged }) => {
  const { confirm, confirmDialog } = useConfirm();
  const [newCategoryName, setNewCategoryName] = useState("");
  const [newCategoryCode, setNewCategoryCode] = useState("");
  const [categorySearch, setCategorySearch] = useState("");
  const [categoryPage, setCategoryPage] = useState(1);
  const [catImportProgress, setCatImportProgress] = useState(null);
  const [isDragOver, setIsDragOver] = useState(false);
  // Validasi silang lunak Kategori ↔ Referensi Kodefikasi (1a, read-only):
  // {jumlah_bermasalah, tanpa_kode, ...} + Set kode utk penanda baris.
  const [cekKodefikasi, setCekKodefikasi] = useState(null);
  const categoryImportRef = useRef(null);

  const muatCekKodefikasi = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/integritas/kategori-kodefikasi`);
      setCekKodefikasi({ ...r.data, set: new Set(r.data.kode_bermasalah || []) });
    } catch { setCekKodefikasi(null); }
  }, []);

  useEffect(() => { if (open) muatCekKodefikasi(); }, [open, muatCekKodefikasi]);

  // Daftar HASIL SARING — bukan daftar yang ditampilkan. Pemotongan per
  // halaman dilakukan saat render (`.slice` di <tbody>), jadi tetap hanya 50
  // baris yang benar-benar dirender berapa pun panjang daftar ini.
  //
  // Dulu baris tanpa-pencarian mengembalikan `cats.slice(0, 50)`. Itu penjaga
  // performa yang sudah tak berlaku sejak paginasi dipasang — dan ia MEMATIKAN
  // paginasi itu: panjangnya selalu 50, sehingga total halaman selalu 1 dan
  // tombol "Sebelumnya"/"Berikutnya" dinonaktifkan permanen. Dari 12.488
  // kategori, hanya 50 pertama yang bisa dilihat, tanpa satu pun petunjuk
  // bahwa sisanya ada — layar bahkan menulis "1-50 dari 50".
  const filteredCategories = useMemo(() => {
    const cats = Array.isArray(categories) ? categories : [];
    if (!categorySearch || categorySearch.length < 2) return cats;
    const s = categorySearch.toLowerCase();
    return cats.filter(c => (c.label||'').toLowerCase().includes(s) || (c.kode_aset||'').toLowerCase().includes(s));
  }, [categories, categorySearch]);

  const totalHalaman = Math.max(1, Math.ceil(filteredCategories.length / CATEGORY_PAGE_SIZE));

  // Halaman aktif dijepit ke rentang yang masih ada. Tanpa ini, menghapus
  // kategori terakhir di halaman terakhir meninggalkan tabel KOSONG dengan
  // kedua tombol mati — pengguna terjebak tanpa cara kembali.
  useEffect(() => {
    setCategoryPage(p => Math.min(p, totalHalaman));
  }, [totalHalaman]);

  const handleAddCategory = useCallback(async () => {
    if (!newCategoryName.trim()) { toast.error("Deskripsi kategori wajib diisi"); return; }
    try { 
      const r = await axios.post(`${API}/categories`, { label: newCategoryName.trim(), kode_aset: newCategoryCode.trim() }); 
      toast.success("Ditambahkan"); 
      if (r.data?.peringatan_kodefikasi) {
        toast.warning(`Kategori tersimpan, tetapi: ${r.data.peringatan_kodefikasi}`, { duration: 8000 });
      }
      onCategoriesChanged(); 
      muatCekKodefikasi();
      setNewCategoryName(""); 
      setNewCategoryCode("");
    } catch (e) { toast.error(getApiError(e, "Gagal")); }
  }, [newCategoryName, newCategoryCode, onCategoriesChanged, muatCekKodefikasi]);

  const handleDeleteCategory = useCallback(async id => {
    const ok = await confirm({
      title: "Hapus Kategori",
      description: "Kategori ini akan dihapus. Lanjutkan?",
      confirmLabel: "Hapus",
      variant: "danger",
    });
    if (!ok) return;
    try { await axios.delete(`${API}/categories/${id}`); toast.success("Dihapus"); onCategoriesChanged(); } catch { toast.error("Gagal"); }
  }, [onCategoriesChanged, confirm]);

  const handleDeleteAllCategories = useCallback(async () => {
    const ok = await confirm({
      title: "Hapus Semua Kategori",
      description: "Seluruh data kategori akan dihapus permanen. Tindakan ini tidak dapat dibatalkan.",
      confirmLabel: "Hapus Semua",
      variant: "danger",
      requireText: "HAPUS SEMUA",
    });
    if (!ok) return;
    try { const r = await axios.delete(`${API}/categories-all`); toast.success(r.data.message); onCategoriesChanged(); } catch { toast.error("Gagal menghapus"); }
  }, [onCategoriesChanged, confirm]);

  const handleCategoryBulkImport = useCallback(async e => {
    const file = e.target.files?.[0]; if (!file) return;
    if (!file.size || file.size > MAKS_IMPOR_KATEGORI) {
      toast.error(!file.size ? "File impor kategori kosong" : "File impor kategori maksimal 10 MB. Pecah data menjadi beberapa file.");
      if (categoryImportRef.current) categoryImportRef.current.value = "";
      return;
    }
    try {
      setCatImportProgress({ status: "uploading", total: 0, processed: 0, imported: 0 });
      const fd = new FormData(); fd.append("file", file);
      const res = await axios.post(`${API}/categories/import-bulk`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      const jobId = res.data.job_id;
      setCatImportProgress({ status: "importing", total: res.data.total, processed: 0, imported: 0 });
      const poll = setInterval(async () => {
        try {
          const pr = await axios.get(`${API}/categories/import-progress/${jobId}`);
          setCatImportProgress(pr.data);
          if (pr.data.done) {
            clearInterval(poll);
            // `done` bukan berarti berhasil: jalur galat parse DAN sapuan
            // job macet (jobs.py) sama-sama menyetel done:true dengan
            // status:"error" — dulu keduanya tetap di-toast "Import selesai".
            if (pr.data.status === "error") {
              toast.error(pr.data.error_message || "Import gagal");
            } else {
              toast.success(`Import selesai: ${pr.data.imported} ditambahkan, ${pr.data.skipped} duplikat`);
            }
            onCategoriesChanged();
            setTimeout(() => setCatImportProgress(null), 3000);
          }
        } catch {
          // Polling putus ≠ import gagal — jobnya jalan terus di server.
          // Tanpa pembersihan, panel "Mengimport..." menggantung selamanya.
          clearInterval(poll);
          toast.warning("Koneksi pemantau progres terputus — periksa hasil import dengan memuat ulang daftar kategori");
          setCatImportProgress(null);
        }
      }, 500);
    } catch (err) { toast.error(getApiError(err, "Gagal import")); setCatImportProgress(null); }
    if (categoryImportRef.current) categoryImportRef.current.value = "";
  }, [onCategoriesChanged]);

  const handleDragOver = useCallback((e) => { e.preventDefault(); e.stopPropagation(); setIsDragOver(true); }, []);
  const handleDragLeave = useCallback((e) => { e.preventDefault(); e.stopPropagation(); setIsDragOver(false); }, []);
  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    const files = e.dataTransfer?.files;
    if (files?.length) {
      const file = files[0];
      const ext = file.name.split('.').pop().toLowerCase();
      if (['csv', 'xlsx', 'xls'].includes(ext)) {
        handleCategoryBulkImport({ target: { files: [file] } });
      } else {
        toast.error("Format file tidak didukung. Gunakan CSV, XLS, atau XLSX.");
      }
    }
  }, [handleCategoryBulkImport]);

  return (
    <>
    {confirmDialog}
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg overflow-x-hidden">
        <DialogHeader><DialogTitle className="flex items-center gap-2"><FolderOpen className="w-5 h-5 text-blue-600" />Kelola Kategori Aset</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div className="flex items-center justify-between bg-blue-50 dark:bg-blue-900/20 rounded-lg px-3 py-2">
            <span className="text-sm text-blue-700 dark:text-blue-300 font-medium">
              Total: {angka(categories.length)} kategori
            </span>
            <Button variant="ghost" size="sm" onClick={handleDeleteAllCategories}
              className={`text-xs text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20 flex-shrink-0 ${TINGGI_KENDALI}`}>
              <Trash2 className="w-3.5 h-3.5 mr-1" />Hapus Semua
            </Button>
          </div>

          {cekKodefikasi && cekKodefikasi.jumlah_bermasalah > 0 && (
            <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg px-3 py-2" data-testid="kategori-kodefikasi-warn">
              <p className="text-[11px] font-semibold text-amber-700 dark:text-amber-300">
                ⚠ {cekKodefikasi.jumlah_bermasalah} kategori kodenya belum terdaftar di Referensi Kodefikasi
              </p>
              <p className="text-[10px] text-amber-700/80 dark:text-amber-300/80 mt-0.5">
                Non-blocking — data tetap dipakai.
              </p>
              <Lipatan judul="Cara memperbaiki" nada="amber" className="mt-1">
                Lengkapi Referensi Kodefikasi Barang (Beranda Modul) atau perbaiki kode
                kategorinya; baris terdampak bertanda ⚠. Rinciannya juga ada di dasbor
                Integritas.
              </Lipatan>
            </div>
          )}
          
          <div
            className={`border-2 border-dashed rounded-lg p-3 space-y-2 transition-colors ${isDragOver ? 'border-emerald-400 bg-emerald-50/80 dark:bg-emerald-900/30' : 'border-emerald-200 dark:border-emerald-700 bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-900/20 dark:to-teal-900/20'}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            data-testid="category-dropzone"
          >
            <p className="text-xs font-semibold text-emerald-800 dark:text-emerald-300">Import Kategori dari Excel/CSV</p>
            <p className="text-[10px] text-emerald-600 dark:text-emerald-400">Format: Kolom "Kode Aset" (10 digit) + "Deskripsi Barang". Maksimal 10 MB per file; pecah data besar menjadi beberapa file.</p>
            {isDragOver ? (
              <div className="flex flex-col items-center justify-center py-3 gap-1">
                <FileUp className="w-6 h-6 text-emerald-500 animate-bounce" />
                <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Lepaskan file di sini...</span>
              </div>
            ) : (
              <Button variant="outline" size="sm" onClick={() => categoryImportRef.current?.click()} className={`w-full ${TINGGI_KENDALI} border-emerald-300 dark:border-emerald-600 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-100 dark:hover:bg-emerald-900/30`} disabled={!!catImportProgress}>
                <Upload className="w-4 h-4 mr-1" />{catImportProgress ? 'Sedang Import...' : 'Pilih File atau Seret & Lepas'}
              </Button>
            )}
            <input ref={categoryImportRef} type="file" accept=".csv,.xlsx,.xls" onChange={handleCategoryBulkImport} className="hidden" data-testid="category-import-input" />
            
            {catImportProgress && (
              <div className="space-y-1.5 bg-card rounded-lg p-2 border">
                <div className="flex justify-between text-[11px]">
                  <span className="font-medium text-foreground">
                    {catImportProgress.status === 'uploading' ? 'Mengupload...' : catImportProgress.status === 'parsing' ? 'Membaca file...' : catImportProgress.status === 'error' ? 'Gagal' : catImportProgress.done ? 'Selesai!' : 'Mengimport...'}
                  </span>
                  <span className="text-muted-foreground">{catImportProgress.processed || 0} / {catImportProgress.total || '?'}</span>
                </div>
                <div className="w-full bg-muted rounded-full h-2">
                  <div className="bg-emerald-500 h-2 rounded-full transition-all duration-300" style={{width: `${catImportProgress.total ? Math.round((catImportProgress.processed / catImportProgress.total) * 100) : 0}%`}} />
                </div>
                <div className="flex gap-3 text-[10px] text-muted-foreground">
                  <span className="text-emerald-600">+{catImportProgress.imported || 0} baru</span>
                  <span className="text-amber-600">{catImportProgress.skipped || 0} duplikat</span>
                  {catImportProgress.errors > 0 && <span className="text-red-600">{catImportProgress.errors} error</span>}
                </div>
              </div>
            )}
          </div>
          
          <div className="space-y-1.5">
            <p className="text-xs font-semibold text-foreground">Tambah Kategori Manual</p>
            <div className="flex items-center gap-2">
              {/* Lebarnya memuat sepuluh digit monospace beserta paddingnya;
                  placeholder "(10 digit)" dulu terpotong jadi "Kode Ase…" —
                  keterangan yang tak terbaca sama saja dengan tak ada, dan
                  placeholder lenyap begitu diketik. Keterangannya pindah ke
                  baris di bawah, tempat ia tetap terlihat. */}
              <Input
                placeholder="Kode Aset"
                value={newCategoryCode}
                onChange={e => setNewCategoryCode(e.target.value)}
                onKeyPress={e => e.key === 'Enter' && handleAddCategory()}
                className={`${TINGGI_KENDALI} text-sm w-28 sm:w-32 flex-shrink-0 font-mono`}
                maxLength={10}
                data-testid="category-code-input"
              />
              <Input
                placeholder="Deskripsi kategori…"
                value={newCategoryName}
                onChange={e => setNewCategoryName(e.target.value)}
                onKeyPress={e => e.key === 'Enter' && handleAddCategory()}
                className={`${TINGGI_KENDALI} text-sm flex-1 min-w-0`}
                data-testid="category-name-input"
              />
              <Button onClick={handleAddCategory} size="sm" aria-label="Tambah kategori"
                className={`${TINGGI_KENDALI} w-11 lg:w-8 p-0 flex-shrink-0`}
                data-testid="category-add-btn"><Plus className="w-4 h-4" /></Button>
            </div>
            <p className="text-[10px] text-muted-foreground">
              Kode Aset 10 digit sesuai kodefikasi BMN.
            </p>
          </div>
          
          <div className="relative space-y-2">
            <Input placeholder="Cari kategori…" value={categorySearch}
              onChange={e => { setCategorySearch(e.target.value); setCategoryPage(1); }}
              className={`${TINGGI_KENDALI} text-sm`} data-testid="category-search-input" />

            {filteredCategories.length > 0 && (
              /* Ketiga angkanya TAK BOLEH membungkus: "1-50 dari 12488" yang
                 patah menjadi "1-50 dari" + "12488" terbaca sebagai dua
                 keterangan, dan "1 / 250" yang patah terbaca sebagai pecahan
                 yang gagal dirender. Label tombolnya yang mengalah di layar
                 sempit — panahnya sendiri sudah menyatakan arah. */
              <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                <span className="whitespace-nowrap" data-testid="kategori-rentang">
                  {angka(Math.min((categoryPage - 1) * CATEGORY_PAGE_SIZE + 1, filteredCategories.length))}
                  &ndash;{angka(Math.min(categoryPage * CATEGORY_PAGE_SIZE, filteredCategories.length))}
                  {" "}dari {angka(filteredCategories.length)}
                </span>
                {/* Ketiga kendali memakai `totalHalaman` yang SAMA. Sebelumnya
                    angka itu dihitung ulang di tiga tempat dengan ekor `|| 1`
                    hanya pada salah satunya — bentuk yang membuat label dan
                    keadaan tombol bisa berbeda pendapat. */}
                <div className="flex items-center gap-1 flex-shrink-0">
                  <Button variant="outline" size="sm" aria-label="Halaman sebelumnya"
                    className={`${TINGGI_KENDALI} w-11 sm:w-auto sm:px-2 p-0 text-xs`}
                    onClick={() => setCategoryPage(p => Math.max(1, p - 1))}
                    disabled={categoryPage <= 1} data-testid="kategori-prev">
                    <ChevronLeft className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline ml-0.5">Sebelumnya</span>
                  </Button>
                  <span className="px-1 text-muted-foreground font-medium whitespace-nowrap"
                    data-testid="kategori-halaman">
                    {angka(categoryPage)} / {angka(totalHalaman)}
                  </span>
                  <Button variant="outline" size="sm" aria-label="Halaman berikutnya"
                    className={`${TINGGI_KENDALI} w-11 sm:w-auto sm:px-2 p-0 text-xs`}
                    onClick={() => setCategoryPage(p => Math.min(totalHalaman, p + 1))}
                    disabled={categoryPage >= totalHalaman} data-testid="kategori-next">
                    <span className="hidden sm:inline mr-0.5">Berikutnya</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
            )}
            
            <div className="border rounded-lg">
              <div className="h-52 overflow-auto" style={{ overflowX: 'auto', overflowY: 'auto' }}>
                <table className="w-full table-fixed border-collapse">
                  <thead className="bg-muted sticky top-0">
                    <tr>
                      <th className="text-left text-[10px] font-semibold text-muted-foreground uppercase px-2 py-1.5 border-b w-28">Kode Aset</th>
                      <th className="text-left text-[10px] font-semibold text-muted-foreground uppercase px-2 py-1.5 border-b">Deskripsi</th>
                      <th className="w-10 border-b"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCategories
                      .slice((categoryPage - 1) * CATEGORY_PAGE_SIZE, categoryPage * CATEGORY_PAGE_SIZE)
                      .map(c => (
                      <tr key={c.id} className="hover:bg-muted group border-b border-border last:border-b-0">
                        <td className="px-2 py-1.5">
                          <span className="text-[11px] font-mono bg-muted text-muted-foreground px-1.5 py-0.5 rounded whitespace-nowrap">{c.kode_aset || '-'}</span>
                          {cekKodefikasi?.set?.has(c.kode_aset) && (
                            <span className="ml-1 text-[10px] text-amber-600 dark:text-amber-400" title="Kode belum terdaftar di Referensi Kodefikasi (peringatan — non-blocking)">⚠</span>
                          )}
                        </td>
                        <td className="px-2 py-1.5">
                          <span className="text-xs text-foreground break-words line-clamp-2" title={c.label}>{c.label}</span>
                        </td>
                        <td className="px-1 py-1.5">
                          {/* Di layar sentuh tombol ini TERLIHAT. Sebelumnya
                              `opacity-0` sampai di-hover — dan layar sentuh tak
                              punya hover — sementara aturan tap-target tetap
                              memberinya 44×44: sebuah tombol HAPUS yang tak
                              kelihatan namun tetap dapat tertekan jari. Yang
                              tak terlihat tak dapat dihindari. */}
                          <Button variant="ghost" size="sm" aria-label={`Hapus ${c.label}`}
                            onClick={() => handleDeleteCategory(c.id)}
                            className="h-11 w-11 lg:h-6 lg:w-6 p-0 opacity-100 lg:opacity-0 lg:group-hover:opacity-100"><XCircle className="w-3.5 h-3.5 text-red-500" /></Button>
                        </td>
                      </tr>
                    ))}
                    {filteredCategories.length === 0 && (
                      <tr><td colSpan={3} className="text-xs text-center text-muted-foreground py-6">Tidak ada kategori</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
    </>
  );
});

CategoryManagerDialog.displayName = "CategoryManagerDialog";
export default CategoryManagerDialog;
