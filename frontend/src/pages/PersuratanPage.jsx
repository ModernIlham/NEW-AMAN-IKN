import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Search, Loader2, Mail, MailPlus, Inbox, FileDown,
  CheckCircle2, XCircle, Pencil, Settings2, Plus, Trash2, GitBranch,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useBackGuard } from "@/hooks/useBackGuard";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import { labelAgenda, noAgendaTampil } from "@/lib/nomorAgenda";
import {
  sebutCakupan, statusKodeKlasifikasi, teksSumberKlasifikasi,
} from "@/lib/klasifikasiNomor";

import { KEPALA_HALAMAN, BARIS_KEPALA, BLOK_JUDUL, JUDUL_KEPALA,
  SUBJUDUL_KEPALA, TOMBOL_KEPALA, IKON_KEPALA,
} from "@/lib/kelasKepala";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function apiErr(e, fb) { return e?.response?.data?.detail || fb; }

const WARNA_STATUS = {
  dibooking: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  disahkan: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  dibatalkan: "bg-red-500/15 text-red-600 dark:text-red-400",
  diterima: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  diproses: "bg-indigo-500/15 text-indigo-600 dark:text-indigo-400",
  selesai: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
};

const LABEL_STATUS = {
  dibooking: "Dibooking", disahkan: "Disahkan", dibatalkan: "Dibatalkan",
  diterima: "Diterima", diproses: "Diproses", selesai: "Selesai",
};

const WARNA_KEBERLAKUAN = {
  berlaku: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  diubah: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  tidak_berlaku: "bg-red-500/15 text-red-600 dark:text-red-400",
  draf: "bg-muted text-muted-foreground",
};
const LABEL_KEBERLAKUAN = {
  berlaku: "Berlaku", diubah: "Diubah", tidak_berlaku: "Tidak Berlaku",
  draf: "Draf",
};

const KELUAR_KOSONG = {
  perihal: "", tujuan: "", jenis_naskah: "Laporan", modul: "umum",
  kegiatan_id: "", kode_klasifikasi: "", kode_keamanan: "B",
  tanggal_surat: "", referensi: "", nomor_eksternal: "", keterangan: "",
  sisipan: false,
};
const MASUK_KOSONG = {
  nomor_surat: "", pengirim: "", perihal: "", tanggal_surat: "",
  modul: "umum", kegiatan_id: "", keterangan: "",
};

/**
 * Persuratan — buku agenda & booking nomor naskah dinas lintas modul
 * (PerANRI 5/2021, pustaka §12). Surat keluar dipesan nomornya saat draf
 * (booking) lalu disahkan setelah ditandatangani atau dibatalkan (nomor
 * hangus — tidak didaur ulang); surat masuk teragenda dengan nomor sendiri.
 */
