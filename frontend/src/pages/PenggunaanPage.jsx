import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Search, Loader2, UserCheck, ChevronLeft, ChevronRight,
  BadgeCheck, FileWarning, FileText, Plus, X, Trash2, ScrollText,
  Paperclip, Upload, FileDown, ArrowLeftRight, IdCard,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { useBackGuard } from "@/hooks/useBackGuard";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import Lipatan from "@/components/ui/Lipatan";
import { useTransitionDialog } from "@/components/ui/TransitionDialog";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import { authMediaUrl } from "@/lib/mediaUrl";
import BookingNomorButton from "@/components/persuratan/BookingNomorButton";
import PerkiraanNomor from "@/components/persuratan/PerkiraanNomor";
import KartuTapDialog from "@/components/pegawai/KartuTapDialog";
import { bagikanWa, bagikanEmail, hasilTtd } from "@/lib/pesanTtd";

import { KEPALA_HALAMAN, BARIS_KEPALA, BLOK_JUDUL, JUDUL_KEPALA,
  SUBJUDUL_KEPALA, TOMBOL_KEPALA, IKON_KEPALA,
} from "@/lib/kelasKepala";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Penggunaan — Fase 3 tahap awal: rekap aset per PEMEGANG lintas kegiatan,
 * dibangun dari data pengguna + NIP + BAST yang sudah dicatat modul
 * inventarisasi — plus daftar pantau BMN IDLE (PMK 120/2024): kandidat
 * otomatis dari status Nonaktif / tanpa pengguna, tiket klarifikasi →
 * digunakan kembali / usul serah → diserahkan ke Pengelola — serta
 * register PSP (SK + BAST PDF) dan tiket proses alih status/alih fungsi
 * (PMK 40/2024).
 */
const WARNA_STATUS_PROSES = {
  draf: "bg-muted text-foreground/70",
  diajukan: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  disetujui: "bg-violet-500/15 text-violet-600 dark:text-violet-400",
  ditolak: "bg-red-500/15 text-red-600 dark:text-red-400",
  bast_selesai: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
  dihapus_dibukukan: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  berjalan: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  berakhir: "bg-muted text-foreground/70",
};

const WARNA_PENGAJUAN_PSP = {
  draf: "bg-muted text-foreground/70",
  diajukan: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  ditetapkan: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  ditolak: "bg-red-500/15 text-red-600 dark:text-red-400",
};

