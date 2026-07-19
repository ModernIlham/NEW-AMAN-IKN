import React, { memo, useState, useCallback, useRef, useMemo, useEffect } from "react";
import {
  X, Loader2, CheckSquare, Tag, MapPin, Wrench, ClipboardList,
  Sticker, Building2, Camera, Images, FileCheck, Receipt,
  Calendar, DollarSign, Navigation, Package, Truck,
  LocateFixed, Search, FileUp, FileText, Check, ChevronDown,
  Eraser, Trash2, Power, UserRound, StickyNote, Plus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { compressImageFile } from "../../lib/imageCompression";
import { compressPdfFile } from "../../lib/pdfCompression";
import { acquireAccuratePosition } from "../../lib/geolocation";
import { toast } from "sonner";
import { DEFAULT_DOC_ITEMS } from "./DocumentChecklist";
import {
  PENGGUNA_MELEKAT_OPTIONS, PENGGUNA_NAME_LABELS, OPERASIONAL_JENIS_OPTIONS,
  CONDITION_OPTIONS, STATUS_OPTIONS,
} from "./InventoryFieldSheet";
import { useConfirm } from "@/components/ui/ConfirmDialog";

const STIKER_STATUSES = ["Belum Terpasang", "Sudah Terpasang"];
const STIKER_SIZES = ["Kecil", "Sedang", "Besar"];
const MAX_BATCH_PHOTOS = 6;
// Satu sumber opsi: InventoryFieldSheet (konvensi repo — jangan duplikasi)
const CONDITIONS = CONDITION_OPTIONS.map((o) => o.value);
const INVENTORY_STATUSES = ["Belum Diinventarisasi",
  ...STATUS_OPTIONS.map((o) => o.value)];
// Selaras dengan opsi Status pada form aset (AssetForm).
const ASSET_STATUSES = ["Aktif", "Idle", "Maintenance", "Nonaktif"];

/** Searchable category dropdown for batch edit */
function BatchCategorySelect({ categories, value, onChange }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 100);
  }, [open]);

  const filtered = useMemo(() => {
    const cats = Array.isArray(categories) ? categories : [];
    if (!q.trim()) return cats.slice(0, 150);
    const s = q.toLowerCase();
    return cats.filter(c => (c.label || '').toLowerCase().includes(s) || (c.kode_aset || '').toLowerCase().includes(s)).slice(0, 150);
  }, [categories, q]);

  const isClear = value === "__clear__";

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button type="button" className={`flex items-center justify-between w-full h-7 px-2 text-xs border rounded-md hover:bg-accent ${isClear ? 'bg-red-50 dark:bg-red-900/20 border-red-300 dark:border-red-700 text-red-600 dark:text-red-400' : 'bg-background'}`} data-testid="batch-category-select">
          <span className="truncate">{isClear ? "— Kosongkan —" : value && value !== "__none__" ? value : "— Tidak diubah —"}</span>
          <ChevronDown className="w-3 h-3 flex-shrink-0 ml-1 text-muted-foreground" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-[260px] p-0" align="start">
        <div className="p-2 border-b">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
            <Input ref={inputRef} placeholder="Cari kategori..." value={q} onChange={e => setQ(e.target.value)} className="pl-7 h-7 text-xs" />
          </div>
        </div>
        <ScrollArea className="h-[200px]">
          <div className="p-1">
            <button onClick={() => { onChange("__none__"); setOpen(false); setQ(""); }} className={`w-full flex items-center gap-1.5 px-2 py-1 text-xs rounded hover:bg-muted ${!value || value === "__none__" ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300" : ""}`}>
              <Check className={`w-3 h-3 ${!value || value === "__none__" ? "opacity-100" : "opacity-0"}`} />— Tidak diubah —
            </button>
            <button onClick={() => { onChange("__clear__"); setOpen(false); setQ(""); }} className={`w-full flex items-center gap-1.5 px-2 py-1 text-xs rounded hover:bg-red-50 dark:hover:bg-red-900/30 ${isClear ? "bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400" : "text-red-500"}`}>
              <Eraser className={`w-3 h-3 ${isClear ? "opacity-100" : "opacity-50"}`} />— Kosongkan —
            </button>
            <div className="border-t my-0.5" />
            {filtered.map(c => (
              <button key={c.id || c.label} onClick={() => { onChange(c.label); setOpen(false); setQ(""); }}
                className={`w-full flex items-center gap-1.5 px-2 py-1 text-xs rounded hover:bg-muted text-left ${value === c.label ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300" : ""}`}>
                <Check className={`w-3 h-3 flex-shrink-0 ${value === c.label ? "opacity-100" : "opacity-0"}`} />
                <span className="truncate">{c.kode_aset ? `${c.kode_aset} - ${c.label}` : c.label}</span>
              </button>
            ))}
            {filtered.length === 0 && <div className="text-xs text-center text-muted-foreground py-2">Tidak ditemukan</div>}
          </div>
        </ScrollArea>
      </PopoverContent>
    </Popover>
  );
}

/** Clearable text input for batch edit */
function ClearableInput({ value, onChange, onClear, isClear, ...props }) {
  if (isClear) {
    return (
      <div className="flex items-center h-7 px-2 text-xs border rounded-md bg-red-50 dark:bg-red-900/20 border-red-300 dark:border-red-700">
        <Eraser className="w-3 h-3 text-red-500 mr-1 flex-shrink-0" />
        <span className="text-red-600 dark:text-red-400 flex-1 text-[10px]">Akan dikosongkan</span>
        <button type="button" onClick={onClear} className="text-red-400 hover:text-red-600 ml-1" title="Batalkan kosongkan">
          <X className="w-3 h-3" />
        </button>
      </div>
    );
  }
  return (
    <div className="flex gap-0.5">
      <Input className="h-7 text-xs flex-1" value={value || ""} onChange={onChange} {...props} />
      <button type="button" onClick={onClear} className="h-7 w-7 flex items-center justify-center rounded-md border border-border hover:bg-red-50 dark:hover:bg-red-900/30 hover:border-red-300 dark:hover:border-red-700 text-muted-foreground hover:text-red-500 transition-colors flex-shrink-0" title="Kosongkan field ini" data-testid="clear-field-btn">
        <Eraser className="w-3 h-3" />
      </button>
    </div>
  );
}