export default function PersuratanPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [data, setData] = useState(null);
  const [ref, setRef] = useState(null);
  const [kegiatan, setKegiatan] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fJenis, setFJenis] = useState("");
  const [fStatus, setFStatus] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [formKeluar, setFormKeluar] = useState(null);
  const [formMasuk, setFormMasuk] = useState(null);
  const [formAtur, setFormAtur] = useState(null);
  // Pratinjau format nomor di dialog pengaturan: {nomor, format_nomor,
  // placeholder}. Dihitung SERVER supaya aturan penyisipan placeholder dan
  // perakitan nomor tetap hanya ada di satu tempat.
  const [praFormat, setPraFormat] = useState(null);
  const praFormatTimer = useRef(null);
  const [batal, setBatal] = useState(null); // {surat, alasan}
  const [relasiSurat, setRelasiSurat] = useState(null); // surat utk dialog relasi/timeline
  const [saving, setSaving] = useState(false);
  const [pratinjau, setPratinjau] = useState(null); // {nomor, sumber_klasifikasi, ...}
  const [klasifikasi, setKlasifikasi] = useState([]); // master kode klasifikasi
  const [klasBaru, setKlasBaru] = useState({ kode: "", uraian: "" });
  const pratinjauTimer = useRef(null);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const load = useCallback(async (p = 1) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(p), page_size: "50" });
      if (fJenis) params.append("jenis", fJenis);
      if (fStatus) params.append("status", fStatus);
      if (q.trim()) params.append("q", q.trim());
      const r = await axios.get(`${API}/persuratan?${params}`);
      setData(r.data);
      setPage(p);
    } catch (e) {
      toast.error(apiErr(e, "Gagal memuat buku agenda"));
    } finally {
      setLoading(false);
    }
  }, [fJenis, fStatus, q]);

  useEffect(() => { load(1); }, [load]);

  useEffect(() => {
    axios.get(`${API}/persuratan/referensi`).then((r) => {
      setRef(r.data);
      setKlasifikasi(r.data?.klasifikasi || []);
    }).catch(() => {
      // Tanpa referensi, dropdown jenis naskah/klasifikasi kosong & form
      // booking tak bisa dipakai — jangan gagal senyap.
      toast.error("Gagal memuat referensi persuratan — muat ulang halaman untuk mencoba lagi");
    });
    axios.get(`${API}/inventory-activities`)
      .then((r) => setKegiatan(Array.isArray(r.data) ? r.data : (r.data?.items || [])))
      .catch(() => {});
  }, []);

  // Pratinjau nomor live: setiap field penentu nomor berubah → perkiraan
  // nomor berikutnya (counter TIDAK naik; keunikan tetap dijamin saat booking).
  useEffect(() => {
    if (!formKeluar || formKeluar.mode) { setPratinjau(null); return; }
    if (pratinjauTimer.current) clearTimeout(pratinjauTimer.current);
    pratinjauTimer.current = setTimeout(async () => {
      try {
        const params = new URLSearchParams({
          jenis_naskah: formKeluar.jenis_naskah || "",
          modul: formKeluar.modul || "",
          kode_klasifikasi: formKeluar.kode_klasifikasi || "",
          kode_keamanan: formKeluar.kode_keamanan || "B",
          tanggal_surat: formKeluar.tanggal_surat || "",
        });
        if (formKeluar.sisipan) params.append("sisipan", "true");
        const r = await axios.get(`${API}/persuratan/pratinjau-nomor?${params}`);
        setPratinjau(r.data);
      } catch { setPratinjau(null); }
    }, 350);
    return () => { if (pratinjauTimer.current) clearTimeout(pratinjauTimer.current); };
  }, [formKeluar]);

  const kirim = async (fn, sukses) => {
    setSaving(true);
    try {
      await fn();
      toast.success(sukses);
      setFormKeluar(null); setFormMasuk(null); setFormAtur(null); setBatal(null);
      load(page);
    } catch (e) {
      toast.error(apiErr(e, "Gagal menyimpan"));
    } finally {
      setSaving(false);
    }
  };

  const booking = () => {
    if (!formKeluar?.perihal?.trim()) { toast.error("Perihal wajib diisi"); return; }
    if (formKeluar?.sisipan && !formKeluar?.tanggal_surat) {
      toast.error("Nomor sisipan membutuhkan Tanggal Surat (tanggal backdate)"); return;
    }
    kirim(async () => {
      const r = await axios.post(`${API}/persuratan/keluar`, formKeluar);
      toast.info(`Nomor dibooking: ${r.data.nomor}`, { duration: 9000 });
    }, "Surat keluar terbooking");
  };

  const catatMasuk = () => {
    const f = formMasuk || {};
    if (!f.nomor_surat?.trim() || !f.pengirim?.trim() || !f.perihal?.trim()) {
      toast.error("Nomor surat, pengirim, dan perihal wajib diisi"); return;
    }
    kirim(() => axios.post(`${API}/persuratan/masuk`, formMasuk), "Surat masuk teragenda");
  };

  const transisi = (s, status, alasan = "") =>
    kirim(() => axios.post(`${API}/persuratan/${s.id}/status`, { status, alasan }),
      status === "disahkan" ? `Surat ${s.nomor} disahkan`
        : status === "dibatalkan" ? `Nomor ${s.nomor} dibatalkan (hangus)`
          : `Status → ${status}`);

  const hapusSurat = async (s) => {
    const ok = await confirm({
      title: `Hapus surat ${s.nomor}?`,
      description: s.jenis === "keluar"
        ? "Catatan booking ini dihapus permanen; nomor agenda yang telanjur terpakai hangus (tidak dipakai ulang)."
        : "Catatan surat masuk ini dihapus permanen dari buku agenda.",
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    kirim(() => axios.delete(`${API}/persuratan/${s.id}`), `Surat ${s.nomor} dihapus`);
  };

  /**
   * Minta server merakit ulang template + contoh nomornya.
   *
   * `komposisi` dikirim saat pilihan komposisi berubah — server mengembalikan
   * `format_nomor` hasil penyisipannya, dan kolom Format Nomor diperbarui
   * SEKETIKA. Sebelumnya kolom itu baru berubah setelah Simpan, sehingga
   * pilihan komposisi tampak tidak berpengaruh apa-apa.
   */
  const mintaPraFormat = useCallback((formatNomor, komposisi) => {
    if (praFormatTimer.current) clearTimeout(praFormatTimer.current);
    praFormatTimer.current = setTimeout(async () => {
      try {
        const q = new URLSearchParams();
        if (formatNomor) q.append("format_nomor", formatNomor);
        if (komposisi) q.append("komposisi", komposisi);
        const r = await axios.get(`${API}/persuratan/pratinjau-nomor?${q}`);
        setPraFormat(r.data);
        if (komposisi && r.data?.format_nomor) {
          setFormAtur((f) => (f ? { ...f, format_nomor: r.data.format_nomor } : f));
        }
      } catch { /* pratinjau bersifat bantuan — diam bila gagal */ }
    }, 250);
  }, []);

  const simpanAtur = async () => {
    // Respons POST berbentuk sama dengan GET, jadi form disegarkan dari
    // hasilnya: setelah komposisi nomor diubah, susunan `format_nomor` yang
    // BARU langsung terlihat alih-alih harus ditebak dari pilihan yang baru
    // ditekan. Scope satker tetap mengosongkan field warisan (lihat pemuat
    // pengaturan) supaya menyimpan tidak memaku salinan nilai Universal.
    await kirim(() => axios.post(`${API}/persuratan/pengaturan`, formAtur)
      .then((r) => {
        const d = { ...r.data };
        if (d.scope && d.sumber) {
          d.warisan = {
            format_nomor: d.format_nomor, kode_unit: d.kode_unit,
            kode_klasifikasi_default: d.kode_klasifikasi_default,
            reset_urut: d.reset_urut, peta_klasifikasi: d.peta_klasifikasi || [],
          };
          for (const f of ["format_nomor", "kode_unit",
            "kode_klasifikasi_default", "reset_urut"]) {
            if (d.sumber[f] !== "satker") d[f] = "";
          }
          if (d.sumber.peta_klasifikasi !== "satker") d.peta_klasifikasi = [];
        }
        setFormAtur((f) => (f ? d : f));
        return r;
      }), "Pengaturan tersimpan");
  };

  /** Jadikan satu kode katalog sebagai KODE BAWAAN semua surat. */
  const pakaiKlasSebagaiBawaan = (kode) => {
    setFormAtur((f) => ({ ...f, kode_klasifikasi_default: kode }));
    toast.info(`${kode} dijadikan kode bawaan — tekan Simpan untuk memberlakukan`);
  };

  const muatKlasifikasi = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/persuratan/klasifikasi`);
      setKlasifikasi(r.data?.items || []);
    } catch { /* abaikan */ }
  }, []);

  const tambahKlas = async () => {
    if (!klasBaru.kode.trim()) { toast.error("Kode klasifikasi wajib diisi"); return; }
    try {
      await axios.post(`${API}/persuratan/klasifikasi`, klasBaru);
      toast.success(`Kode ${klasBaru.kode} ditambahkan`);
      setKlasBaru({ kode: "", uraian: "" });
      muatKlasifikasi();
    } catch (e) { toast.error(apiErr(e, "Gagal menambah kode")); }
  };

  const hapusKlas = async (k) => {
    try {
      await axios.delete(`${API}/persuratan/klasifikasi/${k.id}`);
      toast.success(`Kode ${k.kode} dihapus`);
      muatKlasifikasi();
    } catch (e) { toast.error(apiErr(e, "Gagal menghapus kode")); }
  };

  const setAturan = (i, field, value) => setFormAtur((f) => ({
    ...f,
    peta_klasifikasi: (f.peta_klasifikasi || []).map((a, j) =>
      j === i ? { ...a, [field]: value } : a),
  }));

  // Pintasan "+ aturan" dari daftar master: satu klik memasangkan kode katalog
  // ke aturan otomatis. Inilah langkah yang dulu tak pernah terlihat — pemilik
  // menambah kode di master lalu menunggu efek yang tak mungkin datang.
  const pakaiKlasSebagaiAturan = (kode) => {
    setFormAtur((f) => {
      const peta = f?.peta_klasifikasi || [];
      const kosong = peta.findIndex((a) => !String(a?.kode || "").trim());
      const baru = kosong >= 0
        ? peta.map((a, j) => (j === kosong ? { ...a, kode } : a))
        : [...peta, { modul: "", jenis_naskah: "", kode }];
      return { ...f, peta_klasifikasi: baru };
    });
    toast.info(`Aturan untuk ${kode} ditambahkan — pilih cakupannya, lalu Simpan`);
  };

  // Turunkan aturan Universal jadi milik satker supaya bisa diubah TANPA
  // kehilangan yang sudah berlaku (aturan satker menggantikan seluruh daftar
  // Universal, bukan menambahnya).
  const salinAturanUniversal = () => setFormAtur((f) => ({
    ...f,
    peta_klasifikasi: [...(f?.warisan?.peta_klasifikasi || [])].map((a) => ({
      modul: a.modul || "", jenis_naskah: a.jenis_naskah || "", kode: a.kode || "",
    })),
  }));

  const rk = data?.ringkasan;
  const items = data?.items || [];
  const adaFilter = !!(q.trim() || fJenis || fStatus); // pembeda "belum ada data" vs "hasil filter kosong"
  const setK = (k) => (e) => setFormKeluar((f) => ({ ...f, [k]: e.target.value }));
  const setM = (k) => (e) => setFormMasuk((f) => ({ ...f, [k]: e.target.value }));
  const opsiStatus = useMemo(() => (
    fJenis === "masuk" ? (ref?.status_masuk || [])
      : fJenis === "keluar" ? (ref?.status_keluar || [])
        : [...(ref?.status_keluar || []), ...(ref?.status_masuk || [])]
  ), [ref, fJenis]);

  // Aksi per surat — satu sumber untuk sel tabel (desktop) & kartu (mobile).
  const renderAksi = (s, sfx = "") => (
    <>
      {s.jenis === "keluar" && s.status === "dibooking" && (
        <>
          <Button size="sm" onClick={() => transisi(s, "disahkan")}
            title="Sahkan (surat final ditandatangani)" aria-label={`Sahkan ${s.nomor}`}
            className="h-7 text-[11px] min-h-0 min-w-0 bg-emerald-600 hover:bg-emerald-700 text-white"
            data-testid={`persuratan-sahkan-${s.id}${sfx}`}>
            <CheckCircle2 className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">Sahkan</span>
          </Button>
          <button type="button" onClick={() => setBatal({ surat: s, alasan: "" })}
            title="Batalkan (nomor hangus)" aria-label={`Batalkan ${s.nomor}`}
            className="p-1.5 rounded-md text-red-500 hover:bg-red-500/10 min-w-0 min-h-0"
            data-testid={`persuratan-batal-${s.id}${sfx}`}>
            <XCircle className="w-4 h-4" />
          </button>
          <button type="button" onClick={() => setFormKeluar({ ...KELUAR_KOSONG, ...s, mode: "edit" })}
            title="Ubah draf" aria-label={`Ubah ${s.nomor}`}
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted min-w-0 min-h-0"
            data-testid={`persuratan-edit-${s.id}${sfx}`}>
            <Pencil className="w-3.5 h-3.5" />
          </button>
        </>
      )}
      {s.jenis === "keluar" && s.status === "disahkan" && (
        <button type="button" onClick={() => setFormKeluar({ ...KELUAR_KOSONG, ...s, mode: "edit-final" })}
          title="Isi nomor eksternal / keterangan" aria-label={`Ubah nomor eksternal ${s.nomor}`}
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted min-w-0 min-h-0"
          data-testid={`persuratan-edit-final-${s.id}${sfx}`}>
          <Pencil className="w-3.5 h-3.5" />
        </button>
      )}
      {s.jenis === "masuk" && (
        <button type="button" onClick={() => setFormMasuk({ ...MASUK_KOSONG, ...s, nomor_surat: s.nomor, mode: "edit" })}
          title="Ubah surat masuk" aria-label={`Ubah surat masuk ${s.nomor}`}
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted min-w-0 min-h-0"
          data-testid={`persuratan-edit-masuk-${s.id}${sfx}`}>
          <Pencil className="w-3.5 h-3.5" />
        </button>
      )}
      {s.jenis === "masuk" && s.status !== "selesai" && (
        <Button size="sm"
          className={`h-7 text-[11px] min-h-0 min-w-0 text-white ${s.status === "diterima" ? "bg-cyan-600 hover:bg-cyan-700" : "bg-emerald-600 hover:bg-emerald-700"}`}
          onClick={() => transisi(s, s.status === "diterima" ? "diproses" : "selesai")}
          data-testid={`persuratan-masuk-lanjut-${s.id}${sfx}`}>
          {s.status === "diterima" ? "Proses" : "Selesai"}
        </Button>
      )}
      <button type="button" onClick={() => setRelasiSurat(s)}
        title="Relasi antar surat & timeline (mencabut/mengubah/menetapkan…)"
        aria-label={`Relasi ${s.nomor}`}
        className="p-1.5 rounded-md text-muted-foreground hover:text-cyan-700 dark:hover:text-cyan-400 hover:bg-cyan-500/10 min-w-0 min-h-0"
        data-testid={`persuratan-relasi-${s.id}${sfx}`}>
        <GitBranch className="w-3.5 h-3.5" />
      </button>
      {isAdmin && !(s.jenis === "keluar" && s.status === "disahkan") && (
        <button type="button" onClick={() => hapusSurat(s)}
          title="Hapus surat (salah catat / batal dibuat)"
          aria-label={`Hapus ${s.nomor}`}
          className="p-1.5 rounded-md text-red-500 hover:bg-red-500/10 min-w-0 min-h-0"
          data-testid={`persuratan-hapus-${s.id}${sfx}`}>
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      )}
    </>
  );

  return (
    <div className="min-h-screen bg-background" data-testid="persuratan-page">
      <header className={KEPALA_HALAMAN}>
        <div className={`max-w-6xl mx-auto ${BARIS_KEPALA}`}>
          <button type="button" onClick={onBack} aria-label="Kembali"
            className={TOMBOL_KEPALA}
            data-testid="persuratan-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className={`bg-cyan-700 ${IKON_KEPALA}`}>
            <Mail className="w-4 h-4 text-white" />
          </span>
          <div className={BLOK_JUDUL}>
            <h1 className={JUDUL_KEPALA}>Registrasi Persuratan</h1>
            <p className={SUBJUDUL_KEPALA}>
              Buku agenda & booking nomor naskah dinas lintas modul (PerANRI 5/2021)
            </p>
          </div>
          {isAdmin && (
            <Button variant="outline" size="sm" className="gap-1.5"
              title="Pengaturan format nomor" aria-label="Pengaturan format nomor"
              onClick={async () => {
                try {
                  const r = await axios.get(`${API}/persuratan/pengaturan`);
                  const d = { ...r.data };
                  // Scope SATKER: field warisan Universal DIKOSONGKAN di form
                  // (nilai efektifnya jadi placeholder) — kalau nilai warisan
                  // ikut terkirim, sekali "Simpan" memaku salinannya sebagai
                  // override dan satker tak lagi mengikuti perubahan Universal.
                  if (d.scope && d.sumber) {
                    d.warisan = {
                      format_nomor: d.format_nomor, kode_unit: d.kode_unit,
                      kode_klasifikasi_default: d.kode_klasifikasi_default,
                      reset_urut: d.reset_urut,
                      // Aturan warisan DISIMPAN, bukan dibuang: tanpa ini layar
                      // satker menampilkan daftar aturan KOSONG padahal aturan
                      // Universal sedang berlaku — lalu satu aturan sendiri
                      // diam-diam mematikan semuanya. Keduanya tak terlihat.
                      peta_klasifikasi: d.peta_klasifikasi || [],
                    };
                    for (const f of ["format_nomor", "kode_unit",
                      "kode_klasifikasi_default", "reset_urut"]) {
                      if (d.sumber[f] !== "satker") d[f] = "";
                    }
                    if (d.sumber.peta_klasifikasi !== "satker") d.peta_klasifikasi = [];
                  }
                  setFormAtur(d);
                  setPraFormat(null);
                  // Contoh nomor untuk susunan yang BERLAKU, tampil begitu
                  // dialog dibuka — bukan hanya setelah sesuatu diubah.
                  mintaPraFormat(d.format_nomor || r.data.format_nomor, "");
                  muatKlasifikasi();
                } catch { toast.error("Gagal memuat pengaturan"); }
              }} data-testid="persuratan-atur-btn">
              <Settings2 className="w-3.5 h-3.5" /><span className="hidden sm:inline">Format Nomor</span>
            </Button>
          )}
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {rk && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2" data-testid="persuratan-ringkas">
            {[["Dibooking (belum sah)", rk.keluar_dibooking, "text-amber-600 dark:text-amber-400"],
              ["Keluar disahkan", rk.keluar_disahkan, "text-emerald-600 dark:text-emerald-400"],
              ["Dibatalkan (hangus)", rk.keluar_dibatalkan, "text-red-600 dark:text-red-400"],
              ["Masuk belum selesai", rk.masuk_terbuka, "text-sky-600 dark:text-sky-400"],
            ].map(([label, n, cls]) => (
              <div key={label} className="bg-card rounded-xl border border-border shadow-sm px-3 py-2">
                <p className={`text-lg font-bold ${cls}`}>{n}</p>
                <p className="text-[10px] text-muted-foreground leading-tight">{label}</p>
              </div>
            ))}
          </div>
        )}

        {/* Toolbar: 1 baris penuh mulai tablet (label aksi diringkas s.d. lg
            agar cari + filter + 2 aksi muat sebaris di iPad mini 768).
            Di HP (<sm) tetap 2 baris: baris 1 cari + CSV, baris 2 filter + aksi. */}
        <div className="bg-card rounded-xl border border-border shadow-sm p-2 sm:p-3 flex items-center gap-2 flex-wrap md:flex-nowrap">
          <div className="flex items-center gap-2 basis-full sm:basis-auto sm:flex-1 min-w-0">
            <div className="relative flex-1 min-w-0">
              <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
              <Input value={q} onChange={(e) => setQ(e.target.value)}
                placeholder="Cari nomor / perihal / tujuan / pengirim…" className="pl-9 h-10"
                data-testid="persuratan-cari" />
            </div>
            <Button variant="outline" className="h-10 gap-1.5 flex-shrink-0 px-2.5 lg:px-3"
              title="Unduh buku agenda (CSV)" aria-label="Unduh buku agenda (CSV)"
              onClick={() => downloadFileWithProgress(`${API}/persuratan/export${fJenis ? `?jenis=${fJenis}` : ""}`, "Buku_Agenda_Surat.csv", { label: "Buku Agenda (CSV)" }).catch(() => {})}
              data-testid="persuratan-export">
              <FileDown className="w-4 h-4" /><span className="hidden lg:inline">CSV</span>
            </Button>
          </div>
          <select value={fJenis} onChange={(e) => { setFJenis(e.target.value); setFStatus(""); }}
            aria-label="Filter jenis surat" title="Filter jenis surat"
            className="h-10 rounded-md border border-input bg-background px-2 text-xs sm:text-sm flex-1 sm:flex-none min-w-0" data-testid="persuratan-f-jenis">
            <option value="">Jenis</option>
            <option value="keluar">Surat Keluar</option>
            <option value="masuk">Surat Masuk</option>
          </select>
          <select value={fStatus} onChange={(e) => setFStatus(e.target.value)}
            aria-label="Filter status surat" title="Filter status surat"
            className="h-10 rounded-md border border-input bg-background px-2 text-xs sm:text-sm flex-1 sm:flex-none min-w-0" data-testid="persuratan-f-status">
            <option value="">Status</option>
            {opsiStatus.map((s) => <option key={s.kode} value={s.kode}>{s.uraian}</option>)}
          </select>
          <Button className="h-10 gap-1.5 flex-shrink-0 px-2.5 lg:px-3" onClick={() => setFormKeluar({ ...KELUAR_KOSONG })}
            title="Booking nomor surat keluar" data-testid="persuratan-booking-btn">
            <MailPlus className="w-4 h-4" /><span className="hidden lg:inline">Booking Surat Keluar</span><span className="lg:hidden">Keluar</span>
          </Button>
          <Button variant="outline" className="h-10 gap-1.5 flex-shrink-0 px-2.5 lg:px-3" onClick={() => setFormMasuk({ ...MASUK_KOSONG })}
            title="Catat surat masuk" data-testid="persuratan-masuk-btn">
            <Inbox className="w-4 h-4" /><span className="hidden lg:inline">Catat Surat Masuk</span><span className="lg:hidden">Masuk</span>
          </Button>
        </div>

        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
          {loading && !data ? (
            <div className="flex items-center justify-center py-16"><Loader2 className="w-7 h-7 animate-spin text-cyan-700" /></div>
          ) : items.length === 0 ? (
            <div className="text-center py-16 px-4">
              <Mail className="w-10 h-10 text-muted-foreground/40 mx-auto mb-3" />
              <p className="text-sm font-medium text-foreground">
                {adaFilter ? "Tidak ada surat yang cocok" : "Belum ada surat teragenda"}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {adaFilter
                  ? "Coba kata kunci lain atau hapus filter pencarian."
                  : "Booking nomor surat keluar SEBELUM naskah difinalkan, lalu sahkan setelah ditandatangani."}
              </p>
              {adaFilter ? (
                <Button variant="outline" size="sm" className="mt-3"
                  onClick={() => { setQ(""); setFJenis(""); setFStatus(""); }}
                  data-testid="persuratan-clear-filter">
                  Hapus pencarian
                </Button>
              ) : (
                <Button size="sm" className="mt-3 gap-1.5 bg-cyan-600 hover:bg-cyan-700 text-white"
                  onClick={() => setFormKeluar({ ...KELUAR_KOSONG })} data-testid="persuratan-empty-booking">
                  <MailPlus className="w-4 h-4" />Booking Surat Keluar
                </Button>
              )}
            </div>
          ) : (
            <>
            {/* Mobile (<sm): kartu bertumpuk — tabel 860px + kolom sticky
                menutupi Perihal/Dari di layar sempit (umpan balik tangkapan layar). */}
            <ul className="sm:hidden divide-y divide-border/60" data-testid="persuratan-cards-mobile">
              {items.map((s) => (
                <li key={s.id} className="p-3 space-y-1" data-testid={`persuratan-card-${s.id}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${s.jenis === "keluar" ? "bg-cyan-500/15 text-cyan-700 dark:text-cyan-400" : "bg-violet-500/15 text-violet-600 dark:text-violet-400"}`}>
                      {labelAgenda(s)}
                    </span>
                    {/* `flex-wrap` + `justify-end`: dua lencana pada nomor
                        agenda panjang boleh turun baris alih-alih menggencet
                        lencana agenda di sebelah kiri. */}
                    <span className="flex flex-wrap items-center justify-end gap-1">
                      <span className={`whitespace-nowrap px-2 py-0.5 rounded-full text-[10px] font-semibold ${WARNA_STATUS[s.status] || "bg-muted text-muted-foreground"}`}>
                        {LABEL_STATUS[s.status] || s.status}
                      </span>
                      {s.keberlakuan && s.keberlakuan !== "berlaku" && s.keberlakuan !== "draf" && (
                        <span className={`whitespace-nowrap px-2 py-0.5 rounded-full text-[10px] font-semibold ${WARNA_KEBERLAKUAN[s.keberlakuan] || "bg-muted"}`}
                          title={s.keberlakuan_label} data-testid={`keberlakuan-hp-${s.id}`}>
                          {LABEL_KEBERLAKUAN[s.keberlakuan] || s.keberlakuan}
                        </span>
                      )}
                    </span>
                  </div>
                  <p className="font-mono text-[12px] text-foreground break-words leading-snug">{s.nomor}</p>
                  {s.nomor_eksternal && (
                    <p className="font-mono text-[10px] text-teal-700 dark:text-teal-400 break-words" title="Nomor sah dari aplikasi eksternal">eks: {s.nomor_eksternal}</p>
                  )}
                  <p className="text-[12px] text-foreground/90 line-clamp-2" title={s.perihal}>{s.perihal}</p>
                  {(s.referensi || s.nama_kegiatan) && (
                    <p className="text-[10px] text-muted-foreground truncate" title={[s.referensi, s.nama_kegiatan].filter(Boolean).join(" · ")}>{[s.referensi, s.nama_kegiatan].filter(Boolean).join(" · ")}</p>
                  )}
                  {s.alasan_batal && (
                    <p className="text-[10px] text-red-500/80 truncate" title={s.alasan_batal}>{s.alasan_batal}</p>
                  )}
                  <div className="flex items-center justify-between gap-2 pt-0.5">
                    <p className="text-[10px] text-muted-foreground truncate min-w-0">
                      {[s.tanggal_surat,
                        s.jenis === "keluar" ? (s.tujuan ? `→ ${s.tujuan}` : "") : (s.pengirim ? `← ${s.pengirim}` : ""),
                      ].filter(Boolean).join(" · ") || "—"}
                    </p>
                    <div className="flex items-center gap-0.5 flex-shrink-0">{renderAksi(s, "-m")}</div>
                  </div>
                </li>
              ))}
            </ul>
            <div className="hidden sm:block overflow-x-auto">
              <table className="w-full text-sm min-w-[860px]">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                    <th className="px-3 py-2.5 font-semibold">Agenda</th>
                    <th className="px-3 py-2.5 font-semibold">Nomor / Tanggal</th>
                    <th className="px-3 py-2.5 font-semibold">Perihal</th>
                    <th className="px-3 py-2.5 font-semibold">Dari / Kepada</th>
                    <th className="px-3 py-2.5 font-semibold hidden md:table-cell">Naskah · Modul</th>
                    <th className="px-3 py-2.5 font-semibold">Status</th>
                    {/* Aksi (Sahkan/Batalkan — inti alur booking) menempel di
                        kanan saat tabel discroll di layar kecil. */}
                    <th className="px-3 py-2.5 font-semibold text-right sticky right-0 bg-muted/95 border-l border-border">Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((s) => (
                    <tr key={s.id} className="border-b border-border/60 last:border-0 hover:bg-muted/50" data-testid={`persuratan-row-${s.id}`}>
                      <td className="px-3 py-2 whitespace-nowrap">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${s.jenis === "keluar" ? "bg-cyan-500/15 text-cyan-700 dark:text-cyan-400" : "bg-violet-500/15 text-violet-600 dark:text-violet-400"}`}>
                          {labelAgenda(s)}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <p className="font-mono text-[12px] text-foreground break-all">{s.nomor}</p>
                        {s.nomor_eksternal && (
                          <p className="font-mono text-[10px] text-teal-700 dark:text-teal-400 break-all" title="Nomor sah dari aplikasi eksternal">eks: {s.nomor_eksternal}</p>
                        )}
                        <p className="text-[10px] text-muted-foreground">{s.tanggal_surat || "—"}</p>
                      </td>
                      <td className="px-3 py-2 max-w-[280px]">
                        <p className="text-[12px] text-foreground/90 line-clamp-2" title={s.perihal}>{s.perihal}</p>
                        {(s.referensi || s.nama_kegiatan) && (
                          <p className="text-[10px] text-muted-foreground truncate" title={[s.referensi, s.nama_kegiatan].filter(Boolean).join(" · ")}>{[s.referensi, s.nama_kegiatan].filter(Boolean).join(" · ")}</p>
                        )}
                      </td>
                      <td className="px-3 py-2 text-[12px] text-foreground/80">{s.jenis === "keluar" ? (s.tujuan || "—") : (s.pengirim || "—")}</td>
                      <td className="px-3 py-2 hidden md:table-cell">
                        <p className="text-[11px] text-foreground/80">{s.jenis_naskah || "—"}</p>
                        <p className="text-[10px] text-muted-foreground">{s.modul}</p>
                      </td>
                      {/* Status + keberlakuan DITUMPUK, bukan berjajar.
                          Sebelumnya sel ini `whitespace-nowrap` sementara kedua
                          lencana berupa elemen inline: keduanya terpaksa satu
                          baris, tak boleh turun, sehingga lencana kedua
                          ("Tidak Berlaku") terpotong di tepi kolom. `nowrap`
                          kini melekat pada tiap lencana — yang memang perlu,
                          supaya "Tidak Berlaku" tak patah jadi dua baris —
                          bukan pada selnya. */}
                      <td className="px-3 py-2">
                        <div className="flex flex-col items-start gap-0.5 max-w-[128px]">
                          <span className={`whitespace-nowrap px-2 py-0.5 rounded-full text-[10px] font-semibold ${WARNA_STATUS[s.status] || "bg-muted text-muted-foreground"}`}>
                            {LABEL_STATUS[s.status] || s.status}
                          </span>
                          {s.keberlakuan && s.keberlakuan !== "berlaku" && s.keberlakuan !== "draf" && (
                            <span className={`whitespace-nowrap px-2 py-0.5 rounded-full text-[10px] font-semibold ${WARNA_KEBERLAKUAN[s.keberlakuan] || "bg-muted"}`}
                              title={s.keberlakuan_label} data-testid={`keberlakuan-${s.id}`}>
                              {LABEL_KEBERLAKUAN[s.keberlakuan] || s.keberlakuan}
                            </span>
                          )}
                          {s.alasan_batal && <span className="text-[9px] text-red-500/80 max-w-full truncate" title={s.alasan_batal}>{s.alasan_batal}</span>}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-right whitespace-nowrap sticky right-0 bg-card border-l border-border">
                        {renderAksi(s)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            </>
          )}
          {data && data.total_pages > 1 && (
            <div className="flex items-center justify-between px-3 py-2 border-t border-border bg-muted/30">
              <Button size="sm" variant="ghost" disabled={page <= 1 || loading} onClick={() => load(page - 1)}>Sebelumnya</Button>
              <span className="text-[11px] text-muted-foreground">Hal {data.page}/{data.total_pages} · {data.total} surat</span>
              <Button size="sm" variant="ghost" disabled={page >= data.total_pages || loading} onClick={() => load(page + 1)}>Berikutnya</Button>
            </div>
          )}
        </div>

        <p className="text-center text-[10px] text-muted-foreground pb-4">
          Kaidah: nomor dipesan (booking) saat draf → disahkan setelah tanda tangan; nomor batal hangus &
          tercatat beralasan — urutan agenda tetap utuh (PerANRI 5/2021 · buku agenda kembar).
          Deret nomor kembali ke 001 tiap awal bulan (bisa diubah ke tahunan di Format Nomor);
          surat telat dibooking memakai nomor sisipan backdate (005 → 005.01).
          Tanda &quot;eks:&quot; pada kolom nomor = nomor sah dari aplikasi eksternal (Srikandi dll.).
        </p>
      </main>

      {/* ── Dialog booking / edit surat keluar ── */}
      <Dialog open={!!formKeluar} onOpenChange={(o) => { if (!o) setFormKeluar(null); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{formKeluar?.mode === "edit-final" ? `Nomor Eksternal — ${formKeluar?.nomor}` : formKeluar?.mode === "edit" ? `Ubah Draf — ${formKeluar?.nomor}` : "Booking Nomor Surat Keluar"}</DialogTitle>
            <DialogDescription className="text-xs">
              Nomor dipesan sekarang dan menjadi milik surat ini sampai disahkan/dibatalkan.
            </DialogDescription>
          </DialogHeader>
          {formKeluar && formKeluar.mode === "edit-final" && (
            <div className="space-y-3">
              <p className="text-[11px] text-muted-foreground">
                Surat sudah disahkan — hanya nomor eksternal (anchor dari aplikasi lain) dan keterangan yang dapat diubah.
              </p>
              <Field label="Nomor Eksternal (aplikasi lain)">
                <Input value={formKeluar.nomor_eksternal || ""} onChange={setK("nomor_eksternal")}
                  placeholder="nomor sah dari Srikandi/e-office" className="font-mono"
                  data-testid="final-nomor-eksternal" />
              </Field>
              <Field label="Keterangan"><Input value={formKeluar.keterangan || ""} onChange={setK("keterangan")} /></Field>
            </div>
          )}
          {formKeluar && formKeluar.mode !== "edit-final" && (
            <div className="space-y-3">
              <Field label="Perihal *"><Input value={formKeluar.perihal} onChange={setK("perihal")} placeholder="cth. Penyampaian LHI Semester I 2026" data-testid="keluar-perihal" /></Field>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Field label="Kepada / Tujuan"><Input value={formKeluar.tujuan} onChange={setK("tujuan")} placeholder="cth. KPKNL Balikpapan" /></Field>
                <Field label="Tanggal Surat"><Input type="date" value={formKeluar.tanggal_surat} onChange={setK("tanggal_surat")} /></Field>
                <Field label="Jenis Naskah">
                  <select value={formKeluar.jenis_naskah} onChange={setK("jenis_naskah")}
                    className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm" data-testid="keluar-jenis-naskah">
                    {(ref?.jenis_naskah || ["Laporan"]).map((j) => <option key={j} value={j}>{j}</option>)}
                  </select>
                </Field>
                <Field label="Modul Asal">
                  <select value={formKeluar.modul} onChange={setK("modul")}
                    className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm">
                    {(ref?.modul || ["umum"]).map((m) => <option key={m} value={m}>{m}</option>)}
                  </select>
                </Field>
                <Field label="Kegiatan (opsional)">
                  <select value={formKeluar.kegiatan_id} onChange={setK("kegiatan_id")}
                    className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm">
                    <option value="">— tanpa kegiatan —</option>
                    {kegiatan.map((k) => <option key={k.id} value={k.id}>{k.nama_kegiatan}</option>)}
                  </select>
                </Field>
                <Field label="Klasifikasi Keamanan">
                  <select value={formKeluar.kode_keamanan} onChange={setK("kode_keamanan")}
                    className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm">
                    {(ref?.kode_keamanan || []).map((k) => <option key={k.kode} value={k.kode}>{k.kode} — {k.uraian}</option>)}
                  </select>
                </Field>
                <Field label="Kode Klasifikasi Arsip">
                  <Input value={formKeluar.kode_klasifikasi} onChange={setK("kode_klasifikasi")}
                    list="klasifikasi-arsip-list"
                    placeholder={pratinjau?.kode_klasifikasi ? `otomatis: ${pratinjau.kode_klasifikasi}` : "cth. PL.02"}
                    className="font-mono" data-testid="keluar-klasifikasi" />
                </Field>
                <Field label="Referensi Laporan"><Input value={formKeluar.referensi} onChange={setK("referensi")} placeholder="cth. BAHI / LHI / LBKP S1" /></Field>
                <Field label="Nomor Eksternal (aplikasi lain)">
                  <Input value={formKeluar.nomor_eksternal || ""} onChange={setK("nomor_eksternal")}
                    placeholder="nomor sah dari Srikandi/e-office" className="font-mono"
                    data-testid="keluar-nomor-eksternal" />
                </Field>
              </div>
              <Field label="Keterangan"><Input value={formKeluar.keterangan} onChange={setK("keterangan")} /></Field>
              {formKeluar.mode !== "edit" && (
                <label className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 cursor-pointer">
                  <input type="checkbox" checked={!!formKeluar.sisipan}
                    onChange={(e) => setFormKeluar((f) => ({ ...f, sisipan: e.target.checked }))}
                    className="mt-0.5 w-4 h-4 accent-amber-600 min-w-0 min-h-0 flex-shrink-0"
                    data-testid="keluar-sisipan" />
                  <span className="text-[11px] leading-snug text-amber-800 dark:text-amber-300">
                    <b>Nomor sisipan (backdate)</b> — untuk surat yang lupa dibooking dan baru
                    dibuat sekarang: nomor menempel di belakang nomor terakhir pada tanggal itu
                    (cth. 005 → <span className="font-mono">005.01</span>) sehingga urutan agenda
                    tetap kronologis. Wajib mengisi Tanggal Surat; tidak boleh tanggal masa depan.
                  </span>
                </label>
              )}
              {formKeluar.mode !== "edit" && formKeluar.sisipan && pratinjau?.sisipan_galat && (
                <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2" data-testid="keluar-sisipan-galat">
                  <p className="text-[11px] text-red-700 dark:text-red-400">{pratinjau.sisipan_galat}</p>
                </div>
              )}
              {formKeluar.mode !== "edit" && pratinjau?.nomor && (
                <div className="rounded-lg border border-cyan-500/40 bg-cyan-500/10 px-3 py-2" data-testid="keluar-pratinjau">
                  <p className="text-[10px] text-muted-foreground">Perkiraan nomor yang akan terbit:</p>
                  <p className="font-mono text-sm font-bold text-cyan-700 dark:text-cyan-400 break-all">{pratinjau.nomor}</p>
                  <p className="text-[10px] text-muted-foreground mt-0.5"
                    data-testid="keluar-sumber-klasifikasi">
                    Klasifikasi: {teksSumberKlasifikasi(pratinjau)}
                    {" · "}bisa bergeser bila ada booking lain lebih dulu
                  </p>
                </div>
              )}
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setFormKeluar(null)}>Batal</Button>
            <Button disabled={saving} data-testid="keluar-simpan"
              onClick={formKeluar?.mode === "edit-final"
                ? () => kirim(() => axios.put(`${API}/persuratan/${formKeluar.id}`, {
                    nomor_eksternal: formKeluar.nomor_eksternal,
                    keterangan: formKeluar.keterangan,
                  }), "Nomor eksternal tersimpan")
                : formKeluar?.mode === "edit"
                ? () => kirim(() => axios.put(`${API}/persuratan/${formKeluar.id}`, {
                    perihal: formKeluar.perihal, tujuan: formKeluar.tujuan,
                    jenis_naskah: formKeluar.jenis_naskah, modul: formKeluar.modul,
                    kegiatan_id: formKeluar.kegiatan_id, kode_klasifikasi: formKeluar.kode_klasifikasi,
                    tanggal_surat: formKeluar.tanggal_surat, referensi: formKeluar.referensi,
                    nomor_eksternal: formKeluar.nomor_eksternal, keterangan: formKeluar.keterangan,
                  }), "Draf surat diperbarui")
                : booking}>
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : null}
              {formKeluar?.mode ? "Simpan" : "Booking Nomor"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog surat masuk ── */}
      <Dialog open={!!formMasuk} onOpenChange={(o) => { if (!o) setFormMasuk(null); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{formMasuk?.mode === "edit" ? `Ubah Surat Masuk — M-${noAgendaTampil(formMasuk.no_agenda)}/${formMasuk.tahun}` : "Catat Surat Masuk"}</DialogTitle>
            <DialogDescription className="text-xs">
              {formMasuk?.mode === "edit" ? "Koreksi data surat masuk — nomor agenda tetap." : "Nomor agenda masuk terbit otomatis per periode (bulanan/tahunan sesuai pengaturan Format Nomor)."}
            </DialogDescription>
          </DialogHeader>
          {formMasuk && (
            <div className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Field label="Nomor Surat (pengirim) *"><Input value={formMasuk.nomor_surat} onChange={setM("nomor_surat")} className="font-mono" data-testid="masuk-nomor" /></Field>
                <Field label="Tanggal Surat"><Input type="date" value={formMasuk.tanggal_surat} onChange={setM("tanggal_surat")} /></Field>
                <Field label="Pengirim *"><Input value={formMasuk.pengirim} onChange={setM("pengirim")} placeholder="cth. KPKNL Balikpapan" data-testid="masuk-pengirim" /></Field>
                <Field label="Modul Terkait">
                  <select value={formMasuk.modul} onChange={setM("modul")}
                    className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm">
                    {(ref?.modul || ["umum"]).map((m) => <option key={m} value={m}>{m}</option>)}
                  </select>
                </Field>
              </div>
              <Field label="Perihal *"><Input value={formMasuk.perihal} onChange={setM("perihal")} data-testid="masuk-perihal" /></Field>
              <Field label="Keterangan / disposisi"><Input value={formMasuk.keterangan} onChange={setM("keterangan")} /></Field>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setFormMasuk(null)}>Batal</Button>
            <Button disabled={saving} data-testid="masuk-simpan"
              onClick={formMasuk?.mode === "edit"
                ? () => {
                    const f = formMasuk;
                    if (!f.nomor_surat?.trim() || !f.pengirim?.trim() || !f.perihal?.trim()) {
                      toast.error("Nomor surat, pengirim, dan perihal wajib diisi"); return;
                    }
                    kirim(() => axios.put(`${API}/persuratan/${f.id}`, {
                      nomor_surat: f.nomor_surat, pengirim: f.pengirim,
                      perihal: f.perihal, tanggal_surat: f.tanggal_surat,
                      modul: f.modul, keterangan: f.keterangan,
                    }), "Surat masuk diperbarui");
                  }
                : catatMasuk}>
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : null}
              {formMasuk?.mode === "edit" ? "Simpan" : "Catat"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog pembatalan (wajib alasan) ── */}
      <Dialog open={!!batal} onOpenChange={(o) => { if (!o) setBatal(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Batalkan Nomor {batal?.surat?.nomor}?</DialogTitle>
            <DialogDescription className="text-xs">
              Nomor yang dibatalkan HANGUS — tidak dipakai surat lain, tetap tercatat di agenda dengan alasannya (kaidah kearsipan).
            </DialogDescription>
          </DialogHeader>
          <Field label="Alasan pembatalan *">
            <Input value={batal?.alasan || ""} onChange={(e) => setBatal((b) => ({ ...b, alasan: e.target.value }))}
              placeholder="cth. draf ganda / batal terbit" data-testid="batal-alasan" />
          </Field>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setBatal(null)}>Kembali</Button>
            <Button variant="destructive" disabled={saving || !(batal?.alasan || "").trim()}
              onClick={() => transisi(batal.surat, "dibatalkan", batal.alasan)} data-testid="batal-konfirmasi">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : null}Batalkan Nomor
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog pengaturan format + klasifikasi (admin) ── */}
      <Dialog open={!!formAtur} onOpenChange={(o) => { if (!o) setFormAtur(null); }}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              Pengaturan Penomoran & Klasifikasi Surat
              {formAtur?.scope
                ? ` — Satker ${formAtur.scope}`
                : " — Universal (semua satker)"}
            </DialogTitle>
            <DialogDescription className="text-xs">
              Susunan PerANRI 5/2021 — placeholder: {"{kode_keamanan} {urut} {kode_klasifikasi} {kode_unit} {bulan} {bulan_romawi} {tahun}"}.
              {formAtur?.scope
                ? " Perubahan hanya berlaku untuk satker ini; field yang dikosongkan kembali mengikuti Universal."
                : " Nilai di sini menjadi bawaan bersama — satker yang mengisi pengaturannya sendiri menimpanya."}
            </DialogDescription>
          </DialogHeader>
          {formAtur && (
            <div className="space-y-4">
              <div className="space-y-3">
                <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground border-b border-border/60 pb-1">Format Nomor</p>
                {formAtur.scope && formAtur.sumber && (
                  <p className="text-[10px] text-sky-700 dark:text-sky-300" data-testid="atur-warisan">
                    {(() => {
                      const label = { format_nomor: "Format", kode_unit: "Kode Unit",
                        kode_klasifikasi_default: "Klasifikasi Bawaan", reset_urut: "Reset Urut",
                        peta_klasifikasi: "Aturan Otomatis" };
                      const warisan = Object.entries(formAtur.sumber)
                        .filter(([, v]) => v !== "satker").map(([k]) => label[k]).filter(Boolean);
                      return warisan.length
                        ? `Warisan Universal (belum di-override satker ini): ${warisan.join(", ")}`
                        : "Semua field sudah di-override khusus satker ini";
                    })()}
                  </p>
                )}
                {/* Komposisi nomor — jalan ramah untuk dua placeholder yang
                    paling sering diminta. Ia BUKAN setelan tersendiri: server
                    menulis ulang `format_nomor` dari pilihan ini, dan template
                    tetap satu-satunya sumber kebenaran. Tanpa ini, memakai kode
                    klasifikasi berarti mengetik template ber-placeholder dengan
                    benar — dan salah satu kurung membuat kodenya diam-diam tak
                    pernah muncul di nomor mana pun. */}
                <Field label="Komposisi Nomor">
                  <select
                    value={formAtur.komposisi_nomor || "keduanya"}
                    onChange={(e) => {
                      const pilih = e.target.value;
                      setFormAtur((f) => ({ ...f, komposisi_nomor: pilih }));
                      // Kolom Format Nomor diperbarui dari jawaban server —
                      // aturan penyisipannya tidak disalin ke klien.
                      mintaPraFormat(formAtur.format_nomor, pilih);
                    }}
                    className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
                    data-testid="atur-komposisi">
                    {Object.entries(formAtur.pilihan_komposisi || {
                      keduanya: "Kode keamanan + kode klasifikasi arsip",
                      keamanan: "Kode keamanan saja",
                      klasifikasi: "Kode klasifikasi arsip saja",
                      tanpa: "Tanpa keamanan maupun klasifikasi",
                    }).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                  <p className="text-[10px] text-muted-foreground mt-1">
                    Susunan pada <b>Format Nomor</b> di bawah langsung
                    menyesuaikan — bagian lain (kode unit, bulan, tahun,
                    pemisah) tidak disentuh.
                  </p>
                </Field>
                {/* Saklar deret per kode. Dinonaktifkan — bukan disembunyikan
                    — saat komposisi tak menyediakan kode pembeda: pengguna
                    berhak tahu fiturnya ada beserta syaratnya. Server tetap
                    memaksanya mati kalau setelan lama tertinggal menyala. */}
                <Field label="Deret Nomor Urut">
                  <label className="flex items-start gap-2 text-xs text-foreground">
                    <input
                      type="checkbox"
                      className="mt-0.5 min-h-0 min-w-0"
                      checked={!!formAtur.deret_per_kode && formAtur.deret_per_kode_boleh !== false}
                      disabled={formAtur.deret_per_kode_boleh === false}
                      onChange={(e) => setFormAtur((f) => ({ ...f, deret_per_kode: e.target.checked }))}
                      data-testid="atur-deret-per-kode" />
                    <span>
                      Nomor urut berjalan <b>sendiri-sendiri per kode</b>
                      {formAtur.komposisi_nomor === "klasifikasi"
                        ? " klasifikasi arsip" : " keamanan"}
                      {" "}— tiap kode punya deret 001, 002, … miliknya.
                    </span>
                  </label>
                  <p className="text-[10px] text-muted-foreground mt-1">
                    {formAtur.deret_per_kode_boleh === false
                      ? "Tidak tersedia untuk komposisi yang dipilih: deret terpisah hanya aman bila SATU kode pembeda tercetak pada nomor. Bila keduanya (atau tak satu pun) dipakai, deret kembali menjadi satu."
                      : "Akibatnya nomor 001 bisa ada pada beberapa kode sekaligus — itu memang tujuannya, dan lencana agenda akan menyebut kodenya (mis. K-T-001/VIII/2026) supaya tetap dapat dibedakan."}
                  </p>
                </Field>
                {formAtur.peringatan_klasifikasi && (
                  <p className="text-[11px] leading-snug rounded-lg border border-amber-500/40 bg-amber-500/10 px-2.5 py-1.5 text-amber-700 dark:text-amber-400"
                    data-testid="atur-peringatan-klasifikasi">
                    <b>Perhatian.</b> {formAtur.peringatan_klasifikasi}
                  </p>
                )}
                <Field label="Format Nomor">
                  <Input value={formAtur.format_nomor} className="font-mono"
                    onChange={(e) => {
                      setFormAtur((f) => ({ ...f, format_nomor: e.target.value }));
                      mintaPraFormat(e.target.value, "");
                    }}
                    placeholder={formAtur.warisan?.format_nomor
                      ? `ikut Universal: ${formAtur.warisan.format_nomor}` : undefined}
                    data-testid="atur-format" />
                  {/* Daftar bagian yang bisa dipanggil, berikut ARTINYA.
                      Keluhan pemilik: kolom di atas menerima template mentah
                      sementara nama bagiannya hanya tertulis sebagai deretan
                      {...} di keterangan dialog — tak ada yang menyebutkan apa
                      artinya atau apa isinya nanti. Satu ketukan menyisipkan
                      di ujung template; urutan chip = susunan PerANRI 5/2021,
                      jadi menyisipkannya berurutan sudah menghasilkan bentuk
                      yang benar. */}
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {(praFormat?.placeholder || formAtur.placeholder || []).map((ph) => {
                      const token = `{${ph.kunci}}`;
                      const dipakai = (formAtur.format_nomor || "").includes(token);
                      return (
                        <button
                          key={ph.kunci}
                          type="button"
                          title={`${ph.arti} — contoh: ${ph.contoh}`}
                          onClick={() => {
                            const baru = `${formAtur.format_nomor || ""}${token}`;
                            setFormAtur((f) => ({ ...f, format_nomor: baru }));
                            mintaPraFormat(baru, "");
                          }}
                          className={`min-h-0 min-w-0 px-1.5 py-0.5 rounded border text-[10px] ${
                            dipakai
                              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                              : "border-border text-muted-foreground hover:bg-muted"}`}
                          data-testid={`atur-ph-${ph.kunci}`}>
                          {ph.label} <span className="font-mono opacity-70">{ph.contoh}</span>
                        </button>
                      );
                    })}
                  </div>
                  {praFormat?.nomor && (
                    <p className="text-[11px] mt-1.5 rounded-lg bg-muted/60 px-2.5 py-1.5">
                      Contoh nomor: <span className="font-mono font-semibold text-foreground">{praFormat.nomor}</span>
                    </p>
                  )}
                </Field>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Field label="Kode Unit"><Input value={formAtur.kode_unit} onChange={(e) => setFormAtur((f) => ({ ...f, kode_unit: e.target.value }))} placeholder={formAtur.warisan?.kode_unit ? `ikut Universal: ${formAtur.warisan.kode_unit}` : "cth. OIKN"} /></Field>
                  <Field label="Kode Klasifikasi Bawaan (fallback)"><Input value={formAtur.kode_klasifikasi_default} onChange={(e) => setFormAtur((f) => ({ ...f, kode_klasifikasi_default: e.target.value }))} placeholder={formAtur.warisan?.kode_klasifikasi_default ? `ikut Universal: ${formAtur.warisan.kode_klasifikasi_default}` : "cth. UM.01"} className="font-mono" /></Field>
                </div>
                <Field label="Reset Nomor Urut (metode deret satker ini)">
                  <select value={formAtur.reset_urut || (formAtur.scope ? "" : "bulanan")}
                    onChange={(e) => setFormAtur((f) => ({ ...f, reset_urut: e.target.value }))}
                    className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
                    data-testid="atur-reset-urut">
                    {formAtur.scope && (
                      <option value="">Ikut Universal (tanpa override satker)</option>
                    )}
                    {(ref?.reset_urut?.length ? ref.reset_urut
                      : [{ kode: "bulanan", uraian: "Bulanan — nomor kembali ke 001 tiap awal bulan" },
                         { kode: "tahunan", uraian: "Tahunan — deret satu tahun takwim (PerANRI 5/2021)" }]
                    ).map((r) => <option key={r.kode} value={r.kode}>{r.uraian}</option>)}
                  </select>
                </Field>
                <p className="text-[10px] text-muted-foreground">
                  Contoh hasil: <span className="font-mono">B-015/PL.02/OIKN/VII/2026</span>. Perubahan hanya memengaruhi booking BERIKUTNYA.
                  Reset bulanan: bulan berjalan meneruskan deretnya, bulan baru mulai dari 001 — format wajib memuat {"{bulan}"} / {"{bulan_romawi}"} agar nomor antarbulan tak kembar.
                </p>
              </div>

              <div className="space-y-2">
                <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground border-b border-border/60 pb-1">
                  Master Kode Klasifikasi Arsip
                </p>
                <p className="text-[10px] text-muted-foreground">
                  Daftar ini <b>katalog kode</b> — mendaftarkan kode di sini
                  belum mengubah nomor surat apa pun. Yang mengubah nomor:
                  aturan otomatis di bawah, <b>Kode Klasifikasi Bawaan</b>, atau
                  isian manual di form booking. Badge tiap baris menyebut kode
                  itu sudah terpakai atau masih menganggur; tombol{" "}
                  <span className="font-mono">+ aturan</span> memasangkannya
                  langsung.
                  {formAtur.scope
                    ? " Entri baru tersimpan milik satker ini; entri Bersama (warisan Universal) hanya dikelola super-admin."
                    : " Entri baru tersimpan sebagai Bersama — tampil untuk semua satker."}
                </p>
                {klasifikasi.length > 0 && (
                  <div className="max-h-36 overflow-y-auto border border-border rounded-lg divide-y divide-border/60">
                    {klasifikasi.map((k) => {
                      const scopeK = k.kode_satker || "";
                      const bolehKelola = !formAtur.scope || scopeK === formAtur.scope;
                      const st = statusKodeKlasifikasi(k);
                      return (
                        <div key={k.id} className="flex items-center gap-2 px-2.5 py-1">
                          <span className="font-mono text-[11px] font-semibold text-foreground w-20 flex-shrink-0">{k.kode}</span>
                          <span className="text-[11px] text-foreground/80 truncate flex-1">{k.uraian || "—"}</span>
                          <span className={`text-[9px] px-1.5 py-0.5 rounded-full flex-shrink-0 ${st.warna}`}
                            title={st.aktif
                              ? "Kode ini benar-benar dipakai saat nomor dirakit"
                              : "Kode ini belum dipasang ke aturan mana pun — nomor surat tak akan pernah memakainya"}
                            data-testid={`klas-status-${k.kode}`}>
                            {st.teks}
                          </span>
                          <span className={`text-[9px] px-1.5 py-0.5 rounded-full flex-shrink-0 ${scopeK
                            ? "bg-cyan-500/10 text-cyan-700 dark:text-cyan-300"
                            : "bg-muted text-muted-foreground"}`}>
                            {scopeK ? (formAtur.scope && scopeK === formAtur.scope
                              ? "Satker ini" : `Satker ${scopeK}`) : "Bersama"}
                          </span>
                          {/* Jalan TERCEPAT membuat sebuah kode benar-benar
                              masuk ke nomor: jadikan bawaan, berlaku untuk
                              semua surat. Tombol "+ aturan" di sebelahnya
                              untuk cakupan yang lebih sempit (per modul/jenis
                              naskah). Tanpa salah satunya, kode di katalog
                              hanya katalog — dan itulah yang membuat fiturnya
                              tampak tak berpengaruh. */}
                          <button type="button" onClick={() => pakaiKlasSebagaiBawaan(k.kode)}
                            aria-label={`Jadikan ${k.kode} kode bawaan`}
                            title="Jadikan kode bawaan — dipakai semua surat yang tak punya aturan lebih spesifik"
                            className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-border text-muted-foreground hover:text-foreground hover:bg-muted min-w-0 min-h-0 flex-shrink-0"
                            data-testid={`klas-jadikan-bawaan-${k.kode}`}>
                            bawaan
                          </button>
                          <button type="button" onClick={() => pakaiKlasSebagaiAturan(k.kode)}
                            aria-label={`Buat aturan untuk ${k.kode}`}
                            title="Buat aturan otomatis memakai kode ini"
                            className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-border text-muted-foreground hover:text-foreground hover:bg-muted min-w-0 min-h-0 flex-shrink-0"
                            data-testid={`klas-jadikan-aturan-${k.kode}`}>
                            + aturan
                          </button>
                          {bolehKelola && (
                            <button type="button" onClick={() => hapusKlas(k)} aria-label={`Hapus ${k.kode}`}
                              className="p-1 rounded text-muted-foreground hover:text-red-600 hover:bg-red-500/10 min-w-0 min-h-0"
                              data-testid={`klas-hapus-${k.kode}`}>
                              <Trash2 className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
                <div className="flex flex-wrap items-center gap-2">
                  <Input value={klasBaru.kode} onChange={(e) => setKlasBaru((b) => ({ ...b, kode: e.target.value }))}
                    placeholder="Kode (cth. PL.02)" className="font-mono h-9 w-28 sm:w-36" data-testid="klas-baru-kode" />
                  <Input value={klasBaru.uraian} onChange={(e) => setKlasBaru((b) => ({ ...b, uraian: e.target.value }))}
                    placeholder="Uraian (cth. Pelaporan BMN)" className="h-9 flex-1" data-testid="klas-baru-uraian" />
                  <Button variant="outline" size="sm" className="h-9 gap-1" onClick={tambahKlas} data-testid="klas-tambah">
                    <Plus className="w-3.5 h-3.5" />Tambah
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground border-b border-border/60 pb-1">
                  Aturan Klasifikasi Otomatis
                </p>
                <p className="text-[10px] text-muted-foreground">
                  Saat booking, kode klasifikasi terisi otomatis dari aturan yang paling spesifik (modul + jenis naskah &gt; salah satunya); kosong = berlaku untuk semua. Kode manual di form selalu menang.
                </p>
                {/* Aturan warisan Universal — DITAMPILKAN, tak lagi disembunyikan.
                    Selama satker belum punya aturan sendiri, inilah yang benar-
                    benar berlaku; begitu satker menambah satu aturan, seluruh
                    daftar di bawah ini berhenti berlaku. */}
                {formAtur.scope && (formAtur.warisan?.peta_klasifikasi || []).length > 0 && (
                  <div className="rounded-lg border border-border bg-muted/40 px-2.5 py-2 space-y-1"
                    data-testid="aturan-warisan">
                    <p className="text-[10px] text-muted-foreground">
                      {(formAtur.peta_klasifikasi || []).length > 0 ? (
                        <><b className="text-amber-700 dark:text-amber-400">Aturan Universal di bawah tidak lagi berlaku</b> untuk
                          satker ini — daftar aturan satker menggantikannya seluruhnya, bukan menambah.</>
                      ) : (
                        <><b>Sedang berlaku (warisan Universal).</b> Menambah satu aturan sendiri akan
                          menggantikan SELURUH daftar ini — salin dulu bila ingin mempertahankannya.</>
                      )}
                    </p>
                    <ul className="space-y-0.5">
                      {(formAtur.warisan.peta_klasifikasi || []).map((a, i) => (
                        <li key={i} className="text-[10px] text-muted-foreground flex items-center gap-1.5">
                          <span className="font-mono font-semibold text-foreground/80">{a.kode || "—"}</span>
                          <span className="truncate">{sebutCakupan(a.modul, a.jenis_naskah)}</span>
                        </li>
                      ))}
                    </ul>
                    {(formAtur.peta_klasifikasi || []).length === 0 && (
                      <Button variant="outline" size="sm" className="h-7 gap-1 text-[10px]"
                        onClick={salinAturanUniversal} data-testid="aturan-salin-universal">
                        <Plus className="w-3 h-3" />Salin ke satker ini agar bisa diubah
                      </Button>
                    )}
                  </div>
                )}
                {(formAtur.peta_klasifikasi || []).map((a, i) => (
                  <div key={i} className="flex items-center gap-1.5" data-testid={`aturan-${i}`}>
                    <select value={a.modul || ""} onChange={(e) => setAturan(i, "modul", e.target.value)}
                      className="h-9 rounded-md border border-input bg-background px-2 text-xs w-32">
                      <option value="">semua modul</option>
                      {(ref?.modul || []).map((m) => <option key={m} value={m}>{m}</option>)}
                    </select>
                    <select value={a.jenis_naskah || ""} onChange={(e) => setAturan(i, "jenis_naskah", e.target.value)}
                      className="h-9 rounded-md border border-input bg-background px-2 text-xs flex-1">
                      <option value="">semua jenis naskah</option>
                      {(ref?.jenis_naskah || []).map((j) => <option key={j} value={j}>{j}</option>)}
                    </select>
                    <Input value={a.kode || ""} onChange={(e) => setAturan(i, "kode", e.target.value)}
                      list="klasifikasi-arsip-list" placeholder="kode" className="font-mono h-9 w-24" />
                    <button type="button" aria-label="Hapus aturan"
                      onClick={() => setFormAtur((f) => ({ ...f, peta_klasifikasi: f.peta_klasifikasi.filter((_, j) => j !== i) }))}
                      className="p-1.5 rounded text-muted-foreground hover:text-red-600 hover:bg-red-500/10 min-w-0 min-h-0">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
                <Button variant="outline" size="sm" className="h-8 gap-1 text-[11px]"
                  onClick={() => setFormAtur((f) => ({ ...f, peta_klasifikasi: [...(f.peta_klasifikasi || []), { modul: "", jenis_naskah: "", kode: "" }] }))}
                  data-testid="aturan-tambah">
                  <Plus className="w-3.5 h-3.5" />Tambah Aturan
                </Button>
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setFormAtur(null)}>Batal</Button>
            <Button onClick={simpanAtur} disabled={saving} data-testid="atur-simpan">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : null}Simpan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {relasiSurat && (
        <RelasiDialog surat={relasiSurat} isAdmin={isAdmin}
          jenisRelasi={ref?.jenis_relasi || []}
          onClose={() => setRelasiSurat(null)}
          onChanged={() => load(page)} />
      )}

      {/* Datalist bersama: dipakai input klasifikasi di dialog booking & pengaturan */}
      <datalist id="klasifikasi-arsip-list">
        {klasifikasi.map((k) => <option key={k.id} value={k.kode}>{k.uraian}</option>)}
      </datalist>
      {confirmDialog}
    </div>
  );
}

/**
 * Dialog Relasi & Timeline satu surat: status keberlakuan terhitung, riwayat
 * status + panah relasi dua arah, form tambah relasi (surat ini sebagai
 * pihak AKTIF: Mencabut/Mengubah/… surat sasaran), dan hapus relasi (admin).
 */
function RelasiDialog({ surat, isAdmin, jenisRelasi, onClose, onChanged }) {
  const [data, setData] = useState(null);
  const [cari, setCari] = useState("");
  const [kandidat, setKandidat] = useState([]);
  const [target, setTarget] = useState(null);
  const [jenis, setJenis] = useState("mencabut");
  const [catatan, setCatatan] = useState("");
  const [sibuk, setSibuk] = useState(false);
  const cariTimer = useRef(null);

  const muat = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/persuratan/${surat.id}/timeline`);
      setData(r.data);
    } catch (e) { toast.error(apiErr(e, "Gagal memuat timeline")); }
  }, [surat.id]);
  useEffect(() => { muat(); }, [muat]);

  // Cari surat sasaran (debounce) — tidak menampilkan surat ini sendiri.
  useEffect(() => {
    if (!cari.trim()) { setKandidat([]); return; }
    if (cariTimer.current) clearTimeout(cariTimer.current);
    cariTimer.current = setTimeout(async () => {
      try {
        const r = await axios.get(
          `${API}/persuratan?q=${encodeURIComponent(cari.trim())}&page_size=8`);
        setKandidat((r.data?.items || []).filter((x) => x.id !== surat.id));
      } catch { setKandidat([]); }
    }, 300);
    return () => { if (cariTimer.current) clearTimeout(cariTimer.current); };
  }, [cari, surat.id]);

  const tambah = async () => {
    if (!target) { toast.error("Pilih surat sasarannya dulu"); return; }
    setSibuk(true);
    try {
      await axios.post(`${API}/persuratan/${surat.id}/relasi`,
        { ke_id: target.id, jenis, catatan });
      toast.success("Relasi tercatat");
      setTarget(null); setCari(""); setCatatan("");
      muat(); onChanged?.();
    } catch (e) { toast.error(apiErr(e, "Gagal mencatat relasi")); }
    finally { setSibuk(false); }
  };

  const hapusRelasi = async (r) => {
    setSibuk(true);
    try {
      await axios.delete(`${API}/persuratan/relasi/${r.id}`);
      toast.success("Relasi dihapus");
      muat(); onChanged?.();
    } catch (e) { toast.error(apiErr(e, "Gagal menghapus relasi")); }
    finally { setSibuk(false); }
  };

  const kb = data?.surat?.keberlakuan;
  const infoJenis = (k) => (jenisRelasi.find((j) => j.kode === k) || {});
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 flex-wrap">
            <GitBranch className="w-4 h-4 text-cyan-700 dark:text-cyan-400" />
            Relasi & Timeline Surat
            {kb && (
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${WARNA_KEBERLAKUAN[kb] || "bg-muted"}`}
                data-testid="relasi-keberlakuan">
                {data?.surat?.keberlakuan_label || LABEL_KEBERLAKUAN[kb] || kb}
              </span>
            )}
          </DialogTitle>
          <DialogDescription className="text-xs font-mono break-all">
            {surat.nomor} — {surat.perihal}
          </DialogDescription>
        </DialogHeader>

        {!data ? (
          <div className="py-6 text-center"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
        ) : (
          <div className="space-y-4">
            {/* Panah relasi dua arah + hapus (admin) */}
            {(data.relasi_keluar.length > 0 || data.relasi_masuk.length > 0) && (
              <div className="space-y-1.5">
                <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground border-b border-border/60 pb-1">Hubungan Antar Surat</p>
                {[...data.relasi_keluar.map((r) => ({ r, arah: "keluar" })),
                  ...data.relasi_masuk.map((r) => ({ r, arah: "masuk" }))].map(({ r, arah }) => {
                  const ujungId = arah === "keluar" ? r.ke_id : r.dari_id;
                  const u = data.ujung?.[ujungId];
                  const label = arah === "keluar"
                    ? (infoJenis(r.jenis).aktif || r.jenis)
                    : (infoJenis(r.jenis).pasif || r.jenis);
                  return (
                    <div key={r.id} className="flex items-start gap-2 text-[12px] bg-muted/40 rounded-lg px-2.5 py-1.5" data-testid={`relasi-baris-${r.id}`}>
                      <div className="flex-1 min-w-0">
                        <p className="text-foreground">
                          <span className="font-semibold">{label}</span>{" "}
                          <span className="font-mono break-all">{arah === "keluar" ? (r.ke_nomor || r.ke_id) : (r.dari_nomor || r.dari_id)}</span>
                        </p>
                        <p className="text-[10px] text-muted-foreground truncate">
                          {(arah === "keluar" ? r.ke_perihal : r.dari_perihal) || ""}
                          {r.catatan ? ` — ${r.catatan}` : ""}
                        </p>
                        {u && u.keberlakuan === "tidak_berlaku" && (
                          <p className="text-[10px] text-red-500/90">surat tersebut kini Tidak Berlaku</p>
                        )}
                      </div>
                      {isAdmin && (
                        <button type="button" onClick={() => hapusRelasi(r)} disabled={sibuk}
                          title="Hapus relasi (salah catat)" aria-label="Hapus relasi"
                          className="p-1 rounded text-muted-foreground hover:text-red-600 hover:bg-red-500/10 min-w-0 min-h-0">
                          <Trash2 className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Timeline gabungan */}
            <div className="space-y-1.5">
              <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground border-b border-border/60 pb-1">Timeline</p>
              <ol className="space-y-1 max-h-44 overflow-y-auto pr-1" data-testid="relasi-timeline">
                {data.timeline.map((b, i) => (
                  <li key={i} className="flex gap-2 text-[11px]">
                    <span className="text-muted-foreground whitespace-nowrap font-mono">{(b.tanggal || "").slice(0, 10) || "—"}</span>
                    <span className={b.jenis === "relasi" ? "text-cyan-800 dark:text-cyan-300" : "text-foreground/80"}>{b.teks}</span>
                  </li>
                ))}
                {data.timeline.length === 0 && (
                  <li className="text-[11px] text-muted-foreground">Belum ada riwayat.</li>
                )}
              </ol>
            </div>

            {/* Tambah relasi — surat INI pihak aktifnya */}
            <div className="space-y-2">
              <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground border-b border-border/60 pb-1">Catat Relasi Baru</p>
              <p className="text-[10px] text-muted-foreground">
                Surat INI sebagai pelaku — pilih perannya lalu surat sasarannya.
                Contoh: SK baru <b>Mencabut</b> SK lama → buka dialog ini dari SK baru.
              </p>
              <select value={jenis} onChange={(e) => setJenis(e.target.value)}
                className="w-full h-9 rounded-md border border-input bg-background px-2 text-sm"
                data-testid="relasi-jenis">
                {jenisRelasi.map((j) => (
                  <option key={j.kode} value={j.kode}>{j.aktif}</option>
                ))}
              </select>
              {target ? (
                <div className="flex items-center gap-2 text-[12px] bg-cyan-500/10 rounded-lg px-2.5 py-1.5">
                  <span className="font-mono flex-1 min-w-0 break-all">{target.nomor} — {target.perihal}</span>
                  <button type="button" onClick={() => setTarget(null)} aria-label="Ganti sasaran"
                    className="p-1 rounded text-muted-foreground hover:text-red-600 min-w-0 min-h-0">
                    <XCircle className="w-3.5 h-3.5" />
                  </button>
                </div>
              ) : (
                <>
                  <Input value={cari} onChange={(e) => setCari(e.target.value)}
                    placeholder="Cari surat sasaran (nomor/perihal)…" className="h-9"
                    data-testid="relasi-cari" />
                  {kandidat.length > 0 && (
                    <div className="border border-border rounded-lg divide-y divide-border/60 max-h-36 overflow-y-auto">
                      {kandidat.map((k) => (
                        <button type="button" key={k.id} onClick={() => setTarget(k)}
                          className="w-full text-left px-2.5 py-1.5 hover:bg-muted/60 min-w-0 min-h-0"
                          data-testid={`relasi-kandidat-${k.id}`}>
                          <p className="font-mono text-[11px] text-foreground break-all">{k.nomor}</p>
                          <p className="text-[10px] text-muted-foreground truncate">{k.perihal}</p>
                        </button>
                      ))}
                    </div>
                  )}
                </>
              )}
              <Input value={catatan} onChange={(e) => setCatatan(e.target.value)}
                placeholder="Catatan (opsional, cth. ralat pasal 2)" className="h-9"
                data-testid="relasi-catatan" />
              <Button size="sm" onClick={tambah} disabled={sibuk || !target}
                className="gap-1.5" data-testid="relasi-simpan">
                {sibuk ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                Catat Relasi
              </Button>
            </div>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Tutup</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="text-xs font-medium text-foreground block mb-1">{label}</label>
      {children}
    </div>
  );
}