export default function PenggunaanPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalLengkap, setTotalLengkap] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  // Dialog daftar aset: {pemegang, rows, loading}
  const [detail, setDetail] = useState(null);
  // Data BMN idle: {kandidat, tiket, ringkasan, label_status, catatan}
  const [idle, setIdle] = useState(null);
  // Dialog transisi idle: {tiket, ke, fields{}, saving}
  const [trxIdle, setTrxIdle] = useState(null);
  // Data register PSP: {items, ringkasan, label_jenis, catatan}
  const [psp, setPsp] = useState(null);
  // Dialog catat SK PSP: {data, aset: [], saving}
  const [formPsp, setFormPsp] = useState(null);
  const [cariPsp, setCariPsp] = useState("");
  const [hasilCariPsp, setHasilCariPsp] = useState([]);
  const cariPspTimer = useRef(null);
  // Dialog lampiran SK PSP: {sk, uploading}
  const [lampPsp, setLampPsp] = useState(null);
  // Tiket proses alih status/penggunaan sementara: data GET + dialog baru
  const [proses, setProses] = useState(null);
  const [formProses, setFormProses] = useState(null);
  const lampPspInputRef = useRef(null);
  const searchTimer = useRef(null);
  // Dialog BAST serah terima pengguna: {form, aset:Set(id), saving}
  const [formBast, setFormBast] = useState(null);
  const [jenisBast, setJenisBast] = useState([]);
  // Dialog riwayat BAST pemegang: {items, label_jenis, loading}
  const [riwayatBast, setRiwayatBast] = useState(null);
  const buktiRef = useRef(null);
  const [buktiUntuk, setBuktiUntuk] = useState(null); // id BAST tujuan unggah bukti
  // Foto dokumentasi serah terima (lampiran BAST). Dua mode: PER BARANG
  // (pilih asetnya) atau SATU foto untuk seluruh barang dalam BAST itu.
  const fotoStRef = useRef(null);
  const [fotoSt, setFotoSt] = useState(null);   // {bast, mode:'per'|'semua', asset_id}
  const [fotoStSibuk, setFotoStSibuk] = useState(false);
  // Hasil "Kirim ke TTD" — bentuknya dari `hasilTtd` (lib/pesanTtd), termasuk
  // `ringkas` yang mengisi keterangan pesan WA/email.
  const [ttdHasil, setTtdHasil] = useState(null);
  const [kirimTtdId, setKirimTtdId] = useState(null); // id BAST yang sedang dikirim ke TTD
  // Referensi pejabat yang layak jadi "yang menyerahkan" BAST (peran
  // pengelolaan BMN: KPB / Petugas Penatausahaan / Pengelola BMN Satker),
  // aktif hari ini — dari registry pejabat + metadata peran_penyerah_bast.
  const [pejabatPenyerah, setPejabatPenyerah] = useState([]);
  // Master Pegawai utk autocomplete penerima BAST (dimuat sekali saat dialog
  // BAST pertama dibuka) — identitas satu sumber, NIP tak diketik ulang.
  const [pegawaiList, setPegawaiList] = useState(null);
  // Tap kartu e-KTP utk mengisi pihak BAST — null | "pihak_kedua" | "pihak_pertama"
  const [kartuTapUntuk, setKartuTapUntuk] = useState(null);

  useBackGuard(useCallback(() => onBack?.(), [onBack]));
  const { confirm, confirmDialog } = useConfirm();
  const { minta, transitionDialog } = useTransitionDialog();

  const load = useCallback(async (p = 1, s = search) => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/penggunaan/pemegang`, {
        params: { search: s, page: p, page_size: 50 },
      });
      setItems(r.data?.items || []);
      setTotal(r.data?.total_pemegang || 0);
      setTotalLengkap(r.data?.total_lengkap || 0);
      setTotalPages(r.data?.total_pages || 1);
      setPage(p);
    } catch {
      toast.error("Gagal memuat daftar pemegang");
    } finally {
      setLoading(false);
    }
  }, [search]);

  const loadIdle = useCallback(() => {
    axios.get(`${API}/penggunaan/idle`)
      .then((r) => setIdle(r.data))
      .catch(() => toast.error("Gagal memuat daftar BMN idle"));
  }, []);

  const loadPsp = useCallback(() => {
    axios.get(`${API}/penggunaan/psp`)
      .then((r) => setPsp(r.data))
      .catch(() => toast.error("Gagal memuat register PSP"));
  }, []);

  // Referensi Master Satker — saran pihak asal/tujuan proses penggunaan (W7)
  const [satkerList, setSatkerList] = useState([]);
  useEffect(() => {
    axios.get(`${API}/satker`)
      .then((r) => setSatkerList(r.data?.items || []))
      .catch(() => {});
  }, []);

  // PSP resmi menurut data impor SIMAN V2 (W5) — kandidat pencatatan 1-klik
  const [pspSiman, setPspSiman] = useState(null);
  const loadPspSiman = useCallback(() => {
    axios.get(`${API}/penggunaan/psp-siman`)
      .then((r) => setPspSiman(r.data))
      .catch(() => {});
  }, []);
  useEffect(() => { loadPspSiman(); }, [loadPspSiman]);

  // Prefill form Catat SK dari satu kelompok PSP SIMAN — tanpa ketik ulang
  const catatDariSiman = (k) => {
    const aset = (k.aset_belum.length ? k.aset_belum : k.aset).map((a) => ({
      id: a.asset_id, asset_code: a.asset_code, NUP: a.NUP,
      asset_name: a.asset_name,
    }));
    setCariPsp(""); setHasilCariPsp([]);
    setFormPsp({
      data: {
        nomor_sk: k.no_psp,
        tanggal_sk: (k.tanggal_psp || "").slice(0, 10) || new Date().toISOString().slice(0, 10),
        jenis: "psp", penetap: "",
        keterangan: `Dicatat dari data PSP impor SIMAN V2${k.status_penggunaan ? ` (${k.status_penggunaan})` : ""}`,
        sebagai_draf: false,
      },
      aset, saving: false,
    });
  };

  useEffect(() => { load(1, ""); loadIdle(); loadPsp(); loadProses(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    axios.get(`${API}/bast/referensi`).then((r) => setJenisBast(r.data?.jenis || [])).catch(() => {});
    // Kandidat "yang menyerahkan": pejabat berperan penyerah BAST (peran
    // pengelolaan BMN pusat) yang masih berlaku hari ini.
    Promise.all([
      axios.get(`${API}/pejabat/referensi`),
      axios.get(`${API}/pejabat`),
    ]).then(([ref, list]) => {
      const boleh = new Set(ref.data?.peran_penyerah_bast || []);
      const now = new Date();
      const hariIni = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
      setPejabatPenyerah((list.data?.items || []).filter((p) => {
        if (!(p.peran || []).some((x) => boleh.has(x))) return false;
        if (p.aktif === false) return false;
        const mulai = String(p.berlaku_mulai || "").slice(0, 10);
        const selesai = String(p.berlaku_selesai || "").slice(0, 10);
        if (mulai && hariIni < mulai) return false;
        if (selesai && hariIni > selesai) return false;
        return true;
      }));
    }).catch(() => {});
  }, []);

  const bukaBast = () => {
    const p = detail?.pemegang || {};
    if (pegawaiList === null) {
      axios.get(`${API}/pegawai`)
        .then((r) => setPegawaiList(r.data?.items || []))
        .catch(() => setPegawaiList([]));
    }
    // Bawaan saklar nilai = KEBIJAKAN satker, supaya yang terlihat di layar
    // sama dengan yang nanti tercetak (form tak perlu menebak).
    axios.get(`${API}/kebijakan-dokumen`)
      .then((r) => setFormBast((f) => (f
        ? { ...f, tampilkan_nilai: r.data?.tampilkan_nilai !== false } : f)))
      .catch(() => {});
    setFormBast({
      jenis: "penggunaan_melekat", nomor: "", tanggal: "",
      jangka_dari: "", jangka_sampai: "", sertakan_foto: false, keterangan: "",
      pihak_kedua: { nama: p.nama || "", nip: p.nip || "", jabatan: p.jabatan || p.pegawai_master_jabatan || "", alamat: "" },
      // Utk mutasi/handover: PIHAK KESATU = pemegang lama (prefill dari
      // pemegang yang sedang dibuka); PIHAK KEDUA = pemegang baru.
      pihak_pertama: { nama: p.nama || "", nip: p.nip || "", jabatan: p.jabatan || "", alamat: "" },
      // Utk non-mutasi: "yang menyerahkan" dipilih dari referensi pejabat
      // (kosong = otomatis memakai KPB dari pengaturan/registry).
      penyerah: { id: "", nama: "", nip: "", jabatan: "" },
      // Alamat PIHAK KESATU non-mutasi — diisi manual sesuai lokasi pihaknya;
      // kosong = alamat kantor satker dari pengaturan kop (default server).
      alamat_pihak1: "",
      pj_tambahan: [],
      // Khusus "pengembalian_almarhum": dasar BA (identitas almarhum) + saksi.
      // Prefill dari pemegang yang sedang dibuka — biasanya memang almarhumnya.
      almarhum: { nama: p.nama || "", nip: p.nip || "",
                  tanggal_meninggal: "", nomor_akta_kematian: "" },
      saksi: [{ nama: "", jabatan: "", nip: "" },
              { nama: "", jabatan: "", nip: "" }],
      terapkan_ke_aset: true,
      booking_otomatis: false,
      // Kolom Nilai Perolehan pada PDF — bawaan mengikuti kebijakan satker
      // (dimutakhirkan oleh permintaan /kebijakan-dokumen di atas).
      tampilkan_nilai: true,
      aset: new Set((detail?.rows || []).map((a) => a.id)),
      saving: false,
      // Idempotency-Key sekali per pembukaan form: klik ganda / retry
      // jaringan tidak menggandakan BAST + nomor booking otomatis.
      idem: crypto.randomUUID(),
    });
  };

  const gantiJenisBast = (jenis) => setFormBast((f) => {
    const p = detail?.pemegang || {};
    if (jenis === "mutasi_pengguna") {
      // Handover: pemegang lama jadi PIHAK KESATU, penerima baru dikosongkan.
      return { ...f, jenis,
        pihak_pertama: { nama: p.nama || "", nip: p.nip || "", jabatan: p.jabatan || "", alamat: "" },
        pihak_kedua: { nama: "", nip: "", jabatan: "", alamat: "" } };
    }
    return { ...f, jenis,
      pihak_kedua: { nama: p.nama || "", nip: p.nip || "", jabatan: p.jabatan || p.pegawai_master_jabatan || "", alamat: "" } };
  });

  const pilihPenyerah = (id) => setFormBast((f) => {
    const pj = pejabatPenyerah.find((p) => p.id === id);
    // Bila penyerah BUKAN KPB → bertindak "a.n. KPB" (KPB ikut "Mengetahui").
    const anKpb = pj ? !(pj.peran || []).includes("kuasa_pengguna_barang") : false;
    return { ...f, penyerah: pj
      ? { id, nama: pj.nama || "", nip: pj.nip || "", jabatan: pj.jabatan || "", atas_nama_kpb: anKpb }
      : { id: "", nama: "", nip: "", jabatan: "", atas_nama_kpb: false } };
  });

  const kirimBast = async () => {
    const f = formBast;
    if (!f) return;
    if (f.aset.size === 0) { toast.error("Pilih minimal satu aset"); return; }
    if (!f.pihak_kedua.nama.trim()) { toast.error("Nama penerima wajib diisi"); return; }
    if (f.revisi && !f.revisi.alasan.trim()) {
      toast.error("Alasan revisi wajib diisi"); return;
    }
    setFormBast((x) => ({ ...x, saving: true }));
    try {
      const r = await axios.post(`${API}/bast`, {
        jenis: f.jenis, asset_ids: [...f.aset], pihak_kedua: f.pihak_kedua,
        // Mutasi: PIHAK KESATU = pemegang lama. Non-mutasi: pejabat penyerah
        // terpilih (kosong = biar backend memakai KPB dari pengaturan).
        pihak_pertama: f.jenis === "mutasi_pengguna"
          ? f.pihak_pertama
          : (f.penyerah?.nama?.trim()
            ? { nama: f.penyerah.nama, nip: f.penyerah.nip, jabatan: f.penyerah.jabatan,
                alamat: (f.alamat_pihak1 || "").trim() }
            // Tanpa penyerah terpilih identitas tetap KPB otomatis (server),
            // tapi alamat manual yang diketik harus tetap terbawa.
            : ((f.alamat_pihak1 || "").trim()
              ? { nama: "", nip: "", jabatan: "", alamat: f.alamat_pihak1.trim() }
              : null)),
        penyerah_atas_nama_kpb: f.jenis !== "mutasi_pengguna" && !!f.penyerah?.atas_nama_kpb,
        nomor: f.nomor, tanggal: f.tanggal, jangka_dari: f.jangka_dari,
        jangka_sampai: f.jangka_sampai,
        penanggung_jawab_tambahan: f.pj_tambahan.filter((x) => x.nama.trim()),
        ...(f.jenis === "pengembalian_almarhum"
          ? { almarhum: f.almarhum,
              saksi: (f.saksi || []).filter((x) => (x.nama || "").trim()) }
          : {}),
        sertakan_foto: f.sertakan_foto, keterangan: f.keterangan,
        tampilkan_nilai: !!f.tampilkan_nilai,
        // pengembalian_almarhum WAJIB ikut di sini — tanpanya checkbox
        // "kosongkan pengguna" dipaksa false dan aset tetap atas nama almarhum
        // (alur pengembalian almarhum gagal senyap di langkah terakhirnya).
        terapkan_ke_aset: ["mutasi_pengguna", "pengembalian",
                           "pengembalian_almarhum"].includes(f.jenis)
          ? f.terapkan_ke_aset : false,
        booking_otomatis: f.booking_otomatis,
        ...(f.revisi ? { revisi_dari: f.revisi.dari, revisi_mode: f.revisi.mode,
                         revisi_alasan: f.revisi.alasan } : {}),
      }, { headers: { "Idempotency-Key": f.idem } });
      if (["mutasi_pengguna", "pengembalian",
           "pengembalian_almarhum"].includes(f.jenis) && f.terapkan_ke_aset) {
        load(page, search); // pemegang berubah — segarkan rekap
      } else if (detail?.pemegang) {
        openDetail(detail.pemegang); // badge bast_terakhir baru langsung tampak
      }
      toast.success("BAST tersimpan — mengunduh PDF…");
      if (r.data?.peringatan_pegawai) {
        toast.warning(r.data.peringatan_pegawai, { duration: 8000 });
      }
      setFormBast(null);
      downloadFileWithProgress(`${API}/bast/${r.data.id}/pdf`,
        `BAST_${(f.pihak_kedua.nama || "pengguna").replace(/\s/g, "_")}.pdf`,
        { label: "BAST Serah Terima" }).catch(() => {});
    } catch (e) {
      toast.error(typeof e?.response?.data?.detail === "string"
        ? e.response.data.detail : "Gagal membuat BAST");
      // Kunci idempotensi diganti: kegagalan tervalidasi (400) menyisakan
      // reservasi "pending" ±30 detik di server — submit ulang setelah user
      // membetulkan isian adalah PENGAJUAN BARU, bukan retry yang sama.
      setFormBast((x) => (x
        ? { ...x, saving: false, idem: crypto.randomUUID() } : x));
    }
  };

  // REVISI BAST (SURAT-3C): BAST sah tidak diedit — revisi = BAST BARU yang
  // menggantikan yang lama. Form dibuka terprefill dari BAST lama; pengguna
  // membetulkan isinya, memilih mode (mengubah/mencabut) dan wajib beralasan.
  const bukaRevisiBast = (b) => {
    setRiwayatBast(null);
    axios.get(`${API}/kebijakan-dokumen`)
      .then((r) => setFormBast((f) => (f
        ? { ...f, tampilkan_nilai: r.data?.tampilkan_nilai !== false } : f)))
      .catch(() => {});
    setFormBast({
      jenis: b.jenis, nomor: "", tanggal: "",
      jangka_dari: b.jangka_dari || "", jangka_sampai: b.jangka_sampai || "",
      sertakan_foto: !!b.sertakan_foto, keterangan: b.keterangan || "",
      pihak_kedua: { ...(b.pihak_kedua || { nama: "", nip: "", jabatan: "", alamat: "" }) },
      pihak_pertama: { ...(b.pihak_pertama || { nama: "", nip: "", jabatan: "", alamat: "" }) },
      penyerah: b.jenis === "mutasi_pengguna"
        ? { id: "", nama: "", nip: "", jabatan: "" }
        : { id: "", nama: b.pihak_pertama?.nama || "", nip: b.pihak_pertama?.nip || "",
            jabatan: b.pihak_pertama?.jabatan || "",
            atas_nama_kpb: !!b.penyerah_atas_nama_kpb },
      alamat_pihak1: b.pihak_pertama?.alamat || "",
      pj_tambahan: (b.penanggung_jawab_tambahan || []).map((x) => ({ ...x })),
      almarhum: { ...(b.almarhum || { nama: "", nip: "", tanggal_meninggal: "", nomor_akta_kematian: "" }) },
      saksi: (b.saksi?.length ? b.saksi.map((x) => ({ ...x }))
        : [{ nama: "", jabatan: "", nip: "" }, { nama: "", jabatan: "", nip: "" }]),
      // Revisi = koreksi DOKUMEN; efek data sudah diterapkan BAST aslinya.
      terapkan_ke_aset: false,
      booking_otomatis: true,   // nomor BARU untuk dokumen pengganti
      tampilkan_nilai: b.tampilkan_nilai !== false,
      aset: new Set(b.asset_ids || []),
      revisi: { dari: b.id, dari_nomor: b.nomor || "(tanpa nomor)",
                mode: "mengubah", alasan: "" },
      saving: false,
      idem: crypto.randomUUID(),
    });
  };

  const bukaRiwayatBast = async () => {
    const p = detail?.pemegang || {};
    setRiwayatBast({ items: [], loading: true });
    try {
      // Kunci pada NIP bila ada — nama mirip tak tercampur; tanpa NIP
      // fallback ke pencarian nama.
      const params = p.nip ? { nip: p.nip, page_size: 50 }
        : { q: p.nama || "", page_size: 50 };
      const r = await axios.get(`${API}/bast`, { params });
      setRiwayatBast({ items: r.data?.items || [], label_jenis: r.data?.label_jenis || {}, loading: false });
    } catch {
      toast.error("Gagal memuat riwayat BAST");
      setRiwayatBast(null);
    }
  };

  const unggahBukti = async (file) => {
    if (!file || !buktiUntuk) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await axios.post(`${API}/bast/${buktiUntuk}/bukti`, fd,
        { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(r.data?.nomor_agenda_disahkan
        ? "Bukti tersimpan — nomor agenda di Persuratan otomatis DISAHKAN"
        : "Bukti tanda tangan tersimpan");
      bukaRiwayatBast();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengunggah bukti");
    } finally {
      setBuktiUntuk(null);
      if (buktiRef.current) buktiRef.current.value = "";
    }
  };

  const unggahFotoSerahTerima = async (file) => {
    if (!file || !fotoSt?.bast?.id) return;
    const perBarang = fotoSt.mode === "per";
    if (perBarang && !fotoSt.asset_id) {
      toast.error("Pilih dulu barangnya");
      return;
    }
    const fd = new FormData();
    fd.append("file", file);
    if (perBarang) fd.append("asset_id", fotoSt.asset_id);
    else fd.append("berlaku_semua", "true");
    setFotoStSibuk(true);
    try {
      await axios.post(`${API}/bast/${fotoSt.bast.id}/foto-serah-terima`, fd,
        { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(perBarang
        ? "Foto serah terima barang tersimpan"
        : "Foto perwakilan tersimpan — berlaku untuk seluruh barang");
      bukaRiwayatBast();
      setFotoSt(null);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengunggah foto");
    } finally {
      setFotoStSibuk(false);
      if (fotoStRef.current) fotoStRef.current.value = "";
    }
  };

  const hapusFotoSerahTerima = async (assetId, berlakuSemua) => {
    if (!fotoSt?.bast?.id) return;
    try {
      await axios.delete(`${API}/bast/${fotoSt.bast.id}/foto-serah-terima`,
        { params: berlakuSemua ? { berlaku_semua: true }
                               : { asset_id: assetId } });
      toast.success("Foto serah terima dihapus");
      bukaRiwayatBast();
      setFotoSt(null);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus foto");
    }
  };

  // Kirim BAST ke TTD elektronik — penaut TERSTRUKTUR (doc_ref = id BAST) +
  // penanda tangan otomatis dari pihak BAST. Server balas link per penanda
  // tangan untuk dibagikan (Salin/WhatsApp). Alternatif dari unggah scan bukti.
  const kirimKeTtd = async (b) => {
    setKirimTtdId(b.id);
    try {
      const r = await axios.post(`${API}/bast/${b.id}/kirim-ttd`);
      // Pakai `hasilTtd` — menyusun objek ini dengan tangan pernah membuang
      // `ringkas`, sehingga pesan WA dari Riwayat BAST hanya berisi perihal +
      // tautan sementara pesan dari halaman TTD Elektronik lengkap.
      setTtdHasil(hasilTtd(r.data, "BAST"));
      toast.success("Permintaan TTD elektronik dibuat — bagikan tautan ke penanda tangan");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuat permintaan TTD");
    } finally {
      setKirimTtdId(null);
    }
  };

  // Pencarian aset (debounce) untuk dialog catat SK PSP
  useEffect(() => {
    if ((!formPsp && !formProses) || cariPsp.trim().length < 2) { setHasilCariPsp([]); return undefined; }
    clearTimeout(cariPspTimer.current);
    cariPspTimer.current = setTimeout(async () => {
      try {
        const r = await axios.get(`${API}/assets`, { params: { search: cariPsp.trim(), page_size: 8 } });
        setHasilCariPsp(r.data?.items || []);
      } catch { setHasilCariPsp([]); }
    }, 300);
    return () => clearTimeout(cariPspTimer.current);
  }, [cariPsp, formPsp, formProses]);

  const onSearchChange = (v) => {
    setSearch(v);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => load(1, v), 350);
  };
  useEffect(() => () => { if (searchTimer.current) clearTimeout(searchTimer.current); }, []);

  const openDetail = async (p) => {
    setDetail({ pemegang: p, rows: [], loading: true });
    try {
      const r = await axios.get(`${API}/penggunaan/pemegang/aset`, {
        params: { nama: p.nama, nip: p.nip || "" },
      });
      setDetail({ pemegang: p, rows: r.data?.items || [], loading: false });
    } catch {
      toast.error("Gagal memuat aset pemegang");
      setDetail(null);
    }
  };

  const loadProses = useCallback(() => {
    axios.get(`${API}/penggunaan/proses`)
      .then((r) => setProses(r.data))
      .catch(() => {});
  }, []);

  const simpanProses = async () => {
    if (!formProses) return;
    if (formProses.aset.length === 0) { toast.error("Tambahkan minimal satu aset"); return; }
    setFormProses((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/penggunaan/proses`, {
        ...formProses.data, asset_ids: formProses.aset.map((a) => a.id),
      });
      toast.success("Tiket proses dibuka (draf)");
      setFormProses(null);
      loadProses();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuka tiket proses");
      setFormProses((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const pindahStatusProses = async (t, ke) => {
    const label = proses?.label_status?.[ke] || ke;
    const perluDok = ["disetujui", "ditolak", "bast_selesai", "dihapus_dibukukan", "berjalan"].includes(ke);
    const v = await minta({
      judul: `Pindah status → ${label}`,
      deskripsi: perluDok ? "Isi dokumen dasar transisi (opsional)." : undefined,
      fields: [
        ...(perluDok ? [
          { key: "nomor", label: "Nomor dokumen (persetujuan/BAST/SK/perjanjian)", type: "text" },
          { key: "tanggal", label: "Tanggal dokumen", type: "date" },
        ] : []),
        { key: "catatan", label: "Catatan", type: "textarea" },
      ],
      confirmLabel: label,
    });
    if (v === null) return;
    try {
      await axios.post(`${API}/penggunaan/proses/${t.id}/status`, {
        status: ke, catatan: v.catatan || "", nomor_dokumen: v.nomor || "", tanggal_dokumen: v.tanggal || "",
      });
      toast.success(`Status tiket: ${label}`);
      loadProses();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengubah status tiket");
    }
  };

  const hapusProses = async (t) => {
    const ok = await confirm({
      title: "Hapus tiket proses?",
      description: `${proses?.label_jenis?.[t.jenis_proses] || t.jenis_proses} — ${t.pihak_asal} → ${t.pihak_tujuan}.`,
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/penggunaan/proses/${t.id}`);
      toast.success("Tiket dihapus");
      loadProses();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus tiket");
    }
  };

  const simpanPsp = async () => {
    if (!formPsp) return;
    if (formPsp.aset.length === 0) { toast.error("Tambahkan minimal satu aset"); return; }
    setFormPsp((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/penggunaan/psp`, {
        ...formPsp.data, asset_ids: formPsp.aset.map((a) => a.id),
      });
      toast.success("SK penetapan tercatat");
      setFormPsp(null);
      loadPsp();
      loadPspSiman();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat SK");
      setFormPsp((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const hapusPsp = async (sk) => {
    const ok = await confirm({
      title: "Hapus catatan SK dari register?",
      description: `SK ${sk.nomor_sk || "(tanpa nomor)"} — lampirannya ikut terhapus.`,
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/penggunaan/psp/${sk.id}`);
      toast.success("Catatan SK dihapus");
      loadPsp();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus SK");
    }
  };

  const pindahStatusPsp = async (sk, ke) => {
    const payload = { status: ke, nomor_sk: "", tanggal_sk: "", catatan: "" };
    if (ke === "ditetapkan") {
      const v = await minta({
        judul: "Penetapan SK Penggunaan",
        fields: [
          { key: "nomor", label: "Nomor SK penetapan", type: "text", wajib: true, default: sk.nomor_sk || "" },
          { key: "tanggal", label: "Tanggal SK", type: "date", wajib: true, default: sk.tanggal_sk || new Date().toISOString().slice(0, 10) },
        ],
        confirmLabel: "Tetapkan",
      });
      if (v === null) return;
      payload.nomor_sk = v.nomor; payload.tanggal_sk = v.tanggal;
    }
    if (ke === "ditolak" || ke === "draf") {
      const v = await minta({
        judul: ke === "ditolak" ? "Catatan penolakan" : "Catatan pengembalian",
        fields: [{ key: "catatan", label: "Catatan", type: "textarea", wajib: true }],
        confirmLabel: ke === "ditolak" ? "Tolak" : "Kembalikan",
      });
      if (v === null) return;
      payload.catatan = v.catatan;
    }
    try {
      await axios.post(`${API}/penggunaan/psp/${sk.id}/status`, payload);
      toast.success("Status usulan diperbarui");
      loadPsp();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memindah status");
    }
  };

  const unggahLampiranPsp = async (fileObj) => {
    if (!lampPsp || !fileObj) return;
    setLampPsp((l) => ({ ...l, uploading: true }));
    try {
      const fd = new FormData();
      fd.append("file", fileObj);
      const res = await axios.post(`${API}/penggunaan/psp/${lampPsp.sk.id}/lampiran`, fd);
      toast.success("Lampiran terunggah");
      setLampPsp((l) => (l ? { ...l, uploading: false,
        sk: { ...l.sk, lampiran: res.data?.lampiran || [] } } : l));
      loadPsp();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengunggah lampiran");
      setLampPsp((l) => (l ? { ...l, uploading: false } : l));
    }
  };

  const hapusLampiranPsp = async (fileId) => {
    if (!lampPsp) return;
    try {
      await axios.delete(`${API}/penggunaan/psp/${lampPsp.sk.id}/lampiran/${fileId}`);
      toast.success("Lampiran dihapus");
      setLampPsp((l) => (l ? { ...l,
        sk: { ...l.sk,
          lampiran: (l.sk.lampiran || []).filter((x) => x.file_id !== fileId) } } : l));
      loadPsp();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus lampiran");
    }
  };

  const bukaKlarifikasi = async (k) => {
    try {
      await axios.post(`${API}/penggunaan/idle`, { asset_id: k.asset_id });
      toast.success("Tiket klarifikasi dibuka");
      loadIdle();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuka tiket");
    }
  };

  const kirimTransisiIdle = async (tiket, ke, fields = {}) => {
    try {
      await axios.post(`${API}/penggunaan/idle/${tiket.id}/status`, { status: ke, ...fields });
      toast.success(`Status: ${idle?.label_status?.[ke] || ke}`);
      setTrxIdle(null);
      loadIdle();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengubah status");
      setTrxIdle((t) => (t ? { ...t, saving: false } : t));
    }
  };

  return (
    <div className="min-h-screen bg-background" data-testid="penggunaan-page">
      {/* ── Header ── */}
      <header className={KEPALA_HALAMAN}>
        <div className={`max-w-5xl mx-auto ${BARIS_KEPALA}`}>
          <button
            type="button"
            onClick={onBack}
            aria-label="Kembali ke Beranda Modul"
            className={TOMBOL_KEPALA}
            data-testid="penggunaan-back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className={`bg-sky-600 ${IKON_KEPALA}`}>
            <UserCheck className="w-4 h-4 text-white" />
          </span>
          <div className={BLOK_JUDUL}>
            <h1 className={JUDUL_KEPALA}>Aset per Pemegang</h1>
            <p className={SUBJUDUL_KEPALA}>
              {total} pemegang · {totalLengkap} berkas lengkap (NIP + semua BAST) · lintas kegiatan
            </p>
          </div>
          <BookingNomorButton modul="penggunaan" jenisNaskah="Berita Acara" referensi="BAST PSP" />
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {/* Ringkasan statistik modul — kesehatan Penggunaan sekilas tanpa scroll */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2" data-testid="penggunaan-statistik">
          <div className="bg-card rounded-xl border border-border p-2.5 flex items-center gap-2">
            <UserCheck className="w-4 h-4 text-sky-600 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-sm font-bold text-foreground leading-tight tabular-nums">{total}</p>
              <p className="text-[10px] text-muted-foreground truncate">Total pemegang</p>
            </div>
          </div>
          <div className="bg-card rounded-xl border border-border p-2.5 flex items-center gap-2">
            <BadgeCheck className="w-4 h-4 text-emerald-500 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-sm font-bold text-foreground leading-tight tabular-nums">{totalLengkap}</p>
              <p className="text-[10px] text-muted-foreground truncate">Berkas lengkap</p>
            </div>
          </div>
          <div className="bg-card rounded-xl border border-border p-2.5 flex items-center gap-2">
            <FileWarning className="w-4 h-4 text-amber-500 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-sm font-bold text-foreground leading-tight tabular-nums">{idle?.ringkasan?.kandidat || 0}</p>
              <p className="text-[10px] text-muted-foreground truncate">Kandidat idle</p>
            </div>
          </div>
          <div className="bg-card rounded-xl border border-border p-2.5 flex items-center gap-2">
            <ScrollText className="w-4 h-4 text-sky-500 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-sm font-bold text-foreground leading-tight tabular-nums">
                {psp?.ringkasan?.aset_tercakup || 0}<span className="font-normal text-muted-foreground">/{psp?.ringkasan?.total_aset || 0}</span>
              </p>
              <p className="text-[10px] text-muted-foreground truncate">Aset ter-PSP</p>
            </div>
          </div>
        </div>

        <div className="relative">
          <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
          <Input
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Cari nama, NIP, atau jabatan…"
            className="pl-9 h-10"
            data-testid="penggunaan-search"
          />
        </div>

        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
          <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
            <UserCheck className="w-4 h-4 text-sky-600" />
            <p className="text-xs font-bold text-foreground flex-1">Daftar Pemegang Aset</p>
            <span className="px-2 py-0.5 rounded-full bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[10px] font-semibold">
              {total} pemegang
            </span>
          </div>
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-7 h-7 animate-spin text-sky-600" />
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-16 px-4">
              <UserCheck className="w-10 h-10 text-muted-foreground/40 mx-auto mb-3" />
              <p className="text-sm font-medium text-foreground">Belum ada pemegang tercatat</p>
              <p className="text-xs text-muted-foreground mt-1">
                Isi kolom Pengguna (+NIP & BAST) pada aset di modul Inventarisasi — rekap ini terbangun otomatis.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-border/60">
              {items.map((p) => (
                <li key={`${p.nama}|${p.nip}`}>
                  <button
                    type="button"
                    onClick={() => openDetail(p)}
                    className="w-full text-left p-3 flex items-center gap-3 hover:bg-muted/40"
                    data-testid={`penggunaan-row-${p.nama}`}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-foreground leading-tight">{p.nama}</p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {[p.nip && `NIP ${p.nip}`, p.jabatan, p.melekat_ke,
                          `${p.jumlah_kegiatan} kegiatan`].filter(Boolean).join(" · ")}
                        {p.pegawai_terdaftar === false && (
                          <span className="ml-1.5 px-1.5 py-px rounded bg-orange-500/15 text-orange-600 dark:text-orange-400 font-semibold"
                            title="NIP pemegang ini belum ada di Master Pegawai — daftarkan lewat halaman Master Pegawai agar identitas satu sumber">
                            belum di master
                          </span>
                        )}
                        {p.pegawai_master_status && p.pegawai_master_status !== "aktif" && (
                          <span className="ml-1.5 px-1.5 py-px rounded bg-red-500/15 text-red-600 dark:text-red-400 font-semibold"
                            title="Pemegang berstatus non-aktif di Master Pegawai — pertimbangkan mutasi/pengembalian aset">
                            {p.pegawai_master_status}
                          </span>
                        )}
                      </p>
                    </div>
                    <span className="text-xs font-bold text-foreground flex-shrink-0">{p.jumlah_aset} aset</span>
                    {p.lengkap ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 text-[10px] font-semibold flex-shrink-0">
                        <BadgeCheck className="w-3 h-3" />Lengkap
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30 text-[10px] font-semibold flex-shrink-0">
                        <FileWarning className="w-3 h-3" />BAST {p.jumlah_bast}/{p.jumlah_aset}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1 || loading} onClick={() => load(page - 1, search)} className="gap-1">
              <ChevronLeft className="w-4 h-4" />Sebelumnya
            </Button>
            <span className="text-xs text-muted-foreground">Pemegang — hal. {page} / {totalPages}</span>
            <Button variant="outline" size="sm" disabled={page >= totalPages || loading} onClick={() => load(page + 1, search)} className="gap-1">
              Berikutnya<ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        )}

        {/* ── BMN Idle (PMK 120/2024) ── */}
        {idle && (
          <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="penggunaan-idle">
            <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
              <FileWarning className="w-4 h-4 text-amber-500" />
              <p className="text-xs font-bold text-foreground flex-1">BMN Idle — Daftar Pantau (PMK 120/2024)</p>
              <span className="px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 text-[10px] font-semibold">
                {idle.ringkasan?.kandidat || 0} kandidat
              </span>
              {(idle.tiket || []).length > 0 && (
                <button type="button"
                  onClick={() => downloadFileWithProgress(`${API}/penggunaan/idle/export`, "register_tiket_bmn_idle.csv", { label: "Ekspor Register Tiket BMN Idle (CSV)" }).catch(() => {})}
                  className="h-7 px-2 rounded-lg border border-border text-[11px] font-semibold text-foreground/80 flex items-center gap-1 hover:bg-muted min-h-0 flex-shrink-0"
                  data-testid="penggunaan-idle-export">
                  <FileDown className="w-3.5 h-3.5" /><span className="hidden sm:inline">CSV</span>
                </button>
              )}
            </div>
            {(idle.kandidat || []).length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-5 px-4">
                Tidak ada indikasi idle — seluruh aset berstatus aktif dan berpengguna.
              </p>
            ) : (
              <ul className="divide-y divide-border/60">
                {idle.kandidat.slice(0, 50).map((k) => (
                  <li key={k.asset_id} className="p-3 flex flex-wrap items-center gap-2" data-testid={`penggunaan-idle-${k.asset_id}`}>
                    <span className="min-w-0 flex-1">
                      <span className="block text-xs font-semibold text-foreground truncate">
                        {k.asset_name || "-"} <span className="font-mono font-normal text-muted-foreground">({k.asset_code} · {k.NUP})</span>
                      </span>
                      <span className="block text-[11px] text-muted-foreground truncate">{k.alasan}{k.location && ` · ${k.location}`}</span>
                    </span>
                    {k.tiket ? (
                      <span className="px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[10px] font-semibold">
                        {idle.label_status?.[k.tiket.status] || k.tiket.status}
                      </span>
                    ) : (
                      <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                        onClick={() => bukaKlarifikasi(k)} data-testid={`penggunaan-idle-klarifikasi-${k.asset_id}`}>
                        Klarifikasi
                      </Button>
                    )}
                  </li>
                ))}
                {(idle.kandidat || []).length > 50 && (
                  <li className="text-[11px] text-muted-foreground text-center py-2">Menampilkan 50 kandidat pertama.</li>
                )}
              </ul>
            )}
            {(idle.tiket || []).length > 0 && (
              <div className="border-t border-border">
                <p className="px-3 pt-2.5 pb-1 text-[11px] font-semibold text-foreground/80">Tiket penanganan</p>
                <ul className="divide-y divide-border/60">
                  {idle.tiket.map((t) => (
                    <li key={t.id} className="p-3" data-testid={`penggunaan-tiket-${t.id}`}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[10px] font-semibold">
                          {idle.label_status?.[t.status] || t.status}
                        </span>
                        <p className="text-xs font-semibold text-foreground flex-1 min-w-[120px] truncate">
                          {t.asset_name} <span className="font-mono font-normal text-muted-foreground">({t.asset_code} · {t.NUP})</span>
                        </p>
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5 truncate">
                        {t.alasan}
                        {t.nomor_usulan && ` · Usulan ${t.nomor_usulan}`}
                        {t.nomor_bast_serah && ` · BAST ${t.nomor_bast_serah}`}
                        {t.keterangan && ` · ${t.keterangan}`}
                        {` · oleh ${t.created_by}`}
                      </p>
                      {isAdmin && ["klarifikasi", "usul_serah"].includes(t.status) && (
                        <div className="flex gap-1.5 mt-1.5 flex-wrap">
                          {t.status === "klarifikasi" && (
                            <>
                              <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                                onClick={() => kirimTransisiIdle(t, "digunakan_kembali")}>
                                Digunakan Kembali
                              </Button>
                              <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                                onClick={() => setTrxIdle({ tiket: t, ke: "usul_serah", saving: false, fields: { nomor_usulan: "" } })}
                                data-testid={`penggunaan-idle-usul-${t.id}`}>
                                Usul Serah
                              </Button>
                            </>
                          )}
                          {t.status === "usul_serah" && (
                            <Button size="sm" className="h-7 text-[11px] min-h-0 bg-emerald-600 hover:bg-emerald-700 text-white"
                              onClick={() => setTrxIdle({ tiket: t, ke: "diserahkan", saving: false, fields: { nomor_bast_serah: "" } })}
                              data-testid={`penggunaan-idle-serah-${t.id}`}>
                              Diserahkan (BAST)
                            </Button>
                          )}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <p className="px-3 py-2 text-[11px] text-muted-foreground border-t border-border">{idle.catatan}</p>
          </div>
        )}

        {/* ── Tiket proses alih status & penggunaan sementara (PMK 40/2024) ── */}
        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="penggunaan-proses">
          <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
            <ArrowLeftRight className="w-4 h-4 text-indigo-500 flex-shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-bold text-foreground">Proses Alih Status & Penggunaan Sementara</p>
              <p className="text-[10px] text-muted-foreground truncate">
                Alih status · sementara · dioperasikan pihak lain · bersama (PMK 40/2024) — resmi via SIMAN/DJKN
              </p>
            </div>
            {(proses?.ringkasan?.segera_berakhir || 0) > 0 && (
              <span className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-600 dark:text-amber-400 text-[10px] font-semibold flex-shrink-0">
                {proses.ringkasan.segera_berakhir} segera berakhir
              </span>
            )}
            {(proses?.items || []).length > 0 && (
              <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                onClick={() => downloadFileWithProgress(`${API}/penggunaan/proses/export`, "register_proses_penggunaan.csv", { label: "Ekspor Register Proses Penggunaan (CSV)" }).catch(() => {})}
                data-testid="penggunaan-proses-export">
                <FileDown className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">CSV</span>
              </Button>
            )}
            <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
              onClick={() => { setCariPsp(""); setHasilCariPsp([]); setFormProses({ data: { jenis_proses: "alih_status", arah: "keluar", pihak_asal: "", pihak_tujuan: "", nomor_permohonan: "", tanggal_permohonan: "", tanggal_mulai: "", tanggal_berakhir: "", keterangan: "" }, aset: [], saving: false }); }}
              data-testid="penggunaan-proses-tambah">
              <Plus className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">Buka Tiket</span>
            </Button>
          </div>
          {(proses?.items || []).length === 0 ? (
            <p className="text-[11px] text-muted-foreground text-center py-4 px-3">
              Belum ada tiket — catat proses alih status (permanen) atau penggunaan sementara (berjangka 5/2 tahun).
            </p>
          ) : (
            <ul className="divide-y divide-border/60">
              {proses.items.map((t) => (
                <li key={t.id} className="p-3" data-testid={`penggunaan-proses-${t.id}`}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${WARNA_STATUS_PROSES[t.status] || "bg-muted"}`}>
                      {proses.label_status?.[t.status] || t.status}
                    </span>
                    <span className="px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 text-[10px] font-semibold">
                      {proses.label_jenis?.[t.jenis_proses] || t.jenis_proses}
                    </span>
                    <span className="px-1.5 py-0.5 rounded bg-muted text-[10px] font-semibold text-foreground/70">
                      {proses.label_arah?.[t.arah] || t.arah}
                    </span>
                    {t.info?.saatnya_perpanjangan && (
                      <span className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-600 dark:text-amber-400 text-[10px] font-semibold">
                        {t.info.sisa_hari} hari — ajukan perpanjangan
                      </span>
                    )}
                    <p className="text-sm font-semibold text-foreground flex-1 min-w-[140px] truncate">
                      {t.pihak_asal} → {t.pihak_tujuan}
                    </p>
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {[`${(t.aset || []).length} aset`,
                      t.nomor_permohonan && `Permohonan ${t.nomor_permohonan}`,
                      t.nomor_persetujuan && `Persetujuan ${t.nomor_persetujuan}`,
                      t.nomor_bast && `BAST ${t.nomor_bast}`,
                      t.nomor_sk_penghapusan && `SK Hapus ${t.nomor_sk_penghapusan}`,
                      t.nomor_perjanjian && `Perjanjian ${t.nomor_perjanjian}`,
                      t.tanggal_mulai && t.tanggal_berakhir && `${t.tanggal_mulai} s.d. ${t.tanggal_berakhir}`,
                      t.keterangan, `oleh ${t.created_by}`].filter(Boolean).join(" · ")}
                  </p>
                  <div className="flex gap-1.5 mt-1.5 flex-wrap items-center">
                    {((proses.transisi?.[t.jenis_proses] || {})[t.status] || []).map((ke) => (
                      <Button key={ke} size="sm" variant="outline"
                        className={`h-7 text-[11px] min-h-0 ${ke === "ditolak"
                          ? "text-red-500"
                          : ["disetujui", "berjalan", "bast_selesai"].includes(ke)
                            ? "border-emerald-500/50 text-emerald-600"
                            : ""}`}
                        onClick={() => pindahStatusProses(t, ke)}
                        data-testid={`penggunaan-proses-${t.id}-ke-${ke}`}>
                        {proses.label_status?.[ke] || ke}
                      </Button>
                    ))}
                    {isAdmin && (
                      <button type="button" onClick={() => hapusProses(t)} aria-label="Hapus tiket"
                        className="h-7 w-7 min-h-0 min-w-0 rounded flex items-center justify-center text-muted-foreground hover:text-red-500 hover:bg-red-500/10">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* ── Register SK Penetapan Penggunaan (PSP) ── */}
        {psp && (
          <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="penggunaan-psp">
            <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
              <ScrollText className="w-4 h-4 text-sky-500" />
              <p className="text-xs font-bold text-foreground flex-1">Penetapan Status Penggunaan (PMK 40/2024)</p>
              <span className="px-2 py-0.5 rounded-full bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[10px] font-semibold">
                {psp.ringkasan?.aset_tercakup || 0}/{psp.ringkasan?.total_aset || 0} aset tercakup
              </span>
              {(psp.items || []).length > 0 && (
                <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                  onClick={() => downloadFileWithProgress(`${API}/penggunaan/psp/export`, "register_sk_psp.csv", { label: "Ekspor Register SK PSP (CSV)" }).catch(() => {})}
                  data-testid="penggunaan-psp-export">
                  <FileDown className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">CSV</span>
                </Button>
              )}
              <Button size="sm" onClick={() => { setCariPsp(""); setHasilCariPsp([]); setFormPsp({ data: { nomor_sk: "", tanggal_sk: new Date().toISOString().slice(0, 10), jenis: "psp", penetap: "", keterangan: "", sebagai_draf: false }, aset: [], saving: false }); }}
                className="h-7 text-[11px] min-h-0 bg-sky-600 hover:bg-sky-700 text-white" data-testid="penggunaan-psp-tambah">
                <Plus className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">Catat SK</span>
              </Button>
            </div>
            {(pspSiman?.belum_tercatat || 0) > 0 && (
              <details className="border-b border-border bg-sky-50/60 dark:bg-sky-950/30"
                data-testid="penggunaan-psp-siman">
                <summary className="px-3 py-2 text-[11px] font-semibold text-sky-800 dark:text-sky-300 cursor-pointer select-none">
                  PSP resmi menurut SIMAN V2 belum tercatat di register:{" "}
                  {pspSiman.belum_tercatat} SK — klik untuk mencatat tanpa mengetik ulang
                </summary>
                <ul className="divide-y divide-border/60">
                  {(pspSiman.kelompok || []).filter((k) => !k.sudah_tercatat).map((k) => (
                    <li key={k.no_psp} className="px-3 py-2 flex flex-wrap items-center gap-2">
                      <div className="flex-1 min-w-[160px]">
                        <p className="text-xs font-semibold text-foreground break-words">{k.no_psp}</p>
                        <p className="text-[10px] text-muted-foreground">
                          {[k.tanggal_psp || "tanpa tanggal",
                            `${k.jumlah} aset`,
                            k.status_penggunaan].filter(Boolean).join(" · ")}
                        </p>
                      </div>
                      <Button size="sm" variant="outline"
                        className="h-7 text-[11px] min-h-0 border-sky-300 dark:border-sky-700 text-sky-700 dark:text-sky-300"
                        onClick={() => catatDariSiman(k)}
                        data-testid={`penggunaan-psp-siman-catat-${k.no_psp}`}>
                        Catat 1-klik
                      </Button>
                    </li>
                  ))}
                </ul>
              </details>
            )}
            {(psp.items || []).length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-5 px-4">
                Belum ada SK penetapan tercatat — mulai dari SK PSP terbaru satker.
              </p>
            ) : (
              <ul className="divide-y divide-border/60">
                {psp.items.map((sk) => (
                  <li key={sk.id} className="p-3" data-testid={`penggunaan-psp-${sk.id}`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[10px] font-semibold">
                        {psp.label_jenis?.[sk.jenis] || sk.jenis}
                      </span>
                      <p className="text-xs font-semibold text-foreground flex-1 min-w-[120px] truncate">{sk.nomor_sk || "(SK belum terbit)"}</p>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${WARNA_PENGAJUAN_PSP[sk.status_pengajuan] || "bg-muted text-muted-foreground"}`}>
                        {psp.label_status_pengajuan?.[sk.status_pengajuan] || sk.status_pengajuan}
                      </span>
                      <span className="text-[11px] text-muted-foreground">{sk.tanggal_sk || "—"} · {(sk.aset || []).length} aset</span>
                    </div>
                    <div className="flex gap-1.5 mt-1.5 flex-wrap items-center">
                      {sk.status_pengajuan === "draf" && (
                        <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                          onClick={() => pindahStatusPsp(sk, "diajukan")}
                          data-testid={`penggunaan-psp-ajukan-${sk.id}`}>Ajukan</Button>
                      )}
                      {sk.status_pengajuan === "diajukan" && isAdmin && (
                        <>
                          <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                            onClick={() => pindahStatusPsp(sk, "ditetapkan")}
                            data-testid={`penggunaan-psp-tetapkan-${sk.id}`}>Tetapkan</Button>
                          <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 text-amber-600"
                            onClick={() => pindahStatusPsp(sk, "draf")}>Kembalikan</Button>
                          <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 text-red-500"
                            onClick={() => pindahStatusPsp(sk, "ditolak")}>Tolak</Button>
                        </>
                      )}
                      <button type="button" aria-label="Lampiran SK" title="Lampiran SK"
                        onClick={() => setLampPsp({ sk, uploading: false })}
                        className="h-7 w-7 rounded-lg border border-border text-foreground/70 flex items-center justify-center hover:bg-muted min-h-0 min-w-0"
                        data-testid={`penggunaan-psp-lampiran-${sk.id}`}>
                        <Paperclip className="w-3 h-3" />
                      </button>
                      {sk.status_pengajuan === "ditetapkan" && (
                        <button type="button" aria-label="Unduh BAST (PDF)" title="Unduh BAST (PDF)"
                          onClick={() => downloadFileWithProgress(
                            `${API}/penggunaan/psp/${sk.id}/bast-pdf`,
                            `BAST_PSP_${(sk.nomor_sk || "SK").replace(/[/\s]/g, "-")}.pdf`,
                            { label: `BAST PSP ${sk.nomor_sk}` },
                          ).catch(() => {})}
                          className="h-7 w-7 rounded-lg border border-border text-foreground/70 flex items-center justify-center hover:bg-muted min-h-0 min-w-0"
                          data-testid={`penggunaan-psp-bast-${sk.id}`}>
                          <FileText className="w-3 h-3" />
                        </button>
                      )}
                      {isAdmin && (
                        <button type="button" aria-label="Hapus SK" title="Hapus SK" onClick={() => hapusPsp(sk)}
                          className="h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 min-h-0 min-w-0">
                          <Trash2 className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                    <p className="text-[11px] text-muted-foreground mt-0.5 truncate">
                      {[sk.penetap && `Penetap: ${sk.penetap}`, sk.keterangan,
                        `oleh ${sk.created_by}`].filter(Boolean).join(" · ")}
                    </p>
                    <ul className="mt-1 space-y-0.5">
                      {(sk.aset || []).slice(0, 4).map((a) => (
                        <li key={a.asset_id} className="text-[11px] text-foreground/80 truncate">
                          {a.asset_name} <span className="font-mono text-muted-foreground">({a.asset_code} · {a.NUP})</span>
                        </li>
                      ))}
                      {(sk.aset || []).length > 4 && (
                        <li className="text-[11px] text-muted-foreground">+{sk.aset.length - 4} aset lainnya</li>
                      )}
                    </ul>
                  </li>
                ))}
              </ul>
            )}
            <p className="px-3 py-2 text-[11px] text-muted-foreground border-t border-border">{psp.catatan}</p>
          </div>
        )}

        <p className="text-center text-[11px] text-muted-foreground pb-4">
          Pengajuan resmi alih status/PSP tetap melalui SIMAN/DJKN — halaman ini register pendamping satker.
        </p>
      </main>

      {/* ── Dialog buka tiket proses ── */}
      <Dialog open={!!formProses} onOpenChange={(o) => { if (!o) setFormProses(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Buka Tiket Proses</DialogTitle>
            <DialogDescription className="text-xs">
              Alih status (permanen) / penggunaan sementara (berjangka) — pengajuan resmi via SIMAN/DJKN.
            </DialogDescription>
          </DialogHeader>
          {formProses && (
            <div className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="prs-jenis">Jenis proses</label>
                  <select id="prs-jenis" value={formProses.data.jenis_proses}
                    onChange={(e) => setFormProses((f) => ({ ...f, data: { ...f.data, jenis_proses: e.target.value } }))}
                    className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                    data-testid="proses-jenis">
                    {Object.entries(proses?.label_jenis || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="prs-arah">Arah</label>
                  <select id="prs-arah" value={formProses.data.arah}
                    onChange={(e) => setFormProses((f) => ({ ...f, data: { ...f.data, arah: e.target.value } }))}
                    className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                    data-testid="proses-arah">
                    {Object.entries(proses?.label_arah || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="prs-asal">Pihak asal</label>
                  <Input id="prs-asal" value={formProses.data.pihak_asal} list="proses-satker-list"
                    placeholder="ketik bebas atau pilih dari Master Satker"
                    onChange={(e) => setFormProses((f) => ({ ...f, data: { ...f.data, pihak_asal: e.target.value } }))}
                    data-testid="proses-asal" />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="prs-tujuan">Pihak tujuan</label>
                  <Input id="prs-tujuan" value={formProses.data.pihak_tujuan} list="proses-satker-list"
                    placeholder="ketik bebas atau pilih dari Master Satker"
                    onChange={(e) => setFormProses((f) => ({ ...f, data: { ...f.data, pihak_tujuan: e.target.value } }))}
                    data-testid="proses-tujuan" />
                  <datalist id="proses-satker-list">
                    {satkerList.map((s) => (
                      <option key={s.kode_satker} value={s.nama_satker || s.kode_satker}>{s.kode_satker}</option>
                    ))}
                  </datalist>
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="prs-nomor">No. permohonan (ops.)</label>
                  <Input id="prs-nomor" value={formProses.data.nomor_permohonan}
                    onChange={(e) => setFormProses((f) => ({ ...f, data: { ...f.data, nomor_permohonan: e.target.value } }))}
                    data-testid="proses-nomor" />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="prs-tgl">Tgl. permohonan (ops.)</label>
                  <Input id="prs-tgl" type="date" value={formProses.data.tanggal_permohonan}
                    onChange={(e) => setFormProses((f) => ({ ...f, data: { ...f.data, tanggal_permohonan: e.target.value } }))}
                    data-testid="proses-tgl" />
                </div>
                {["penggunaan_sementara", "dioperasikan_pihak_lain", "penggunaan_bersama"].includes(formProses.data.jenis_proses) && (
                  <>
                    <div>
                      <label className="text-xs font-medium text-foreground block mb-1" htmlFor="prs-mulai">Mulai</label>
                      <Input id="prs-mulai" type="date" value={formProses.data.tanggal_mulai}
                        onChange={(e) => setFormProses((f) => ({ ...f, data: { ...f.data, tanggal_mulai: e.target.value } }))}
                        data-testid="proses-mulai" />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-foreground block mb-1" htmlFor="prs-berakhir">Berakhir (maks 5 th tanah/bangunan, 2 th lainnya)</label>
                      <Input id="prs-berakhir" type="date" value={formProses.data.tanggal_berakhir}
                        onChange={(e) => setFormProses((f) => ({ ...f, data: { ...f.data, tanggal_berakhir: e.target.value } }))}
                        data-testid="proses-berakhir" />
                    </div>
                  </>
                )}
                <div className="col-span-2">
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="prs-ket">Keterangan (ops.)</label>
                  <Input id="prs-ket" value={formProses.data.keterangan}
                    onChange={(e) => setFormProses((f) => ({ ...f, data: { ...f.data, keterangan: e.target.value } }))}
                    data-testid="proses-ket" />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="prs-cari">Tambah aset</label>
                <div className="relative">
                  <Search className="w-4 h-4 absolute left-2.5 top-2.5 text-muted-foreground" />
                  <Input id="prs-cari" className="pl-8" placeholder="nama / kode / NUP…"
                    value={cariPsp} onChange={(e) => setCariPsp(e.target.value)} data-testid="proses-cari" />
                </div>
                <ul className="mt-2 space-y-1.5 max-h-32 overflow-y-auto">
                  {hasilCariPsp.map((a) => (
                    <li key={a.id}>
                      <button type="button"
                        onClick={() => setFormProses((f) => (f.aset.some((x) => x.id === a.id) ? f : { ...f, aset: [...f.aset, a] }))}
                        className="w-full text-left rounded-lg border border-border p-2 text-xs hover:bg-muted min-h-0"
                        data-testid={`proses-pilih-${a.id}`}>
                        <span className="text-foreground/90">{a.asset_name || "-"}</span>{" "}
                        <span className="font-mono text-[10px] text-muted-foreground">({a.asset_code} · {a.NUP})</span>
                      </button>
                    </li>
                  ))}
                </ul>
                {formProses.aset.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {formProses.aset.map((a) => (
                      <li key={a.id} className="rounded-lg border border-border p-1.5 text-xs flex items-center justify-between gap-2">
                        <span className="min-w-0 truncate text-foreground/90">{a.asset_name || "-"} <span className="font-mono text-[10px] text-muted-foreground">({a.asset_code})</span></span>
                        <button type="button" onClick={() => setFormProses((f) => ({ ...f, aset: f.aset.filter((x) => x.id !== a.id) }))}
                          className="h-6 w-6 min-h-0 min-w-0 rounded flex items-center justify-center text-muted-foreground hover:text-red-500 flex-shrink-0" aria-label="Lepas aset">
                          <X className="w-3 h-3" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="flex flex-wrap justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setFormProses(null)}>Batal</Button>
                <Button size="sm" className="bg-indigo-600 hover:bg-indigo-700 text-white"
                  disabled={formProses.saving || !formProses.data.pihak_asal.trim() || !formProses.data.pihak_tujuan.trim() || formProses.aset.length === 0}
                  onClick={simpanProses} data-testid="proses-simpan">
                  {formProses.saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Buka Tiket (Draf)"}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Dialog catat SK PSP ── */}
      <Dialog open={!!formPsp} onOpenChange={(o) => { if (!o) setFormPsp(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Catat SK Penetapan Penggunaan</DialogTitle>
            <DialogDescription className="text-xs">
              Satu catatan per SK — cakupan aset dipetakan agar terlihat aset yang belum ter-PSP.
            </DialogDescription>
          </DialogHeader>
          {formPsp && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psp-nomor">Nomor SK</label>
                <Input id="psp-nomor" placeholder="KEP-1/MK.6/2026" value={formPsp.data.nomor_sk}
                  onChange={(e) => setFormPsp((f) => ({ ...f, data: { ...f.data, nomor_sk: e.target.value } }))}
                  data-testid="penggunaan-psp-nomor" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psp-tgl">Tanggal SK</label>
                <Input id="psp-tgl" type="date" value={formPsp.data.tanggal_sk}
                  onChange={(e) => setFormPsp((f) => ({ ...f, data: { ...f.data, tanggal_sk: e.target.value } }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psp-jenis">Jenis</label>
                <select id="psp-jenis" value={formPsp.data.jenis}
                  onChange={(e) => setFormPsp((f) => ({ ...f, data: { ...f.data, jenis: e.target.value } }))}
                  className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                  data-testid="penggunaan-psp-jenis">
                  {Object.entries(psp?.label_jenis || { psp: "PSP" }).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psp-penetap">Penetap</label>
                <Input id="psp-penetap" placeholder="Pengelola/Pengguna Barang" value={formPsp.data.penetap}
                  onChange={(e) => setFormPsp((f) => ({ ...f, data: { ...f.data, penetap: e.target.value } }))} />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psp-ket">Keterangan</label>
                <Input id="psp-ket" value={formPsp.data.keterangan}
                  onChange={(e) => setFormPsp((f) => ({ ...f, data: { ...f.data, keterangan: e.target.value } }))} />
              </div>
              <label className="col-span-2 flex items-center gap-2 text-xs text-foreground cursor-pointer">
                <input type="checkbox" checked={!!formPsp.data.sebagai_draf}
                  onChange={(e) => setFormPsp((f) => ({ ...f, data: { ...f.data, sebagai_draf: e.target.checked } }))}
                  data-testid="penggunaan-psp-draf" />
                Simpan sebagai <b>draf usulan</b> — SK belum terbit (nomor/tanggal SK diisi saat penetapan)
              </label>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psp-cari">Tambah aset</label>
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <Input id="psp-cari" className="pl-8" placeholder="Cari nama/kode aset (min. 2 huruf)"
                    value={cariPsp} onChange={(e) => setCariPsp(e.target.value)} data-testid="penggunaan-psp-cari" />
                  {hasilCariPsp.length > 0 && cariPsp.trim().length >= 2 && (
                    <div className="absolute z-50 mt-1 w-full max-h-44 overflow-y-auto rounded-lg border border-border bg-card shadow-lg">
                      {hasilCariPsp.map((a) => (
                        <button key={a.id} type="button"
                          onClick={() => { setFormPsp((f) => (f.aset.some((x) => x.id === a.id) ? f : { ...f, aset: [...f.aset, a] })); setCariPsp(""); setHasilCariPsp([]); }}
                          className="w-full px-2.5 py-1.5 text-left hover:bg-muted">
                          <span className="block text-xs font-semibold text-foreground truncate">{a.asset_name}</span>
                          <span className="block text-[10px] text-muted-foreground font-mono">{a.asset_code} · {a.NUP}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              {formPsp.aset.length > 0 && (
                <ul className="col-span-2 space-y-1">
                  {formPsp.aset.map((a) => (
                    <li key={a.id} className="rounded-lg border border-border p-2 flex items-center gap-2">
                      <span className="min-w-0 flex-1">
                        <span className="block text-xs font-semibold text-foreground truncate">{a.asset_name}</span>
                        <span className="block text-[10px] text-muted-foreground font-mono">{a.asset_code} · {a.NUP}</span>
                      </span>
                      <button type="button" aria-label="Keluarkan aset"
                        onClick={() => setFormPsp((f) => ({ ...f, aset: f.aset.filter((x) => x.id !== a.id) }))}
                        className="h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 flex-shrink-0 min-h-0 min-w-0">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="outline" onClick={() => setFormPsp(null)}>Batal</Button>
            <Button onClick={simpanPsp} disabled={formPsp?.saving || (formPsp?.aset?.length || 0) === 0}
              className="bg-sky-600 hover:bg-sky-700 text-white" data-testid="penggunaan-psp-simpan">
              {formPsp?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <ScrollText className="w-4 h-4 mr-1.5" />}Catat SK
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Dialog lampiran SK PSP (arsip scan SK + dokumen pendukung) ── */}
      <Dialog open={!!lampPsp} onOpenChange={(o) => { if (!o) setLampPsp(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Lampiran SK Penetapan Penggunaan</DialogTitle>
            <DialogDescription className="text-xs">
              {lampPsp && `${lampPsp.sk.nomor_sk} (${lampPsp.sk.tanggal_sk}). Scan SK PSP / dokumen pendukung (PDF/JPG/PNG, maks 10MB, 10 berkas).`}
            </DialogDescription>
          </DialogHeader>
          <input ref={lampPspInputRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) unggahLampiranPsp(f); }} />
          <Button size="sm" variant="outline" className="h-8 text-xs min-h-0 self-start"
            disabled={lampPsp?.uploading || (lampPsp?.sk?.lampiran || []).length >= 10}
            onClick={() => lampPspInputRef.current?.click()} data-testid="penggunaan-psp-lampiran-unggah">
            {lampPsp?.uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Upload className="w-3.5 h-3.5 mr-1.5" />}
            Unggah Berkas
          </Button>
          {(lampPsp?.sk?.lampiran || []).length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">Belum ada lampiran.</p>
          ) : (
            <ul className="space-y-1.5">
              {(lampPsp?.sk?.lampiran || []).map((f) => (
                <li key={f.file_id} className="rounded-lg border border-border p-2 flex items-center gap-2">
                  <button type="button"
                    onClick={() => window.open(authMediaUrl(`${API}/penggunaan/psp/${lampPsp.sk.id}/lampiran/${f.file_id}`), "_blank", "noopener")}
                    className="min-w-0 flex-1 text-left hover:underline">
                    <span className="block text-xs font-semibold text-foreground truncate">{f.filename}</span>
                    <span className="block text-[10px] text-muted-foreground">
                      {String(f.tanggal || "").slice(0, 10)} · oleh {f.oleh}
                    </span>
                  </button>
                  {isAdmin && (
                    <button type="button" aria-label="Hapus lampiran" onClick={() => hapusLampiranPsp(f.file_id)}
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

      {/* ── Dialog transisi tiket idle ── */}
      <Dialog open={!!trxIdle} onOpenChange={(o) => { if (!o) setTrxIdle(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>{idle?.label_status?.[trxIdle?.ke] || trxIdle?.ke}</DialogTitle>
            <DialogDescription className="text-xs">
              {trxIdle?.tiket && `${trxIdle.tiket.asset_name} (${trxIdle.tiket.asset_code} · ${trxIdle.tiket.NUP})`}
            </DialogDescription>
          </DialogHeader>
          {trxIdle?.ke === "usul_serah" && (
            <div>
              <label className="text-xs font-medium text-foreground block mb-1" htmlFor="idle-usulan">No. Surat Usulan Penyerahan</label>
              <Input id="idle-usulan" placeholder="S-12/SATKER/2026" value={trxIdle.fields.nomor_usulan}
                onChange={(e) => setTrxIdle((t) => ({ ...t, fields: { ...t.fields, nomor_usulan: e.target.value } }))}
                data-testid="penggunaan-idle-nomor-usulan" />
            </div>
          )}
          {trxIdle?.ke === "diserahkan" && (
            <div>
              <label className="text-xs font-medium text-foreground block mb-1" htmlFor="idle-bast">No. BAST Penyerahan ke Pengelola</label>
              <Input id="idle-bast" placeholder="BAST-01/KNL.05/2026" value={trxIdle.fields.nomor_bast_serah}
                onChange={(e) => setTrxIdle((t) => ({ ...t, fields: { ...t.fields, nomor_bast_serah: e.target.value } }))}
                data-testid="penggunaan-idle-nomor-bast" />
            </div>
          )}
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="outline" onClick={() => setTrxIdle(null)}>Batal</Button>
            <Button disabled={trxIdle?.saving}
              onClick={() => { setTrxIdle((t) => ({ ...t, saving: true })); kirimTransisiIdle(trxIdle.tiket, trxIdle.ke, trxIdle.fields); }}
              className="bg-sky-600 hover:bg-sky-700 text-white" data-testid="penggunaan-idle-simpan">
              Simpan
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Dialog daftar aset pemegang ── */}
      {/* ── Dialog Riwayat BAST pemegang (pratinjau/unduh/bukti ttd) ── */}
      <input ref={buktiRef} type="file" accept=".pdf,.jpg,.jpeg,.png" className="hidden"
        onChange={(e) => unggahBukti(e.target.files?.[0])} data-testid="bast-bukti-input" />
      <Dialog open={!!riwayatBast} onOpenChange={(o) => { if (!o) setRiwayatBast(null); }}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Riwayat BAST — {detail?.pemegang?.nama}</DialogTitle>
            <DialogDescription className="text-xs">
              Pratinjau membuka PDF di tab baru; unggah bukti tanda tangan akan otomatis MENYAHKAN nomor agendanya di Persuratan.
            </DialogDescription>
          </DialogHeader>
          {riwayatBast?.loading ? (
            <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-sky-600" /></div>
          ) : (riwayatBast?.items || []).length === 0 ? (
            <p className="text-center text-xs text-muted-foreground py-6">Belum ada BAST untuk pemegang ini.</p>
          ) : (
            <ul className="space-y-2">
              {riwayatBast.items.map((b) => (
                <li key={b.id} className="rounded-lg border border-border p-2.5 text-xs" data-testid={`riwayat-bast-${b.id}`}>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0 flex-1 basis-full sm:basis-auto">
                      <p className="font-semibold text-foreground truncate">
                        {(riwayatBast.label_jenis || {})[b.jenis] || b.jenis}
                      </p>
                      <p className="font-mono text-[11px] text-muted-foreground break-all">
                        {b.nomor || "(tanpa nomor)"} · {String(b.tanggal || "").slice(0, 10)} · {(b.asset_ids || []).length} aset → {b.pihak_kedua?.nama}
                      </p>
                      {b.bukti?.file_id ? (
                        <p className="text-[10px] text-emerald-600 dark:text-emerald-400">✓ Bukti ttd terunggah ({String(b.bukti.diunggah_pada || "").slice(0, 10)})</p>
                      ) : (
                        <p className="text-[10px] text-amber-600 dark:text-amber-400">Bukti ttd belum diunggah</p>
                      )}
                      {b.tt_dicabut && !b.bukti?.file_id ? (
                        <p className="text-[10px] font-semibold text-red-600 dark:text-red-400" data-testid={`bast-tt-dicabut-${b.id}`}>
                          ⚠ TTD elektronik dibatalkan — tanda tangan tidak berlaku
                        </p>
                      ) : null}
                      {b.revisi_ke ? (
                        <p className="text-[10px] text-cyan-700 dark:text-cyan-400" data-testid={`bast-revisi-ke-${b.id}`}>
                          Revisi ke-{b.revisi_ke} atas {b.revisi_dari_nomor || "BAST sebelumnya"}
                          {b.revisi_alasan ? ` — ${b.revisi_alasan}` : ""}
                        </p>
                      ) : null}
                      {b.direvisi_oleh ? (
                        <p className="text-[10px] font-semibold text-red-600 dark:text-red-400" data-testid={`bast-direvisi-${b.id}`}>
                          ⚠ Telah {b.direvisi_mode === "mencabut" ? "dicabut" : "direvisi"} — digantikan {b.direvisi_oleh_nomor || "BAST pengganti"}
                        </p>
                      ) : null}
                    </div>
                    {/* `flex-shrink-0` DIHAPUS (bug tombol meluber kanvas):
                        kontainer jadi menolak menyusut sehingga empat tombol
                        mendorong "Unggah Bukti TTD" keluar tepi dialog alih-alih
                        membungkus. `w-full` di layar sempit membuat tombol turun
                        rapi ke barisnya sendiri. */}
                    <div className="flex w-full flex-wrap items-center gap-1.5 sm:w-auto sm:justify-end">
                      <Button size="sm" variant="outline" className="h-7 text-[11px]"
                        onClick={() => window.open(authMediaUrl(`${API}/bast/${b.id}/pdf`), "_blank")}
                        data-testid={`bast-pratinjau-${b.id}`}>Pratinjau</Button>
                      <Button size="sm" variant="outline" className="h-7 text-[11px]"
                        onClick={() => downloadFileWithProgress(`${API}/bast/${b.id}/pdf`,
                          `BAST_${(b.pihak_kedua?.nama || "pengguna").replace(/\s/g, "_")}.pdf`,
                          { label: "BAST Serah Terima" }).catch(() => {})}>Unduh</Button>
                      <Button size="sm" variant="outline" className="h-7 text-[11px]"
                        onClick={() => setFotoSt({ bast: b, mode: "per", asset_id: "" })}
                        data-testid={`bast-foto-st-${b.id}`}>Foto Serah Terima</Button>
                      {b.bukti?.file_id ? (
                        <Button size="sm" variant="outline" className="h-7 text-[11px]"
                          onClick={() => window.open(authMediaUrl(`${API}/bast/${b.id}/bukti`), "_blank")}>Lihat Bukti</Button>
                      ) : b.direvisi_oleh ? null : (
                        <>
                          <Button size="sm" variant="outline" className="h-7 text-[11px]"
                            disabled={kirimTtdId === b.id} onClick={() => kirimKeTtd(b)}
                            data-testid={`bast-kirim-ttd-${b.id}`}>
                            {kirimTtdId === b.id ? "Mengirim…" : "Kirim ke TTD"}
                          </Button>
                          <Button size="sm" className="h-7 text-[11px]"
                            onClick={() => { setBuktiUntuk(b.id); buktiRef.current?.click(); }}
                            data-testid={`bast-unggah-bukti-${b.id}`}>Unggah Bukti TTD</Button>
                        </>
                      )}
                      {!b.direvisi_oleh && (
                        <Button size="sm" variant="outline"
                          className="h-7 text-[11px] text-amber-700 dark:text-amber-400 border-amber-500/40"
                          onClick={() => bukaRevisiBast(b)}
                          title="Terbitkan BAST pengganti (revisi/cabut) — arsip lama tetap utuh"
                          data-testid={`bast-revisi-${b.id}`}>Revisi</Button>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Dialog FOTO SERAH TERIMA (lampiran BAST) ──
          Dua mode sesuai kondisi lapangan: tiap barang punya fotonya sendiri,
          atau satu foto perwakilan untuk seluruh barang. Foto per barang
          dicetak berdampingan dengan foto sampul aset; foto perwakilan
          dicetak sekali di akhir lampiran. */}
      <input ref={fotoStRef} type="file" accept=".jpg,.jpeg,.png,.webp" className="hidden"
        onChange={(e) => unggahFotoSerahTerima(e.target.files?.[0])}
        data-testid="bast-foto-st-input" />
      <Dialog open={!!fotoSt} onOpenChange={(o) => { if (!o) setFotoSt(null); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Foto Serah Terima Barang</DialogTitle>
            <DialogDescription className="text-xs">
              Foto ini masuk ke <b>Lampiran Foto Bukti Serah Terima Barang</b> pada
              PDF BAST — berdampingan dengan foto sampul barangnya.
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant={fotoSt?.mode === "per" ? "default" : "outline"}
              className="h-8 text-xs flex-1 min-w-[9rem]"
              onClick={() => setFotoSt((f) => ({ ...f, mode: "per" }))}
              data-testid="foto-st-mode-per">Per barang</Button>
            <Button size="sm" variant={fotoSt?.mode === "semua" ? "default" : "outline"}
              className="h-8 text-xs flex-1 min-w-[9rem]"
              onClick={() => setFotoSt((f) => ({ ...f, mode: "semua", asset_id: "" }))}
              data-testid="foto-st-mode-semua">Satu untuk semua</Button>
          </div>

          {fotoSt?.mode === "per" ? (
            <div className="space-y-1.5">
              <p className="text-[11px] text-muted-foreground">
                Pilih barang, lalu unggah fotonya. Barang tanpa foto tetap tampil
                di lampiran memakai foto sampulnya saja — kolomnya tidak dibiarkan
                kosong, aset berikutnya maju mengisinya.
              </p>
              <ul className="space-y-1 max-h-56 overflow-y-auto pr-1">
                {/* Sumber identitas barang = SNAPSHOT milik BAST itu sendiri
                    (`b.aset`), bukan `detail.rows` yang hanya berisi aset yang
                    dipegang SAAT INI — untuk BAST pengembalian/mutasi, asetnya
                    sudah tak dipegang lagi sehingga daftarnya akan menampilkan
                    UUID mentah. `detail.rows` tetap jadi cadangan. */}
                {(fotoSt?.bast?.asset_ids || []).map((aid) => {
                  const a = (fotoSt?.bast?.aset || []).find((x) => x.id === aid)
                    || (detail?.rows || []).find((x) => x.id === aid) || {};
                  const sudah = (fotoSt?.bast?.foto_serah_terima || {})[aid];
                  const dipilih = fotoSt?.asset_id === aid;
                  return (
                    <li key={aid}>
                      <button type="button"
                        onClick={() => setFotoSt((f) => ({ ...f, asset_id: aid }))}
                        className={`w-full text-left rounded-lg border p-2 text-[11px] transition-colors ${dipilih ? "border-sky-500 bg-sky-500/10" : "border-border hover:bg-muted"}`}
                        data-testid={`foto-st-aset-${aid}`}>
                        <span className="block font-semibold text-foreground truncate">
                          {a.asset_name || aid}
                        </span>
                        <span className="block font-mono text-[10px] text-muted-foreground truncate">
                          {a.asset_code || "-"} · NUP {a.NUP ?? "-"}
                        </span>
                        {sudah ? (
                          <span className="text-[10px] text-emerald-600 dark:text-emerald-400">✓ sudah ada foto</span>
                        ) : null}
                      </button>
                      {sudah ? (
                        <div className="flex flex-wrap gap-1 pl-2 pt-0.5">
                          <button type="button" className="text-[10px] underline text-sky-600 dark:text-sky-400"
                            onClick={() => window.open(authMediaUrl(
                              `${API}/bast/${fotoSt.bast.id}/foto-serah-terima/${sudah}`), "_blank")}
                            data-testid={`foto-st-lihat-${aid}`}>Lihat</button>
                          <button type="button" className="text-[10px] underline text-red-600 dark:text-red-400"
                            onClick={() => hapusFotoSerahTerima(aid, false)}
                            data-testid={`foto-st-hapus-${aid}`}>Hapus</button>
                        </div>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : (
            <div className="space-y-1.5">
              <p className="text-[11px] text-muted-foreground">
                Satu foto mewakili <b>seluruh barang</b> dalam BAST ini. Di lampiran,
                foto ini dicetak sekali di bagian akhir — tidak diulang pada tiap barang.
              </p>
              {fotoSt?.bast?.foto_serah_terima_bersama ? (
                <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-2">
                  <span className="text-[11px] text-emerald-600 dark:text-emerald-400">
                    ✓ sudah ada foto perwakilan
                  </span>
                  <button type="button" className="text-[10px] underline text-sky-600 dark:text-sky-400"
                    onClick={() => window.open(authMediaUrl(
                      `${API}/bast/${fotoSt.bast.id}/foto-serah-terima/${fotoSt.bast.foto_serah_terima_bersama}`), "_blank")}
                    data-testid="foto-st-lihat-bersama">Lihat</button>
                  <button type="button" className="text-[10px] underline text-red-600 dark:text-red-400"
                    onClick={() => hapusFotoSerahTerima("", true)}
                    data-testid="foto-st-hapus-bersama">Hapus</button>
                </div>
              ) : null}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" size="sm" className="h-8 text-xs"
              onClick={() => setFotoSt(null)}>Batal</Button>
            <Button size="sm" className="h-8 text-xs"
              disabled={fotoStSibuk || (fotoSt?.mode === "per" && !fotoSt?.asset_id)}
              onClick={() => fotoStRef.current?.click()}
              data-testid="foto-st-pilih-berkas">
              {fotoStSibuk ? "Mengunggah…" : "Pilih Foto…"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog hasil "Kirim ke TTD": tautan e-sign per penanda tangan ── */}
      <Dialog open={!!ttdHasil} onOpenChange={(o) => { if (!o) setTtdHasil(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="break-words">Tautan Tanda Tangan Elektronik</DialogTitle>
            <DialogDescription className="break-words">
              {ttdHasil?.judul} — bagikan tiap tautan ke penanda tangannya (berlaku 14 hari, sekali pakai).
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            {(ttdHasil?.links || []).map((l, i) => (
              <div key={i} className="rounded-lg border border-border p-2.5 text-xs space-y-1" data-testid={`ttd-link-${i}`}>
                <p className="font-semibold truncate">{l.nama}</p>
                <p className="text-[10px] text-muted-foreground break-all">{l.link}</p>
                <div className="flex gap-1.5">
                  <Button size="sm" variant="outline" className="h-7 text-[10px]"
                    onClick={() => { navigator.clipboard?.writeText(l.link); toast.success("Tautan disalin"); }}>Salin</Button>
                  <Button size="sm" variant="outline" className="h-7 text-[10px]"
                    onClick={() => bagikanWa(l.nama, ttdHasil?.judul, l.link, ttdHasil?.ringkas)}>WhatsApp</Button>
                  <Button size="sm" variant="outline" className="h-7 text-[10px]"
                    onClick={() => bagikanEmail(l.nama, ttdHasil?.judul, l.link, ttdHasil?.ringkas)}>Email</Button>
                </div>
              </div>
            ))}
            <p className="text-[10px] text-muted-foreground">
              Kelola lebih lanjut (terbitkan ulang tautan, unduh Lembar Pengesahan, pantau status) di menu <b>Tanda Tangan Elektronik</b>.
            </p>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Dialog Buat BAST Serah Terima (multi-aset, per jenis) ── */}
      <Dialog open={!!formBast} onOpenChange={(o) => { if (!o) setFormBast(null); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {formBast?.revisi ? "Revisi BAST" : "Buat BAST"} — {detail?.pemegang?.nama}
            </DialogTitle>
            <DialogDescription className="text-xs">
              {formBast?.revisi
                ? "BAST sah tidak diedit — revisi menerbitkan BAST PENGGANTI bernomor baru; arsip lama utuh dan diberi penanda telah direvisi."
                : "Multi-aset dalam satu BAST; nomor bisa dipesan lewat tombol Booking Nomor lalu ditempel di sini."}
            </DialogDescription>
          </DialogHeader>
          {formBast?.revisi && (
            <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-2.5 space-y-2" data-testid="bast-revisi-banner">
              <p className="text-[11px] text-amber-800 dark:text-amber-300">
                Menggantikan <span className="font-mono break-all">{formBast.revisi.dari_nomor}</span>
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <select value={formBast.revisi.mode}
                  onChange={(e) => setFormBast((f) => ({ ...f, revisi: { ...f.revisi, mode: e.target.value } }))}
                  className="h-8 rounded-md border border-input bg-background px-2 text-xs"
                  data-testid="bast-revisi-mode">
                  <option value="mengubah">Mengubah (koreksi isi — serah terima tetap terjadi)</option>
                  <option value="mencabut">Mencabut (serah terimanya dibatalkan)</option>
                </select>
              </div>
              <Input value={formBast.revisi.alasan}
                onChange={(e) => setFormBast((f) => ({ ...f, revisi: { ...f.revisi, alasan: e.target.value } }))}
                placeholder="Alasan revisi * (cth. salah ketik NIP penerima)"
                className="h-8 text-xs" data-testid="bast-revisi-alasan" />
            </div>
          )}
          {formBast && (
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium block mb-1">Jenis Serah Terima</label>
                  <select value={formBast.jenis} onChange={(e) => gantiJenisBast(e.target.value)}
                    className="w-full h-10 rounded-md border border-input bg-background px-2 text-sm" data-testid="bast-jenis">
                    {jenisBast.map((j) => <option key={j.kode} value={j.kode}>{j.uraian}</option>)}
                  </select>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    {{
                      penggunaan_melekat: "Barang melekat ke satu pegawai (laptop/HP dinas) — pemakaian sehari-hari.",
                      mutasi_pengguna: "Alih pemegang lama → baru; KPB ikut tanda tangan Mengetahui; bisa langsung memindahkan data pengguna aset.",
                      operasional_unit: "Barang dipakai bersama pada unit/tempat/tugas; bisa menambah penanggung jawab per unit.",
                      penggunaan_sementara: "Pinjam pakai internal ber-jangka waktu — wajib tanggal dari & sampai; barang tetap tercatat di satker.",
                      pengembalian: "Barang dikembalikan pegawai ke satker; bisa langsung mengosongkan data pengguna aset.",
                      lainnya: "Jenis bebas — judul BAST diketik sendiri.",
                    }[formBast.jenis] || ""}
                  </p>
                </div>
                <div>
                  <label className="text-xs font-medium block mb-1">Tanggal BAST</label>
                  <Input type="date" value={formBast.tanggal} onChange={(e) => setFormBast((f) => ({ ...f, tanggal: e.target.value }))} />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium block mb-1">Nomor (opsional — dari Booking Nomor)</label>
                <Input value={formBast.nomor} onChange={(e) => setFormBast((f) => ({ ...f, nomor: e.target.value }))} className="font-mono" placeholder={formBast.booking_otomatis ? "otomatis dari Persuratan" : "kosong = titik-titik utk diisi"} disabled={formBast.booking_otomatis} data-testid="bast-nomor" />
                <label className="flex items-center gap-2 text-[11px] mt-1 cursor-pointer">
                  <input type="checkbox" checked={formBast.booking_otomatis} className="w-3.5 h-3.5" data-testid="bast-booking-otomatis"
                    onChange={(e) => setFormBast((f) => ({ ...f, booking_otomatis: e.target.checked, nomor: e.target.checked ? "" : f.nomor }))} />
                  Pesan nomor otomatis dari Registrasi Persuratan (tercatat di buku agenda)
                </label>
                {/* Parameter SAMA dengan jalur booking backend (bast.py):
                    modul penggunaan + Berita Acara + tanggal BAST. */}
                <PerkiraanNomor aktif={formBast.booking_otomatis} modul="penggunaan"
                  jenisNaskah="Berita Acara" tanggal={formBast.tanggal}
                  testId="bast-perkiraan-nomor" />
              </div>
              {formBast.jenis === "mutasi_pengguna" && (
                <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-2.5 space-y-2">
                  <p className="text-[11px] font-semibold text-amber-700 dark:text-amber-300">Pemegang lama (PIHAK KESATU) — menyerahkan</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {/* Terhubung Master Pegawai (datalist sama dgn Penerima):
                        nama cocok → NIP & jabatan terisi otomatis (audit W4).
                        Tap kartu e-KTP juga bisa (tombol ikon kartu). */}
                    <div className="flex gap-1.5 min-w-0">
                    <Input value={formBast.pihak_pertama.nama} list="bast-pegawai-list"
                      placeholder="Nama pemegang lama *" data-testid="bast-lama-nama"
                      className="flex-1 min-w-0"
                      onChange={(e) => {
                        const v = e.target.value;
                        const m = (pegawaiList || []).find((x) => (x.nama || "") === v);
                        setFormBast((f) => ({ ...f, pihak_pertama: {
                          ...f.pihak_pertama, nama: v,
                          ...(m ? { nip: m.nip || f.pihak_pertama.nip,
                                    jabatan: m.jabatan || f.pihak_pertama.jabatan,
                                    alamat: (m.alamat || m.unit_kerja || m.unit_organisasi || "").trim() || f.pihak_pertama.alamat } : {}) } }));
                      }} />
                    <button type="button" title="Tap kartu pegawai (e-KTP/NFC)"
                      onClick={() => setKartuTapUntuk("pihak_pertama")}
                      className="h-9 px-2 rounded-md border border-input bg-card hover:bg-accent flex items-center shrink-0 min-w-0 min-h-0"
                      data-testid="bast-lama-tap-kartu">
                      <IdCard className="w-4 h-4 text-blue-600" />
                    </button>
                    </div>
                    <Input value={formBast.pihak_pertama.nip} placeholder="NIP/NIK" className="font-mono"
                      onChange={(e) => setFormBast((f) => ({ ...f, pihak_pertama: { ...f.pihak_pertama, nip: e.target.value } }))} />
                    <Input value={formBast.pihak_pertama.jabatan} placeholder="Jabatan" className="col-span-2"
                      onChange={(e) => setFormBast((f) => ({ ...f, pihak_pertama: { ...f.pihak_pertama, jabatan: e.target.value } }))} />
                    <Input value={formBast.pihak_pertama.alamat} placeholder="Alamat/lokasi pihak kesatu (boleh diisi manual)"
                      className="col-span-2" data-testid="bast-lama-alamat"
                      onChange={(e) => setFormBast((f) => ({ ...f, pihak_pertama: { ...f.pihak_pertama, alamat: e.target.value } }))} />
                  </div>
                  <p className="text-[10px] text-amber-700/80 dark:text-amber-300/80">Isian Penerima di bawah = pemegang BARU; KPB ikut menandatangani sebagai Mengetahui.</p>
                </div>
              )}
              {["mutasi_pengguna", "pengembalian", "pengembalian_almarhum"].includes(formBast.jenis) && (
                <label className="flex items-center gap-2 text-xs cursor-pointer">
                  <input type="checkbox" checked={formBast.terapkan_ke_aset} className="w-3.5 h-3.5" data-testid="bast-terapkan"
                    onChange={(e) => setFormBast((f) => ({ ...f, terapkan_ke_aset: e.target.checked }))} />
                  {formBast.jenis === "mutasi_pengguna"
                    ? "Handover langsung: pindahkan pengguna aset ke pemegang baru"
                    : "Kosongkan pengguna pada aset (barang kembali ke satker)"}
                </label>
              )}
              {formBast.jenis === "penggunaan_sementara" && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div><label className="text-xs font-medium block mb-1">Jangka: dari *</label>
                    <Input type="date" value={formBast.jangka_dari} onChange={(e) => setFormBast((f) => ({ ...f, jangka_dari: e.target.value }))} /></div>
                  <div><label className="text-xs font-medium block mb-1">sampai *</label>
                    <Input type="date" value={formBast.jangka_sampai} onChange={(e) => setFormBast((f) => ({ ...f, jangka_sampai: e.target.value }))} /></div>
                </div>
              )}
              {formBast.jenis !== "mutasi_pengguna" && (
                <div>
                  <label className="text-xs font-medium block mb-1">
                    {formBast.jenis === "pengembalian"
                      ? "Yang menerima (PIHAK KESATU — wakil satker)"
                      : "Yang menyerahkan (PIHAK KESATU)"} — dari Referensi Pejabat
                  </label>
                  <select value={formBast.penyerah.id} data-testid="bast-penyerah"
                    className="w-full h-10 rounded-md border border-input bg-background px-2 text-sm"
                    onChange={(e) => pilihPenyerah(e.target.value)}>
                    <option value="">Otomatis: Kuasa Pengguna Barang (KPB) dari pengaturan</option>
                    {pejabatPenyerah.map((p) => (
                      <option key={p.id} value={p.id}>{p.nama}{p.jabatan ? ` — ${p.jabatan}` : ""}</option>
                    ))}
                  </select>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    {pejabatPenyerah.length === 0
                      ? "Belum ada pejabat penyerah — sementara memakai KPB."
                      : "Kosong = otomatis memakai KPB aktif."}
                  </p>
                  <Lipatan judul="Peran apa saja yang boleh menyerahkan?" className="mt-0.5">
                    Hanya peran pengelolaan BMN: KPB, Petugas Penatausahaan, atau
                    Pengelola BMN Satker a.n. KPB — berlaku pada tanggal BAST.
                    {pejabatPenyerah.length === 0
                      ? " Tambahkan di halaman Referensi Pejabat dengan salah satu peran itu."
                      : ""}
                  </Lipatan>
                  <div className="mt-2">
                    <label className="text-xs font-medium block mb-1">Alamat/Lokasi PIHAK KESATU</label>
                    <Input value={formBast.alamat_pihak1}
                      placeholder="kosong = alamat kantor satker (pengaturan kop)"
                      data-testid="bast-alamat-pihak1"
                      onChange={(e) => setFormBast((f) => ({ ...f, alamat_pihak1: e.target.value }))} />
                  </div>
                </div>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div><label className="text-xs font-medium block mb-1">Penerima (PIHAK KEDUA) *</label>
                  <div className="flex gap-1.5">
                  <Input value={formBast.pihak_kedua.nama} list="bast-pegawai-list"
                    placeholder="ketik nama — saran dari Master Pegawai"
                    className="flex-1 min-w-0"
                    onChange={(e) => {
                      const v = e.target.value;
                      // Nama persis cocok dengan Master Pegawai → NIP & jabatan terisi otomatis.
                      const m = (pegawaiList || []).find((x) => (x.nama || "") === v);
                      setFormBast((f) => ({ ...f, pihak_kedua: m
                        ? { ...f.pihak_kedua, nama: v, nip: m.nip || f.pihak_kedua.nip, jabatan: m.jabatan || f.pihak_kedua.jabatan,
                            alamat: (m.alamat || m.unit_kerja || m.unit_organisasi || "").trim() || f.pihak_kedua.alamat }
                        : { ...f.pihak_kedua, nama: v } }));
                    }} data-testid="bast-penerima" />
                  {/* Tap kartu e-KTP penerima → identitas terisi otomatis */}
                  <button type="button" title="Tap kartu pegawai (e-KTP/NFC)"
                    onClick={() => setKartuTapUntuk("pihak_kedua")}
                    className="h-9 px-2 rounded-md border border-input bg-card hover:bg-accent flex items-center shrink-0 min-w-0 min-h-0"
                    data-testid="bast-penerima-tap-kartu">
                    <IdCard className="w-4 h-4 text-blue-600" />
                  </button>
                  </div>
                  {/* Almarhum tak ditawarkan sebagai penerima — server juga
                      menolaknya (serah terima kepada yang telah meninggal
                      mustahil); gunakan alur pengembalian BMN almarhum. */}
                  <datalist id="bast-pegawai-list">
                    {(pegawaiList || []).filter((x) => String(x?.status || "") !== "meninggal").map((x) => (
                      <option key={x.id || x.nip || x.nama} value={x.nama}>{x.nip ? `NIP ${x.nip}` : ""}</option>
                    ))}
                  </datalist></div>
                <div><label className="text-xs font-medium block mb-1">NIP/NIK</label>
                  <Input value={formBast.pihak_kedua.nip} onChange={(e) => setFormBast((f) => ({ ...f, pihak_kedua: { ...f.pihak_kedua, nip: e.target.value } }))} className="font-mono" /></div>
                <div><label className="text-xs font-medium block mb-1">Jabatan</label>
                  <Input value={formBast.pihak_kedua.jabatan} onChange={(e) => setFormBast((f) => ({ ...f, pihak_kedua: { ...f.pihak_kedua, jabatan: e.target.value } }))} /></div>
                <div><label className="text-xs font-medium block mb-1">Alamat/Unit</label>
                  <Input value={formBast.pihak_kedua.alamat} onChange={(e) => setFormBast((f) => ({ ...f, pihak_kedua: { ...f.pihak_kedua, alamat: e.target.value } }))} /></div>
              </div>
              {formBast.jenis === "pengembalian_almarhum" && (
                <div className="space-y-2 rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50/60 dark:bg-amber-950/30 p-2.5">
                  <p className="text-[11px] text-amber-800 dark:text-amber-200">
                    <b>Dasar berita acara.</b> Yang menyerahkan adalah <b>ahli waris / atasan
                    langsung</b> (isi di PIHAK KEDUA di atas), bukan almarhum. BAST lama atas
                    nama almarhum <b>tetap sah</b> dan tidak dibatalkan.
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <div><label className="text-xs font-medium block mb-1">Nama Almarhum *</label>
                      <Input value={formBast.almarhum.nama} data-testid="bast-almarhum-nama"
                        onChange={(e) => setFormBast((f) => ({ ...f, almarhum: { ...f.almarhum, nama: e.target.value } }))} /></div>
                    <div><label className="text-xs font-medium block mb-1">NIP Almarhum</label>
                      <Input value={formBast.almarhum.nip} className="font-mono"
                        onChange={(e) => setFormBast((f) => ({ ...f, almarhum: { ...f.almarhum, nip: e.target.value } }))} /></div>
                    <div><label className="text-xs font-medium block mb-1">Tanggal Meninggal *</label>
                      <Input type="date" value={formBast.almarhum.tanggal_meninggal} data-testid="bast-almarhum-tanggal"
                        onChange={(e) => setFormBast((f) => ({ ...f, almarhum: { ...f.almarhum, tanggal_meninggal: e.target.value } }))} /></div>
                    <div><label className="text-xs font-medium block mb-1">Nomor Akta Kematian</label>
                      <Input value={formBast.almarhum.nomor_akta_kematian}
                        onChange={(e) => setFormBast((f) => ({ ...f, almarhum: { ...f.almarhum, nomor_akta_kematian: e.target.value } }))} /></div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium block">Saksi (wajib minimal 2 — pemegang berhalangan tetap)</label>
                    {(formBast.saksi || []).map((sk, i) => (
                      <div key={i} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-1.5">
                        <Input value={sk.nama} placeholder={`Nama saksi ${i + 1}`} data-testid={`bast-saksi-nama-${i}`}
                          onChange={(e) => setFormBast((f) => ({ ...f, saksi: f.saksi.map((x, j) => j === i ? { ...x, nama: e.target.value } : x) }))} />
                        <Input value={sk.jabatan} placeholder="Jabatan"
                          onChange={(e) => setFormBast((f) => ({ ...f, saksi: f.saksi.map((x, j) => j === i ? { ...x, jabatan: e.target.value } : x) }))} />
                        <button type="button" className="px-2 rounded border border-border text-muted-foreground hover:bg-muted min-w-0 min-h-0"
                          aria-label={`Hapus saksi ${i + 1}`}
                          onClick={() => setFormBast((f) => ({ ...f, saksi: f.saksi.filter((_, j) => j !== i) }))}><X className="w-3.5 h-3.5" /></button>
                      </div>
                    ))}
                    <button type="button" className="text-[11px] font-semibold text-sky-600 dark:text-sky-400 min-w-0 min-h-0"
                      onClick={() => setFormBast((f) => ({ ...f, saksi: [...(f.saksi || []), { nama: "", jabatan: "", nip: "" }] }))}>
                      + Tambah saksi
                    </button>
                  </div>
                </div>
              )}
              {formBast.jenis === "operasional_unit" && (
                <div className="space-y-1.5">
                  <label className="text-xs font-medium block">Penanggung jawab tambahan per unit/tempat/tugas (opsional)</label>
                  {formBast.pj_tambahan.map((pj, i) => (
                    <div key={i} className="flex gap-2">
                      <Input value={pj.nama} placeholder="Nama" onChange={(e) => setFormBast((f) => ({ ...f, pj_tambahan: f.pj_tambahan.map((x, j) => j === i ? { ...x, nama: e.target.value } : x) }))} />
                      <Input value={pj.unit_tempat_tugas} placeholder="Unit/tempat/tugas" onChange={(e) => setFormBast((f) => ({ ...f, pj_tambahan: f.pj_tambahan.map((x, j) => j === i ? { ...x, unit_tempat_tugas: e.target.value } : x) }))} />
                      <button type="button" className="p-1.5 rounded text-red-500 hover:bg-red-500/10 min-w-0 min-h-0" aria-label="Hapus baris"
                        onClick={() => setFormBast((f) => ({ ...f, pj_tambahan: f.pj_tambahan.filter((_, j) => j !== i) }))}><X className="w-3.5 h-3.5" /></button>
                    </div>
                  ))}
                  <Button size="sm" variant="outline" className="h-7 text-[11px]"
                    onClick={() => setFormBast((f) => ({ ...f, pj_tambahan: [...f.pj_tambahan, { nama: "", unit_tempat_tugas: "" }] }))}>
                    <Plus className="w-3 h-3 mr-1" />Tambah penanggung jawab
                  </Button>
                </div>
              )}
              <div>
                <label className="text-xs font-medium block mb-1">Aset yang diserahterimakan ({formBast.aset.size} dipilih)</label>
                <div className="max-h-36 overflow-y-auto border border-border rounded-lg divide-y divide-border/60">
                  {(detail?.rows || []).map((a) => (
                    <label key={a.id} className="flex items-center gap-2 px-2.5 py-1.5 text-xs cursor-pointer hover:bg-muted">
                      <input type="checkbox" checked={formBast.aset.has(a.id)} className="w-3.5 h-3.5"
                        onChange={(e) => setFormBast((f) => { const s = new Set(f.aset); if (e.target.checked) s.add(a.id); else s.delete(a.id); return { ...f, aset: s }; })} />
                      <span className="font-mono">{a.asset_code}·{a.NUP}</span>
                      <span className="truncate flex-1">{a.asset_name}</span>
                    </label>
                  ))}
                </div>
              </div>
              <label className="flex items-start gap-2 text-xs cursor-pointer">
                <input type="checkbox" checked={formBast.sertakan_foto} className="w-3.5 h-3.5 mt-0.5 shrink-0" data-testid="bast-foto"
                  onChange={(e) => setFormBast((f) => ({ ...f, sertakan_foto: e.target.checked }))} />
                <span>Sertakan lampiran foto: <b>foto barang</b> (sampul tiap aset) + <b>foto serah terima</b> (dari scan bukti TTD BAST, bila berupa gambar)</span>
              </label>
              <label className="flex items-start gap-2 text-xs cursor-pointer">
                <input type="checkbox" checked={!!formBast.tampilkan_nilai}
                  className="w-3.5 h-3.5 mt-0.5 shrink-0" data-testid="bast-tampilkan-nilai"
                  onChange={(e) => setFormBast((f) => ({ ...f, tampilkan_nilai: e.target.checked }))} />
                <span>
                  Tampilkan kolom <b>Nilai Perolehan</b> pada PDF
                  {" "}<span className="text-muted-foreground">
                    — bawaan mengikuti kebijakan satker (Pengaturan → Satker); banyak satker
                    menutup nilai pada naskah yang dipegang pegawai. Pilihan ini dibekukan
                    bersama dokumen.
                  </span>
                </span>
              </label>
              <div>
                <label className="text-xs font-medium block mb-1">Pasal/ketentuan tambahan (opsional)</label>
                <Textarea value={formBast.keterangan} rows={3} data-testid="bast-keterangan"
                  placeholder="Satu baris = satu butir ketentuan. Contoh:&#10;Pemeliharaan rutin menjadi tanggung jawab PIHAK KEDUA.&#10;Kerusakan akibat kelalaian diganti sesuai ketentuan."
                  onChange={(e) => setFormBast((f) => ({ ...f, keterangan: e.target.value }))} />
                <p className="text-[10px] text-muted-foreground mt-0.5">Tiap baris menjadi satu butir pada pasal "Ketentuan Tambahan".</p>
              </div>
              <div className="flex flex-wrap justify-end gap-2 pt-1">
                <Button variant="outline" onClick={() => setFormBast(null)}>Batal</Button>
                <Button onClick={kirimBast} disabled={formBast.saving} data-testid="bast-simpan">
                  {formBast.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : null}Simpan &amp; Unduh PDF
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={!!detail} onOpenChange={(o) => { if (!o) setDetail(null); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Aset — {detail?.pemegang?.nama}</DialogTitle>
            <DialogDescription className="text-xs">
              {[detail?.pemegang?.nip && `NIP ${detail.pemegang.nip}`, detail?.pemegang?.jabatan]
                .filter(Boolean).join(" · ") || "Daftar aset yang melekat pada pemegang ini"}
            </DialogDescription>
          </DialogHeader>
          {detail?.loading ? (
            <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-sky-600" /></div>
          ) : (
            <>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" className="h-8 text-xs min-h-0"
                onClick={() => downloadFileWithProgress(
                  `${API}/penggunaan/pemegang/daftar-pdf?nama=${encodeURIComponent(detail?.pemegang?.nama || "")}&nip=${encodeURIComponent(detail?.pemegang?.nip || "")}`,
                  `Daftar_Barang_${(detail?.pemegang?.nama || "pemegang").replace(/\s/g, "_")}.pdf`,
                  { label: `Daftar Barang ${detail?.pemegang?.nama}` },
                ).catch(() => {})}
                data-testid="penggunaan-unduh-daftar">
                <FileText className="w-3.5 h-3.5 mr-1.5" />Unduh Daftar (PDF Lampiran BAST)
              </Button>
              <Button size="sm" className="h-8 text-xs min-h-0 bg-sky-600 hover:bg-sky-700 text-white"
                onClick={bukaBast} data-testid="penggunaan-buat-bast">
                <ScrollText className="w-3.5 h-3.5 mr-1.5" />Buat BAST Serah Terima
              </Button>
              <Button size="sm" variant="outline" className="h-8 text-xs min-h-0"
                onClick={bukaRiwayatBast} data-testid="penggunaan-riwayat-bast">
                <FileText className="w-3.5 h-3.5 mr-1.5" />Riwayat BAST
              </Button>
            </div>
            <ul className="space-y-2">
              {(detail?.rows || []).map((a) => (
                <li key={a.id} className="rounded-lg border border-border p-2.5 text-xs" data-testid={`penggunaan-aset-${a.id}`}>
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-semibold text-foreground">{a.asset_name || "-"}</p>
                    {a.bast_terakhir?.id && (
                      <span className="px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-700 dark:text-cyan-400 text-[10px] font-semibold"
                        title={`BAST ${a.bast_terakhir.jenis} — ${a.bast_terakhir.nomor || "tanpa nomor"} → ${a.bast_terakhir.penerima}`}>
                        BAST {String(a.bast_terakhir.tanggal || "").slice(0, 10)}
                      </span>
                    )}
                    {a.ada_bast ? (
                      <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 text-[10px] font-semibold">BAST ✓</span>
                    ) : a.bast_terakhir?.id ? (
                      <span className="px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 text-[10px] font-semibold"
                        title="BAST sudah dibuat — unggah bukti tanda tangan di Riwayat BAST agar tuntas">Bukti belum diunggah</span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 text-[10px] font-semibold">Tanpa BAST</span>
                    )}
                  </div>
                  <p className="text-muted-foreground mt-1 font-mono">{a.asset_code} · NUP {a.NUP}</p>
                  <p className="text-muted-foreground mt-0.5">
                    {[a.location, a.condition, a.inventory_status].filter(Boolean).join(" · ") || "—"}
                  </p>
                </li>
              ))}
            </ul>
            </>
          )}
        </DialogContent>
      </Dialog>
      {/* Tap kartu e-KTP → identitas pihak BAST terisi otomatis */}
      <KartuTapDialog open={!!kartuTapUntuk}
        onOpenChange={(o) => { if (!o) setKartuTapUntuk(null); }}
        onPegawai={(p) => {
          const pihak = kartuTapUntuk;
          if (!pihak || !p) return;
          // Null-guard: respons tap bisa tiba SETELAH dialog BAST ditutup
          // (form null) — tanpa guard, spread f[pihak] melempar & layar putih.
          setFormBast((f) => (f ? { ...f, [pihak]: {
            ...f[pihak], nama: p.nama || f[pihak]?.nama || "",
            nip: p.nip || f[pihak]?.nip || "",
            jabatan: p.jabatan || f[pihak]?.jabatan || "",
            alamat: (p.alamat || p.unit_kerja || p.unit_organisasi || "").trim() || f[pihak]?.alamat || "",
          } } : f));
        }} />

      {confirmDialog}
      {transitionDialog}
    </div>
  );
}