/** Select with clear option */
function ClearableSelect({ value, onValueChange, children, placeholder, ...props }) {
  const isClear = value === "__clear__";
  return (
    <Select value={value || "__none__"} onValueChange={onValueChange} {...props}>
      <SelectTrigger className={`h-7 text-xs ${isClear ? 'bg-red-50 dark:bg-red-900/20 border-red-300 dark:border-red-700 text-red-600 dark:text-red-400' : ''}`}>
        <SelectValue placeholder={placeholder || "—"} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="__none__">— Tidak diubah —</SelectItem>
        <SelectItem value="__clear__" className="text-red-500">
          <span className="flex items-center gap-1"><Eraser className="w-3 h-3" />Kosongkan</span>
        </SelectItem>
        {children}
      </SelectContent>
    </Select>
  );
}

// Seksi berkategori — header ringkas (ikon + judul kecil) + isi. Membuat panel
// Ubah Massal terbaca BERKELOMPOK/terkategori & padat tanpa makan banyak ruang.
// `right` = elemen aksi opsional (mis. tombol Hapus Semua) di kanan judul.
function Section({ icon: Icon, title, right, children, first = false }) {
  return (
    <div className={first ? "" : "mt-2 pt-2 border-t border-blue-200 dark:border-blue-800"}>
      <div className="flex items-center gap-1 mb-1">
        <div className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-blue-700/80 dark:text-blue-300/80">
          {Icon && <Icon className="w-3 h-3" />}
          {title}
        </div>
        {right && <div className="ml-auto">{right}</div>}
      </div>
      {children}
    </div>
  );
}

