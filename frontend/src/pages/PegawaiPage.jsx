import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Search, Plus, Pencil, Trash2, Loader2, IdCard, Upload, Download,
  AlertTriangle, Network, Wand2, MoreVertical,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
  DropdownMenuLabel, DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";
import { downloadFileWithProgress } from "@/lib/downloadFile";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function getApiError(err, fallback) {
  return err?.response?.data?.detail || fallback;
}

const EMPTY = {
  mode: "tambah", nama: "", nip: "", gelar_depan: "", gelar_belakang: "",
  kewarganegaraan: "wni", jenis_identitas_wna: "", nomor_identitas_wna: "",
  jenis_kelamin: "", tempat_lahir: "", tanggal_lahir: "", agama: "",
  status_perkawinan: "", status_kepegawaian: "", sub_kategori_non_asn: "",
  pangkat_golongan: "", jabatan: "", jenis_jabatan: "", kategori_pegawai: "",
  eselon: "", eselon1: "", eselon2: "", eselon3: "", eselon4: "", eselon5: "",
  unit_kerja: "", unit_organisasi: "", npwp: "", pendidikan_terakhir: "",
  no_hp: "", email: "", alamat: "", nama_bank: "", no_rekening: "",
  nomor_kontrak: "", tgl_mulai_kontrak: "", tgl_selesai_kontrak: "",
  jenis_kontrak_non_asn: "", perusahaan_penyedia: "",
  tanggal_akhir_jabatan: "", kode_satker: "", kode_satker_lengkap: "",
  tmt_jabatan: "", status: "aktif", keterangan: "",
};

// Status kontrak Non-ASN utk badge (pemegang aset berisiko saat kontrak habis).
function statusKontrak(p) {
  const sel = String(p.tgl_selesai_kontrak || "").slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(sel)) return null;
  const sisa = Math.ceil((new Date(sel) - new Date()) / 86400000);
  if (sisa < 0) return { habis: true, teks: `Kontrak berakhir ${Math.abs(sisa)} hari lalu`, singkat: "kontrak habis" };
  if (sisa <= 30) return { segera: true, teks: `Kontrak berakhir dalam ${sisa} hari`, singkat: `kontrak ≤${sisa} hr` };
  return null;
}

// Nama + gelar untuk tampilan (samakan dengan nama_lengkap di backend).
function namaLengkap(p) {
  const depan = (p.gelar_depan || "").trim();
  const belakang = (p.gelar_belakang || "").trim();
  let out = `${depan} ${(p.nama || "").trim()}`.trim();
  if (belakang) out = `${out}, ${belakang}`;
  return out;
}

/**
 * Master Pegawai (data kepegawaian menyeluruh satker, adopsi SIMAN-G).
 *
 * Berbeda dari Referensi Pejabat (khusus penanda tangan/penatausahaan):
 * halaman ini menampung SELURUH pegawai + unit kerjanya sebagai rujukan
 * lintas modul. Semua user login melihat; admin mengelola (CRUD).
 */
