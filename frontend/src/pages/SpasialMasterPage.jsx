import React, { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { TENGGAT_BAKA, muatAndal, pesanGalat } from "@/lib/muatAndal";
import {
  ArrowLeft, Plus, Pencil, Trash2, Loader2, Layers, ChevronRight, ChevronDown,
  Search, MapPinned, LandPlot, Upload, Download, Boxes, ClipboardCheck,
  MoreVertical, Gauge, AlertTriangle, RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Editor denah dimuat LAZY — Leaflet + geoman berat, dan mayoritas kunjungan
// halaman pohon tak pernah membuka editor.
const DenahEditor = lazy(() => import("@/components/spasial/DenahEditor"));
const ImporDenahDialog = lazy(() => import("@/components/spasial/ImporDenahDialog"));
const EksporDenahDialog = lazy(() => import("@/components/spasial/EksporDenahDialog"));
const IsiNodeDialog = lazy(() => import("@/components/spasial/IsiNodeDialog"));
const OpnameDialog = lazy(() => import("@/components/spasial/OpnameDialog"));

function getApiError(err, fallback) {
  return err?.response?.data?.detail || fallback;
}

const KATEGORI_LANTAI = ["basement", "dasar", "reguler", "mezanin", "atap", "teknis"];

/**
 * Master Hierarki Spasial — denah kawasan berlapis (Fase 2).
 *
 * Menyusun pohon Kawasan → Zona → Distrik → … → Ruangan. Belum ada geometri
 * (gambar poligon + deteksi lokasi otomatis menyusul di Fase 3); halaman ini
 * fokus membangun STRUKTUR-nya. Data ter-isolasi per satker; registry tingkat
 * (label) mengikuti preset — "Zona (WP)"/"Distrik (Sub-WP)" atau kode baku.
 */
export default function SpasialMasterPage({ user, onBack }) {
  const isWriter = user?.role !== "viewer";
  const [levels, setLevels] = useState([]);
  const [nodes, setNodes] = useState([]);
  const [preset, setPreset] = useState("ikn_akrab");
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [buka, setBuka] = useState({}); // id → terbuka?
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [editorNode, setEditorNode] = useState(null);  // node yang denahnya digambar
  const [imporBuka, setImporBuka] = useState(false);   // dialog impor file GIS
  const [eksporBuka, setEksporBuka] = useState(false); // dialog ekspor + template
  const [isiNode, setIsiNode] = useState(null);        // node yang dilihat isinya (Fase 9)
  const [opnameNode, setOpnameNode] = useState(null);  // node yang di-opname via scan (Fase 11)
  const [optimasi, setOptimasi] = useState(false);     // tombol optimasi sedang berjalan
  // Pemuatan pohon: pesan gagal DISIMPAN (bukan cuma toast) supaya layar bisa
  // membedakan "belum ada data" dari "gagal memuat", plus penjaga urutan.
  const [galatMuat, setGalatMuat] = useState(null);
  const [mencobaUlang, setMencobaUlang] = useState(false);
  const reqNodeRef = useRef(0);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const labelLevel = useMemo(() => {
    const m = {};
    levels.forEach((l) => { m[l.kode_baku] = l.label || l.label_ui; });
    return m;
  }, [levels]);
  const ordinalLevel = useMemo(() => {
    const m = {};
    levels.forEach((l) => { m[l.kode_baku] = l.ordinal_level; });
    return m;
  }, [levels]);

  // Registry tingkat dipisah dari pohon: ganti preset hanya mengubah LABEL, jadi
  // cukup ambil ulang level (tanpa spinner layar-penuh & tanpa memuat ulang node).
  // timeout WAJIB: tanpa ini, satu request yang menggantung (backend lambat/
  // mati) meninggalkan `loading` true selamanya — halaman denah berputar tanpa
  // henti tanpa menampilkan apa pun (bug lapangan). Dengan timeout, request
  // ditolak → catch → toast → finally membereskan spinner.
  const loadLevels = useCallback(async () => {
    try {
      const rl = await axios.get(`${API}/spasial/level?preset=${preset}`,
                                 { timeout: 20000 });
      setLevels(rl.data?.items || []);
    } catch (err) {
      toast.error(getApiError(err, "Gagal memuat daftar tingkat"));
    }
  }, [preset]);

  // Pemuatan pohon TAHAN kedip jaringan. Tiga hal yang dulu tidak ada:
  //
  // 1. COBA-ULANG. Satu kedip sinyal — hal paling biasa di lapangan — dulu
  //    berakhir sebagai layar kosong, dan satu-satunya pemulihan adalah keluar
  //    lalu masuk lagi ke halaman (efeknya `loadNodes` stabil, jadi useEffect
  //    tak pernah menjalankannya ulang).
  // 2. BEDA "KOSONG" vs "GAGAL". Dulu keduanya merender kalimat yang sama —
  //    "Belum ada data. Mulai dari tingkat teratas" — sehingga operator satker
  //    yang pohonnya PENUH disuruh mulai dari nol saat jaringannya sedang buruk.
  // 3. PENJAGA URUTAN. Menyimpan lalu memuat ulang sementara muatan sebelumnya
  //    masih di jalan membuat pohon melompat balik ke keadaan lama.
  const loadNodes = useCallback(async () => {
    const seq = ++reqNodeRef.current;
    setLoading(true);
    setGalatMuat(null);
    try {
      const rn = await muatAndal(
        () => axios.get(`${API}/spasial/node`, { timeout: TENGGAT_BAKA }),
        { padaUlang: () => {
          if (seq === reqNodeRef.current) setMencobaUlang(true);
        } });
      if (seq !== reqNodeRef.current) return;      // muatan lain sudah menyusul
      setNodes(rn.data?.items || []);
    } catch (err) {
      if (seq !== reqNodeRef.current) return;
      // Disimpan di state, BUKAN sekadar toast: toast hilang setelah beberapa
      // detik dan meninggalkan layar yang tampak seperti "memang kosong".
      setGalatMuat(pesanGalat(err, "Gagal memuat hierarki spasial"));
    } finally {
      if (seq === reqNodeRef.current) { setLoading(false); setMencobaUlang(false); }
    }
  }, []);

  useEffect(() => { loadNodes(); }, [loadNodes]);
  useEffect(() => { loadLevels(); }, [loadLevels]);

  // Pohon dari daftar datar: anak per parent_id (null = akar).
  const anakDari = useMemo(() => {
    const m = {};
    nodes.forEach((n) => {
      const p = n.parent_id || "__root__";
      (m[p] = m[p] || []).push(n);
    });
    Object.values(m).forEach((arr) => arr.sort(
      (a, b) => (a.ordinal_level - b.ordinal_level) || String(a.nama).localeCompare(b.nama)));
    return m;
  }, [nodes]);

  // Kandidat induk untuk sebuah tipe: node yang tingkatnya lebih LUAS (ordinal
  // lebih kecil). Registry mengizinkan lompat tingkat, jadi tak dibatasi ketat.
  const kandidatInduk = useCallback((tipe) => {
    const o = ordinalLevel[tipe];
    if (o == null) return [];
    return nodes
      .filter((n) => ordinalLevel[n.tipe] < o)
      .sort((a, b) => (a.ordinal_level - b.ordinal_level) || String(a.nama).localeCompare(b.nama));
  }, [nodes, ordinalLevel]);

  // Id node yang TAMPIL saat pencarian: node yang cocok + SELURUH leluhurnya
  // (agar hasil di tingkat dalam terlihat & jalurnya terbuka). Dihitung SEKALI
  // per (nodes, search) dalam satu lintasan — bukan memindai subtree per baris
  // (yang jadi O(n²) tiap ketikan). null = tanpa pencarian, semua tampil.
  const idTampil = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return null;
    const cocok = (n) => [n.nama, n.kode, ...(n.nama_alias || [])]
      .some((v) => String(v || "").toLowerCase().includes(q));
    const byId = {};
    nodes.forEach((n) => { byId[n.id] = n; });
    const set = new Set();
    nodes.forEach((n) => {
      if (!cocok(n)) return;
      set.add(n.id);
      // Naikkan ke leluhur; `set.has(p)` menghentikan jalur yang sudah ditandai
      // → total O(n) dan aman terhadap data bersiklus (tak berputar).
      let p = n.parent_id;
      while (p && !set.has(p) && byId[p]) { set.add(p); p = byId[p].parent_id; }
    });
    return set;
  }, [nodes, search]);

  const simpan = async () => {
    if (!form.nama.trim()) { toast.error("Nama wajib diisi"); return; }
    setSaving(true);
    try {
      const body = {
        tipe: form.tipe, nama: form.nama.trim(), kode: form.kode.trim(),
        parent_id: form.parent_id || "",
        nama_alias: form.nama_alias
          ? form.nama_alias.split(",").map((s) => s.trim()).filter(Boolean) : [],
        zona_kode: form.zona_kode.trim(),
      };
      // Peruntukan hanya dikirim untuk tingkat tempat standar SBSK ruang kerja
      // bermakna. Untuk tipe lain field ini SENGAJA absen dari body: server
      // memperlakukan "tak dikirim" sebagai "tak diubah", sehingga mengubah
      // sebuah gedung tak menyentuh peruntukan ruangan mana pun.
      if (form.tipe === "RUANGAN" || form.tipe === "SAYAP") {
        body.peruntukan = (form.peruntukan || "").trim();
      }
      // Mode ubah membawa status EKSPLISIT (aktivasi draft = keputusan sadar);
      // mode tambah membiarkan server men-default "aktif". properties sengaja
      // TIDAK dikirim — server mempertahankan yang tersimpan (jejak impor,
      // overlay denah) saat field ini absen.
      if (form.mode === "ubah" && form.status) body.status = form.status;
      if (form.tipe === "LANTAI") {
        body.lantai = {
          ordinal: form.lantai_ordinal === "" ? null : parseInt(form.lantai_ordinal, 10),
          label: form.lantai_label.trim(),
          label_pendek: form.lantai_pendek.trim(),
          kategori: form.lantai_kategori,
        };
      }
      // Respons membawa `peringatan[]` containment — WAJIB ditampilkan. Inilah
      // satu-satunya UI yang bisa mengubah induk, dan backend sengaja menghitung
      // containment bentuk TERSIMPAN terhadap induk BARU untuk kasus itu. Karena
      // pelanggaran containment sengaja TIDAK memblokir simpan, membuang respons
      // berarti operator tak pernah tahu gedungnya kini di luar batas induknya.
      let r;
      if (form.mode === "tambah") {
        r = await axios.post(`${API}/spasial/node`, body);
        toast.success("Node ditambahkan");
      } else {
        r = await axios.put(`${API}/spasial/node/${form.id}`, body);
        toast.success("Node diperbarui");
      }
      for (const p of r?.data?.peringatan || []) toast.warning(p, { duration: 8000 });
      setForm(null);
      await loadNodes();
    } catch (err) {
      toast.error(getApiError(err, "Gagal menyimpan"));
    } finally {
      setSaving(false);
    }
  };

  const hapus = async (n) => {
    const ok = await confirm({
      title: "Hapus node?",
      description: `Hapus "${n.nama}" (${labelLevel[n.tipe] || n.tipe})? Node yang masih memiliki anak tak dapat dihapus.`,
      confirmText: "Hapus", danger: true,
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/spasial/node/${n.id}`);
      toast.success("Node dihapus");
      await loadNodes();
    } catch (err) {
      toast.error(getApiError(err, "Gagal menghapus"));
    }
  };

  const bukaTambah = (parent) => setForm({
    mode: "tambah", id: null,
    tipe: parent ? tipeAnakDefault(parent) : (levels[0]?.kode_baku || "KAWASAN"),
    nama: "", kode: "", parent_id: parent?.id || "",
    nama_alias: "", zona_kode: "", peruntukan: "",
    lantai_ordinal: "", lantai_label: "", lantai_pendek: "", lantai_kategori: "reguler",
  });

  const bukaUbah = (n) => setForm({
    mode: "ubah", id: n.id, tipe: n.tipe, nama: n.nama || "", kode: n.kode || "",
    parent_id: n.parent_id || "", nama_alias: (n.nama_alias || []).join(", "),
    zona_kode: n.zona_kode || "", peruntukan: n.peruntukan || "",
    // Status EKSPLISIT — dulu form tak mengirim status dan server men-default
    // "aktif", sehingga sekadar mengganti nama draft impor MENGAKTIFKANNYA
    // diam-diam (temuan Fase 7). Kini server "None = tak diubah" + form ini
    // jadi satu-satunya tempat aktivasi yang disengaja.
    status: n.status || "aktif",
    lantai_ordinal: n.lantai?.ordinal ?? "", lantai_label: n.lantai?.label || "",
    lantai_pendek: n.lantai?.label_pendek || "", lantai_kategori: n.lantai?.kategori || "reguler",
  });

  // Tipe anak yang paling mungkin: tingkat tepat setelah induk (ordinal berikut).
  const tipeAnakDefault = (parent) => {
    const urut = [...levels].sort((a, b) => a.ordinal_level - b.ordinal_level);
    const next = urut.find((l) => l.ordinal_level > ordinalLevel[parent.tipe]);
    return next?.kode_baku || parent.tipe;
  };

  const toggle = (id) => setBuka((b) => ({ ...b, [id]: !b[id] }));

  // Hitung versi RINGAN untuk denah yang sudah terlanjur tersimpan. Node baru
  // dioptimalkan otomatis saat disimpan; tombol ini untuk denah lama —
  // lazimnya hasil impor SHP kawasan, yang justru paling berat.
  const jalankanOptimasi = async () => {
    const ok = await confirm({
      title: "Ringankan denah untuk tampilan peta?",
      description: "Server menghitung SALINAN ringan tiap poligon supaya peta "
        + "cepat dibuka di HP lapangan. Geometri ASLI tidak diubah sama sekali "
        + "\u2014 luas ruangan SBSK, deteksi lokasi, dan ekspor tetap memakai "
        + "angka survei yang sama persis.",
      confirmLabel: "Jalankan",
    });
    if (!ok) return;
    setOptimasi(true);
    try {
      const r = await axios.post(`${API}/spasial/optimasi`, {});
      const d = r.data || {};
      if (!d.kandidat) {
        toast.info("Semua denah sudah diringankan \u2014 tak ada yang perlu dihitung");
      } else {
        toast.success(`${d.diproses} denah diringankan: `
          + `${d.titik_sebelum.toLocaleString("id-ID")} \u2192 `
          + `${d.titik_sesudah.toLocaleString("id-ID")} titik (hemat ${d.hemat_persen}%)`,
        { duration: 9000 });
      }
      if (d.terpotong) {
        toast.warning("Masih ada denah tersisa \u2014 tekan sekali lagi untuk "
          + "melanjutkan (dibatasi agar server tak kewalahan).", { duration: 9000 });
      }
      loadNodes();
    } catch (e) {
      toast.error(getApiError(e, "Gagal meringankan denah"));
    } finally {
      setOptimasi(false);
    }
  };

  const Baris = ({ node, level }) => {
    if (idTampil && !idTampil.has(node.id)) return null;   // pencarian: sembunyikan
    const anak = anakDari[node.id] || [];
    // Saat mencari, PAKSA terbuka agar jalur menuju hasil ikut terbentang.
    const terbuka = idTampil ? true : (buka[node.id] ?? level < 1);
    const labelTipe = labelLevel[node.tipe] || node.tipe;
    return (
      <div>
        {/* DUA TINGKAT, bukan satu baris (umpan balik lapangan: di HP nama node
            HILANG sama sekali). Dulu nama memakai `flex-1 min-w-0` sementara
            enam tombol + tiga badge di sisinya `shrink-0`: flexbox mengecilkan
            satu-satunya item yang boleh menyusut sampai NOL, lalu sisanya tetap
            meluber keluar layar. Kini nama berdiri sendiri di tingkat atas dan
            badge turun ke tingkat bawah — tak ada lagi yang berebut lebar
            dengannya. Indentasi juga lebih rapat di HP (lihat .spasial-baris). */}
        <div
          className="spasial-baris flex items-start gap-1.5 py-2 border-b border-border/60 hover:bg-muted/50 rounded"
          style={{ "--lvl": String(level) }}
          data-testid={`spasial-node-${node.id}`}
        >
          <button
            type="button" onClick={() => toggle(node.id)}
            className={`tap-expand shrink-0 p-0.5 mt-0.5 rounded ${anak.length ? "" : "invisible"}`}
            aria-label={terbuka ? "Tutup" : "Buka"}
            data-testid={`spasial-toggle-${node.id}`}
          >
            {terbuka ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          </button>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium" title={node.nama}>
              {node.nama || <span className="text-muted-foreground italic">(tanpa nama)</span>}
            </div>
            <div className="flex flex-wrap items-center gap-1 mt-1">
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                {labelTipe}
              </span>
              {node.kode ? (
                <span className="text-[10px] font-mono text-muted-foreground">{node.kode}</span>
              ) : null}
              {/* Hasil impor & gambar setengah-jadi berstatus DRAFT: tak ikut
                  deteksi lokasi maupun lapisan denah sampai diaktifkan manusia. */}
              {node.status === "draft" && (
                <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-700 dark:text-amber-300"
                      title="Draft — belum aktif; periksa lalu ubah status jadi Aktif"
                      data-testid={`spasial-draft-${node.id}`}>
                  draft
                </span>
              )}
              {node.status === "nonaktif" && (
                <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-muted text-muted-foreground/70"
                      data-testid={`spasial-nonaktif-${node.id}`}>
                  nonaktif
                </span>
              )}
              {/* Sudah punya bentuk di peta? `bbox` ada HANYA bila geometri terisi —
                  dipakai sebagai penanda ringan karena `geometry` sengaja tak ikut
                  dikirim ke daftar pohon (poligon bisa ribuan verteks). */}
              <span
                className={`text-[9px] font-semibold px-1.5 py-0.5 rounded ${
                  node.bbox
                    ? "bg-teal-500/15 text-teal-700 dark:text-teal-300"
                    : "bg-muted text-muted-foreground/70"}`}
                title={node.bbox
                  ? "Sudah punya bentuk (poligon) — tampil di lapisan Denah pada Peta Aset"
                  : "Belum digambar — node ini tak akan muncul di peta"}
                data-testid={`spasial-geo-${node.id}`}
              >
                {node.bbox ? "denah" : "belum digambar"}
              </span>
              {/* Status optimasi per node. Tanpa ini, "Ringankan Peta" adalah
                  tombol yang hasilnya hanya tampak sebagai angka di toast —
                  tak ada cara melihat denah MANA yang masih berat, dan
                  operator tak tahu apakah ada yang perlu ditekan lagi. */}
              {node.bbox && (
                <span
                  className={`text-[9px] font-semibold px-1.5 py-0.5 rounded ${
                    node.dioptimalkan
                      ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
                      : "bg-amber-500/15 text-amber-700 dark:text-amber-300"}`}
                  title={node.dioptimalkan
                    ? "Sudah punya salinan ringan — peta memakainya; geometri asli tetap utuh"
                    : "Belum diringankan — peta menggambar geometri penuh. Tekan “Ringankan Peta”"}
                  data-testid={`spasial-opt-${node.id}`}
                >
                  {node.dioptimalkan ? "ringan" : "belum ringan"}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {/* Isi lokasi = operasi BACA (viewer boleh): "aset apa saja di sini",
                bentuk yang dibutuhkan opname fisik. Fase 9. */}
            <button type="button" onClick={() => setIsiNode(node)}
              className="tap-expand p-0.5 rounded hover:bg-muted min-h-0 min-w-0"
              title="Lihat aset yang menempati lokasi ini"
              aria-label={`Isi lokasi ${node.nama || labelTipe}`}
              data-testid={`spasial-isi-${node.id}`}>
              <Boxes className="w-4 h-4 text-sky-600" />
            </button>
            {/* Opname lewat scan stiker (Fase 11). BACA juga boleh: viewer berhak
                melihat rekonsiliasi; tombol Terapkan-lah yang dibatasi penulis. */}
            <button type="button" onClick={() => setOpnameNode(node)}
              className="tap-expand p-0.5 rounded hover:bg-muted min-h-0 min-w-0"
              title="Opname: pindai stiker QR & sanding dengan catatan lokasi"
              aria-label={`Opname ${node.nama || labelTipe}`}
              data-testid={`spasial-opname-${node.id}`}>
              <ClipboardCheck className="w-4 h-4 text-emerald-600" />
            </button>
            {isWriter && (
              <>
                {/* HP: empat aksi tulis dilipat ke menu ⋮ — di layar 360px
                    enam ikon sebaris tak muat bersama nama node. */}
                <div className="sm:hidden">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button type="button"
                        className="tap-expand p-0.5 rounded hover:bg-muted min-h-0 min-w-0"
                        title="Aksi lain" aria-label={`Aksi untuk ${node.nama || labelTipe}`}
                        data-testid={`spasial-menu-${node.id}`}>
                        <MoreVertical className="w-4 h-4 text-muted-foreground" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-52">
                      <DropdownMenuItem className="min-h-[42px]" onClick={() => bukaTambah(node)}
                        data-testid={`spasial-menu-tambah-${node.id}`}>
                        <Plus className="w-4 h-4 mr-2 text-emerald-600" />Tambah anak
                      </DropdownMenuItem>
                      <DropdownMenuItem className="min-h-[42px]" onClick={() => bukaUbah(node)}
                        data-testid={`spasial-menu-ubah-${node.id}`}>
                        <Pencil className="w-4 h-4 mr-2 text-sky-600" />Ubah
                      </DropdownMenuItem>
                      <DropdownMenuItem className="min-h-[42px]" onClick={() => setEditorNode(node)}
                        data-testid={`spasial-menu-gambar-${node.id}`}>
                        <LandPlot className="w-4 h-4 mr-2 text-teal-600" />
                        {node.bbox ? "Ubah denah" : "Gambar denah"}
                      </DropdownMenuItem>
                      <DropdownMenuItem className="min-h-[42px]" onClick={() => hapus(node)}
                        data-testid={`spasial-menu-hapus-${node.id}`}>
                        <Trash2 className="w-4 h-4 mr-2 text-rose-600" />Hapus
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                {/* ≥sm: tetap sebaris — di sana lebarnya memang cukup. */}
                <span className="hidden sm:flex items-center gap-1.5">
                  {/* tap-expand: ikon kecil, area sentuh ~44px (lihat index.css) */}
                  <button type="button" onClick={() => bukaTambah(node)}
                    className="tap-expand p-0.5 rounded hover:bg-muted min-h-0 min-w-0" title="Tambah anak"
                    data-testid={`spasial-tambah-anak-${node.id}`}>
                    <Plus className="w-4 h-4 text-emerald-600" />
                  </button>
                  <button type="button" onClick={() => bukaUbah(node)}
                    className="tap-expand p-0.5 rounded hover:bg-muted min-h-0 min-w-0" title="Ubah"
                    data-testid={`spasial-ubah-${node.id}`}>
                    <Pencil className="w-4 h-4 text-sky-600" />
                  </button>
                  <button type="button" onClick={() => setEditorNode(node)}
                    className="tap-expand p-0.5 rounded hover:bg-muted min-h-0 min-w-0"
                    title={node.bbox ? "Ubah denah (gambar poligon)" : "Gambar denah (poligon)"}
                    data-testid={`spasial-gambar-${node.id}`}>
                    <LandPlot className="w-4 h-4 text-teal-600" />
                  </button>
                  <button type="button" onClick={() => hapus(node)}
                    className="tap-expand p-0.5 rounded hover:bg-muted min-h-0 min-w-0" title="Hapus"
                    data-testid={`spasial-hapus-${node.id}`}>
                    <Trash2 className="w-4 h-4 text-rose-600" />
                  </button>
                </span>
              </>
            )}
          </div>
        </div>
        {terbuka && anak.map((c) => <Baris key={c.id} node={c} level={level + 1} />)}
      </div>
    );
  };

  const akar = anakDari["__root__"] || [];

  return (
    <div className="min-h-screen bg-background text-foreground">
      {confirmDialog}
      {editorNode && (
        <Suspense fallback={null}>
          <DenahEditor
            node={editorNode}
            onClose={() => setEditorNode(null)}
            onSaved={loadNodes}
          />
        </Suspense>
      )}
      {imporBuka && (
        <Suspense fallback={null}>
          <ImporDenahDialog
            levels={levels}
            nodes={nodes}
            labelLevel={labelLevel}
            onClose={() => setImporBuka(false)}
            onSaved={loadNodes}
          />
        </Suspense>
      )}
      {isiNode && (
        <Suspense fallback={null}>
          <IsiNodeDialog
            node={isiNode}
            labelLevel={labelLevel}
            onClose={() => setIsiNode(null)}
          />
        </Suspense>
      )}
      {opnameNode && (
        <Suspense fallback={null}>
          <OpnameDialog
            node={opnameNode}
            labelLevel={labelLevel}
            isWriter={isWriter}
            onClose={() => setOpnameNode(null)}
          />
        </Suspense>
      )}
      {eksporBuka && (
        <Suspense fallback={null}>
          <EksporDenahDialog
            nodes={nodes}
            labelLevel={labelLevel}
            onClose={() => setEksporBuka(false)}
          />
        </Suspense>
      )}
      <div className="max-w-4xl mx-auto p-3 sm:p-4">
        <div className="flex items-center gap-2 mb-3">
          <Button variant="ghost" size="icon" onClick={onBack} aria-label="Kembali">
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <MapPinned className="w-5 h-5 text-indigo-500 shrink-0" />
          <div className="min-w-0">
            <h1 className="text-base sm:text-lg font-bold truncate">Hierarki Spasial</h1>
            <p className="text-[11px] text-muted-foreground truncate">
              Denah kawasan berlapis — Kawasan → Zona → Distrik → … → Ruangan
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 mb-3">
          <div className="relative flex-1 min-w-[160px]">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="Cari nama / kode / alias…" className="pl-8" data-testid="spasial-cari" />
          </div>
          <select value={preset} onChange={(e) => setPreset(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm"
            title="Penamaan tingkat" data-testid="spasial-preset">
            <option value="ikn_akrab">Label akrab (Zona/Distrik)</option>
            <option value="rdtr_baku">Kode baku (WP/SWP)</option>
          </select>
          {/* Ekspor = operasi BACA — viewer pun boleh (server require_user). */}
          <Button variant="outline" onClick={() => setEksporBuka(true)} size="sm"
                  title="Ekspor denah ke GeoJSON / KML / KMZ / Shapefile + template QGIS/Google Earth"
                  data-testid="spasial-ekspor">
            <Download className="w-4 h-4 mr-1" /> Ekspor
          </Button>
          {isWriter && (
            <Button variant="outline" onClick={() => setImporBuka(true)} size="sm"
                    title="Impor denah dari Shapefile / KML / KMZ / GeoJSON"
                    data-testid="spasial-impor">
              <Upload className="w-4 h-4 mr-1" /> Impor
            </Button>
          )}
          {isWriter && (
            <Button variant="outline" onClick={jalankanOptimasi} size="sm"
                    disabled={optimasi}
                    title="Hitung salinan ringan untuk peta \u2014 geometri asli tak diubah"
                    data-testid="spasial-optimasi">
              {optimasi ? <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                        : <Gauge className="w-4 h-4 mr-1" />}
              <span className="hidden sm:inline">Ringankan Peta</span>
            </Button>
          )}
          {isWriter && (
            <Button onClick={() => bukaTambah(null)} size="sm" data-testid="spasial-tambah-akar">
              <Plus className="w-4 h-4 mr-1" /> Tambah
            </Button>
          )}
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16 text-muted-foreground">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            {mencobaUlang ? "Jaringan tersendat — mencoba lagi…" : "Memuat…"}
          </div>
        ) : galatMuat ? (
          /* GAGAL ≠ KOSONG. Dulu cabang ini tidak ada: kegagalan jaringan jatuh
             ke cabang "Belum ada data. Mulai dari tingkat teratas" — menyuruh
             operator yang pohonnya PENUH membangun ulang dari nol. Layar tak
             boleh menyatakan sesuatu yang tidak diketahuinya. */
          <div className="text-center py-16" data-testid="spasial-galat-muat">
            <AlertTriangle className="w-10 h-10 mx-auto mb-2 text-amber-500" />
            <p className="text-sm text-foreground max-w-md mx-auto break-words">{galatMuat}</p>
            <p className="text-xs text-muted-foreground mt-1">
              Data Anda aman — yang gagal hanya menampilkannya.
            </p>
            <Button onClick={loadNodes} size="sm" variant="outline" className="mt-3"
                    data-testid="spasial-coba-lagi">
              <RefreshCw className="w-4 h-4 mr-1" /> Coba lagi
            </Button>
          </div>
        ) : akar.length === 0 ? (
          <div className="text-center py-16 text-muted-foreground">
            <Layers className="w-10 h-10 mx-auto mb-2 opacity-40" />
            <p className="text-sm">Belum ada data. Mulai dari tingkat teratas (mis. Kawasan).</p>
            {isWriter && (
              <Button onClick={() => bukaTambah(null)} size="sm" className="mt-3">
                <Plus className="w-4 h-4 mr-1" /> Tambah tingkat teratas
              </Button>
            )}
          </div>
        ) : (
          <div className="rounded-lg border border-border p-1">
            {akar.map((n) => <Baris key={n.id} node={n} level={0} />)}
          </div>
        )}
      </div>

      {form && (
        <Dialog open onOpenChange={(o) => !o && setForm(null)}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>{form.mode === "tambah" ? "Tambah Node" : "Ubah Node"}</DialogTitle>
              <DialogDescription>
                Tingkat, nama, dan induk. Induk harus tingkat yang lebih luas.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3 max-h-[60vh] overflow-y-auto px-0.5">
              <div>
                <label className="text-xs font-medium">Tingkat</label>
                <select value={form.tipe}
                  onChange={(e) => setForm((f) => ({ ...f, tipe: e.target.value, parent_id: "" }))}
                  className="w-full h-9 mt-1 rounded-md border border-input bg-background px-2 text-sm"
                  data-testid="spasial-form-tipe">
                  {levels.filter((l) => l.aktif !== false).map((l) => (
                    <option key={l.kode_baku} value={l.kode_baku}>{l.label || l.label_ui}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium">Induk</label>
                <select value={form.parent_id}
                  onChange={(e) => setForm((f) => ({ ...f, parent_id: e.target.value }))}
                  className="w-full h-9 mt-1 rounded-md border border-input bg-background px-2 text-sm"
                  data-testid="spasial-form-induk">
                  <option value="">— Tanpa induk (tingkat teratas) —</option>
                  {kandidatInduk(form.tipe).map((n) => (
                    <option key={n.id} value={n.id}>
                      {(labelLevel[n.tipe] || n.tipe)} · {n.nama}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium">Nama</label>
                <Input value={form.nama} onChange={(e) => setForm((f) => ({ ...f, nama: e.target.value }))}
                  className="mt-1" data-testid="spasial-form-nama" autoFocus />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs font-medium">Kode <span className="text-muted-foreground">(opsional)</span></label>
                  <Input value={form.kode} onChange={(e) => setForm((f) => ({ ...f, kode: e.target.value }))}
                    className="mt-1 font-mono" />
                </div>
                <div>
                  <label className="text-xs font-medium">Alias <span className="text-muted-foreground">(pisah koma)</span></label>
                  <Input value={form.nama_alias} onChange={(e) => setForm((f) => ({ ...f, nama_alias: e.target.value }))}
                    className="mt-1" placeholder="Gedung A, Tower A" />
                </div>
              </div>
              {(form.tipe === "BLOK" || form.tipe === "SUBBLOK") && (
                <div>
                  <label className="text-xs font-medium">Kode Zona RDTR <span className="text-muted-foreground">(mis. R.2, K.3)</span></label>
                  <Input value={form.zona_kode} onChange={(e) => setForm((f) => ({ ...f, zona_kode: e.target.value }))}
                    className="mt-1 font-mono" />
                </div>
              )}
              {(form.tipe === "RUANGAN" || form.tipe === "SAYAP") && (
                <div>
                  <label className="text-xs font-medium">
                    Peruntukan <span className="text-muted-foreground">(acuan standar SBSK ruang kerja)</span>
                  </label>
                  <Input value={form.peruntukan}
                    onChange={(e) => setForm((f) => ({ ...f, peruntukan: e.target.value }))}
                    className="mt-1" placeholder="mis. Ruang kerja Kepala Biro Umum"
                    data-testid="spasial-peruntukan" />
                  <p className="text-[10px] text-muted-foreground mt-1">
                    Ditetapkan manusia, bukan ditebak dari isi asetnya. Dikosongkan =
                    ruangan belum ditetapkan peruntukannya (muncul di laporan SBSK Ruang).
                  </p>
                </div>
              )}
              {form.tipe === "LANTAI" && (
                <div className="rounded-md border border-border p-2 space-y-2">
                  <p className="text-[11px] text-muted-foreground">
                    Ordinal: 0 = lantai akses masuk utama, negatif = basement. "Lantai 1" di Indonesia
                    lazim berarti lantai dasar — pisahkan dari label.
                  </p>
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <label className="text-xs font-medium">Ordinal</label>
                      <Input type="number" value={form.lantai_ordinal}
                        onChange={(e) => setForm((f) => ({ ...f, lantai_ordinal: e.target.value }))}
                        className="mt-1" placeholder="0" />
                    </div>
                    <div>
                      <label className="text-xs font-medium">Label</label>
                      <Input value={form.lantai_label}
                        onChange={(e) => setForm((f) => ({ ...f, lantai_label: e.target.value }))}
                        className="mt-1" placeholder="Basement 1" />
                    </div>
                    <div>
                      <label className="text-xs font-medium">Pendek</label>
                      <Input value={form.lantai_pendek}
                        onChange={(e) => setForm((f) => ({ ...f, lantai_pendek: e.target.value }))}
                        className="mt-1" placeholder="B1" />
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-medium">Kategori</label>
                    <select value={form.lantai_kategori}
                      onChange={(e) => setForm((f) => ({ ...f, lantai_kategori: e.target.value }))}
                      className="w-full h-9 mt-1 rounded-md border border-input bg-background px-2 text-sm">
                      {KATEGORI_LANTAI.map((k) => <option key={k} value={k}>{k}</option>)}
                    </select>
                  </div>
                </div>
              )}
              {/* Status hanya di mode ubah — aktivasi DRAFT (hasil impor /
                  gambar setengah jadi) harus keputusan sadar, bukan efek
                  samping mengganti nama (temuan Fase 7). */}
              {form.mode === "ubah" && (
                <div>
                  <label className="text-xs font-medium">Status</label>
                  <select value={form.status}
                    onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}
                    className="w-full h-9 mt-1 rounded-md border border-input bg-background px-2 text-sm"
                    data-testid="spasial-form-status">
                    <option value="aktif">Aktif — ikut deteksi & peta</option>
                    <option value="draft">Draft — belum diperiksa, tak ikut deteksi</option>
                    <option value="nonaktif">Nonaktif — disimpan tapi dimatikan</option>
                  </select>
                </div>
              )}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setForm(null)} disabled={saving} data-testid="spasial-form-batal">Batal</Button>
              <Button onClick={simpan} disabled={saving} data-testid="spasial-form-simpan">
                {saving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />} Simpan
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