const BatchEditPanel = memo(function BatchEditPanel({
  selectedCount, categories, onApply, onClose, updating, activity, assets, selectedAssets,
  attached = false,
}) {
  const [updates, setUpdates] = useState({});
  const [gpsLoading, setGpsLoading] = useState(false);
  const [showMore, setShowMore] = useState(false);
  const [clearPhotos, setClearPhotos] = useState(false);
  const [clearDocChecklist, setClearDocChecklist] = useState(false);
  const photoInputRef = useRef(null);
  const { confirm, confirmDialog } = useConfirm();

  // Collect unique doc checklist item names from selected assets
  const docItemNames = useMemo(() => {
    if (!assets || !selectedAssets) return DEFAULT_DOC_ITEMS;
    const names = new Set(DEFAULT_DOC_ITEMS);
    const selectedIds = selectedAssets instanceof Set ? selectedAssets : new Set(selectedAssets);
    (assets || []).forEach(a => {
      if (selectedIds.has(a.id) && a.document_checklist) {
        a.document_checklist.forEach(item => {
          if (item.name) names.add(item.name);
        });
      }
    });
    return Array.from(names);
  }, [assets, selectedAssets]);

  // Doc checklist state: active items + their files
  const [docItems, setDocItems] = useState([]);
  // Input "tambah dokumen baru" (nama kustom) — agar bisa menambah kelengkapan
  // dokumen yang belum ada di daftar bawaan, secara MASSAL ke semua aset terpilih.
  const [customDoc, setCustomDoc] = useState("");

  // Rebuild doc items when docItemNames changes
  useEffect(() => {
    setDocItems(docItemNames.map(name => ({
      name, _active: false, checked: false, photos: [], documents: [],
    })));
  }, [docItemNames]);

  // Extract eselon data from activity
  const eselon1List = (activity?.eselon1 || []).map(e => typeof e === 'string' ? { nama: e, eselon2: [] } : e);
  const selectedEselon1 = updates.eselon1 || "";
  const eselon2List = eselon1List.find(e => e.nama === selectedEselon1)?.eselon2 || [];

  const setField = useCallback((field, value) => {
    setUpdates(prev => {
      // __clear__ is a valid value — means "clear this field"
      if (value === "__clear__") {
        return { ...prev, [field]: "__clear__" };
      }
      if (value === undefined || value === null || value === "" || value === "__none__") {
        const next = { ...prev };
        delete next[field];
        return next;
      }
      return { ...prev, [field]: value };
    });
  }, []);

  // Toggle clear mode for text fields
  const toggleClearField = useCallback((field) => {
    setUpdates(prev => {
      if (prev[field] === "__clear__") {
        const next = { ...prev };
        delete next[field];
        return next;
      }
      return { ...prev, [field]: "__clear__" };
    });
  }, []);

  // Pengguna "melekat ke": klik ulang = batal (tidak diubah). Sub-field yang
  // tak relevan dilepas dari daftar perubahan (mis. pindah ke Individual
  // melepas jabatan & jenis operasional) — konsisten dengan form edit, tanpa
  // memaksa pengosongan tersembunyi pada aset.
  const setPenggunaMelekat = useCallback((v) => {
    setUpdates(prev => {
      const next = { ...prev };
      if (prev.pengguna_melekat_ke === v) {
        delete next.pengguna_melekat_ke;
        delete next.pengguna_jabatan;
        delete next.operasional_jenis;
        return next;
      }
      next.pengguna_melekat_ke = v;
      if (v !== "Jabatan") delete next.pengguna_jabatan;
      if (v !== "Operasional") delete next.operasional_jenis;
      return next;
    });
  }, []);

  const setOperasionalJenis = useCallback((v) => {
    setUpdates(prev => {
      const next = { ...prev };
      if (prev.operasional_jenis === v) delete next.operasional_jenis;
      else next.operasional_jenis = v;
      return next;
    });
  }, []);

  // GPS fetch — realtime & akurat (watchPosition + maximumAge:0, ambil akurasi terbaik)
  const fetchGPS = useCallback(() => {
    if (!navigator.geolocation) { toast.error("GPS tidak didukung di browser ini"); return; }
    setGpsLoading(true);
    acquireAccuratePosition({
      onUpdate: ({ lat, lng }) => setUpdates(prev => ({ ...prev, koordinat_latitude: lat, koordinat_longitude: lng })),
    }).then(({ lat, lng, accuracy }) => {
      setGpsLoading(false);
      const acc = Number.isFinite(accuracy) ? Math.round(accuracy) : null;
      // Ikut aturan kamera: koordinat hanya disimpan bila akurasi ≤8 m. Di atas
      // itu, buang koordinat sementara (dari onUpdate) agar tak terekam ke banyak
      // aset dengan radius terlalu lebar.
      if (acc != null && acc > 8) {
        setUpdates(prev => { const n = { ...prev }; delete n.koordinat_latitude; delete n.koordinat_longitude; return n; });
        toast.error(`Akurasi GPS ±${acc} m terlalu lebar (maks ±8 m) — koordinat tidak disimpan. Coba lagi di tempat lebih terbuka.`);
        return;
      }
      setUpdates(prev => ({ ...prev, koordinat_latitude: lat, koordinat_longitude: lng }));
      toast.success(`Koordinat GPS diperbarui${acc != null ? ` (±${acc} m)` : ""}`);
    }).catch(err => {
      setGpsLoading(false);
      if (err?.code === 1) toast.error("Akses lokasi ditolak. Izinkan di pengaturan browser.");
      else toast.error("Gagal mendapatkan lokasi GPS");
    });
  }, []);

  // Upload foto MASSAL — banyak foto, tiap foto lewat kompresi klien. Disimpan
  // di updates.batch_photos (array data-URL); backend distribusi ke tiap aset
  // menghormati batas 6 foto/aset.
  const handlePhotoUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    const existing = (updates.batch_photos || []).length;
    const room = MAX_BATCH_PHOTOS - existing;
    if (room <= 0) { toast.error(`Maksimal ${MAX_BATCH_PHOTOS} foto`); e.target.value = ""; return; }
    const picked = files.slice(0, room);
    if (files.length > room) toast.warning(`Hanya ${room} foto ditambahkan (maks ${MAX_BATCH_PHOTOS}).`);
    const toastId = toast.loading("Mengompresi foto...");
    try {
      const compressedList = [];
      for (const file of picked) {
        if (file.size > 15 * 1024 * 1024) { toast.error(`${file.name || "Foto"} terlalu besar (maks 15MB)`); continue; }
        if (!file.type.startsWith('image/')) { toast.error("File harus berupa gambar"); continue; }
        compressedList.push(await compressImageFile(file));
      }
      if (compressedList.length) {
        setUpdates(prev => ({ ...prev, batch_photos: [...(prev.batch_photos || []), ...compressedList].slice(0, MAX_BATCH_PHOTOS) }));
        setClearPhotos(false);
      }
      toast.dismiss(toastId);
    } catch (err) {
      toast.dismiss(toastId);
      toast.error(`Gagal memproses foto: ${err.message || err}`);
    }
    e.target.value = "";
  };

  const removePhoto = (idx) => {
    setUpdates(prev => {
      const arr = (prev.batch_photos || []).filter((_, i) => i !== idx);
      const next = { ...prev };
      if (arr.length) next.batch_photos = arr; else delete next.batch_photos;
      return next;
    });
  };

  // Tambah item kelengkapan dokumen BARU (nama kustom) — langsung AKTIF supaya
  // ikut diterapkan ke semua aset terpilih. Dedupe nama (case-insensitive)
  // terhadap item yang sudah ada (bawaan + existing + kustom sebelumnya).
  const addCustomDoc = useCallback(() => {
    const name = customDoc.trim();
    if (!name) return;
    if (docItems.some(d => (d.name || "").toLowerCase() === name.toLowerCase())) {
      toast.error("Dokumen sudah ada di daftar");
      return;
    }
    setDocItems(prev => [...prev, { name, _active: true, checked: true, photos: [], documents: [] }]);
    setCustomDoc("");
  }, [customDoc, docItems]);

  // Doc checklist toggle + file upload
  const toggleDocItem = (idx) => {
    setDocItems(prev => {
      const next = [...prev];
      next[idx] = { ...next[idx], _active: !next[idx]._active, checked: !next[idx]._active, photos: !next[idx]._active ? next[idx].photos : [], documents: !next[idx]._active ? next[idx].documents : [] };
      return next;
    });
  };

  const handleDocFileUpload = async (idx, e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    for (const file of files) {
      if (file.size > 25 * 1024 * 1024) { toast.error(`${file.name} terlalu besar (maks 25MB)`); continue; }
      try {
        if (file.type === 'application/pdf') {
          // PDFs: compress via backend (iLoveAPI → WhipDoc fallback)
          const tId = toast.loading(`Mengompres ${file.name}...`);
          const { dataUrl, originalBytes, compressedBytes, method, savingsPercent, error } =
            await compressPdfFile(file);
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
          setDocItems(prev => {
            const next = [...prev];
            if ((next[idx].documents || []).length >= 1) { toast.error("Maks 1 PDF per item"); return prev; }
            next[idx] = { ...next[idx], documents: [...(next[idx].documents || []), { name: file.name, data: dataUrl }] };
            return next;
          });
        } else if (file.type.startsWith('image/')) {
          // Images: compress client-side first
          const compressed = await compressImageFile(file);
          setDocItems(prev => {
            const next = [...prev];
            if ((next[idx].photos || []).length >= 3) { toast.error("Maks 3 foto per item"); return prev; }
            next[idx] = { ...next[idx], photos: [...(next[idx].photos || []), compressed] };
            return next;
          });
          toast.success(`${file.name} berhasil diupload`);
        }
      } catch (err) {
        toast.error(`Gagal memproses ${file.name}: ${err.message || err}`);
      }
    }
    e.target.value = "";
  };

  const removeDocFile = (idx, type, fileIdx) => {
    setDocItems(prev => {
      const next = [...prev];
      if (type === 'photo') next[idx] = { ...next[idx], photos: (next[idx].photos || []).filter((_, i) => i !== fileIdx) };
      else next[idx] = { ...next[idx], documents: (next[idx].documents || []).filter((_, i) => i !== fileIdx) };
      return next;
    });
  };

  const handleApply = async () => {
    const finalUpdates = { ...updates };

    // Add active doc checklist items with their files
    const activeItems = docItems.filter(d => d._active);
    if (activeItems.length > 0) {
      finalUpdates.document_checklist_items = activeItems.map(d => ({
        name: d.name, checked: d.checked,
        photos: d.photos || [], documents: d.documents || [],
      }));
    }

    // Add clear flags
    if (clearPhotos) finalUpdates.clear_photos = true;
    if (clearDocChecklist) finalUpdates.clear_document_checklist = true;

    // Count how many fields are being changed
    const clearFieldCount = Object.values(updates).filter(v => v === "__clear__").length;
    const setFieldCount = Object.keys(updates).filter(k => updates[k] !== "__clear__").length;
    const totalChanges = clearFieldCount + setFieldCount + activeItems.length + (clearPhotos ? 1 : 0) + (clearDocChecklist ? 1 : 0);

    if (totalChanges === 0) {
      toast.error("Tidak ada perubahan yang dipilih");
      return;
    }

    // Confirmation for destructive clear actions
    const clearActions = [];
    if (clearPhotos) clearActions.push("semua foto");
    if (clearDocChecklist) clearActions.push("semua dokumen kelengkapan");
    if (clearFieldCount > 0) clearActions.push(`${clearFieldCount} field data`);

    if (clearActions.length > 0) {
      const ok = await confirm({
        title: "Kosongkan Data Massal",
        description: `Anda akan mengosongkan ${clearActions.join(", ")} dari ${selectedCount} aset. Tindakan ini tidak dapat dibatalkan. Lanjutkan?`,
        confirmLabel: "Ya, Kosongkan",
        variant: "danger",
      });
      if (!ok) return;
    }

    onApply(finalUpdates);
  };

  const activeDocCount = docItems.filter(d => d._active).length;
  const clearCount = Object.values(updates).filter(v => v === "__clear__").length + (clearPhotos ? 1 : 0) + (clearDocChecklist ? 1 : 0);
  const setCount = Object.keys(updates).filter(k => updates[k] !== "__clear__").length + activeDocCount;
  const hasUpdates = setCount > 0 || clearCount > 0;

  return (
    // `attached`: panel menyambung mulus di bawah toolbar seleksi (satu kartu) —
    // atas rata + tanpa garis atas ganda. Header ringkas (judul & tombol tutup
    // sudah ada di toolbar), sisakan hanya pengalih "Tampilkan Semua Field".
    <div className={`bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 p-3 print:hidden ${attached ? "rounded-b-lg border-t-0 pt-2" : "rounded-lg"}`} data-testid="batch-edit-panel">
      {confirmDialog}
      <div className="flex items-center justify-between mb-2">
        {!attached && (
          <div className="flex items-center gap-2">
            <CheckSquare className="w-4 h-4 text-blue-600" />
            <span className="text-sm font-medium text-blue-800 dark:text-blue-300">
              {selectedCount} aset dipilih — Ubah Massal
            </span>
          </div>
        )}
        <div className="flex items-center gap-1 ml-auto">
          <button onClick={() => setShowMore(!showMore)} className="text-[10px] text-blue-600 dark:text-blue-400 hover:underline px-2 py-0.5" data-testid="batch-toggle-more">
            {showMore ? "Tampilkan Sedikit" : "Tampilkan Semua Field"}
          </button>
          {!attached && <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={onClose}><X className="w-3.5 h-3.5" /></Button>}
        </div>
      </div>

      {/* ── Klasifikasi & Lokasi (selalu tampil) ── */}
      <Section icon={Tag} title="Klasifikasi & Lokasi" first>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {/* Kategori - with search */}
          <div className="space-y-0.5">
            <label className="text-[10px] text-muted-foreground flex items-center gap-1"><Tag className="w-2.5 h-2.5" />Kategori</label>
            <BatchCategorySelect categories={categories} value={updates.category} onChange={v => setField("category", v)} />
          </div>

          {/* Lokasi */}
          <div className="space-y-0.5">
            <label className="text-[10px] text-muted-foreground flex items-center gap-1"><MapPin className="w-2.5 h-2.5" />Lokasi</label>
            <ClearableInput placeholder="—" value={updates.location === "__clear__" ? "" : updates.location} isClear={updates.location === "__clear__"} onChange={e => setField("location", e.target.value)} onClear={() => toggleClearField("location")} />
          </div>

          {/* Eselon I */}
          <div className="space-y-0.5">
            <label className="text-[10px] text-muted-foreground flex items-center gap-1"><Building2 className="w-2.5 h-2.5" />Eselon I</label>
            <ClearableSelect value={updates.eselon1 || "__none__"} onValueChange={v => { setField("eselon1", v); if (v === "__clear__" || v === "__none__") setField("eselon2", undefined); }}>
              {eselon1List.map(e => <SelectItem key={e.nama} value={e.nama}>{e.nama}</SelectItem>)}
            </ClearableSelect>
          </div>

          {/* Eselon II */}
          <div className="space-y-0.5">
            <label className="text-[10px] text-muted-foreground flex items-center gap-1"><Building2 className="w-2.5 h-2.5" />Eselon II</label>
            <ClearableSelect value={updates.eselon2 || "__none__"} onValueChange={v => setField("eselon2", v)} disabled={!selectedEselon1 || selectedEselon1 === "__clear__" || eselon2List.length === 0} placeholder={selectedEselon1 && selectedEselon1 !== "__clear__" ? "—" : "Pilih Eselon I dulu"}>
              {eselon2List.map(e2 => <SelectItem key={e2} value={e2}>{e2}</SelectItem>)}
            </ClearableSelect>
          </div>
        </div>
      </Section>

      {/* ── Kondisi & Status (selalu tampil) ── */}
      <Section icon={ClipboardList} title="Kondisi & Status">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {/* Kondisi */}
          <div className="space-y-0.5">
            <label className="text-[10px] text-muted-foreground flex items-center gap-1"><Wrench className="w-2.5 h-2.5" />Kondisi</label>
            <ClearableSelect value={updates.condition || "__none__"} onValueChange={v => setField("condition", v)}>
              {CONDITIONS.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
            </ClearableSelect>
          </div>

          {/* Status Inventaris */}
          <div className="space-y-0.5">
            <label className="text-[10px] text-muted-foreground flex items-center gap-1"><ClipboardList className="w-2.5 h-2.5" />Status Inventaris</label>
            <ClearableSelect value={updates.inventory_status || "__none__"} onValueChange={v => setField("inventory_status", v)}>
              {INVENTORY_STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </ClearableSelect>
          </div>

          {/* Status Aset */}
          <div className="space-y-0.5">
            <label className="text-[10px] text-muted-foreground flex items-center gap-1"><Power className="w-2.5 h-2.5" />Status Aset</label>
            <ClearableSelect value={updates.status || "__none__"} onValueChange={v => setField("status", v)}>
              {ASSET_STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </ClearableSelect>
          </div>

          {/* Stiker Status */}
          <div className="space-y-0.5">
            <label className="text-[10px] text-muted-foreground flex items-center gap-1"><Sticker className="w-2.5 h-2.5" />Status Stiker</label>
            <ClearableSelect value={updates.stiker_status || "__none__"} onValueChange={v => setField("stiker_status", v)}>
              {STIKER_STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </ClearableSelect>
          </div>

          {/* Stiker Ukuran */}
          <div className="space-y-0.5">
            <label className="text-[10px] text-muted-foreground flex items-center gap-1"><Sticker className="w-2.5 h-2.5" />Ukuran Stiker</label>
            <ClearableSelect value={updates.stiker_ukuran || "__none__"} onValueChange={v => setField("stiker_ukuran", v)}>
              {STIKER_SIZES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </ClearableSelect>
          </div>
        </div>
      </Section>

      {/* Extended Fields */}
      {showMore && (
        <>
          {/* ── Administrasi Perolehan ── */}
          <Section icon={Receipt} title="Administrasi Perolehan">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
            <div className="space-y-0.5">
              <label className="text-[10px] text-muted-foreground flex items-center gap-1"><Receipt className="w-2.5 h-2.5" />Nomor SPM</label>
              <ClearableInput placeholder="—" value={updates.nomor_spm === "__clear__" ? "" : updates.nomor_spm} isClear={updates.nomor_spm === "__clear__"} onChange={e => setField("nomor_spm", e.target.value)} onClear={() => toggleClearField("nomor_spm")} />
            </div>
            <div className="space-y-0.5">
              <label className="text-[10px] text-muted-foreground flex items-center gap-1"><Truck className="w-2.5 h-2.5" />Perolehan Dari</label>
              <ClearableInput placeholder="—" value={updates.perolehan_dari_nama === "__clear__" ? "" : updates.perolehan_dari_nama} isClear={updates.perolehan_dari_nama === "__clear__"} onChange={e => setField("perolehan_dari_nama", e.target.value)} onClear={() => toggleClearField("perolehan_dari_nama")} />
            </div>
            <div className="space-y-0.5">
              <label className="text-[10px] text-muted-foreground flex items-center gap-1"><FileCheck className="w-2.5 h-2.5" />Nomor Kontrak</label>
              <ClearableInput placeholder="—" value={updates.nomor_kontrak === "__clear__" ? "" : updates.nomor_kontrak} isClear={updates.nomor_kontrak === "__clear__"} onChange={e => setField("nomor_kontrak", e.target.value)} onClear={() => toggleClearField("nomor_kontrak")} />
            </div>
            <div className="space-y-0.5">
              <label className="text-[10px] text-muted-foreground flex items-center gap-1"><FileCheck className="w-2.5 h-2.5" />Bukti Perolehan (BAST)</label>
              <ClearableInput placeholder="—" value={updates.nomor_bukti_perolehan === "__clear__" ? "" : updates.nomor_bukti_perolehan} isClear={updates.nomor_bukti_perolehan === "__clear__"} onChange={e => setField("nomor_bukti_perolehan", e.target.value)} onClear={() => toggleClearField("nomor_bukti_perolehan")} />
            </div>
            <div className="space-y-0.5">
              <label className="text-[10px] text-muted-foreground flex items-center gap-1"><Package className="w-2.5 h-2.5" />Supplier</label>
              <ClearableInput placeholder="—" value={updates.supplier === "__clear__" ? "" : updates.supplier} isClear={updates.supplier === "__clear__"} onChange={e => setField("supplier", e.target.value)} onClear={() => toggleClearField("supplier")} />
            </div>
            <div className="space-y-0.5">
              <label className="text-[10px] text-muted-foreground flex items-center gap-1"><Calendar className="w-2.5 h-2.5" />Tanggal Beli</label>
              <ClearableInput type="date" value={updates.purchase_date === "__clear__" ? "" : updates.purchase_date} isClear={updates.purchase_date === "__clear__"} onChange={e => setField("purchase_date", e.target.value)} onClear={() => toggleClearField("purchase_date")} />
            </div>
            <div className="space-y-0.5">
              <label className="text-[10px] text-muted-foreground flex items-center gap-1"><DollarSign className="w-2.5 h-2.5" />Harga (Rp)</label>
              <ClearableInput type="number" placeholder="—" value={updates.purchase_price === "__clear__" ? "" : updates.purchase_price} isClear={updates.purchase_price === "__clear__"} onChange={e => setField("purchase_price", e.target.value)} onClear={() => toggleClearField("purchase_price")} />
            </div>
          </div>
          </Section>

          {/* ── Identitas & Catatan ── */}
          <Section icon={Package} title="Identitas & Catatan">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
            <div className="space-y-0.5">
              <label className="text-[10px] text-muted-foreground flex items-center gap-1"><Tag className="w-2.5 h-2.5" />Brand</label>
              <ClearableInput placeholder="—" value={updates.brand === "__clear__" ? "" : updates.brand} isClear={updates.brand === "__clear__"} onChange={e => setField("brand", e.target.value)} onClear={() => toggleClearField("brand")} />
            </div>
            <div className="space-y-0.5">
              <label className="text-[10px] text-muted-foreground flex items-center gap-1"><Tag className="w-2.5 h-2.5" />Model</label>
              <ClearableInput placeholder="—" value={updates.model === "__clear__" ? "" : updates.model} isClear={updates.model === "__clear__"} onChange={e => setField("model", e.target.value)} onClear={() => toggleClearField("model")} />
            </div>

            {/* Catatan */}
            <div className="space-y-0.5">
              <label className="text-[10px] text-muted-foreground flex items-center gap-1"><StickyNote className="w-2.5 h-2.5" />Catatan</label>
              <ClearableInput placeholder="—" value={updates.notes === "__clear__" ? "" : updates.notes} isClear={updates.notes === "__clear__"} onChange={e => setField("notes", e.target.value)} onClear={() => toggleClearField("notes")} />
            </div>
          </div>
          </Section>

          {/* ── Pengguna / Penanggung Jawab — struktur sama seperti form edit ── */}
          <Section icon={UserRound} title="Pengguna / Penanggung Jawab">
            <div className="p-2 rounded-md border border-blue-200 dark:border-blue-800 bg-background/50">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {/* Melekat ke */}
                <div className="space-y-0.5">
                  <label className="text-[10px] text-muted-foreground">Melekat ke</label>
                  <div className="grid grid-cols-3 gap-1">
                    {PENGGUNA_MELEKAT_OPTIONS.map(o => (
                      <button key={o} type="button" onClick={() => setPenggunaMelekat(o)}
                        className={`h-7 rounded-md border text-[10px] font-semibold leading-tight px-1 transition-colors ${updates.pengguna_melekat_ke === o ? 'bg-blue-600 border-blue-600 text-white' : 'bg-background border-border text-foreground/80 hover:bg-accent'}`}>
                        {o}
                      </button>
                    ))}
                  </div>
                </div>
                {/* Nama pengguna — di HP tampil SETELAH Jenis Operasional/Jabatan
                    (order-2); di desktop kembali ke urutan sumber (grid 2 kolom). */}
                <div className="space-y-0.5 order-2 sm:order-none">
                  <label className="text-[10px] text-muted-foreground">{PENGGUNA_NAME_LABELS[updates.pengguna_melekat_ke] || "Nama Pengguna"}</label>
                  <ClearableInput placeholder="—" value={updates.user === "__clear__" ? "" : updates.user} isClear={updates.user === "__clear__"} onChange={e => setField("user", e.target.value)} onClear={() => toggleClearField("user")} />
                </div>
                {/* NIP/NIK pegawai pengguna */}
                <div className="space-y-0.5 order-2 sm:order-none">
                  <label className="text-[10px] text-muted-foreground">NIP/NIK Pegawai</label>
                  <ClearableInput placeholder="—" value={updates.pengguna_nip === "__clear__" ? "" : updates.pengguna_nip} isClear={updates.pengguna_nip === "__clear__"} onChange={e => setField("pengguna_nip", e.target.value)} onClear={() => toggleClearField("pengguna_nip")} />
                </div>
                {/* Nama Jabatan (bila melekat ke Jabatan) — di HP di atas Nama */}
                {updates.pengguna_melekat_ke === "Jabatan" && (
                  <div className="space-y-0.5 order-1 sm:order-none">
                    <label className="text-[10px] text-muted-foreground">Nama Jabatan</label>
                    <ClearableInput placeholder="Contoh: Kepala Subbagian Umum" value={updates.pengguna_jabatan === "__clear__" ? "" : updates.pengguna_jabatan} isClear={updates.pengguna_jabatan === "__clear__"} onChange={e => setField("pengguna_jabatan", e.target.value)} onClear={() => toggleClearField("pengguna_jabatan")} />
                  </div>
                )}
                {/* Jenis Operasional (bila melekat ke Operasional) — di HP di atas Nama */}
                {updates.pengguna_melekat_ke === "Operasional" && (
                  <div className="space-y-0.5 order-1 sm:order-none">
                    <label className="text-[10px] text-muted-foreground">Jenis Operasional</label>
                    <div className="grid grid-cols-2 gap-1">
                      {OPERASIONAL_JENIS_OPTIONS.map(o => (
                        <button key={o} type="button" onClick={() => setOperasionalJenis(o)}
                          className={`h-7 rounded-md border text-[9px] font-semibold leading-tight px-1 transition-colors ${updates.operasional_jenis === o ? 'bg-blue-600 border-blue-600 text-white' : 'bg-background border-border text-foreground/80 hover:bg-accent'}`}>
                          {o}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {/* Nomor BAST — selalu paling bawah di blok pengguna */}
                <div className="space-y-0.5 order-3 sm:order-none">
                  <label className="text-[10px] text-muted-foreground flex items-center gap-1"><FileCheck className="w-2.5 h-2.5" />Nomor BAST</label>
                  <ClearableInput placeholder="—" value={updates.nomor_bast === "__clear__" ? "" : updates.nomor_bast} isClear={updates.nomor_bast === "__clear__"} onChange={e => setField("nomor_bast", e.target.value)} onClear={() => toggleClearField("nomor_bast")} />
                </div>
              </div>
            </div>
          </Section>

          {/* ── Koordinat GPS ── */}
          <Section icon={Navigation} title="Koordinat GPS">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              <div className="space-y-0.5">
                <label className="text-[10px] text-muted-foreground flex items-center gap-1"><Navigation className="w-2.5 h-2.5" />Latitude</label>
                <ClearableInput placeholder="—" value={updates.koordinat_latitude === "__clear__" ? "" : updates.koordinat_latitude} isClear={updates.koordinat_latitude === "__clear__"} onChange={e => setField("koordinat_latitude", e.target.value)} onClear={() => toggleClearField("koordinat_latitude")} />
              </div>
              <div className="space-y-0.5">
                <label className="text-[10px] text-muted-foreground flex items-center gap-1"><Navigation className="w-2.5 h-2.5" />Longitude</label>
                <ClearableInput placeholder="—" value={updates.koordinat_longitude === "__clear__" ? "" : updates.koordinat_longitude} isClear={updates.koordinat_longitude === "__clear__"} onChange={e => setField("koordinat_longitude", e.target.value)} onClear={() => toggleClearField("koordinat_longitude")} />
              </div>
              <div className="space-y-0.5 col-span-2 sm:col-span-1">
                <label className="text-[10px] text-muted-foreground">Ambil Otomatis</label>
                <button
                  type="button"
                  onClick={fetchGPS}
                  disabled={gpsLoading}
                  className="w-full h-7 px-2 flex items-center justify-center gap-1 text-[11px] font-medium bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 rounded-md border border-emerald-300 dark:border-emerald-700 hover:bg-emerald-200 dark:hover:bg-emerald-900/50 transition-colors"
                  data-testid="batch-gps-btn"
                  title="Ambil lokasi GPS saat ini"
                >
                  {gpsLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <LocateFixed className="w-3 h-3" />}
                  Ambil GPS
                </button>
              </div>
            </div>
          </Section>

          {/* ── Foto ── */}
          <div className="mt-2 pt-2 border-t border-blue-200 dark:border-blue-800">
            <div className="flex items-center gap-1 mb-1 text-[10px] font-semibold uppercase tracking-wide text-blue-700/80 dark:text-blue-300/80"><Camera className="w-3 h-3" />Foto</div>
            {clearPhotos ? (
              <div className="flex items-center gap-2 p-2 bg-red-50 dark:bg-red-900/20 border border-red-300 dark:border-red-700 rounded-md">
                <Trash2 className="w-4 h-4 text-red-500 flex-shrink-0" />
                <span className="text-xs text-red-600 dark:text-red-400 flex-1">Semua foto akan dihapus dari {selectedCount} aset</span>
                <button onClick={() => setClearPhotos(false)} className="text-red-400 hover:text-red-600"><X className="w-4 h-4" /></button>
              </div>
            ) : (
              <div className="space-y-1.5">
                {(updates.batch_photos || []).length > 0 && (
                  <>
                    <div className="flex flex-wrap gap-1.5">
                      {(updates.batch_photos || []).map((p, i) => (
                        <div key={i} className="relative w-12 h-12 flex-shrink-0">
                          <img src={p} alt={`Foto ${i + 1}`} className="w-12 h-12 object-cover rounded border" />
                          <button onClick={() => removePhoto(i)} title="Hapus foto ini" aria-label={`Hapus foto ${i + 1}`}
                            className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-red-500 text-white flex items-center justify-center shadow ring-1 ring-white dark:ring-slate-900">
                            <X className="w-2.5 h-2.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                    <span className="text-[10px] text-muted-foreground">{(updates.batch_photos || []).length} foto akan ditambahkan ke {selectedCount} aset (maks {MAX_BATCH_PHOTOS}/aset)</span>
                  </>
                )}
                {(updates.batch_photos || []).length < MAX_BATCH_PHOTOS && (
                  <div className="flex gap-2">
                    {/* Dua opsi sumber: KAMERA (jepret langsung) & GALERI (multi-pilih). */}
                    <label className="flex-1 flex items-center justify-center gap-1.5 text-xs text-blue-600 dark:text-blue-400 bg-blue-100/50 dark:bg-blue-900/30 hover:bg-blue-100 dark:hover:bg-blue-900/50 rounded-md p-2 cursor-pointer border border-dashed border-blue-300 dark:border-blue-700" data-testid="batch-photo-camera">
                      <Camera className="w-4 h-4" />Kamera
                      <input type="file" accept="image/*" capture="environment" className="hidden" onChange={handlePhotoUpload} />
                    </label>
                    <label className="flex-1 flex items-center justify-center gap-1.5 text-xs text-blue-600 dark:text-blue-400 bg-blue-100/50 dark:bg-blue-900/30 hover:bg-blue-100 dark:hover:bg-blue-900/50 rounded-md p-2 cursor-pointer border border-dashed border-blue-300 dark:border-blue-700" data-testid="batch-photo-upload">
                      <Images className="w-4 h-4" />Galeri
                      <input ref={photoInputRef} type="file" accept="image/*" multiple className="hidden" onChange={handlePhotoUpload} />
                    </label>
                    <button
                      onClick={() => setClearPhotos(true)}
                      className="flex items-center justify-center text-red-500 hover:text-red-700 bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/40 rounded-md px-2.5 py-2 border border-dashed border-red-300 dark:border-red-700 transition-colors flex-shrink-0"
                      data-testid="batch-clear-photos-btn"
                      title="Hapus semua foto dari aset terpilih"
                      aria-label="Hapus semua foto"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ── Kelengkapan Dokumen & Peralatan ── */}
          <div className="mt-2 pt-2 border-t border-blue-200 dark:border-blue-800">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-blue-700/80 dark:text-blue-300/80">
                <FileCheck className="w-3 h-3" />Kelengkapan Dokumen & Peralatan
                {activeDocCount > 0 && <span className="text-[9px] bg-blue-200 dark:bg-blue-800/50 text-blue-700 dark:text-blue-300 px-1 rounded-full ml-1 normal-case">{activeDocCount} aktif</span>}
              </div>
              {!clearDocChecklist && (
                <button
                  onClick={() => setClearDocChecklist(true)}
                  className="flex items-center gap-1 text-[10px] text-red-500 hover:text-red-700 hover:underline"
                  data-testid="batch-clear-docs-btn"
                >
                  <Trash2 className="w-3 h-3" />Hapus Semua Dokumen
                </button>
              )}
            </div>

            {clearDocChecklist ? (
              <div className="flex items-center gap-2 p-2 bg-red-50 dark:bg-red-900/20 border border-red-300 dark:border-red-700 rounded-md">
                <Trash2 className="w-4 h-4 text-red-500 flex-shrink-0" />
                <span className="text-xs text-red-600 dark:text-red-400 flex-1">Semua dokumen kelengkapan akan dihapus dari {selectedCount} aset</span>
                <button onClick={() => setClearDocChecklist(false)} className="text-red-400 hover:text-red-600"><X className="w-4 h-4" /></button>
              </div>
            ) : (
              <>
                <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
                  {docItems.map((item, idx) => (
                    <div key={idx}
                      className={`rounded-md border transition-all ${item._active ? 'border-blue-400 dark:border-blue-600 bg-blue-50 dark:bg-blue-900/30' : 'border-border bg-card hover:bg-muted/50'}`}
                      data-testid={`batch-doc-item-${idx}`}
                    >
                      {/* Toggle row */}
                      <div className="flex items-center gap-2 p-1.5 cursor-pointer" onClick={() => toggleDocItem(idx)}>
                        <div className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 ${item._active ? 'bg-blue-500 border-blue-500 text-white' : 'border-border'}`}>
                          {item._active && <Check className="w-2.5 h-2.5" />}
                        </div>
                        <span className={`text-[11px] flex-1 ${item._active ? 'text-blue-800 dark:text-blue-300 font-medium' : 'text-muted-foreground'}`}>{item.name}</span>
                        {item._active && ((item.photos?.length || 0) + (item.documents?.length || 0) > 0) && (
                          <span className="text-[9px] bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-400 px-1 rounded">{(item.photos?.length || 0) + (item.documents?.length || 0)} file</span>
                        )}
                      </div>

                      {/* Upload area when active */}
                      {item._active && (
                        <div className="px-2 pb-2 space-y-1.5">
                          <label className="flex items-center justify-center gap-1 text-[10px] text-blue-600 dark:text-blue-400 bg-blue-100/50 dark:bg-blue-900/20 hover:bg-blue-100 dark:hover:bg-blue-900/40 rounded px-2 py-1 cursor-pointer border border-dashed border-blue-300 dark:border-blue-700">
                            <FileUp className="w-3 h-3" />Upload Foto/PDF untuk semua aset
                            <input type="file" accept="image/*,.pdf" multiple className="hidden" onChange={e => handleDocFileUpload(idx, e)} />
                          </label>
                          <div className="text-[9px] text-muted-foreground">Maks 3 foto + 1 PDF per item</div>

                          {/* Uploaded files preview */}
                          {((item.photos?.length || 0) + (item.documents?.length || 0) > 0) && (
                            <div className="space-y-1">
                              {(item.photos || []).map((photo, pi) => (
                                <div key={`p${pi}`} className="flex items-center gap-1.5 bg-card rounded p-1 border border-border">
                                  <img src={photo} alt="" className="w-8 h-8 object-cover rounded" />
                                  <span className="text-[9px] text-muted-foreground flex-1">Foto {pi + 1}</span>
                                  <button type="button" onClick={() => removeDocFile(idx, 'photo', pi)} className="text-red-400 hover:text-red-600"><X className="w-3 h-3" /></button>
                                </div>
                              ))}
                              {(item.documents || []).map((doc, di) => (
                                <div key={`d${di}`} className="flex items-center gap-1.5 bg-red-50 dark:bg-red-900/20 rounded p-1 border border-red-200 dark:border-red-700">
                                  <FileText className="w-4 h-4 text-red-600 dark:text-red-400 flex-shrink-0" />
                                  <span className="text-[9px] text-red-700 dark:text-red-400 flex-1 truncate">{doc.name}</span>
                                  <button type="button" onClick={() => removeDocFile(idx, 'doc', di)} className="text-red-400 hover:text-red-600"><X className="w-3 h-3" /></button>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                {/* Tambah dokumen kelengkapan BARU (nama kustom) → langsung
                    aktif & diterapkan massal ke semua aset terpilih. */}
                <div className="flex gap-1 mt-1.5">
                  <Input
                    placeholder="Tambah dokumen baru…"
                    value={customDoc}
                    onChange={e => setCustomDoc(e.target.value)}
                    onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addCustomDoc(); } }}
                    className="h-7 text-xs flex-1"
                    data-testid="batch-doc-custom-input"
                  />
                  <button
                    type="button"
                    onClick={addCustomDoc}
                    disabled={!customDoc.trim()}
                    className="h-7 px-2 rounded-md border border-blue-300 dark:border-blue-700 bg-blue-100/50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 text-[11px] font-semibold flex items-center gap-1 flex-shrink-0 hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors disabled:opacity-40 disabled:pointer-events-none"
                    data-testid="batch-doc-custom-add"
                  >
                    <Plus className="w-3 h-3" />Tambah
                  </button>
                </div>
                <p className="text-[9px] text-muted-foreground mt-1">Klik item untuk mengaktifkan (atau tambahkan dokumen baru), lalu upload foto/PDF yang akan diterapkan ke semua aset terpilih</p>
              </>
            )}
          </div>
        </>
      )}

      {/* Action Buttons */}
      <div className="flex items-center gap-2 mt-3">
        <Button onClick={handleApply} disabled={!hasUpdates || updating} className="bg-blue-600 hover:bg-blue-700 text-white h-8 text-xs" data-testid="batch-apply-btn">
          {updating ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <CheckSquare className="w-3 h-3 mr-1" />}
          Terapkan ke {selectedCount} aset
        </Button>
        <Button variant="outline" size="sm" className="h-8 text-xs" onClick={onClose}>Batal</Button>
        <span className="text-[10px] text-muted-foreground ml-auto">
          {setCount > 0 && <span className="text-blue-600 dark:text-blue-400">{setCount} diubah</span>}
          {setCount > 0 && clearCount > 0 && <span className="mx-1">·</span>}
          {clearCount > 0 && <span className="text-red-500">{clearCount} dikosongkan</span>}
          {setCount === 0 && clearCount === 0 && "Pilih field untuk diubah"}
        </span>
      </div>
    </div>
  );
});

export default BatchEditPanel;