export default function PegawaiPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [items, setItems] = useState([]);
  const [rekap, setRekap] = useState(null);
  const [ref, setRef] = useState({ jenis_kelamin: [], status_kepegawaian: [], jenis_jabatan: [], kategori_pegawai: [], sub_kategori_non_asn: [], agama: [], status_perkawinan: [], status: [] });
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState(null);
  const [deteksi, setDeteksi] = useState(null); // hasil deteksi jenis nomor identitas
  // Filter & sortir lanjutan (pola halaman aset)
  const [fStatus, setFStatus] = useState("");
  const [fStatusPeg, setFStatusPeg] = useState("");
  const [fUnit, setFUnit] = useState("");
  const [sortBy, setSortBy] = useState("nama");
  const [sortDir, setSortDir] = useState("asc");
  const [tabForm, setTabForm] = useState("identitas"); // tab aktif form 5-tab
  const [saving, setSaving] = useState(false);
  const [mengimpor, setMengimpor] = useState(false);
  const [hasilImpor, setHasilImpor] = useState(null);
  const [serahTerima, setSerahTerima] = useState([]); // pegawai berisiko masih pegang aset
  const [detailAset, setDetailAset] = useState(null); // {pegawai, items, memuat}
  const [units, setUnits] = useState([]);             // master unit kerja hierarkis
  const [kelolaUnit, setKelolaUnit] = useState(null); // {eselon, nama, parentId, sibuk}
  const [struktur, setStruktur] = useState(false);    // dialog bagan struktur organisasi
  const [strukturBuka, setStrukturBuka] = useState({}); // {unitId: true} simpul terbuka
  const fileRef = useRef(null);
  const { confirm, confirmDialog } = useConfirm();

  const muatUnits = useCallback(() => {
    axios.get(`${API}/unit-kerja`)
      .then((r) => setUnits(r.data?.items || []))
      .catch(() => setUnits([]));
  }, []);

  const bukaForm = (data) => { setTabForm("identitas"); setForm(data); };

  // Opsi bertingkat: opsi Eselon N mengikuti induk Eselon N-1 yang dipilih
  // (dicocokkan via nama — data pegawai menyimpan nama unit). Induk tak
  // dipilih/tak dikenal → semua unit level itu.
  const opsiEselon = useCallback((level, f) => {
    const perLevel = units.filter((u) => String(u.eselon) === String(level));
    if (level === 1) return perLevel.map((u) => u.nama_unit);
    const indukNama = String(f?.[`eselon${level - 1}`] || "").trim();
    const induk = units.find((u) => String(u.eselon) === String(level - 1) && u.nama_unit === indukNama);
    const anak = induk ? perLevel.filter((u) => u.parent_id === induk.id) : perLevel;
    return anak.map((u) => u.nama_unit);
  }, [units]);

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const uraian = useCallback((list, kode) => (ref[list] || []).find((o) => o.kode === kode)?.uraian || kode, [ref]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/pegawai`);
      setItems(r.data?.items || []);
    } catch (err) {
      toast.error(getApiError(err, "Gagal memuat daftar pegawai"));
    } finally {
      setLoading(false);
    }
    // Rekap per unit kerja (ringkasan adopsi SIMAN-G) — best-effort.
    axios.get(`${API}/pegawai/rekap-unit`)
      .then((r) => setRekap(r.data))
      .catch(() => setRekap(null));
    // Pegawai berisiko yang masih memegang aset (alert serah terima BMN).
    axios.get(`${API}/pegawai/perlu-serah-terima`)
      .then((r) => setSerahTerima(r.data?.items || []))
      .catch(() => setSerahTerima([]));
  }, []);

  useEffect(() => { muatUnits(); }, [muatUnits]);

  const tambahUnit = async () => {
    if (!kelolaUnit?.nama?.trim()) { toast.error("Nama unit wajib diisi"); return; }
    const level = Number(kelolaUnit.eselon);
    if (level > 1 && !kelolaUnit.parentId) {
      toast.error(`Pilih induk Eselon ${level - 1} dulu`); return;
    }
    setKelolaUnit((k) => ({ ...k, sibuk: true }));
    try {
      await axios.post(`${API}/unit-kerja`, {
        nama_unit: kelolaUnit.nama.trim(), eselon: String(level),
        parent_id: level > 1 ? kelolaUnit.parentId : "",
      });
      toast.success(`Unit Eselon ${level} ditambahkan`);
      setKelolaUnit((k) => ({ ...k, nama: "", sibuk: false }));
      muatUnits();
    } catch (err) {
      toast.error(getApiError(err, "Gagal menambah unit"));
      setKelolaUnit((k) => ({ ...k, sibuk: false }));
    }
  };

  const hapusUnit = async (u) => {
    const ok = await confirm({
      title: `Hapus unit ${u.nama_unit}?`,
      description: `Eselon ${u.eselon}. Ditolak bila masih punya sub-unit atau dipakai pegawai.`,
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/unit-kerja/${u.id}`);
      toast.success(`Unit ${u.nama_unit} dihapus`);
      muatUnits();
    } catch (err) { toast.error(getApiError(err, "Gagal menghapus unit")); }
  };

  // Jumlah pegawai sebuah unit: pegawai yang eselon{level}-nya = nama unit.
  const jumlahPegawaiUnit = useCallback((u) => items.filter(
    (p) => String(p[`eselon${u.eselon}`] || "").trim() === u.nama_unit).length,
  [items]);

  const bangunDariPegawai = async () => {
    setKelolaUnit((k) => ({ ...k, sibuk: true }));
    try {
      const r = await axios.post(`${API}/unit-kerja/bangun-dari-pegawai`);
      toast.success(`Master unit dibangun: ${r.data.dibuat} unit baru dari data pegawai`);
      muatUnits();
    } catch (err) { toast.error(getApiError(err, "Gagal membangun master unit")); }
    finally { setKelolaUnit((k) => ({ ...k, sibuk: false })); }
  };

  const bukaDetailAset = async (p) => {
    setDetailAset({ pegawai: p, items: [], memuat: true });
    try {
      const r = await axios.get(`${API}/pegawai/${p.id}/aset`);
      setDetailAset({ pegawai: p, items: r.data?.items || [], memuat: false });
    } catch (err) {
      toast.error(getApiError(err, "Gagal memuat aset pegawai"));
      setDetailAset(null);
    }
  };

  useEffect(() => {
    load();
    // Ambil SEMUA kunci referensi apa adanya — pemetaan manual sebelumnya
    // membuang kewarganegaraan/jenis_identitas_wna/pangkat_golongan/digit_bank
    // sehingga dropdown Kewarganegaraan kosong & tak bisa dipakai (bug).
    axios.get(`${API}/pegawai/referensi`)
      .then((r) => setRef((prev) => ({ ...prev, ...(r.data || {}) })))
      .catch(() => {});
  }, [load]);

  // Deteksi jenis nomor identitas (NIP PNS / NI PPPK / NRP / NIK) — debounce
  // ke server agar logika satu sumber dengan label laporan.
  useEffect(() => {
    const nomor = String(form?.nip || "").trim();
    if (!nomor || nomor.length < 5) { setDeteksi(null); return undefined; }
    const t = setTimeout(() => {
      axios.get(`${API}/pegawai/deteksi-identitas`, { params: { nomor } })
        .then((r) => setDeteksi(r.data))
        .catch(() => setDeteksi(null));
    }, 350);
    return () => clearTimeout(t);
  }, [form?.nip]);

  const unduhTemplate = () => {
    downloadFileWithProgress(`${API}/pegawai/template-impor`, "template_impor_pegawai.csv",
      { label: "Template Impor Pegawai (CSV)" }).catch(() => {});
  };

  const pilihBerkas = () => fileRef.current?.click();

  const onBerkasDipilih = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // reset agar file sama bisa dipilih ulang
    if (!file) return;
    setMengimpor(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await axios.post(`${API}/pegawai/impor`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 120000,
      });
      setHasilImpor(r.data);
      toast.success(`Impor selesai: ${r.data.dibuat} baru, ${r.data.diperbarui} diperbarui`);
      load();
    } catch (err) {
      toast.error(getApiError(err, "Gagal mengimpor pegawai"));
    } finally {
      setMengimpor(false);
    }
  };

  const submitForm = async () => {
    if (!form) return;
    if (!(form.nama || "").trim()) { toast.error("Nama pegawai wajib diisi"); return; }
    setSaving(true);
    const body = { ...form };
    delete body.mode; delete body.id; delete body.created_at; delete body.updated_at;
    try {
      if (form.mode === "tambah") {
        await axios.post(`${API}/pegawai`, body);
        toast.success(`Pegawai ${form.nama} ditambahkan`);
      } else {
        const r = await axios.put(`${API}/pegawai/${form.id}`, body);
        toast.success(`Pegawai ${form.nama} diperbarui`);
        // Peringatan lunak: status non-aktif tapi masih memegang aset.
        if (r.data?.peringatan) toast.warning(r.data.peringatan, { duration: 9000 });
      }
      setForm(null);
      load();
    } catch (err) {
      toast.error(getApiError(err, "Gagal menyimpan pegawai"));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (it) => {
    const ok = await confirm({
      title: `Hapus pegawai ${it.nama}?`,
      description: "Data pegawai ini akan dihapus dari master pegawai.",
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/pegawai/${it.id}`);
      toast.success(`Pegawai ${it.nama} dihapus`);
      load();
    } catch (err) {
      toast.error(getApiError(err, "Gagal menghapus pegawai"));
    }
  };

  const q = search.trim().toLowerCase();
  // Filter & sortir lanjutan (pola halaman aset) — semua dihitung klien
  // karena daftar sudah dimuat penuh per satker.
  const filtered = useMemo(() => {
    let hasil = items;
    if (q) {
      hasil = hasil.filter((it) =>
        [it.nama, it.nip, it.jabatan, it.unit_kerja, it.email, it.perusahaan_penyedia]
          .some((v) => String(v || "").toLowerCase().includes(q)));
    }
    if (fStatus) hasil = hasil.filter((it) => (it.status || "aktif") === fStatus);
    if (fStatusPeg) hasil = hasil.filter((it) => (it.status_kepegawaian || "") === fStatusPeg);
    if (fUnit) hasil = hasil.filter((it) => (it.unit_kerja || "") === fUnit);
    const arah = sortDir === "desc" ? -1 : 1;
    const nilai = (it) => {
      const im = it.info_masa || {};
      switch (sortBy) {
        case "updated": return String(it.updated_at || "");
        case "pensiun": return im.sisa_hari_pensiun ?? Infinity;
        case "kontrak": return im.kontrak?.sisa_hari ?? Infinity;
        case "jabatan": return String(it.jabatan || "").toLowerCase();
        case "unit": return String(it.unit_kerja || "").toLowerCase();
        default: return String(it.nama || "").toLowerCase();
      }
    };
    return [...hasil].sort((a, b) => {
      const va = nilai(a), vb = nilai(b);
      if (va < vb) return -1 * arah;
      if (va > vb) return 1 * arah;
      return String(a.nama || "").localeCompare(String(b.nama || ""));
    });
  }, [items, q, fStatus, fStatusPeg, fUnit, sortBy, sortDir]);

  // Unit kerja yang benar-benar terpakai di data (utk pilihan filter)
  const unitTerpakai = useMemo(
    () => [...new Set(items.map((it) => it.unit_kerja).filter(Boolean))].sort(),
    [items]);

  // Format sisa hari → teks ringkas Indonesia ("28 hr lagi"/"3 bln lagi"/
  // "lewat 12 hr"); null → "".
  const fmtSisa = (hari) => {
    if (hari == null) return "";
    if (hari < 0) return `lewat ${Math.abs(hari)} hr`;
    if (hari === 0) return "hari ini";
    if (hari < 90) return `${hari} hr lagi`;
    if (hari < 730) return `${Math.round(hari / 30)} bln lagi`;
    return `${Math.round(hari / 365)} th lagi`;
  };
  // "diubah X lalu" dari updated_at (ISO)
  const sejakUpdate = (iso) => {
    const t = Date.parse(iso || "");
    if (Number.isNaN(t)) return "";
    const dtk = Math.max(0, Math.floor((Date.now() - t) / 1000));
    if (dtk < 3600) return `${Math.max(1, Math.floor(dtk / 60))} mnt lalu`;
    if (dtk < 86400) return `${Math.floor(dtk / 3600)} jam lalu`;
    if (dtk < 86400 * 60) return `${Math.floor(dtk / 86400)} hr lalu`;
    if (dtk < 86400 * 730) return `${Math.floor(dtk / (86400 * 30))} bln lalu`;
    return `${Math.floor(dtk / (86400 * 365))} th lalu`;
  };

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div className="min-h-screen bg-background" data-testid="pegawai-page">
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button type="button" onClick={onBack} title="Kembali ke Beranda Modul" aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="pegawai-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-sky-600 flex items-center justify-center flex-shrink-0">
            <IdCard className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Master Pegawai</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              {items.length} pegawai · data kepegawaian menyeluruh &amp; unit kerja (adopsi SIMAN-G)
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        <div className="bg-card rounded-xl border border-border shadow-sm p-2 sm:p-3">
          {/* Baris utama: pencarian + aksi. Di HP tombol data (Struktur/
              Template/Ekspor/Impor) dilipat ke satu menu ⋯ agar hemat ruang;
              di desktop tetap tampil terpisah berlabel. Tombol Tambah selalu
              terlihat sebagai aksi utama. */}
          <div className="flex items-center gap-2">
            <div className="relative flex-1 min-w-0">
              <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
              <Input value={search} onChange={(e) => setSearch(e.target.value)}
                placeholder="Cari nama / NIP / jabatan / unit / email…" className="pl-9 h-10" data-testid="pegawai-search" />
            </div>
            {isAdmin && (
              <input ref={fileRef} type="file" accept=".xlsx,.xlsm,.csv" className="hidden"
                onChange={onBerkasDipilih} data-testid="pegawai-impor-file" />
            )}
            {/* Desktop: tombol terpisah berlabel */}
            <div className="hidden sm:flex items-center gap-2">
              {units.length > 0 && (
                <Button variant="outline" className="h-10 gap-1.5" onClick={() => setStruktur(true)}
                  title="Struktur Organisasi" aria-label="Struktur Organisasi"
                  data-testid="pegawai-struktur">
                  <Network className="w-4 h-4" />Struktur
                </Button>
              )}
              {isAdmin && (
                <>
                  <Button variant="outline" className="h-10 gap-1.5" onClick={unduhTemplate}
                    title="Unduh Template Impor (CSV)" aria-label="Unduh Template Impor (CSV)"
                    data-testid="pegawai-template">
                    <Download className="w-4 h-4" />Template
                  </Button>
                  <Button variant="outline" className="h-10 gap-1.5"
                    onClick={() => downloadFileWithProgress(`${API}/pegawai/export-xlsx`,
                      "master_pegawai.xlsx", { label: "Ekspor Master Pegawai (Excel)" }).catch(() => {})}
                    title="Ekspor Excel siap-edit (dropdown + bisa diimpor kembali)"
                    aria-label="Ekspor Excel siap-edit"
                    data-testid="pegawai-export-xlsx">
                    <Download className="w-4 h-4" />Ekspor Excel
                  </Button>
                  <Button variant="outline" className="h-10 gap-1.5" disabled={mengimpor}
                    title="Impor Excel/CSV" aria-label="Impor Excel/CSV"
                    onClick={pilihBerkas} data-testid="pegawai-impor">
                    {mengimpor ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                    Impor Excel
                  </Button>
                </>
              )}
            </div>
            {/* HP: satu menu ⋯ menampung semua aksi data */}
            {(units.length > 0 || isAdmin) && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button type="button"
                    className="sm:hidden h-10 w-10 rounded-lg border border-input bg-background text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
                    aria-label="Menu data pegawai" title="Struktur, template, ekspor, impor"
                    data-testid="pegawai-menu">
                    <MoreVertical className="w-4 h-4" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuLabel className="text-[11px]">Data & berkas pegawai</DropdownMenuLabel>
                  {units.length > 0 && (
                    <DropdownMenuItem className="min-h-[42px]" onClick={() => setStruktur(true)} data-testid="pegawai-struktur-m">
                      <Network className="w-4 h-4 mr-2" />Struktur Organisasi
                    </DropdownMenuItem>
                  )}
                  {isAdmin && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem className="min-h-[42px]" onClick={unduhTemplate} data-testid="pegawai-template-m">
                        <Download className="w-4 h-4 mr-2" />Unduh Template (CSV)
                      </DropdownMenuItem>
                      <DropdownMenuItem className="min-h-[42px]" data-testid="pegawai-export-xlsx-m"
                        onClick={() => downloadFileWithProgress(`${API}/pegawai/export-xlsx`,
                          "master_pegawai.xlsx", { label: "Ekspor Master Pegawai (Excel)" }).catch(() => {})}>
                        <Download className="w-4 h-4 mr-2" />Ekspor Excel
                      </DropdownMenuItem>
                      <DropdownMenuItem className="min-h-[42px]" disabled={mengimpor} onClick={pilihBerkas} data-testid="pegawai-impor-m">
                        {mengimpor ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Upload className="w-4 h-4 mr-2" />}
                        Impor Excel/CSV
                      </DropdownMenuItem>
                    </>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
            {isAdmin && (
              <Button className="h-10 gap-1.5 bg-sky-600 hover:bg-sky-700 text-white flex-shrink-0"
                title="Tambah Pegawai" aria-label="Tambah Pegawai"
                onClick={() => bukaForm({ ...EMPTY })} data-testid="pegawai-add">
                <Plus className="w-4 h-4" /><span className="hidden sm:inline">Tambah</span>
              </Button>
            )}
          </div>
          {/* Baris filter & sortir — di HP jadi grid 2 kolom rapi (bukan
              membungkus berantakan), sebaris penuh di desktop. */}
          <div className="mt-2 space-y-1.5">
            <div className="grid grid-cols-2 sm:flex sm:flex-wrap sm:items-center gap-1.5">
              <select value={fStatusPeg} onChange={(e) => setFStatusPeg(e.target.value)}
                aria-label="Filter status kepegawaian" title="Filter status kepegawaian"
                className="h-9 rounded-md border border-input bg-background px-2 text-xs w-full sm:w-auto min-w-0"
                data-testid="pegawai-f-statuspeg">
                <option value="">Kepegawaian</option>
                {(ref.status_kepegawaian || []).map((o) => <option key={o.kode} value={o.kode}>{o.uraian}</option>)}
              </select>
              <select value={fStatus} onChange={(e) => setFStatus(e.target.value)}
                aria-label="Filter status di satker" title="Filter status di satker"
                className="h-9 rounded-md border border-input bg-background px-2 text-xs w-full sm:w-auto min-w-0"
                data-testid="pegawai-f-status">
                <option value="">Status</option>
                {(ref.status || []).map((o) => <option key={o.kode} value={o.kode}>{o.uraian}</option>)}
              </select>
              <select value={fUnit} onChange={(e) => setFUnit(e.target.value)}
                aria-label="Filter unit kerja" title="Filter unit kerja"
                className="h-9 rounded-md border border-input bg-background px-2 text-xs w-full sm:w-auto min-w-0 sm:max-w-[180px]"
                data-testid="pegawai-f-unit">
                <option value="">Unit kerja</option>
                {unitTerpakai.map((u) => <option key={u} value={u}>{u}</option>)}
              </select>
              {/* Urut + arah dalam satu sel agar berpasangan */}
              <div className="flex items-center gap-1.5 min-w-0">
                <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}
                  aria-label="Urutkan berdasarkan" title="Urutkan berdasarkan"
                  className="h-9 rounded-md border border-input bg-background px-2 text-xs flex-1 sm:flex-none min-w-0"
                  data-testid="pegawai-sort">
                  <option value="nama">Urut: Nama</option>
                  <option value="updated">Urut: Terakhir diubah</option>
                  <option value="pensiun">Urut: Terdekat pensiun</option>
                  <option value="kontrak">Urut: Kontrak berakhir</option>
                  <option value="jabatan">Urut: Jabatan</option>
                  <option value="unit">Urut: Unit kerja</option>
                </select>
                <button type="button" onClick={() => setSortDir((d) => (d === "asc" ? "desc" : "asc"))}
                  aria-label={sortDir === "asc" ? "Urut naik (klik utk turun)" : "Urut turun (klik utk naik)"}
                  title={sortDir === "asc" ? "Urut naik (klik utk turun)" : "Urut turun (klik utk naik)"}
                  className="h-9 w-9 rounded-md border border-input bg-background text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0 min-w-0 min-h-0"
                  data-testid="pegawai-sort-dir">
                  {sortDir === "asc" ? "↑" : "↓"}
                </button>
              </div>
            </div>
            {/* Baris info tipis: reset (bila ada filter) + jumlah pegawai */}
            <div className="flex items-center gap-2">
              {(fStatus || fStatusPeg || fUnit || sortBy !== "nama") && (
                <button type="button"
                  onClick={() => { setFStatus(""); setFStatusPeg(""); setFUnit(""); setSortBy("nama"); setSortDir("asc"); }}
                  className="h-7 px-2 rounded-md text-[11px] font-semibold text-muted-foreground hover:text-foreground hover:bg-muted min-w-0 min-h-0"
                  data-testid="pegawai-f-reset">
                  Reset filter
                </button>
              )}
              <span className="text-[10px] text-muted-foreground ml-auto">{filtered.length}/{items.length} pegawai</span>
            </div>
          </div>
        </div>

        {/* Alert serah terima BMN — pegawai berisiko (keluar/mutasi/pensiun/
            kontrak habis) yang masih tercatat memegang aset. */}
        {serahTerima.length > 0 && (
          <div className="bg-amber-500/10 border border-amber-500/40 rounded-xl shadow-sm p-2.5 sm:p-3" data-testid="pegawai-serah-terima-panel">
            <p className="text-[11px] font-bold uppercase tracking-wide text-amber-700 dark:text-amber-400 mb-1.5 flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5" />Perlu Serah Terima BMN — {serahTerima.length} pegawai berisiko masih memegang aset
            </p>
            <div className="space-y-1">
              {serahTerima.map((p) => (
                <button key={p.id} type="button" onClick={() => bukaDetailAset(p)}
                  className="w-full text-left flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-amber-500/10 min-w-0 min-h-0"
                  data-testid={`pegawai-serah-terima-${p.id}`}>
                  <span className="flex-1 min-w-0">
                    <span className="text-[12px] font-semibold text-foreground">{p.nama}</span>
                    <span className="text-[10px] text-muted-foreground font-mono ml-1.5">{p.nip}</span>
                    <span className="block text-[10px] text-amber-700 dark:text-amber-400 truncate">{p.alasan}{p.unit_kerja ? ` · ${p.unit_kerja}` : ""}</span>
                  </span>
                  <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-700 dark:text-amber-400 text-[10px] font-bold whitespace-nowrap">
                    {p.jumlah_aset} aset
                  </span>
                </button>
              ))}
            </div>
            <p className="text-[10px] text-muted-foreground mt-1.5">
              Tindak lanjut: proses <b>BAST pengembalian</b> atau <b>mutasi pemegang</b> di modul Penggunaan → tab Pemegang.
            </p>
          </div>
        )}

        {rekap && (rekap.unit || []).length > 0 && (
          <div className="bg-card rounded-xl border border-border shadow-sm p-2.5 sm:p-3" data-testid="pegawai-rekap-unit">
            <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground mb-2">
              Rekap per Unit Kerja — {rekap.jumlah_unit} unit · {rekap.jumlah_pegawai} pegawai
            </p>
            <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto pr-1">
              {rekap.unit.map((u) => {
                const tanpaUnit = u.unit_kerja === "(unit kerja belum dicatat)";
                return (
                  <button key={u.unit_kerja} type="button"
                    onClick={() => !tanpaUnit && setSearch(search === u.unit_kerja ? "" : u.unit_kerja)}
                    disabled={tanpaUnit}
                    className={`px-2 py-1 rounded-full border text-[11px] min-w-0 min-h-0 ${
                      search === u.unit_kerja
                        ? "border-sky-500 bg-sky-500/15 text-sky-600 dark:text-sky-400 font-semibold"
                        : tanpaUnit
                          ? "border-border/60 text-muted-foreground/70 cursor-default"
                          : "border-border text-foreground/80 hover:bg-muted"}`}
                    data-testid={`pegawai-rekap-chip-${u.unit_kerja}`}>
                    {u.unit_kerja} <span className="font-bold">{u.jumlah}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-7 h-7 animate-spin text-sky-600" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-16 px-4">
              <IdCard className="w-10 h-10 text-muted-foreground/40 mx-auto mb-3" />
              <p className="text-sm font-medium text-foreground">
                {items.length === 0 ? "Belum ada pegawai" : "Tidak ada yang cocok"}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {isAdmin ? "Tambah data pegawai satker (seluruh pegawai & unit kerjanya)."
                  : "Minta admin menambah data pegawai."}
              </p>
              {isAdmin && items.length === 0 && (
                <Button size="sm" className="mt-3 gap-1.5 bg-sky-600 hover:bg-sky-700 text-white"
                  onClick={() => bukaForm({ ...EMPTY })} data-testid="pegawai-empty-tambah">
                  <Plus className="w-4 h-4" />Tambah Pegawai
                </Button>
              )}
            </div>
          ) : (
            <>
            {/* ── Mobile (<sm): KARTU muat-layar (scroll vertikal saja) —
                ringkas & padat sampai tombol aksi (umpan balik pengguna). ── */}
            <ul className="sm:hidden divide-y divide-border/60" data-testid="pegawai-cards-mobile">
              {filtered.map((it) => {
                const im = it.info_masa || {};
                const k = statusKontrak(it);
                return (
                  <li key={it.id} className="p-3 space-y-1" data-testid={`pegawai-card-${it.id}`}>
                    <div className="flex items-start gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="font-semibold text-foreground text-sm leading-tight break-words">{namaLengkap(it)}</p>
                        <p className="text-[10px] text-muted-foreground font-mono">
                          {im.label_identitas && it.nip ? `${im.label_identitas} ` : ""}{it.nip || "—"}
                        </p>
                      </div>
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold flex-shrink-0 ${
                        (it.status || "aktif") === "aktif"
                          ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                          : "bg-slate-500/15 text-muted-foreground"}`}>
                        {uraian("status", it.status || "aktif")}
                      </span>
                    </div>
                    {(it.jabatan || it.unit_kerja) && (
                      <p className="text-[11px] text-foreground/80 truncate">
                        {[it.jabatan, it.unit_kerja].filter(Boolean).join(" · ")}
                      </p>
                    )}
                    <div className="flex items-center gap-1 flex-wrap text-[9px] font-semibold">
                      {it.status_kepegawaian && (
                        <span className="px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-600 dark:text-sky-400 uppercase">
                          {uraian("status_kepegawaian", it.status_kepegawaian).split(" (")[0]}
                        </span>
                      )}
                      {it.jenis_kontrak_non_asn === "outsourcing" && (
                        <span className="px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-600 dark:text-violet-400"
                          title={`Outsourcing — ${it.perusahaan_penyedia || "?"}`}>
                          Outsourcing{it.perusahaan_penyedia ? ` · ${it.perusahaan_penyedia}` : ""}
                        </span>
                      )}
                      {im.tanggal_pensiun && (
                        <span className={`px-1.5 py-0.5 rounded ${((im.sisa_hari_pensiun ?? 9e9) < 365) ? "bg-amber-500/15 text-amber-600 dark:text-amber-400" : "bg-muted text-muted-foreground"}`}
                          title={`Perkiraan pensiun ${im.tanggal_pensiun} (BUP ${im.bup} th)`}>
                          Pensiun {fmtSisa(im.sisa_hari_pensiun)}
                        </span>
                      )}
                      {im.akhir_jabatan && (
                        <span className={`px-1.5 py-0.5 rounded ${((im.sisa_hari_jabatan ?? 9e9) < 90) ? "bg-amber-500/15 text-amber-600 dark:text-amber-400" : "bg-muted text-muted-foreground"}`}
                          title={`Akhir periode jabatan ${im.akhir_jabatan}`}>
                          Jabatan {fmtSisa(im.sisa_hari_jabatan)}
                        </span>
                      )}
                      {k && (
                        <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded whitespace-nowrap ${k.habis ? "bg-red-500/15 text-red-600 dark:text-red-400" : "bg-amber-500/15 text-amber-600 dark:text-amber-400"}`}
                          title={k.teks}>
                          <AlertTriangle className="w-2.5 h-2.5" />{k.singkat}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center justify-between gap-2 pt-0.5">
                      <span className="text-[10px] text-muted-foreground">
                        {it.updated_at ? `diubah ${sejakUpdate(it.updated_at)}` : ""}
                      </span>
                      {isAdmin && (
                        <span className="flex items-center gap-0.5 flex-shrink-0">
                          <button type="button" onClick={() => bukaForm({ ...EMPTY, ...it, mode: "edit" })}
                            title={`Ubah ${it.nama}`} aria-label={`Ubah ${it.nama}`}
                            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted min-w-0 min-h-0"
                            data-testid={`pegawai-edit-${it.id}-m`}>
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button type="button" onClick={() => remove(it)}
                            title={`Hapus ${it.nama}`} aria-label={`Hapus ${it.nama}`}
                            className="p-1.5 rounded-md text-muted-foreground hover:text-red-600 hover:bg-red-500/10 min-w-0 min-h-0"
                            data-testid={`pegawai-delete-${it.id}-m`}>
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </span>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
            {/* ── Desktop (≥sm): tabel + kolom Masa (durasi) ── */}
            <div className="hidden sm:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                    <th className="px-3 py-2.5 font-semibold">Nama / Identitas</th>
                    <th className="px-3 py-2.5 font-semibold">Jabatan / Unit Kerja</th>
                    <th className="px-3 py-2.5 font-semibold hidden md:table-cell">Masa</th>
                    <th className="px-3 py-2.5 font-semibold">Status</th>
                    {isAdmin && <th className="px-3 py-2.5 font-semibold text-right">Aksi</th>}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((it) => {
                    const im = it.info_masa || {};
                    return (
                    <tr key={it.id} className="border-b border-border/60 last:border-0 hover:bg-muted/50" data-testid={`pegawai-row-${it.id}`}>
                      <td className="px-3 py-2">
                        <p className="font-semibold text-foreground flex items-center gap-1.5 flex-wrap">
                          {namaLengkap(it)}
                          {it.status_kepegawaian && (
                            <span className="px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[9px] font-semibold uppercase">
                              {uraian("status_kepegawaian", it.status_kepegawaian).split(" (")[0]}
                            </span>
                          )}
                          {it.jenis_kontrak_non_asn === "outsourcing" && (
                            <span className="px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-600 dark:text-violet-400 text-[9px] font-semibold"
                              title={`Outsourcing — ${it.perusahaan_penyedia || "?"}`}>
                              Outsourcing
                            </span>
                          )}
                          {(() => {
                            const k = statusKontrak(it);
                            if (!k) return null;
                            return (
                              <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-semibold whitespace-nowrap ${k.habis ? "bg-red-500/15 text-red-600 dark:text-red-400" : "bg-amber-500/15 text-amber-600 dark:text-amber-400"}`}
                                title={k.teks}>
                                <AlertTriangle className="w-2.5 h-2.5" />{k.singkat}
                              </span>
                            );
                          })()}
                        </p>
                        <p className="text-[11px] text-muted-foreground font-mono">
                          {im.label_identitas && it.nip ? `${im.label_identitas} ` : ""}{it.nip || "—"}
                        </p>
                      </td>
                      <td className="px-3 py-2">
                        <p className="text-[12px] text-foreground/90">{it.jabatan || "—"}</p>
                        <p className="text-[10px] text-muted-foreground/80">{it.unit_kerja || ""}</p>
                      </td>
                      <td className="px-3 py-2 hidden md:table-cell">
                        {/* Kolom MASA: pensiun / akhir jabatan / kontrak (durasi) */}
                        <div className="space-y-0.5 text-[10px]">
                          {im.tanggal_pensiun && (
                            <p className={((im.sisa_hari_pensiun ?? 9e9) < 365) ? "text-amber-600 dark:text-amber-400 font-semibold" : "text-muted-foreground"}
                              title={`Perkiraan pensiun ${im.tanggal_pensiun} (BUP ${im.bup} th)`}>
                              Pensiun {fmtSisa(im.sisa_hari_pensiun)}
                            </p>
                          )}
                          {im.akhir_jabatan && (
                            <p className={((im.sisa_hari_jabatan ?? 9e9) < 90) ? "text-amber-600 dark:text-amber-400 font-semibold" : "text-muted-foreground"}
                              title={`Akhir periode jabatan ${im.akhir_jabatan}`}>
                              Jabatan {fmtSisa(im.sisa_hari_jabatan)}
                            </p>
                          )}
                          {im.kontrak?.ada && (
                            <p className={im.kontrak.habis || im.kontrak.segera ? "text-red-600 dark:text-red-400 font-semibold" : "text-muted-foreground"}
                              title={`Kontrak s.d. ${im.kontrak.tgl_selesai}`}>
                              Kontrak {fmtSisa(im.kontrak.sisa_hari)}
                            </p>
                          )}
                          {!im.tanggal_pensiun && !im.akhir_jabatan && !im.kontrak?.ada && (
                            <p className="text-muted-foreground/50">—</p>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                          (it.status || "aktif") === "aktif"
                            ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                            : "bg-slate-500/15 text-muted-foreground"}`}>
                          {uraian("status", it.status || "aktif")}
                        </span>
                        {it.updated_at && (
                          <p className="text-[9px] text-muted-foreground mt-0.5">diubah {sejakUpdate(it.updated_at)}</p>
                        )}
                      </td>
                      {isAdmin && (
                        <td className="px-3 py-2 text-right whitespace-nowrap">
                          <button type="button" onClick={() => bukaForm({ ...EMPTY, ...it, mode: "edit" })}
                            title={`Ubah ${it.nama}`} aria-label={`Ubah ${it.nama}`}
                            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted min-w-0 min-h-0"
                            data-testid={`pegawai-edit-${it.id}`}>
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button type="button" onClick={() => remove(it)}
                            title={`Hapus ${it.nama}`} aria-label={`Hapus ${it.nama}`}
                            className="p-1.5 rounded-md text-muted-foreground hover:text-red-600 hover:bg-red-500/10 min-w-0 min-h-0"
                            data-testid={`pegawai-delete-${it.id}`}>
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      )}
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            </>
          )}
        </div>
      </main>

      {/* ── Dialog tambah / edit ── */}
      <Dialog open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }}>
        <DialogContent className="max-w-2xl max-h-[88vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{form?.mode === "tambah" ? "Tambah Pegawai" : `Ubah Pegawai — ${form?.nama}`}</DialogTitle>
            <DialogDescription className="text-xs">
              Data kepegawaian menyeluruh — dipakai sebagai rujukan lintas modul (pemegang barang, penanggung jawab ruangan, dll.).
            </DialogDescription>
          </DialogHeader>
          {form && (
            <div className="space-y-4">
              {/* Form 5-TAB (pola KERJA-BARENG): Identitas · Pribadi ·
                  Kepegawaian · Jabatan & Unit · Kontak & Bank. */}
              <div className="flex bg-muted rounded-lg p-0.5 gap-0.5 sticky top-0 z-10">
                {[["identitas", "Identitas"], ["pribadi", "Pribadi"],
                  ["kepegawaian", "Kepegawaian"], ["jabatan", "Jabatan & Unit"],
                  ["kontak", "Kontak & Bank"]].map(([k, label]) => (
                  <button key={k} type="button" onClick={() => setTabForm(k)}
                    className={`flex-1 truncate px-1 text-[10px] sm:text-[11px] font-semibold py-1.5 rounded-md min-w-0 min-h-0 ${tabForm === k ? "bg-card text-sky-700 dark:text-sky-400 shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
                    title={label}
                    data-testid={`pegawai-tab-${k}`}>
                    {label}
                  </button>
                ))}
              </div>

              {tabForm === "identitas" && (
                <div className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                    <Field label="Gelar Depan"><Input value={form.gelar_depan} onChange={set("gelar_depan")} placeholder="cth. Dr." /></Field>
                    <Field label="Nama *" span2><Input value={form.nama} onChange={set("nama")} data-testid="pegawai-form-nama" /></Field>
                    <Field label="Gelar Belakang"><Input value={form.gelar_belakang} onChange={set("gelar_belakang")} placeholder="cth. S.E." /></Field>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <Field label="Kewarganegaraan">
                      <Select value={form.kewarganegaraan || "wni"} onChange={set("kewarganegaraan")} opts={ref.kewarganegaraan} allowEmpty={false} data-testid="pegawai-form-wn" />
                    </Field>
                  </div>
                  {(form.kewarganegaraan || "wni") === "wni" ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-2.5 rounded-lg bg-sky-500/5 border border-sky-500/30">
                      <Field label={deteksi?.jenis ? deteksi.label : "NIP / NIK / NRP"}>
                        <Input value={form.nip} onChange={set("nip")} className="font-mono" inputMode="numeric" placeholder="8–20 digit (opsional)" data-testid="pegawai-form-nip" />
                        {/* Deteksi jenis nomor OTOMATIS (server, satu sumber
                            logika): NIP PNS / NI PPPK / NRP / NIK. */}
                        {deteksi?.keterangan && (
                          <p className="text-[10px] text-sky-700 dark:text-sky-400 mt-1" data-testid="pegawai-deteksi-identitas">
                            ✓ {deteksi.keterangan}
                          </p>
                        )}
                      </Field>
                      <Field label="NPWP"><Input value={form.npwp} onChange={set("npwp")} className="font-mono" /></Field>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-2.5 rounded-lg bg-amber-500/5 border border-amber-500/30">
                      <Field label="Jenis Identitas WNA">
                        <Select value={form.jenis_identitas_wna} onChange={set("jenis_identitas_wna")} opts={ref.jenis_identitas_wna} data-testid="pegawai-form-wna-jenis" />
                      </Field>
                      <Field label="Nomor Identitas"><Input value={form.nomor_identitas_wna} onChange={set("nomor_identitas_wna")} className="font-mono" placeholder="No. Paspor/KITAS/KITAP" /></Field>
                      <Field label="NPWP (opsional)"><Input value={form.npwp} onChange={set("npwp")} className="font-mono" /></Field>
                    </div>
                  )}
                </div>
              )}

              {tabForm === "pribadi" && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Field label="Jenis Kelamin">
                    <Select value={form.jenis_kelamin} onChange={set("jenis_kelamin")} data-testid="pegawai-form-jk" opts={ref.jenis_kelamin} />
                  </Field>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Tempat Lahir"><Input value={form.tempat_lahir} onChange={set("tempat_lahir")} /></Field>
                    <Field label="Tgl Lahir"><Input type="date" value={form.tanggal_lahir} onChange={set("tanggal_lahir")} /></Field>
                  </div>
                  <Field label="Agama">
                    <Select value={form.agama} onChange={set("agama")} opts={ref.agama} />
                  </Field>
                  <Field label="Status Perkawinan">
                    <Select value={form.status_perkawinan} onChange={set("status_perkawinan")} opts={ref.status_perkawinan} />
                  </Field>
                  <Field label="Pendidikan Terakhir"><Input value={form.pendidikan_terakhir} onChange={set("pendidikan_terakhir")} placeholder="cth. S1 Akuntansi" /></Field>
                  <Field label="Alamat"><Input value={form.alamat} onChange={set("alamat")} /></Field>
                </div>
              )}

              {tabForm === "kepegawaian" && (
                <div className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <Field label="Status Kepegawaian">
                      <Select value={form.status_kepegawaian} onChange={set("status_kepegawaian")} data-testid="pegawai-form-status-peg" opts={ref.status_kepegawaian} />
                    </Field>
                    {/* Pangkat hanya utk PNS/CPNS/PPPK/TNI/POLRI — Non-ASN
                        tidak punya pangkat/golongan (riset PER-31/PB/2016). */}
                    {form.status_kepegawaian !== "non_asn" && (
                      <Field label={form.status_kepegawaian === "pppk" ? "Golongan PPPK (I–XVII)"
                        : ["tni", "polri"].includes(form.status_kepegawaian) ? "Pangkat"
                        : "Pangkat / Golongan"}>
                        <Input value={form.pangkat_golongan} onChange={set("pangkat_golongan")} list="opsi-pangkat"
                          placeholder={form.status_kepegawaian === "pppk" ? "cth. Golongan IX"
                            : ["tni", "polri"].includes(form.status_kepegawaian) ? "cth. Kapten / Iptu"
                            : "cth. Penata (III/c)"} data-testid="pegawai-form-pangkat" />
                        <datalist id="opsi-pangkat">
                          {((ref.pangkat_golongan || {})[form.status_kepegawaian] || (ref.pangkat_golongan || {}).pns || []).map((p) => <option key={p} value={p} />)}
                        </datalist>
                      </Field>
                    )}
                    {form.status_kepegawaian === "non_asn" && (
                      <Field label="Sub-Kategori Non-ASN">
                        <Select value={form.sub_kategori_non_asn} onChange={set("sub_kategori_non_asn")} opts={ref.sub_kategori_non_asn} />
                      </Field>
                    )}
                    <Field label="Status di Satker">
                      <Select value={form.status} onChange={set("status")} data-testid="pegawai-form-status" opts={ref.status} allowEmpty={false} />
                    </Field>
                    {form.status_kepegawaian !== "non_asn" && (
                      <>
                        <Field label="TMT Jabatan"><Input type="date" value={form.tmt_jabatan} onChange={set("tmt_jabatan")} /></Field>
                        <Field label="Akhir Periode Jabatan (ops.)">
                          <Input type="date" value={form.tanggal_akhir_jabatan} onChange={set("tanggal_akhir_jabatan")} data-testid="pegawai-form-akhir-jabatan" />
                        </Field>
                      </>
                    )}
                  </div>
                  {/* Kontrak Non-ASN — internal instansi vs OUTSOURCING (riset
                      PER-31/PB/2016 + Perpres 16/2018); pemantauan pemegang
                      aset saat kontrak berakhir. */}
                  {form.status_kepegawaian === "non_asn" && (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-2.5 rounded-lg bg-muted/40 border border-border/60">
                      <Field label="Jenis Kontrak">
                        <Select value={form.jenis_kontrak_non_asn} onChange={set("jenis_kontrak_non_asn")}
                          opts={ref.jenis_kontrak_non_asn} data-testid="pegawai-form-jenis-kontrak" />
                      </Field>
                      {form.jenis_kontrak_non_asn === "outsourcing" && (
                        <Field label="Perusahaan Penyedia *" span2>
                          <Input value={form.perusahaan_penyedia} onChange={set("perusahaan_penyedia")}
                            placeholder="cth. PT Aman Sarana Jasa" data-testid="pegawai-form-penyedia" />
                        </Field>
                      )}
                      <Field label="Nomor Kontrak"><Input value={form.nomor_kontrak} onChange={set("nomor_kontrak")} placeholder="cth. 001/KONTRAK/2026" /></Field>
                      <Field label="Mulai Kontrak"><Input type="date" value={form.tgl_mulai_kontrak} onChange={set("tgl_mulai_kontrak")} /></Field>
                      <Field label="Selesai Kontrak"><Input type="date" value={form.tgl_selesai_kontrak} onChange={set("tgl_selesai_kontrak")} /></Field>
                    </div>
                  )}
                </div>
              )}

              {tabForm === "jabatan" && (
                <div className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <Field label="Jabatan" span2><Input value={form.jabatan} onChange={set("jabatan")} placeholder="cth. Analis Pengelolaan BMN" /></Field>
                    <Field label="Jenis Jabatan">
                      <Select value={form.jenis_jabatan} onChange={set("jenis_jabatan")} opts={ref.jenis_jabatan} />
                    </Field>
                    <Field label="Kategori Pegawai (UU ASN)">
                      <Select value={form.kategori_pegawai} onChange={set("kategori_pegawai")} opts={ref.kategori_pegawai} />
                    </Field>
                    <Field label="Eselon (teks)"><Input value={form.eselon} onChange={set("eselon")} placeholder="cth. IV.a" /></Field>
                    {/* Penghubung lintas modul: kode satker 6 digit + lengkap
                        12 digit (selaras field satker aset/laporan). */}
                    <Field label="Kode Satker (6 digit)">
                      <Input value={form.kode_satker} onChange={set("kode_satker")} className="font-mono"
                        inputMode="numeric" maxLength={6} placeholder="cth. 527010" data-testid="pegawai-form-kode-satker" />
                    </Field>
                    <Field label="Kode Satker Lengkap (12 digit)">
                      <Input value={form.kode_satker_lengkap} onChange={set("kode_satker_lengkap")} className="font-mono"
                        inputMode="numeric" maxLength={12} placeholder="cth. 527010401987" data-testid="pegawai-form-kode-satker-lengkap" />
                    </Field>
                  </div>
                  {/* Unit kerja berjenjang (Eselon I–V) — pilihan BERTINGKAT dari
                      master unit; jenjang terdalam otomatis jadi Unit Kerja. */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {[1, 2, 3, 4, 5].map((lv) => (
                      <Field key={lv} label={`Eselon ${lv}`}>
                        <Input value={form[`eselon${lv}`]} onChange={set(`eselon${lv}`)}
                          list={`opsi-eselon-${lv}`}
                          placeholder={["cth. Kedeputian / Sekretariat", "cth. Direktorat / Biro", "cth. Bagian / Subdirektorat", "cth. Subbagian / Seksi", ""][lv - 1]}
                          data-testid={`pegawai-form-eselon${lv}`} />
                        <datalist id={`opsi-eselon-${lv}`}>
                          {opsiEselon(lv, form).map((n) => <option key={n} value={n} />)}
                        </datalist>
                      </Field>
                    ))}
                    {isAdmin && (
                      <div className="flex items-end">
                        <Button type="button" variant="outline" size="sm" className="h-10 gap-1.5 w-full"
                          onClick={() => setKelolaUnit({ eselon: "1", nama: "", parentId: "", sibuk: false })}
                          data-testid="pegawai-kelola-unit">
                          <Network className="w-3.5 h-3.5" />Kelola Unit Kerja ({units.length})
                        </Button>
                      </div>
                    )}
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <Field label="Unit Kerja (ringkas)">
                      {/* Terhubung Master Unit Kerja yang sudah dimuat (audit W4 #9) */}
                      <Input value={form.unit_kerja} list="pegawai-unit-list" onChange={set("unit_kerja")} placeholder="otomatis dari Eselon terdalam bila kosong" data-testid="pegawai-form-unit" />
                      <datalist id="pegawai-unit-list">
                        {[...new Set(units.map((u) => u.nama_unit || "").filter(Boolean))].sort().map((u) => <option key={u} value={u} />)}
                      </datalist>
                    </Field>
                    <Field label="Unit Organisasi / Satker"><Input value={form.unit_organisasi} onChange={set("unit_organisasi")} /></Field>
                  </div>
                </div>
              )}

              {tabForm === "kontak" && (
                <div className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <Field label="No. HP"><Input value={form.no_hp} onChange={set("no_hp")} inputMode="tel" placeholder="cth. 0812…" /></Field>
                    <Field label="Email"><Input type="email" value={form.email} onChange={set("email")} placeholder="nama@instansi.go.id" data-testid="pegawai-form-email" /></Field>
                    <Field label="Nama Bank">
                      <Input value={form.nama_bank} onChange={set("nama_bank")} list="opsi-bank" placeholder="cth. BRI" data-testid="pegawai-form-bank" />
                      <datalist id="opsi-bank">
                        {["BRI", "BNI", "Mandiri", "BTN", "BSI", "BCA", "CIMB Niaga", "Danamon", "Permata", "Maybank"].map((b) => <option key={b} value={b} />)}
                      </datalist>
                    </Field>
                    <Field label="No. Rekening"><Input value={form.no_rekening} onChange={set("no_rekening")} className="font-mono" inputMode="numeric" data-testid="pegawai-form-rekening" /></Field>
                  </div>
                  {(() => {
                    // Peringatan LUNAK digit rekening per bank (non-blocking).
                    const bank = String(form.nama_bank || "").trim().toLowerCase();
                    const digit = String(form.no_rekening || "").replace(/\D/g, "");
                    const harus = (ref.digit_bank || {})[bank];
                    if (!bank || !digit || !harus || digit.length === harus) return null;
                    return (
                      <p className="text-[11px] text-amber-700 dark:text-amber-400 flex items-center gap-1.5 p-2 rounded-lg bg-amber-500/10 border border-amber-500/30" data-testid="pegawai-rekening-warning">
                        <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
                        No. rekening {form.nama_bank} lazimnya {harus} digit (saat ini {digit.length} digit) — periksa kembali.
                      </p>
                    );
                  })()}
                  <Field label="Keterangan"><Input value={form.keterangan} onChange={set("keterangan")} /></Field>
                </div>
              )}
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setForm(null)}>Batal</Button>
            <Button onClick={submitForm} disabled={saving} className="bg-sky-600 hover:bg-sky-700 text-white" data-testid="pegawai-form-save">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : null}Simpan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog bagan Struktur Organisasi (pohon unit + jumlah pegawai) ── */}
      <Dialog open={struktur} onOpenChange={setStruktur}>
        <DialogContent className="max-w-2xl max-h-[88vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Struktur Organisasi</DialogTitle>
            <DialogDescription className="text-xs">
              Bagan hierarki unit kerja (Eselon I–V) dari master, dengan jumlah pegawai per unit. Klik unit untuk membuka/menutup sub-unitnya; klik jumlah untuk memfilter daftar pegawai.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1" data-testid="struktur-organisasi-pohon">
            {units.filter((u) => String(u.eselon) === "1").map((akar) => (
              <PohonUnit key={akar.id} unit={akar} units={units} depth={0}
                buka={strukturBuka}
                onToggle={(id) => setStrukturBuka((b) => ({ ...b, [id]: !b[id] }))}
                jumlah={jumlahPegawaiUnit}
                onFilter={(nama) => { setSearch(nama); setStruktur(false); }} />
            ))}
            {units.filter((u) => String(u.eselon) === "1").length === 0 && (
              <p className="text-center text-xs text-muted-foreground py-8">
                Master unit kerja masih kosong — buka &quot;Kelola Unit Kerja&quot; di form pegawai (tab Jabatan &amp; Unit) lalu gunakan &quot;Bangun otomatis dari data pegawai&quot;.
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setStruktur(false)}>Tutup</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog kelola master unit kerja (Eselon I–V, hierarkis) ── */}
      <Dialog open={!!kelolaUnit} onOpenChange={(o) => { if (!o && !kelolaUnit?.sibuk) setKelolaUnit(null); }}>
        <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Kelola Unit Kerja (Eselon I–V)</DialogTitle>
            <DialogDescription className="text-xs">
              Master hierarkis — unit Eselon N bernaung di bawah Eselon N−1. Dipakai pilihan bertingkat form pegawai &amp; rekap laporan.
            </DialogDescription>
          </DialogHeader>
          {kelolaUnit && (
            <div className="space-y-3">
              <Button variant="outline" size="sm" className="h-9 text-xs gap-1.5 w-full" disabled={kelolaUnit.sibuk}
                onClick={bangunDariPegawai} data-testid="unit-bangun-otomatis">
                {kelolaUnit.sibuk ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wand2 className="w-3.5 h-3.5" />}
                Bangun otomatis dari data pegawai (jalur Eselon 1–5 yang sudah terisi)
              </Button>
              <div className="flex bg-muted rounded-lg p-0.5 gap-0.5">
                {["1", "2", "3", "4", "5"].map((es) => (
                  <button key={es} type="button"
                    onClick={() => setKelolaUnit((k) => ({ ...k, eselon: es, parentId: "" }))}
                    className={`flex-1 text-[11px] font-semibold py-1.5 rounded-md min-w-0 min-h-0 ${kelolaUnit.eselon === es ? "bg-card text-sky-700 dark:text-sky-400 shadow-sm" : "text-muted-foreground"}`}>
                    Eselon {es}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                {Number(kelolaUnit.eselon) > 1 && (
                  <select value={kelolaUnit.parentId}
                    onChange={(e) => setKelolaUnit((k) => ({ ...k, parentId: e.target.value }))}
                    className="h-9 rounded-md border border-input bg-background px-2 text-sm flex-1 min-w-[150px]"
                    data-testid="unit-induk">
                    <option value="">— induk Eselon {Number(kelolaUnit.eselon) - 1} —</option>
                    {units.filter((u) => String(u.eselon) === String(Number(kelolaUnit.eselon) - 1))
                      .map((u) => <option key={u.id} value={u.id}>{u.nama_unit}</option>)}
                  </select>
                )}
                <Input value={kelolaUnit.nama}
                  onChange={(e) => setKelolaUnit((k) => ({ ...k, nama: e.target.value }))}
                  placeholder={`Nama unit Eselon ${kelolaUnit.eselon}`} className="h-9 flex-1 min-w-[160px]"
                  data-testid="unit-nama" />
                <Button size="sm" className="h-9 gap-1 bg-sky-600 hover:bg-sky-700 text-white" disabled={kelolaUnit.sibuk}
                  onClick={tambahUnit} data-testid="unit-tambah">
                  <Plus className="w-3.5 h-3.5" />Tambah
                </Button>
              </div>
              <div className="divide-y divide-border/60 border border-border rounded-lg overflow-hidden max-h-64 overflow-y-auto">
                {units.filter((u) => String(u.eselon) === kelolaUnit.eselon).length === 0 ? (
                  <p className="text-center text-[11px] text-muted-foreground py-5">Belum ada unit Eselon {kelolaUnit.eselon}.</p>
                ) : units.filter((u) => String(u.eselon) === kelolaUnit.eselon).map((u) => {
                  const induk = units.find((x) => x.id === u.parent_id);
                  return (
                    <div key={u.id} className="px-3 py-1.5 flex items-center gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-[12px] font-medium text-foreground truncate">{u.nama_unit}</p>
                        {induk && <p className="text-[10px] text-muted-foreground truncate">↳ {induk.nama_unit}</p>}
                      </div>
                      {u.sumber === "derivasi pegawai" && (
                        <span className="px-1 py-0.5 rounded bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[9px] font-semibold">otomatis</span>
                      )}
                      <button type="button" onClick={() => hapusUnit(u)} title={`Hapus ${u.nama_unit}`} aria-label={`Hapus ${u.nama_unit}`}
                        className="p-1 rounded text-muted-foreground hover:text-red-600 hover:bg-red-500/10 min-w-0 min-h-0">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" disabled={kelolaUnit?.sibuk} onClick={() => setKelolaUnit(null)}>Tutup</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog aset yang dipegang pegawai berisiko ── */}
      <Dialog open={!!detailAset} onOpenChange={(o) => { if (!o) setDetailAset(null); }}>
        <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Aset dipegang — {detailAset?.pegawai?.nama}</DialogTitle>
            <DialogDescription className="text-xs">
              NIP {detailAset?.pegawai?.nip || "—"} · {detailAset?.pegawai?.alasan}. Proses serah terima via modul Penggunaan → tab Pemegang (BAST pengembalian / mutasi pemegang).
            </DialogDescription>
          </DialogHeader>
          {detailAset?.memuat ? (
            <div className="flex items-center justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-amber-600" /></div>
          ) : (
            <div className="divide-y divide-border/60 border border-border rounded-lg overflow-hidden">
              {(detailAset?.items || []).length === 0 ? (
                <p className="text-center text-xs text-muted-foreground py-6">Tidak ada aset tercatat atas NIP ini.</p>
              ) : (detailAset?.items || []).map((a) => (
                <div key={a.id} className="px-3 py-2 flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-[12px] font-semibold text-foreground truncate">{a.asset_name || "—"}</p>
                    <p className="text-[10px] text-muted-foreground font-mono">{a.asset_code}{a.NUP ? ` · NUP ${a.NUP}` : ""}{a.location ? ` · ${a.location}` : ""}</p>
                  </div>
                  {a.condition && <span className="text-[10px] text-muted-foreground whitespace-nowrap">{a.condition}</span>}
                  {a.bast_file_id
                    ? <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 text-[9px] font-semibold">BAST ✓</span>
                    : <span className="px-1.5 py-0.5 rounded bg-slate-500/15 text-muted-foreground text-[9px] font-semibold">tanpa BAST</span>}
                </div>
              ))}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDetailAset(null)}>Tutup</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog hasil impor ── */}
      <Dialog open={!!hasilImpor} onOpenChange={(o) => { if (!o) setHasilImpor(null); }}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Hasil Impor Pegawai</DialogTitle>
            <DialogDescription className="text-xs">
              Baris dinormalkan otomatis (status kepegawaian &amp; status keberadaan dipetakan, NIP dibersihkan, unit kerja dari Eselon terdalam).
            </DialogDescription>
          </DialogHeader>
          {hasilImpor && (
            <div className="space-y-3">
              <div className="grid grid-cols-4 gap-2 text-center">
                {[["Dibaca", hasilImpor.dibaca, "text-foreground"],
                  ["Baru", hasilImpor.dibuat, "text-emerald-600 dark:text-emerald-400"],
                  ["Diperbarui", hasilImpor.diperbarui, "text-sky-600 dark:text-sky-400"],
                  ["Dilewati", hasilImpor.dilewati, "text-amber-600 dark:text-amber-400"]].map(([l, v, c]) => (
                  <div key={l} className="rounded-lg border border-border p-2">
                    <p className={`text-lg font-bold ${c}`}>{v}</p>
                    <p className="text-[10px] text-muted-foreground">{l}</p>
                  </div>
                ))}
              </div>
              {(hasilImpor.catatan || []).length > 0 && (
                <div className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-2.5">
                  <p className="text-[11px] font-bold text-amber-700 dark:text-amber-400 mb-1">
                    Catatan ({hasilImpor.catatan.length} baris dilewati):
                  </p>
                  <ul className="text-[10px] text-muted-foreground space-y-0.5 max-h-40 overflow-y-auto">
                    {hasilImpor.catatan.map((c, i) => <li key={i}>• {c}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setHasilImpor(null)}>Tutup</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}

// Simpul bagan struktur organisasi (rekursif): unit + jumlah pegawai +
// sub-unit yang dapat dibuka/ditutup.
function PohonUnit({ unit, units, depth, buka, onToggle, jumlah, onFilter }) {
  const anak = units.filter((u) => u.parent_id === unit.id);
  const terbuka = buka[unit.id] !== false; // default terbuka
  const n = jumlah(unit);
  return (
    <div style={{ marginLeft: depth ? 16 : 0 }} className={depth ? "border-l border-border/60 pl-2" : ""}>
      <div className="flex items-center gap-1.5 py-1">
        <button type="button" onClick={() => anak.length && onToggle(unit.id)}
          className={`flex items-center gap-1.5 flex-1 min-w-0 text-left rounded px-1.5 py-1 hover:bg-muted min-h-0 ${anak.length ? "" : "cursor-default"}`}
          data-testid={`struktur-unit-${unit.id}`}>
          {anak.length > 0
            ? <span className="text-[10px] text-muted-foreground w-3">{terbuka ? "▾" : "▸"}</span>
            : <span className="w-3" />}
          <span className="text-[12px] font-medium text-foreground truncate">{unit.nama_unit}</span>
          <span className="px-1 py-0.5 rounded bg-muted text-[9px] font-semibold text-muted-foreground uppercase">Es. {unit.eselon}</span>
        </button>
        <button type="button" onClick={() => onFilter(unit.nama_unit)}
          title={`Lihat ${n} pegawai unit ini`}
          className={`px-2 py-0.5 rounded-full text-[10px] font-bold min-w-0 min-h-0 ${n ? "bg-sky-500/15 text-sky-600 dark:text-sky-400 hover:bg-sky-500/25" : "bg-muted text-muted-foreground/60 cursor-default"}`}>
          {n} <span className="font-normal">pegawai</span>
        </button>
      </div>
      {terbuka && anak.map((a) => (
        <PohonUnit key={a.id} unit={a} units={units} depth={depth + 1}
          buka={buka} onToggle={onToggle} jumlah={jumlah} onFilter={onFilter} />
      ))}
    </div>
  );
}

function Field({ label, children, span2 }) {
  return (
    <div className={span2 ? "col-span-full sm:col-span-2" : ""}>
      <label className="text-xs font-medium text-foreground block mb-1">{label}</label>
      {children}
    </div>
  );
}

function Select({ value, onChange, opts, allowEmpty = true, ...rest }) {
  return (
    <select value={value} onChange={onChange}
      className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm" {...rest}>
      {allowEmpty && <option value="">— pilih —</option>}
      {(opts || []).map((o) => <option key={o.kode} value={o.kode}>{o.uraian}</option>)}
    </select>
  );
}
