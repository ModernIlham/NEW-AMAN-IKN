import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Loader2, ShoppingCart, Plus, Search, Trash2, X, Coins,
  ClipboardCheck, Download, Link2, Paperclip, Upload, PackagePlus,
  Check, Circle, Boxes, FileDown, PenLine, FileSignature,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import Lipatan from "@/components/ui/Lipatan";
import StatKartu from "@/components/ui/StatKartu";
import { useBackGuard } from "@/hooks/useBackGuard";
import { authMediaUrl } from "@/lib/mediaUrl";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import BookingNomorButton from "@/components/persuratan/BookingNomorButton";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Picker kode barang dari REFERENSI KODEFIKASI — ketik kode/nama, pilih dari
// daftar. Dulu kolom kode diketik buta; salah satu digit membuat pemilahan
// aset/persediaan salah kandang. Pola fetch debounce meniru AssetForm.
function KodeBarangPicker({ value, onChange, onPick, testid }) {
  const [sug, setSug] = useState(null);   // null = tertutup; [] = kosong
  const [buka, setBuka] = useState(false);
  const timerRef = useRef(null);
  const cari = (q) => {
    clearTimeout(timerRef.current);
    if (!q || q.length < 2) { setSug(null); return; }
    timerRef.current = setTimeout(async () => {
      try {
        const r = await axios.get(`${API}/kodefikasi`, { params: { search: q, page_size: 12 } });
        setSug(r.data?.items || []);
      } catch { setSug(null); /* offline → biarkan ketik manual */ }
    }, 300);
  };
  return (
    <div className="relative">
      <Input placeholder="Kode barang — ketik kode/nama" className="font-mono" value={value}
        onChange={(e) => { onChange(e.target.value); cari(e.target.value.trim()); setBuka(true); }}
        onFocus={() => { if (sug) setBuka(true); }}
        onBlur={() => setTimeout(() => setBuka(false), 150)}
        data-testid={testid} />
      {buka && Array.isArray(sug) && sug.length > 0 && (
        <div className="absolute z-50 left-0 right-0 mt-1 max-h-56 overflow-y-auto rounded-lg border border-border bg-popover shadow-elev-2">
          {sug.map((k) => (
            <button key={k.kode} type="button"
              onMouseDown={(e) => { e.preventDefault(); onPick(k); setBuka(false); }}
              className="w-full px-2 py-1.5 text-left hover:bg-accent flex items-start gap-2 min-h-0 min-w-0">
              <span className="font-mono text-[11px] text-teal-700 dark:text-teal-400 flex-shrink-0">{k.kode}</span>
              <span className="text-[11px] text-foreground flex-1 leading-snug">
                {k.uraian}
                <span className="text-muted-foreground"> · {k.label_level}{k.is_persediaan ? " · persediaan" : ""}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const BARANG_KOSONG = { uraian: "", kode: "", jumlah: "1", harga_satuan: "" };

/**
 * Pengadaan — Fase 4 tahap awal: register perolehan per dokumen
 * (Perpres 16/2018 jo. 46/2025, pustaka §10): satu entri per BAST/kontrak,
 * checklist dokumen sumber (penangkal "BAST tercecer"), tautan barang ke
 * aset master + penanda ekstrakomptabel PMK 181. Pencatatan resmi tetap
 * di SAKTI; barang belum tertaut dapat dibuatkan draft aset otomatis
 * (tombol "Buat Draft Aset", NUP berurut).
 */
export default function PengadaanPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  // Dialog perolehan baru: {data, barang: [], saving}
  const [form, setForm] = useState(null);
  // Dialog tautkan aset: {perolehan, index, saving}
  const [taut, setTaut] = useState(null);
  // Dialog lampiran berkas: {perolehan, uploading}
  const [lamp, setLamp] = useState(null);
  // Dialog buat draft aset dari perolehan (evaluasi #5): {perolehan, activityId, saving}
  const [draftAset, setDraftAset] = useState(null);
  const [kegiatanList, setKegiatanList] = useState([]);
  const lampInputRef = useRef(null);
  const [cari, setCari] = useState("");
  const [hasilCari, setHasilCari] = useState([]);
  const [mencari, setMencari] = useState(false);
  const cariTimer = useRef(null);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  // Opsi usulan penganggaran untuk dropdown tautan (#117 ↔ #115)
  const [opsiAnggaran, setOpsiAnggaran] = useState([]);
  // Pejabat ber-peran PPK untuk dropdown penetapan (Referensi Pejabat).
  const [opsiPpk, setOpsiPpk] = useState([]);
  // Hasil "Catat Semua Barang" — LPB yang baru TERBIT ditampilkan sebagai
  // dialog, bukan hanya toast. Nomor surat yang menghilang bersama toast
  // memaksa operator berpindah ke modul Persediaan hanya untuk mencetaknya.
  const [hasilCatat, setHasilCatat] = useState(null);
  const [tautanTtd, setTautanTtd] = useState(null);
  // Dialog LPB gabungan: {pilih: {id: bool}, saving} — merangkum banyak
  // BAST PPK → KPB (aset & persediaan) dalam SATU surat laporan.
  const [lpbGab, setLpbGab] = useState(null);

  const muat = useCallback(() => {
    axios.get(`${API}/pengadaan`)
      .then((r) => setData(r.data))
      .catch(() => toast.error("Gagal memuat register perolehan"))
      .finally(() => setLoading(false));
    // Daftar usulan penganggaran (opsional — kegagalan tak menahan register)
    axios.get(`${API}/penganggaran`)
      .then((r) => setOpsiAnggaran(r.data?.items || []))
      .catch(() => setOpsiAnggaran([]));
    // Daftar kegiatan inventarisasi — tujuan "buat draft aset" (best-effort)
    axios.get(`${API}/inventory-activities`)
      .then((r) => setKegiatanList(Array.isArray(r.data) ? r.data : []))
      .catch(() => setKegiatanList([]));
    // Pejabat ber-peran PPK. Dibiarkan kosong bila gagal: server tetap bisa
    // meresolusi PPK sendiri dari tanggal BAST, jadi dropdown ini pelengkap,
    // bukan syarat.
    axios.get(`${API}/pejabat`)
      .then((r) => {
        const semua = Array.isArray(r.data) ? r.data : (r.data?.items || []);
        setOpsiPpk(semua.filter((pj) => (pj?.peran || []).includes("ppk")));
      })
      .catch(() => setOpsiPpk([]));
  }, []);
  useEffect(() => { muat(); }, [muat]);

  useEffect(() => {
    if (!taut || cari.trim().length < 2) { setHasilCari([]); return undefined; }
    clearTimeout(cariTimer.current);
    cariTimer.current = setTimeout(async () => {
      setMencari(true);
      try {
        const r = await axios.get(`${API}/assets`, { params: { search: cari.trim(), page_size: 8 } });
        setHasilCari(r.data?.items || []);
      } catch { setHasilCari([]); } finally { setMencari(false); }
    }, 300);
    return () => clearTimeout(cariTimer.current);
  }, [cari, taut]);

  const fmtRp = (n) => `Rp${Math.round(Number(n || 0)).toLocaleString("id-ID")}`;
  const labelJenis = data?.label_jenis || {};
  const kodeJenis = data?.kode_jenis || {};
  const labelDokumen = data?.label_dokumen || {};
  const dokumenWajib = data?.dokumen_wajib || {};

  const simpanPerolehan = async () => {
    if (!form) return;
    setForm((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/pengadaan`, {
        ...form.data,
        barang: form.barang.map((b) => ({
          ...b, jumlah: Number(b.jumlah || 0), harga_satuan: Number(b.harga_satuan || 0),
        })),
      });
      toast.success("Perolehan dicatat");
      setForm(null);
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat perolehan");
      setForm((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const toggleDokumen = async (p, kunci) => {
    try {
      await axios.put(`${API}/pengadaan/${p.id}/dokumen`, {
        dokumen: { [kunci]: !(p.dokumen || {})[kunci] },
      });
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memperbarui checklist");
    }
  };

  const tautkan = async (assetId) => {
    if (!taut) return;
    setTaut((t) => ({ ...t, saving: true }));
    try {
      await axios.post(`${API}/pengadaan/${taut.perolehan.id}/tautkan`, {
        index: taut.index, asset_id: assetId,
      });
      toast.success(assetId ? "Barang tertaut ke aset" : "Tautan dilepas");
      setTaut(null);
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menautkan");
      setTaut((t) => (t ? { ...t, saving: false } : t));
    }
  };

  const unggahLampiran = async (fileObj) => {
    if (!lamp || !fileObj) return;
    setLamp((l) => ({ ...l, uploading: true }));
    try {
      const fd = new FormData();
      fd.append("file", fileObj);
      const res = await axios.post(`${API}/pengadaan/${lamp.perolehan.id}/lampiran`, fd);
      toast.success("Lampiran terunggah");
      setLamp((l) => (l ? { ...l, uploading: false,
        perolehan: { ...l.perolehan, lampiran_berkas: res.data?.lampiran_berkas || [] } } : l));
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengunggah lampiran");
      setLamp((l) => (l ? { ...l, uploading: false } : l));
    }
  };

  const hapusLampiran = async (fileId) => {
    if (!lamp) return;
    try {
      await axios.delete(`${API}/pengadaan/${lamp.perolehan.id}/lampiran/${fileId}`);
      toast.success("Lampiran dihapus");
      setLamp((l) => (l ? { ...l,
        perolehan: { ...l.perolehan,
          lampiran_berkas: (l.perolehan.lampiran_berkas || []).filter((x) => x.file_id !== fileId) } } : l));
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus lampiran");
    }
  };

  // SATU tombol untuk seluruh barang BAST: server memilah sendiri golongan 1
  // (persediaan) dari golongan 2–8 (aset tetap), lalu menerbitkan LPB untuk
  // sisi aset. Sebelumnya operator harus tahu pemilahan itu sendiri DAN
  // menekan dua tombol berbeda — dan menekan keduanya justru mencatat barang
  // persediaan dua kali.
  const catatSemua = async () => {
    if (!draftAset) return;
    // Kegiatan hanya wajib bila ada barang yang akan jadi ASET. BAST berisi
    // persediaan saja tak perlu kegiatan inventarisasi sama sekali.
    if (draftAset.butuhKegiatan && !draftAset.activityId) {
      toast.error("Pilih kegiatan inventarisasi tujuan"); return;
    }
    setDraftAset((d) => ({ ...d, saving: true }));
    try {
      const r = await axios.post(`${API}/pengadaan/${draftAset.perolehan.id}/catat-semua`, {
        activity_id: draftAset.activityId,
        booking_nomor: draftAset.bookingNomor !== false,
      });
      const d = r.data || {};
      const bagian = [];
      if (d.aset_dibuat) bagian.push(`${d.aset_dibuat} aset`);
      if (d.persediaan_masuk) bagian.push(`${d.persediaan_masuk} barang persediaan`);
      // Toast HIJAU hanya bila memang ada yang tercatat. Saat semua baris
      // gagal, "tidak ada barang baru" adalah kalimat yang menyesatkan —
      // seolah tak ada yang perlu dikerjakan (temuan audit).
      if (bagian.length) {
        toast.success(`Tercatat: ${bagian.join(" dan ")}`
          + (d.nomor_lpb ? ` · LPB ${d.nomor_lpb}` : ""));
        // LPB baru terbit = dokumen resmi yang harus DICETAK dan DITEKEN.
        // Nomornya di dalam toast akan lenyap dalam beberapa detik, dan
        // satu-satunya jalan mencetaknya dulu adalah berpindah ke modul
        // Persediaan → Riwayat LPB. Loop-nya ditutup di tempat kerjanya.
        if (d.lpb_id) {
          setHasilCatat({
            lpbId: d.lpb_id, nomor: d.nomor_lpb || d.lpb_id.slice(0, 8),
            asetDibuat: d.aset_dibuat || 0,
            persediaanMasuk: d.persediaan_masuk || 0,
            nomorBast: draftAset.perolehan.nomor_bast, mengirim: false,
          });
        }
      } else if (!(d.gagal || []).length && !d.tanpa_kode) {
        toast.info("Semua barang di BAST ini sudah tercatat sebelumnya");
      }
      // Kegagalan sebagian TIDAK boleh tenggelam di balik toast hijau — jalur
      // ini memang tak transaksional.
      if (d.tanpa_kode) {
        toast.warning(`${d.tanpa_kode} baris belum berkode barang `
          + `(baris ${(d.baris_tanpa_kode || []).join(", ")}) — isi kode dulu.`,
        { duration: 9000 });
      }
      // SELURUH alasan gagal ditampilkan, bukan hanya yang pertama: baris
      // kedua dan seterusnya bisa gagal karena sebab yang sama sekali lain.
      if ((d.gagal || []).length) {
        toast.error(`${d.total_gagal} baris gagal:\n· ${d.gagal.join("\n· ")}`,
          { duration: 15000 });
      }
      setDraftAset(null);
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat barang");
      setDraftAset((d) => (d ? { ...d, saving: false } : d));
    }
  };

  // Kirim LPB yang BARU terbit untuk ditandatangani — tanpa berpindah modul.
  // Endpoint-nya milik Persediaan karena `db.lpb` satu koleksi untuk kedua
  // kategori; yang berbeda hanya pintu masuknya.
  const kirimTtdLpbBaru = async () => {
    if (!hasilCatat?.lpbId) return;
    const ok = await confirm({
      title: "Kirim LPB untuk ditandatangani?",
      description: `${hasilCatat.nomor} — dokumen PDF dibekukan sekarang, lalu `
        + "tiap penanda tangan menerima tautan sendiri. Penanda tangan diambil "
        + "dari Referensi Pejabat (Pengurus Barang → Pemeriksa LPB → KPB).",
      confirmLabel: "Kirim",
    });
    if (!ok) return;
    setHasilCatat((h) => (h ? { ...h, mengirim: true } : h));
    try {
      const r = await axios.post(`${API}/persediaan/lpb/${hasilCatat.lpbId}/kirim-ttd`, {});
      const tautan = r.data?.links || [];
      toast.success(`Permintaan TTD terkirim ke ${tautan.length} penanda tangan`
        + (tautan.some((x) => x.email_terkirim) ? " (email terkirim)" : ""));
      // Tautannya DITAMPILKAN, bukan hanya jumlahnya: tanpa email
      // terkonfigurasi, tautan yang tak pernah muncul di layar berarti
      // permintaan TTD tak sampai ke siapa pun.
      setTautanTtd({ nomor: hasilCatat.nomor, links: tautan });
      setHasilCatat(null);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengirim permintaan TTD",
        { duration: 9000 });
      setHasilCatat((h) => (h ? { ...h, mengirim: false } : h));
    }
  };

  // BAST PPK → KPB: serah terima LANJUTAN hasil pengadaan. Nomor BAST yang
  // diinput operator adalah BAST Penyedia → PPK (dinomori PPK sendiri);
  // dokumen PPK → KPB inilah yang DITERBITKAN aplikasi — sekali terbit,
  // tombol yang sama menjadi tombol unduh PDF-nya.
  const unduhBastPpk = (p) => downloadFileWithProgress(
    `${API}/pengadaan/${p.id}/bast-ppk-kpb/pdf`,
    `BAST_PPK_KPB_${String(p.bast_ppk?.nomor || p.nomor_bast || p.id.slice(0, 8)).replace(/[/\s]/g, "_")}.pdf`,
    { label: "BAST PPK → KPB (PDF)" }).catch(() => {});

  const terbitkanBastPpk = async (p) => {
    if (p.bast_ppk) { unduhBastPpk(p); return; }
    if (!p.ppk_nama) {
      toast.error("Tetapkan PPK dulu (ketuk baris PPK) — PIHAK KESATU dokumen ini adalah PPK.");
      return;
    }
    const ok = await confirm({
      title: "Terbitkan BAST PPK → KPB?",
      description: `Hasil pengadaan ${p.nomor_bast} diserahterimakan dari `
        + `${p.ppk_nama} (PPK) kepada Kuasa Pengguna Barang untuk ditatausahakan `
        + "sebagai BMN. Nomor Berita Acara dipesan otomatis dari Persuratan dan "
        + "identitas kedua pihak dibekukan pada dokumen.",
      confirmLabel: "Terbitkan",
    });
    if (!ok) return;
    try {
      const r = await axios.post(`${API}/pengadaan/${p.id}/bast-ppk-kpb`, {});
      const nomor = r.data?.bast_ppk?.nomor;
      toast.success(nomor ? `BAST PPK → KPB terbit: ${nomor}` : "BAST PPK → KPB terbit");
      unduhBastPpk({ ...p, bast_ppk: r.data?.bast_ppk });
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menerbitkan BAST PPK → KPB",
        { duration: 9000 });
    }
  };

  // LPB gabungan: SATU laporan penerimaan merangkum banyak BAST PPK → KPB —
  // baris aset maupun persediaan. Hanya perolehan yang SUDAH ber-BAST
  // PPK → KPB yang bisa dipilih (server menolak sisanya juga).
  const buatLpbGabungan = async () => {
    if (!lpbGab) return;
    const ids = Object.keys(lpbGab.pilih).filter((k) => lpbGab.pilih[k]);
    if (!ids.length) { toast.error("Pilih minimal satu perolehan"); return; }
    setLpbGab((g) => ({ ...g, saving: true }));
    try {
      const r = await axios.post(`${API}/pengadaan/lpb-gabungan`, { perolehan_ids: ids });
      const d = r.data || {};
      toast.success(`LPB gabungan terbit${d.nomor ? `: ${d.nomor}` : ""}`);
      setLpbGab(null);
      setHasilCatat({
        lpbId: d.lpb_id, nomor: d.nomor || String(d.lpb_id || "").slice(0, 8),
        gabungan: d.jumlah_bast || ids.length, jumlahBarang: d.jumlah_barang || 0,
        mengirim: false,
      });
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuat LPB gabungan",
        { duration: 9000 });
      setLpbGab((g) => (g ? { ...g, saving: false } : g));
    }
  };

  // PPK bisa DIPERBAIKI tanpa mencatat ulang BAST (endpoint PUT sudah ada
  // sejak awal, tetapi tak pernah punya jalan masuk dari layar — operator
  // justru disuruh "catat ulang", yang berarti membuat register ganda).
  const ubahPpk = async (p) => {
    const pilihan = [{ id: "auto", label: "Otomatis dari Referensi Pejabat" },
                     ...opsiPpk.map((pj) => ({
                       id: pj.id,
                       label: `${pj.nama}${pj.nip ? ` · ${pj.nip}` : ""}` })),
                     { id: "", label: "Kosongkan penetapan" }];
    const ok = await confirm({
      title: "Perbarui PPK pada BAST ini?",
      description: `${p.nomor_bast} — PPK saat ini: ${p.ppk_nama || "(belum ditetapkan)"}. `
        + "Server akan mencari PPK yang berlaku pada tanggal BAST, lalu "
        + "memperbarui aset-aset yang sudah tercatat dari BAST ini.",
      confirmLabel: "Perbarui otomatis",
    });
    if (!ok) return;
    try {
      const r = await axios.put(`${API}/pengadaan/${p.id}/ppk`,
        { ppk_pejabat_id: "auto" });
      const nama = r.data?.ppk_nama;
      toast.success(nama ? `PPK diperbarui: ${nama}`
        : "Tak ada PPK yang berlaku pada tanggal BAST ini — "
          + "isi Referensi Pejabat lebih dulu.");
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memperbarui PPK");
    }
    void pilihan;
  };

  const hapus = async (p) => {
    const ok = await confirm({
      title: "Hapus register perolehan?",
      description: `${p.nomor_bast} — ${p.pihak}.`,
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/pengadaan/${p.id}`);
      toast.success("Register perolehan dihapus");
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus");
    }
  };

  const setFormBarang = (i, k, v) => setForm((f) => ({
    ...f, barang: f.barang.map((b, idx) => (idx === i ? { ...b, [k]: v } : b)),
  }));
  // Buka dialog catat perolehan baru — dipakai tombol header & empty-state
  const bukaFormBaru = () => setForm({
    data: { jenis: "pembelian", pihak: "", nomor_kontrak: "", nomor_bast: "", tanggal_bast: new Date().toISOString().slice(0, 10), keterangan: "", penganggaran_id: "", ppk_pejabat_id: "" },
    barang: [{ ...BARANG_KOSONG }], saving: false,
  });
  const r = data?.ringkasan;

  return (
    <div className="min-h-screen bg-background" data-testid="pengadaan-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex flex-wrap items-center gap-2 sm:gap-3 gap-y-2">
          <button type="button" onClick={onBack} aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="pengadaan-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-orange-600 flex items-center justify-center flex-shrink-0">
            <ShoppingCart className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight truncate">Pengadaan — Register Perolehan</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Dokumen sumber per BAST/kontrak (Perpres 16/2018 jo. 46/2025)
            </p>
          </div>
          <Button size="sm" variant="outline" className="flex-shrink-0"
            onClick={() => downloadFileWithProgress(`${API}/pengadaan/export`, "register_pengadaan.csv", { label: "Ekspor Register Pengadaan (CSV)" }).catch(() => {})}
            data-testid="pengadaan-export">
            <Download className="w-4 h-4 sm:mr-1.5" /><span className="hidden sm:inline">CSV</span>
          </Button>
          <Button size="sm" variant="outline" className="flex-shrink-0"
            title="Satu LPB merangkum banyak BAST PPK → KPB (aset & persediaan)"
            onClick={() => setLpbGab({ pilih: {}, saving: false })}
            data-testid="pengadaan-lpb-gabungan">
            <Boxes className="w-4 h-4 sm:mr-1.5" /><span className="hidden sm:inline">LPB Gabungan</span>
          </Button>
          <Button size="sm" onClick={bukaFormBaru}
            className="bg-orange-600 hover:bg-orange-700 text-white flex-shrink-0" data-testid="pengadaan-tambah">
            <Plus className="w-4 h-4 sm:mr-1.5" /><span className="hidden sm:inline">Catat Perolehan</span>
          </Button>
          <BookingNomorButton modul="pengadaan" jenisNaskah="Berita Acara" referensi="BAST Perolehan" />
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-7 h-7 animate-spin text-orange-600" />
          </div>
        ) : !data ? null : (
          <>
            {/* ── Ringkasan ── */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <StatKartu
                icon={ShoppingCart} warna="text-orange-500" tint="bg-orange-500/10"
                value={r.jumlah}
                label="Perolehan tercatat"
                testid="pengadaan-stat-jumlah"
              />
              <StatKartu
                icon={Coins} warna="text-blue-500" tint="bg-blue-500/10"
                value={fmtRp(r.nilai)}
                label="Nilai perolehan"
                title={fmtRp(r.nilai)}
                testid="pengadaan-stat-nilai"
              />
              <StatKartu
                icon={ClipboardCheck} warna="text-emerald-500" tint="bg-emerald-500/10"
                value={`${r.dokumen_lengkap}/${r.jumlah}`}
                label="Dokumen lengkap"
                testid="pengadaan-stat-dokumen"
                className="border-emerald-500/40"
              />
              <StatKartu
                icon={Link2}
                warna={r.belum_tertaut > 0 ? "text-amber-500" : "text-muted-foreground"}
                tint={r.belum_tertaut > 0 ? "bg-amber-500/10" : "bg-muted"}
                value={r.belum_tertaut}
                label="Barang belum tertaut aset"
                testid="pengadaan-stat-tertaut"
                className={r.belum_tertaut > 0 ? "border-amber-500/40" : ""}
              />
            </div>

            {/* ── Daftar perolehan ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
              {data.items.length === 0 ? (
                <div className="text-center py-10 px-4">
                  <ShoppingCart className="w-8 h-8 text-muted-foreground/50 mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">Belum ada perolehan tercatat — mulai dari BAST/kontrak terbaru.</p>
                  <Button size="sm" className="mt-3 bg-orange-600 hover:bg-orange-700 text-white"
                    onClick={bukaFormBaru} data-testid="pengadaan-empty-tambah">
                    <Plus className="w-4 h-4 mr-1.5" />Catat Perolehan Pertama
                  </Button>
                </div>
              ) : (
                <ul className="divide-y divide-border/60">
                  {data.items.map((p) => (
                    <li key={p.id} className="p-3" data-testid={`pengadaan-row-${p.id}`}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="px-1.5 py-0.5 rounded bg-orange-500/15 text-orange-600 dark:text-orange-400 text-[10px] font-semibold">
                          {labelJenis[p.jenis] || p.jenis} · {kodeJenis[p.jenis]}
                        </span>
                        <p className="text-sm font-semibold text-foreground flex-1 min-w-[140px] truncate">{p.pihak}</p>
                        <span className="text-xs font-bold text-foreground whitespace-nowrap">{fmtRp(p.nilai)}</span>
                        {(() => {
                          const w = dokumenWajib[p.jenis] || [];
                          if (!w.length) return null;
                          const n = w.filter((k) => (p.dokumen || {})[k]).length;
                          return (
                            <span title={`${n} dari ${w.length} dokumen wajib tersedia`}
                              className={`px-1.5 py-0.5 rounded text-[10px] font-semibold flex-shrink-0 ${
                                n === w.length
                                  ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                                  : "bg-amber-500/15 text-amber-600 dark:text-amber-400"
                              }`}
                              data-testid={`pengadaan-dok-ringkas-${p.id}`}>
                              {n}/{w.length} dok
                            </span>
                          );
                        })()}
                        {/* SATU tombol. Pemilahan persediaan↔aset dikerjakan
                            server (lihat lpb_utils.pilah_barang_perolehan) —
                            bukan pengetahuan yang harus dihafal operator. */}
                        {(p.barang || []).some((b) => !b.asset_id && !b.psd_item_id) && (
                          <button type="button" aria-label="Catat semua barang BAST ke pencatatan"
                            title="Barang golongan 1 → Persediaan; golongan 2–8 → aset draft ber-NUP; lalu LPB terbit"
                            onClick={() => setDraftAset({
                              perolehan: p, activityId: "", bookingNomor: true,
                              // Kegiatan inventarisasi hanya wajib bila BAST ini
                              // memuat barang golongan ASET. Dihitung SEKALI di
                              // sini — daftar barangnya tak berubah selama
                              // dialog terbuka.
                              butuhKegiatan: (p.barang || []).some((b) =>
                                !b.asset_id && !b.psd_item_id
                                && String(b.kode || "").trim()
                                && !String(b.kode || "").trim().startsWith("1")),
                              saving: false })}
                            className="h-7 px-2 rounded-lg border border-emerald-500/40 bg-emerald-600/10 text-emerald-600 dark:text-emerald-400 flex items-center gap-1 text-[10px] font-semibold hover:bg-emerald-600/20 min-h-0 min-w-0"
                            data-testid={`pengadaan-catat-semua-${p.id}`}>
                            <PackagePlus className="w-3.5 h-3.5" />
                            <span className="hidden sm:inline">Catat Semua Barang</span>
                          </button>
                        )}
                        {/* BAST PPK→KPB: belum terbit → terbitkan (butuh PPK);
                            sudah terbit → tombol yang sama mengunduh PDF-nya. */}
                        <button type="button"
                          aria-label={p.bast_ppk ? "Unduh BAST PPK ke KPB (PDF)" : "Terbitkan BAST PPK ke KPB"}
                          title={p.bast_ppk?.nomor
                            ? `Unduh BAST PPK → KPB (${p.bast_ppk.nomor})`
                            : p.bast_ppk
                              ? "Unduh BAST PPK → KPB (PDF)"
                              : "Terbitkan BAST PPK → KPB — serah terima lanjutan dari PPK kepada Kuasa Pengguna Barang"}
                          onClick={() => terbitkanBastPpk(p)}
                          className={`h-7 px-2 rounded-lg border flex items-center gap-1 text-[10px] font-semibold min-h-0 min-w-0 ${
                            p.bast_ppk
                              ? "border-sky-500/40 bg-sky-600/10 text-sky-600 dark:text-sky-400 hover:bg-sky-600/20"
                              : "border-border text-foreground/70 hover:bg-muted"}`}
                          data-testid={`pengadaan-bast-ppk-${p.id}`}>
                          <FileSignature className="w-3.5 h-3.5" />
                          <span className="hidden sm:inline">BAST PPK→KPB</span>
                        </button>
                        <button type="button" aria-label="Lampiran berkas"
                          onClick={() => setLamp({ perolehan: p, uploading: false })}
                          className="h-7 w-7 rounded-lg border border-border text-foreground/70 flex items-center justify-center hover:bg-muted min-h-0 min-w-0"
                          data-testid={`pengadaan-lampiran-${p.id}`}>
                          <Paperclip className="w-3.5 h-3.5" />
                        </button>
                        {isAdmin && (
                          <button type="button" aria-label="Hapus perolehan" onClick={() => hapus(p)}
                            className="h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 min-h-0 min-w-0">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5 truncate">
                        {`BAST ${p.nomor_bast} (${p.tanggal_bast})`}
                        {p.nomor_kontrak && ` · Kontrak ${p.nomor_kontrak}`}
                        {p.bast_ppk?.nomor && ` · BAST PPK→KPB ${p.bast_ppk.nomor}`}
                        {p.keterangan && ` · ${p.keterangan}`}
                        {` · oleh ${p.created_by}`}
                      </p>
                      {/* PPK: pertanyaan pertama pemeriksa saat menelusuri satu
                          BAST. Ketiadaannya ditampilkan TERUS TERANG, bukan
                          dibiarkan sebagai baris yang hilang begitu saja. */}
                      <button type="button"
                        onClick={() => ubahPpk(p)}
                        title="Klik untuk memperbarui PPK dari Referensi Pejabat"
                        className={`block text-left text-[11px] mt-0.5 truncate w-full min-h-0 hover:underline ${
                          p.ppk_nama
                            ? "text-sky-600 dark:text-sky-400"
                            : "text-amber-600 dark:text-amber-400"}`}
                        data-testid={`pengadaan-ppk-${p.id}`}>
                        {p.ppk_nama
                          ? `PPK: ${p.ppk_nama}${p.ppk_nip ? ` · NIP ${p.ppk_nip}` : ""}`
                          : "PPK belum ditetapkan — ketuk untuk mengisi dari Referensi Pejabat"}
                      </button>
                      {p.penganggaran_id && (
                        <p className="text-[11px] text-violet-600 dark:text-violet-400 mt-0.5 truncate" data-testid={`pengadaan-anggaran-${p.id}`}>
                          Anggaran: {p.penganggaran_uraian || "(usulan)"}
                          {p.penganggaran_tahun && ` · TA ${p.penganggaran_tahun}`}
                          {p.penganggaran_nomor_dipa && ` · ${p.penganggaran_nomor_dipa}`}
                        </p>
                      )}
                      {/* Checklist dokumen sumber */}
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {(dokumenWajib[p.jenis] || []).map((k) => {
                          const ada = !!(p.dokumen || {})[k];
                          return (
                            <button key={k} type="button" onClick={() => toggleDokumen(p, k)}
                              title="Klik untuk menandai dokumen ada/belum"
                              className={`px-1.5 py-0.5 rounded text-[10px] font-semibold border transition-colors min-h-0 ${
                                ada
                                  ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/40"
                                  : "bg-muted text-muted-foreground border-border hover:text-foreground"
                              }`}
                              data-testid={`pengadaan-dok-${p.id}-${k}`}>
                              {ada ? <Check className="w-3 h-3 inline mr-0.5" /> : <Circle className="w-3 h-3 inline mr-0.5" />}
                              {labelDokumen[k] || k}
                            </button>
                          );
                        })}
                      </div>
                      {/* Daftar barang */}
                      <ul className="mt-1.5 space-y-1">
                        {(p.barang || []).map((b, i) => (
                          <li key={`${p.id}-${i}`} className="rounded-lg border border-border/70 px-2 py-1.5 flex flex-wrap items-center gap-2">
                            <span className="min-w-0 flex-1">
                              <span className="block text-xs font-semibold text-foreground truncate">
                                {b.uraian} <span className="font-normal text-muted-foreground">×{b.jumlah} @ {fmtRp(b.harga_satuan)}</span>
                              </span>
                              {/* Tiga keadaan, bukan dua. Baris yang sudah masuk
                                  KARTU STOK dulu ikut berbunyi "belum tertaut"
                                  — kalimat yang menyuruh operator menautkannya
                                  ke aset, persis pencatatan ganda yang penjaga
                                  golongan dipasang untuk mencegah. */}
                              {b.asset_id ? (
                                <span className="block text-[10px] text-emerald-600 dark:text-emerald-400 font-mono truncate">
                                  <Link2 className="w-3 h-3 inline mr-0.5 align-[-2px]" />{b.asset_name} ({b.asset_code} · {b.NUP})
                                </span>
                              ) : b.psd_item_id ? (
                                <span className="block text-[10px] text-cyan-600 dark:text-cyan-400">
                                  <Boxes className="w-3 h-3 inline mr-0.5 align-[-2px]" />Tercatat sebagai persediaan (kartu stok)
                                </span>
                              ) : (
                                <span className="block text-[10px] text-amber-600 dark:text-amber-400">Belum tertaut ke aset master</span>
                              )}
                            </span>
                            {b.ekstrakomptabel && (
                              <span className="px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-600 dark:text-violet-400 text-[10px] font-semibold">
                                Ekstrakomptabel
                              </span>
                            )}
                            {/* Baris yang sudah di kartu stok TIDAK menawarkan
                                "Tautkan": server menolaknya, dan tombol yang
                                pasti gagal hanyalah undangan untuk mencoba. */}
                            {!b.psd_item_id && (
                              <Button size="sm" variant="outline" className="h-6 text-[10px] min-h-0 px-2"
                                onClick={() => { setCari(""); setHasilCari([]); setTaut({ perolehan: p, index: i, saving: false }); }}
                                data-testid={`pengadaan-taut-${p.id}-${i}`}>
                                {b.asset_id ? "Ubah Tautan" : "Tautkan"}
                              </Button>
                            )}
                          </li>
                        ))}
                      </ul>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <p className="text-center text-[11px] text-muted-foreground pb-4">{data.catatan}</p>
          </>
        )}
      </main>

      {/* ── Dialog perolehan baru ── */}
      <Dialog open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }}>
        <DialogContent className="max-w-2xl w-[calc(100%-1.5rem)]">
          <DialogHeader>
            <DialogTitle>Catat Perolehan</DialogTitle>
            <DialogDescription className="text-xs">
              Satu entri per dokumen BAST/kontrak — BAST adalah pemicu pencatatan BMN.
            </DialogDescription>
          </DialogHeader>
          {form && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pgd-jenis">Jenis perolehan</label>
                <select id="pgd-jenis" value={form.data.jenis}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, jenis: e.target.value } }))}
                  className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                  data-testid="pengadaan-jenis">
                  {Object.entries(labelJenis).length
                    ? Object.entries(labelJenis).map(([k, v]) => <option key={k} value={k}>{v}</option>)
                    : <option value="pembelian">Pembelian</option>}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pgd-pihak">Penyedia/pemberi</label>
                <Input id="pgd-pihak" placeholder="cth. CV Sumber Rejeki" value={form.data.pihak}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, pihak: e.target.value } }))}
                  data-testid="pengadaan-pihak" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pgd-kontrak">No. Kontrak/SPK (opsional)</label>
                <Input id="pgd-kontrak" value={form.data.nomor_kontrak}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, nomor_kontrak: e.target.value } }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pgd-bast">No. BAST (Penyedia → PPK)</label>
                <Input id="pgd-bast" placeholder="BAST-01/PPK/2026" value={form.data.nomor_bast}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, nomor_bast: e.target.value } }))}
                  data-testid="pengadaan-nomor-bast" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pgd-tgl">Tanggal BAST</label>
                <Input id="pgd-tgl" type="date" value={form.data.tanggal_bast}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, tanggal_bast: e.target.value } }))} />
              </div>
              <p className="col-span-2 -mt-1 text-[11px] text-muted-foreground leading-snug rounded-lg bg-muted/60 px-2.5 py-1.5">
                BAST ini adalah serah terima dari <b>Penyedia kepada PPK</b>, dan
                <b> penomorannya dibuat PPK sendiri</b> — cukup catat nomornya di sini,
                lalu centang dokumen BAST &amp; unggah berkasnya bila sudah ada.
                Serah terima lanjutan dari PPK kepada KPB dibuatkan dokumennya
                lewat tombol <b>BAST PPK → KPB</b> setelah perolehan tersimpan.
              </p>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pgd-ket">Keterangan</label>
                <Input id="pgd-ket" value={form.data.keterangan}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, keterangan: e.target.value } }))} />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pgd-anggaran">Usulan Penganggaran terkait (opsional)</label>
                <select id="pgd-anggaran" value={form.data.penganggaran_id}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, penganggaran_id: e.target.value } }))}
                  className="w-full h-9 rounded-md border border-input bg-background px-2 text-sm text-foreground"
                  data-testid="pengadaan-penganggaran">
                  <option value="">— Tidak ditautkan —</option>
                  {opsiAnggaran.map((u) => (
                    <option key={u.id} value={u.id}>
                      {`${u.tahun_anggaran || "?"} · ${u.uraian || "(tanpa uraian)"}${u.nomor_dipa ? ` · ${u.nomor_dipa}` : ""}`}
                    </option>
                  ))}
                </select>
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pgd-ppk">
                  Pejabat Pembuat Komitmen (PPK)
                </label>
                <select id="pgd-ppk" value={form.data.ppk_pejabat_id}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, ppk_pejabat_id: e.target.value } }))}
                  className="w-full h-9 rounded-md border border-input bg-background px-2 text-sm text-foreground"
                  data-testid="pengadaan-ppk">
                  <option value="">— Otomatis: PPK yang berlaku pada tanggal BAST —</option>
                  {opsiPpk.map((pj) => (
                    <option key={pj.id} value={pj.id}>
                      {`${pj.nama}${pj.nip ? ` · ${pj.nip}` : ""}${pj.jabatan ? ` · ${pj.jabatan}` : ""}`}
                    </option>
                  ))}
                </select>
                <p className="text-[10px] text-muted-foreground mt-1">
                  Namanya <strong>dibekukan</strong> pada dokumen ini — pergantian PPK di
                  kemudian hari tidak mengubah BAST yang sudah terbit.
                  {opsiPpk.length === 0 && " Belum ada pejabat ber-peran PPK di Referensi Pejabat."}
                </p>
              </div>
              <div className="col-span-2 space-y-2">
                <p className="text-xs font-medium text-foreground">Daftar barang</p>
                {/* Tiap barang = KARTU berlabel, bukan sebaris kotak sempit:
                    uraian panjang & kode 10-16 digit butuh ruang baca saat
                    diketik — laporan lapangan "agar lega". */}
                {form.barang.map((b, i) => (
                  <div key={i} className="rounded-lg border border-border p-3 space-y-2 relative">
                    {form.barang.length > 1 && (
                      <button type="button" aria-label="Hapus baris barang"
                        onClick={() => setForm((f) => ({ ...f, barang: f.barang.filter((_, idx) => idx !== i) }))}
                        className="absolute right-2 top-2 h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 min-h-0 min-w-0">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                    <div>
                      <label className="text-[11px] font-medium text-muted-foreground block mb-1">Uraian barang</label>
                      <Input placeholder="cth. Laptop Dell Latitude 5440" value={b.uraian} className="pr-9"
                        onChange={(e) => setFormBarang(i, "uraian", e.target.value)}
                        data-testid={`pengadaan-barang-uraian-${i}`} />
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-[1fr_5rem_9rem] gap-2">
                      <div className="col-span-2 sm:col-span-1">
                        <label className="text-[11px] font-medium text-muted-foreground block mb-1">
                          Kode barang <span className="font-normal">(10 digit aset · 16 digit persediaan)</span>
                        </label>
                        <KodeBarangPicker value={b.kode}
                          onChange={(v) => setFormBarang(i, "kode", v)}
                          onPick={(k) => {
                            setFormBarang(i, "kode", k.kode);
                            if (!b.uraian) setFormBarang(i, "uraian", k.uraian);
                          }}
                          testid={`pengadaan-barang-kode-${i}`} />
                      </div>
                      <div>
                        <label className="text-[11px] font-medium text-muted-foreground block mb-1">Jumlah</label>
                        <Input type="number" min="1" placeholder="1" value={b.jumlah}
                          onChange={(e) => setFormBarang(i, "jumlah", e.target.value)} />
                      </div>
                      <div>
                        <label className="text-[11px] font-medium text-muted-foreground block mb-1">Harga satuan (Rp)</label>
                        <Input type="number" min="0" placeholder="0" value={b.harga_satuan}
                          onChange={(e) => setFormBarang(i, "harga_satuan", e.target.value)}
                          data-testid={`pengadaan-barang-harga-${i}`} />
                      </div>
                    </div>
                  </div>
                ))}
                <Button size="sm" variant="outline" className="h-8 text-xs min-h-0"
                  onClick={() => setForm((f) => ({ ...f, barang: [...f.barang, { ...BARANG_KOSONG }] }))}>
                  <Plus className="w-3.5 h-3.5 mr-1" />Tambah baris
                </Button>
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setForm(null)}>Batal</Button>
            <Button onClick={simpanPerolehan} disabled={form?.saving}
              className="bg-orange-600 hover:bg-orange-700 text-white" data-testid="pengadaan-simpan">
              {form?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <ShoppingCart className="w-4 h-4 mr-1.5" />}Catat
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog tautkan aset ── */}
      <Dialog open={!!taut} onOpenChange={(o) => { if (!o) setTaut(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Tautkan ke Aset Master</DialogTitle>
            <DialogDescription className="text-xs">
              {taut && `${taut.perolehan.barang?.[taut.index]?.uraian || ""} — cegah entri ganda dengan menautkan ke aset yang sudah dicatat.`}
            </DialogDescription>
          </DialogHeader>
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" />
            <Input className="pl-8" placeholder="Cari nama/kode aset (min. 2 huruf)"
              value={cari} onChange={(e) => setCari(e.target.value)} data-testid="pengadaan-cari-aset" />
          </div>
          {(mencari || hasilCari.length > 0) && cari.trim().length >= 2 && (
            <div className="max-h-52 overflow-y-auto rounded-lg border border-border">
              {mencari ? (
                <div className="flex justify-center py-3"><Loader2 className="w-4 h-4 animate-spin text-orange-600" /></div>
              ) : hasilCari.map((a) => (
                <button key={a.id} type="button" onClick={() => tautkan(a.id)} disabled={taut?.saving}
                  className="w-full px-2.5 py-1.5 text-left hover:bg-muted">
                  <span className="block text-xs font-semibold text-foreground truncate">{a.asset_name}</span>
                  <span className="block text-[10px] text-muted-foreground font-mono">{a.asset_code} · {a.NUP} · {a.condition}</span>
                </button>
              ))}
            </div>
          )}
          <DialogFooter className="gap-2">
            {taut?.perolehan?.barang?.[taut?.index]?.asset_id && (
              <Button variant="outline" className="text-red-500 hover:text-red-600" disabled={taut?.saving}
                onClick={() => tautkan("")}>
                Lepas Tautan
              </Button>
            )}
            <Button variant="outline" onClick={() => setTaut(null)}>Tutup</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog lampiran berkas perolehan ── */}
      <Dialog open={!!lamp} onOpenChange={(o) => { if (!o) setLamp(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Lampiran Berkas Perolehan</DialogTitle>
            <DialogDescription className="text-xs">
              {lamp && `BAST ${lamp.perolehan.nomor_bast} — ${lamp.perolehan.pihak}. Scan kontrak/BAPHP/BAST/kuitansi/SP2D (PDF/JPG/PNG, maks 10MB, 10 berkas).`}
            </DialogDescription>
          </DialogHeader>
          <input ref={lampInputRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) unggahLampiran(f); }} />
          <Button size="sm" variant="outline" className="h-8 text-xs min-h-0 self-start"
            disabled={lamp?.uploading || (lamp?.perolehan?.lampiran_berkas || []).length >= 10}
            onClick={() => lampInputRef.current?.click()} data-testid="pengadaan-lampiran-unggah">
            {lamp?.uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Upload className="w-3.5 h-3.5 mr-1.5" />}
            Unggah Berkas
          </Button>
          {(lamp?.perolehan?.lampiran_berkas || []).length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">Belum ada lampiran berkas.</p>
          ) : (
            <ul className="space-y-1.5">
              {(lamp?.perolehan?.lampiran_berkas || []).map((f) => (
                <li key={f.file_id} className="rounded-lg border border-border p-2 flex items-center gap-2">
                  <button type="button"
                    onClick={() => window.open(authMediaUrl(`${API}/pengadaan/${lamp.perolehan.id}/lampiran/${f.file_id}`), "_blank", "noopener")}
                    className="min-w-0 flex-1 text-left hover:underline">
                    <span className="block text-xs font-semibold text-foreground truncate">{f.filename}</span>
                    <span className="block text-[10px] text-muted-foreground">
                      {String(f.tanggal || "").slice(0, 10)} · oleh {f.oleh}
                    </span>
                  </button>
                  {isAdmin && (
                    <button type="button" aria-label="Hapus lampiran" onClick={() => hapusLampiran(f.file_id)}
                      className="h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 flex-shrink-0 min-h-0 min-w-0">
                      <Trash2 className="w-3 h-3" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Dialog catat semua barang BAST (aset + persediaan sekaligus) ── */}
      <Dialog open={!!draftAset} onOpenChange={(o) => { if (!o) setDraftAset(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Catat Semua Barang — BAST {draftAset?.perolehan?.nomor_bast}</DialogTitle>
            <DialogDescription className="text-xs">
              Barang <strong>golongan 1</strong> masuk <strong>Persediaan</strong> (stok + jurnal
              FIFO); <strong>golongan 2–8</strong> jadi <strong>aset draft ber-NUP</strong> di
              kegiatan terpilih — harga, tanggal, BAST, dan PPK terisi dari perolehan.
              Setelahnya <strong>LPB</strong> untuk sisi aset diterbitkan otomatis.
            </DialogDescription>
          </DialogHeader>
          {draftAset && (() => {
            // Hitungan ditampilkan MUKA supaya operator tahu apa yang akan
            // terjadi sebelum menekan, bukan sesudahnya lewat toast.
            const belum = (draftAset.perolehan.barang || [])
              .filter((b) => !b.asset_id && !b.psd_item_id);
            const psd = belum.filter((b) => String(b.kode || "").trim().startsWith("1"));
            const tanpaKode = belum.filter((b) => !String(b.kode || "").trim());
            const aset = belum.filter((b) => String(b.kode || "").trim()
              && !String(b.kode || "").trim().startsWith("1"));
            return (
              <div className="space-y-3">
                <ul className="text-xs text-foreground/90 space-y-1">
                  <li>• <strong>{aset.length}</strong> baris → aset draft ber-NUP</li>
                  <li>• <strong>{psd.length}</strong> baris → masuk stok persediaan</li>
                  {tanpaKode.length > 0 && (
                    <li className="text-amber-600 dark:text-amber-400">
                      • <strong>{tanpaKode.length}</strong> baris <strong>dilewati</strong> —
                      belum berkode barang (isi kodenya dulu)
                    </li>
                  )}
                </ul>
                {/* Kegiatan inventarisasi hanya relevan untuk sisi ASET. BAST
                    berisi persediaan saja tak perlu memilihnya sama sekali. */}
                {aset.length > 0 && (
                  <div>
                    <label className="text-xs font-medium text-foreground block mb-1" htmlFor="draft-aset-kegiatan">Kegiatan inventarisasi tujuan</label>
                    <select id="draft-aset-kegiatan" value={draftAset.activityId}
                      onChange={(e) => setDraftAset((d) => ({ ...d, activityId: e.target.value }))}
                      className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
                      data-testid="pengadaan-draft-kegiatan">
                      <option value="">— pilih kegiatan —</option>
                      {kegiatanList.map((k) => (
                        <option key={k.id} value={k.id}>
                          {k.nama_kegiatan || k.id}{k.tahun ? ` (${k.tahun})` : ""}
                        </option>
                      ))}
                    </select>
                    {kegiatanList.length === 0 && (
                      <p className="text-[10px] text-muted-foreground mt-1">Belum ada kegiatan inventarisasi — buat dulu di halaman kegiatan.</p>
                    )}
                  </div>
                )}
                <label className="flex items-start gap-2 text-xs cursor-pointer">
                  <input type="checkbox" className="mt-0.5 h-4 w-4"
                    checked={draftAset.bookingNomor !== false}
                    onChange={(e) => setDraftAset((d) => ({ ...d, bookingNomor: e.target.checked }))}
                    data-testid="pengadaan-catat-booking" />
                  <span>
                    Pesan <strong>nomor surat</strong> untuk LPB dari Registrasi Persuratan
                    <span className="block text-[10px] text-muted-foreground">
                      Nomor tercatat berstatus &quot;dibooking&quot; di buku agenda satker.
                    </span>
                  </span>
                </label>
              </div>
            );
          })()}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setDraftAset(null)}>Batal</Button>
            <Button onClick={catatSemua}
              disabled={draftAset?.saving
                || (draftAset?.butuhKegiatan && !draftAset?.activityId)}
              data-testid="pengadaan-draft-submit">
              {draftAset?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <PackagePlus className="w-4 h-4 mr-1.5" />}
              Catat Semua
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── LPB yang baru terbit: cetak & teken di tempat kerjanya ──
          Dipakai DUA jalur: hasil "Catat Semua Barang" (per BAST) dan hasil
          LPB gabungan (field `gabungan` terisi jumlah BAST-nya). */}
      <Dialog open={!!hasilCatat} onOpenChange={(o) => { if (!o) setHasilCatat(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>
              {hasilCatat?.gabungan ? "LPB Gabungan terbit" : "Laporan Penerimaan Barang terbit"}
            </DialogTitle>
            <DialogDescription className="text-xs">
              {hasilCatat?.gabungan
                ? `Satu laporan merangkum ${hasilCatat.gabungan} BAST PPK → KPB — aset maupun persediaan. `
                : `BAST ${hasilCatat?.nomorBast} sudah tercatat. LPB ini adalah bukti resmi penerimaannya — `}
              cetak dan tandatangani sekarang, atau buka
              lagi kapan pun lewat <strong>Persediaan → Riwayat LPB</strong>.
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-lg border border-border bg-muted/40 px-3 py-2.5">
            <p className="font-mono text-sm font-semibold text-foreground break-all"
               data-testid="pengadaan-lpb-nomor">
              {hasilCatat?.nomor}
            </p>
            <p className="text-[11px] text-muted-foreground mt-1">
              {hasilCatat?.gabungan
                ? `${hasilCatat.jumlahBarang} baris barang · ${hasilCatat.gabungan} BAST PPK → KPB`
                : [hasilCatat?.asetDibuat ? `${hasilCatat.asetDibuat} aset ber-NUP` : null,
                   hasilCatat?.persediaanMasuk ? `${hasilCatat.persediaanMasuk} barang persediaan` : null,
                  ].filter(Boolean).join(" · ") || "—"}
            </p>
          </div>
          <DialogFooter className="gap-2 sm:gap-2">
            <Button variant="outline" onClick={() => setHasilCatat(null)}>Nanti saja</Button>
            <Button variant="outline"
              onClick={() => downloadFileWithProgress(
                `${API}/persediaan/lpb/${hasilCatat.lpbId}/pdf`,
                `LPB_${String(hasilCatat.nomor).replace(/[/\s]/g, "_")}.pdf`,
                { label: "Laporan Penerimaan Barang" }).catch(() => {})}
              data-testid="pengadaan-lpb-unduh">
              <FileDown className="w-4 h-4 mr-1.5" />Unduh PDF
            </Button>
            <Button onClick={kirimTtdLpbBaru} disabled={hasilCatat?.mengirim}
              data-testid="pengadaan-lpb-kirim-ttd">
              {hasilCatat?.mengirim
                ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                : <PenLine className="w-4 h-4 mr-1.5" />}
              Kirim TTD
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Tautan TTD LPB yang baru dikirim ── */}
      <Dialog open={!!tautanTtd} onOpenChange={(o) => { if (!o) setTautanTtd(null); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Tautan tanda tangan — LPB {tautanTtd?.nomor}</DialogTitle>
            <DialogDescription className="text-xs">
              Satu tautan per penanda tangan. Bagikan lewat WhatsApp/email bila
              pengiriman otomatis tak aktif — tanpa tautan ini permintaan TTD
              tak sampai ke siapa pun.
            </DialogDescription>
          </DialogHeader>
          <ul className="divide-y divide-border/60">
            {(tautanTtd?.links || []).map((t, i) => (
              <li key={i} className="py-2">
                <p className="text-xs font-medium text-foreground">
                  {t.nama}
                  {t.email_terkirim && (
                    <span className="ml-1.5 text-[9px] font-semibold px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-700 dark:text-emerald-300">
                      email terkirim
                    </span>
                  )}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <code className="flex-1 min-w-0 truncate text-[10px] bg-muted rounded px-2 py-1">
                    {t.link}
                  </code>
                  <Button size="sm" variant="outline" className="h-7 text-[11px] flex-shrink-0"
                    onClick={() => {
                      navigator.clipboard?.writeText(t.link)
                        .then(() => toast.success("Tautan disalin"))
                        .catch(() => toast.error("Gagal menyalin — salin manual dari kotak di samping"));
                    }}>
                    Salin
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </DialogContent>
      </Dialog>

      {/* ── Dialog LPB gabungan: pilih BAST PPK→KPB yang dirangkum ── */}
      <Dialog open={!!lpbGab} onOpenChange={(o) => { if (!o) setLpbGab(null); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>LPB Gabungan</DialogTitle>
            <DialogDescription className="text-xs">
              Satu LPB untuk banyak BAST PPK → KPB — aset maupun persediaan.
            </DialogDescription>
          </DialogHeader>
          <Lipatan judul="Kenapa sebagian perolehan tak bisa dipilih?">
            Perolehan yang belum menerbitkan BAST PPK → KPB tidak dapat ikut.
            Terbitkan dulu lewat tombol BAST PPK→KPB di baris perolehan tersebut
            (di layar HP tombolnya berupa ikon saja).
          </Lipatan>
          {lpbGab && (() => {
            const semua = data?.items || [];
            const siap = semua.filter((p) => p.bast_ppk);
            const terpilih = Object.keys(lpbGab.pilih).filter((k) => lpbGab.pilih[k]);
            return (
              <div className="space-y-2">
                {siap.length > 1 && (
                  <button type="button"
                    onClick={() => setLpbGab((g) => ({
                      ...g,
                      pilih: terpilih.length === siap.length
                        ? {}
                        : Object.fromEntries(siap.map((p) => [p.id, true])),
                    }))}
                    className="text-[11px] font-semibold text-sky-600 dark:text-sky-400 hover:underline min-h-0"
                    data-testid="lpb-gabungan-pilih-semua">
                    {terpilih.length === siap.length ? "Kosongkan pilihan" : `Pilih semua (${siap.length})`}
                  </button>
                )}
                {semua.length === 0 && (
                  <p className="text-center text-xs text-muted-foreground py-4">
                    Belum ada perolehan tercatat.
                  </p>
                )}
                <ul className="divide-y divide-border/60 rounded-lg border border-border">
                  {semua.map((p) => {
                    const bisa = !!p.bast_ppk;
                    return (
                      <li key={p.id}>
                        <label className={`flex items-start gap-2 px-2.5 py-2 text-xs ${
                          bisa ? "cursor-pointer hover:bg-muted/50" : "opacity-55"}`}>
                          <input type="checkbox" className="mt-0.5 h-4 w-4 flex-shrink-0"
                            disabled={!bisa}
                            checked={!!lpbGab.pilih[p.id]}
                            onChange={(e) => setLpbGab((g) => ({
                              ...g, pilih: { ...g.pilih, [p.id]: e.target.checked } }))}
                            data-testid={`lpb-gabungan-pilih-${p.id}`} />
                          <span className="min-w-0 flex-1">
                            <span className="block font-semibold text-foreground truncate">
                              {p.pihak} <span className="font-normal text-muted-foreground">· {fmtRp(p.nilai)}</span>
                            </span>
                            <span className="block text-[11px] text-muted-foreground truncate">
                              BAST {p.nomor_bast} ({p.tanggal_bast})
                            </span>
                            {bisa ? (
                              <span className="block text-[11px] text-sky-600 dark:text-sky-400 truncate">
                                BAST PPK→KPB {p.bast_ppk.nomor || "(tanpa nomor)"}
                              </span>
                            ) : (
                              <span className="block text-[11px] text-amber-600 dark:text-amber-400">
                                BAST PPK→KPB belum terbit
                              </span>
                            )}
                          </span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })()}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setLpbGab(null)}>Batal</Button>
            <Button onClick={buatLpbGabungan}
              disabled={lpbGab?.saving
                || !Object.values(lpbGab?.pilih || {}).some(Boolean)}
              data-testid="lpb-gabungan-submit">
              {lpbGab?.saving
                ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                : <Boxes className="w-4 h-4 mr-1.5" />}
              Terbitkan LPB Gabungan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}
