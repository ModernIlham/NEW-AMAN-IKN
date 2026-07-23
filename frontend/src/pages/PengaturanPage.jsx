import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Building2, ChevronRight, Clock, DatabaseBackup, FileDown,
  Globe2, Info, Landmark, Loader2, Mail, CalendarClock, Moon, RotateCcw,
  Settings as SettingsIcon, ShieldAlert, Sun, Trash2, Upload,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useBackGuard } from "@/hooks/useBackGuard";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useDarkMode } from "@/hooks/useDarkMode";
import { getApiError } from "../lib/utils";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import ReportSettingsEditor from "@/components/assets/ReportSettingsEditor";
import { ResetAllDialog, RestoreDialog } from "@/components/sistem/DataSistemDialogs";
import { SatkerPanel } from "./SatkerPage";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function fmtUkuran(b) {
  const n = Number(b || 0);
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)} GB`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)} MB`;
  return `${Math.round(n / 1e3)} KB`;
}

// Warna status kuota email: aman (hijau) / hampir (kuning) / penuh (merah).
const WARNA_KUOTA = {
  aman: { bar: "bg-emerald-500", teks: "text-emerald-600 dark:text-emerald-400" },
  hampir: { bar: "bg-amber-500", teks: "text-amber-600 dark:text-amber-400" },
  penuh: { bar: "bg-red-500", teks: "text-red-600 dark:text-red-400" },
};

function BarKuota({ judul, d }) {
  if (!d) return null;
  const w = WARNA_KUOTA[d.status] || WARNA_KUOTA.aman;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2 mb-1">
        <span className="text-[11px] font-semibold text-foreground">{judul}</span>
        <span className={`text-[11px] font-bold ${w.teks}`}>
          {d.terpakai}<span className="text-muted-foreground font-medium"> / {d.limit}</span>
          <span className="text-muted-foreground font-normal"> · sisa {d.sisa}</span>
        </span>
      </div>
      <div className="h-2.5 rounded-full bg-muted overflow-hidden">
        <div className={`h-full rounded-full ${w.bar} transition-all`}
          style={{ width: `${Math.min(100, Math.max(2, d.persen))}%` }} />
      </div>
      {(d.rincian || []).length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1.5">
          {d.rincian.map((r) => (
            <span key={r.jenis} className="px-1.5 py-0.5 rounded bg-muted text-[10px] text-muted-foreground">
              {r.label}: <b className="text-foreground">{r.jumlah}</b>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Pengaturan Terpadu — SATU pintu seluruh setelan aplikasi (Mandat-2):
 *  - Universal : kop/logo/judul laporan global (report_settings) — berlaku
 *    untuk semua satker KECUALI ditimpa per satker.
 *  - Per-Satker: master satker + kop per-satker (menimpa universal).
 *  - Lainnya   : pintasan setelan yang hidup di modulnya (persuratan,
 *    akuntansi/ambang, periode pelaporan) supaya tetap satu pintu.
 *  - Sistem    : SIKLUS DATA lengkap satu rumah (#407) — backup manual/
 *    terjadwal + arsip server + pulihkan (restore) + reset, semua di sini.
 */
export default function PengaturanPage({ user, onBack, onOpenSatker,
  onOpenReferensiAkun, onOpenPersuratan, onOpenPelaporan, dark, toggleDark }) {
  const isAdmin = user?.role === "admin";
  // Backup/restore/reset = operasi SELURUH-DB lintas-satker → KHUSUS super-admin
  // pusat (admin dengan kode_satker kosong). Admin satker hanya mengelola
  // satkernya sendiri dan TIDAK boleh menyentuh data satker lain, jadi seluruh
  // tab Sistem (siklus data) digerbang isSuperAdmin — selaras backend
  // require_super_admin.
  const isSuperAdmin = isAdmin && !String(user?.kode_satker || "").trim();
  // Tema: pakai prop dari App bila diteruskan; fallback hook lokal (state awal
  // sinkron via localStorage) supaya toggle tetap berfungsi seperti di ModuleHomePage.
  const temaLokal = useDarkMode();
  const isDark = dark ?? temaLokal.dark;
  const toggleTema = toggleDark ?? temaLokal.toggle;
  const [tab, setTab] = useState("universal"); // universal | satker | sistem
  const [backupLoading, setBackupLoading] = useState(false);
  const [arsipkanBackup, setArsipkanBackup] = useState(false);
  // Setelan backup otomatis {aktif, jam, retensi, jumlah_arsip, total_ukuran}
  const [oto, setOto] = useState(null);
  const [otoSaving, setOtoSaving] = useState(false);
  const [arsip, setArsip] = useState(null); // daftar berkas arsip server
  const [showRestore, setShowRestore] = useState(false);
  const [showResetAll, setShowResetAll] = useState(false);
  // Pemantauan kuota email Resend (100/hari, 3000/bulan — dinamis dari server)
  const [email, setEmail] = useState(null);
  const [emailLoading, setEmailLoading] = useState(false);
  const [limitDraf, setLimitDraf] = useState(null); // {harian, bulanan} saat edit
  const [limitSaving, setLimitSaving] = useState(false);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const muatSistem = useCallback(() => {
    if (!isSuperAdmin) return;
    axios.get(`${API}/backup/otomatis`).then((r) => setOto(r.data)).catch(() => {});
    axios.get(`${API}/backup/arsip`).then((r) => setArsip(r.data?.items || [])).catch(() => setArsip([]));
  }, [isSuperAdmin]);

  // Pemantauan email terbuka utk semua admin (read); ubah limit khusus super-admin.
  const muatEmail = useCallback(() => {
    setEmailLoading(true);
    axios.get(`${API}/email/usage`)
      .then((r) => setEmail(r.data))
      .catch(() => setEmail(null))
      .finally(() => setEmailLoading(false));
  }, []);

  useEffect(() => { if (tab === "sistem") { muatSistem(); muatEmail(); } }, [tab, muatSistem, muatEmail]);

  const simpanLimitEmail = async () => {
    if (!limitDraf) return;
    setLimitSaving(true);
    try {
      await axios.put(`${API}/email/limit`, {
        limit_harian: Math.max(1, parseInt(limitDraf.harian, 10) || 0),
        limit_bulanan: Math.max(1, parseInt(limitDraf.bulanan, 10) || 0),
      });
      toast.success("Batas kuota email diperbarui");
      setLimitDraf(null);
      muatEmail();
    } catch (e) {
      toast.error(getApiError(e, "Gagal menyimpan batas kuota"));
    } finally { setLimitSaving(false); }
  };

  const mulaiBackup = async () => {
    setBackupLoading(true);
    try {
      await axios.post(`${API}/backup/start?arsipkan=${arsipkanBackup}`, {}, { timeout: 30000 });
      toast.success(arsipkanBackup
        ? "Backup dimulai — hasil TERSIMPAN di arsip server (juga bisa diunduh). Progres di panel kanan bawah."
        : "Backup dimulai di background — progres di panel kanan bawah, hasil ZIP siap diunduh setelah selesai.");
    } catch (e) {
      toast.error(getApiError(e, "Gagal memulai backup"));
    } finally {
      setBackupLoading(false);
    }
  };

  const simpanOto = async () => {
    setOtoSaving(true);
    try {
      await axios.post(`${API}/backup/otomatis`, {
        aktif: !!oto?.aktif, jam: oto?.jam || "02:00", retensi: oto?.retensi ?? 7,
      });
      toast.success("Setelan backup otomatis tersimpan");
      muatSistem();
    } catch (e) {
      toast.error(getApiError(e, "Gagal menyimpan setelan"));
    } finally {
      setOtoSaving(false);
    }
  };

  const hapusArsip = async (a) => {
    const ok = await confirm({
      title: `Hapus arsip ${a.nama}?`,
      description: "Berkas backup ini dihapus permanen dari server.",
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/backup/arsip/${a.nama}`);
      toast.success("Arsip dihapus");
      muatSistem();
    } catch (e) { toast.error(getApiError(e, "Gagal menghapus arsip")); }
  };

  const pulihkanDariArsip = async (a) => {
    const ok = await confirm({
      title: `Pulihkan data dari ${a.nama}?`,
      description: "SEMUA data saat ini akan DIGANTI dengan isi arsip ini. Safety backup otomatis dibuat dulu — bila gagal, data dikembalikan.",
      confirmLabel: "Lanjut", variant: "danger",
    });
    if (!ok) return;
    const ok2 = await confirm({
      title: "Yakin? Konfirmasi terakhir",
      description: `Restore dari arsip ${String(a.waktu).slice(0, 10)} (${fmtUkuran(a.ukuran)}) berjalan di background dan mengganti seluruh data.`,
      confirmLabel: "Pulihkan Sekarang", variant: "danger",
    });
    if (!ok2) return;
    try {
      await axios.post(`${API}/backup/restore/dari-arsip/${a.nama}`);
      toast.success("Restore dari arsip dimulai — progres di panel kanan bawah.");
    } catch (e) { toast.error(getApiError(e, "Gagal memulai restore")); }
  };

  const TABS = [
    ["universal", "Universal", Globe2],
    ["satker", "Per-Satker", Building2],
    ["sistem", "Sistem", DatabaseBackup],
  ];

  const pintasan = [
    onOpenPersuratan && {
      label: "Persuratan — format nomor & kode klasifikasi",
      desc: "Template nomor naskah dinas, kode unit, peta klasifikasi otomatis.",
      Icon: Mail, onClick: onOpenPersuratan,
    },
    onOpenReferensiAkun && {
      label: "Akuntansi BMN — akun BAS, pemetaan & ambang kapitalisasi",
      desc: "Master segmen akun, akun aset/persediaan, ambang intra/ekstra PMK 181.",
      Icon: Landmark, onClick: onOpenReferensiAkun,
    },
    onOpenPelaporan && {
      label: "Pelaporan — periode & tenggat",
      desc: "Daftar periode, kunci/final, tenggat penyampaian laporan.",
      Icon: CalendarClock, onClick: onOpenPelaporan,
    },
  ].filter(Boolean);

  return (
    <div className="min-h-screen bg-background" data-testid="pengaturan-page">
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button type="button" onClick={onBack} aria-label="Kembali" title="Kembali"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="pengaturan-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-slate-700 flex items-center justify-center flex-shrink-0">
            <SettingsIcon className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight truncate">Pengaturan</h1>
            <p className="text-[11px] text-muted-foreground leading-tight truncate">
              Satu pintu: universal → dapat ditimpa per-satker → sistem
            </p>
          </div>
          <button
            type="button"
            onClick={toggleTema}
            aria-label={isDark ? "Mode terang" : "Mode gelap"}
            title={isDark ? "Mode terang" : "Mode gelap"}
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="pengaturan-theme"
          >
            {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        <div className="flex bg-muted rounded-lg p-0.5 gap-0.5">
          {TABS.map(([k, label, Icon]) => (
            <button key={k} type="button" onClick={() => setTab(k)}
              className={`flex-1 text-[11px] sm:text-xs font-semibold py-1.5 rounded-md transition-colors flex items-center justify-center gap-1.5 min-w-0 min-h-0 ${tab === k ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
              data-testid={`pengaturan-tab-${k}`}>
              <Icon className="w-3.5 h-3.5" />{label}
            </button>
          ))}
        </div>

        {tab === "universal" && (
          <div className="space-y-3">
            <div className="rounded-lg border border-blue-500/20 bg-blue-500/5 px-3 py-2 flex items-start gap-2">
              <Info className="w-3.5 h-3.5 text-blue-500 flex-shrink-0 mt-0.5" />
              <p className="text-[11px] text-muted-foreground">
                Setelan <b>universal</b> berlaku untuk seluruh aplikasi & semua satker.
                Field kop yang diisi pada tab <b>Per-Satker</b> menimpa nilai di sini untuk laporan satker yang bersangkutan.
              </p>
            </div>
            {/* onClose sengaja TIDAK diteruskan: tombol "Tutup" editor dulunya
                melempar keluar seluruh halaman Pengaturan (bug navigasi). */}
            <ReportSettingsEditor />
            {pintasan.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-[11px] font-bold text-muted-foreground uppercase tracking-wide px-1">Setelan universal lainnya</p>
                {pintasan.map(({ label, desc, Icon, onClick }) => (
                  <button key={label} type="button" onClick={onClick}
                    className="w-full text-left rounded-xl border border-border bg-card p-3 hover:bg-muted/60 transition-colors flex items-center gap-3 min-w-0 min-h-0">
                    <Icon className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                    <span className="min-w-0 flex-1">
                      <span className="block text-xs font-semibold text-foreground">{label}</span>
                      <span className="block text-[10px] text-muted-foreground">{desc}</span>
                    </span>
                    <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "satker" && (
          <div className="space-y-2">
            <div className="rounded-lg border border-blue-500/20 bg-blue-500/5 px-3 py-2 flex items-start gap-2">
              <Info className="w-3.5 h-3.5 text-blue-500 flex-shrink-0 mt-0.5" />
              <p className="text-[11px] text-muted-foreground">
                Kop per-satker <b>menimpa</b> setelan universal untuk laporan kegiatan satker yang bersangkutan.
                Urutan resolusi: kegiatan → satker → universal.
                {onOpenSatker && (
                  <> {" "}Halaman penuh: <button type="button" className="underline font-semibold min-w-0 min-h-0" onClick={onOpenSatker}>Master Satker</button>.</>
                )}
              </p>
            </div>
            <SatkerPanel user={user} />
          </div>
        )}

        {tab === "sistem" && (
          <div className="space-y-2.5">
            {/* ── 0. Pemantauan kuota email (Resend) ── */}
            <div className="rounded-xl border border-border bg-card p-3.5 space-y-2.5" data-testid="pengaturan-email-monitor">
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-bold flex items-center gap-1.5">
                  <Mail className="w-4 h-4" />Pemantauan Email (Resend)
                </p>
                <button type="button" onClick={muatEmail} disabled={emailLoading}
                  className="h-7 w-7 rounded-md border border-border flex items-center justify-center text-muted-foreground hover:bg-muted min-w-0 min-h-0"
                  aria-label="Muat ulang" title="Muat ulang" data-testid="email-refresh">
                  <RotateCcw className={`w-3.5 h-3.5 ${emailLoading ? "animate-spin" : ""}`} />
                </button>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Semua email keluar (OTP registrasi, OTP lupa password, link tanda tangan)
                lewat Resend — terpantau di sini. Batas plan gratis: 100/hari &amp; 3.000/bulan.
              </p>

              {emailLoading && !email ? (
                <div className="py-6 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-muted-foreground" /></div>
              ) : !email ? (
                <p className="text-[11px] text-muted-foreground">Gagal memuat data pemantauan email.</p>
              ) : (
                <>
                  {!email.resend_terkonfigurasi && (
                    <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-2.5 py-1.5 flex items-start gap-1.5">
                      <ShieldAlert className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                      <p className="text-[10.5px] text-amber-700 dark:text-amber-300">
                        Layanan email (Resend) belum dikonfigurasi di server (RESEND_API_KEY kosong) —
                        angka di bawah tetap tercatat dari kejadian pengiriman.
                      </p>
                    </div>
                  )}
                  {(email.kuota_tercapai?.harian || email.kuota_tercapai?.bulanan) && (
                    <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-2.5 py-1.5 flex items-start gap-1.5" data-testid="email-kuota-tercapai">
                      <ShieldAlert className="w-3.5 h-3.5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
                      <p className="text-[10.5px] text-red-700 dark:text-red-300">
                        Resend menolak kirim karena <b>kuota {email.kuota_tercapai?.harian ? "harian" : "bulanan"} tercapai</b>.
                        Bila ini berulang, mungkin ketentuan limit Resend berubah — sesuaikan batas di bawah (super-admin).
                      </p>
                    </div>
                  )}

                  <BarKuota judul="Hari ini" d={email.harian} />
                  <BarKuota judul="Bulan ini" d={email.bulanan} />

                  <p className="text-[10px] text-muted-foreground">
                    Pengirim: <span className="font-mono">{email.pengirim || "—"}</span> ·
                    Periode {email.periode?.hari} / {email.periode?.bulan} (reset mengikuti Resend, {email.periode?.zona}).
                  </p>

                  {/* Ubah batas (dinamis) — khusus super-admin, bila Resend mengubah limit */}
                  {isSuperAdmin && (
                    limitDraf ? (
                      <div className="rounded-lg border border-border bg-muted/40 p-2.5 space-y-2">
                        <p className="text-[11px] font-semibold">Ubah batas kuota email</p>
                        <div className="grid grid-cols-2 gap-2">
                          <label className="text-[10px] text-muted-foreground">Per hari
                            <Input type="number" inputMode="numeric" min="1" value={limitDraf.harian} className="h-8 mt-0.5"
                              onChange={(e) => setLimitDraf((s) => ({ ...s, harian: e.target.value }))} data-testid="email-limit-harian" />
                          </label>
                          <label className="text-[10px] text-muted-foreground">Per bulan
                            <Input type="number" inputMode="numeric" min="1" value={limitDraf.bulanan} className="h-8 mt-0.5"
                              onChange={(e) => setLimitDraf((s) => ({ ...s, bulanan: e.target.value }))} data-testid="email-limit-bulanan" />
                          </label>
                        </div>
                        <div className="flex gap-2 justify-end">
                          <Button variant="outline" size="sm" className="h-8 text-xs" onClick={() => setLimitDraf(null)}>Batal</Button>
                          <Button size="sm" className="h-8 text-xs" onClick={simpanLimitEmail} disabled={limitSaving} data-testid="email-limit-simpan">
                            {limitSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : null}Simpan
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <button type="button" data-testid="email-limit-ubah"
                        onClick={() => setLimitDraf({ harian: email.harian?.limit ?? 100, bulanan: email.bulanan?.limit ?? 3000 })}
                        className="text-[11px] font-semibold text-blue-600 dark:text-blue-400 hover:underline min-w-0 min-h-0">
                        Ubah batas kuota (bila ketentuan Resend berubah)
                      </button>
                    )
                  )}
                </>
              )}
            </div>

            {/* ── 1. Backup sekarang ── */}
            <div className="rounded-xl border border-border bg-card p-3.5 space-y-2">
              <p className="text-xs font-bold flex items-center gap-1.5">
                <DatabaseBackup className="w-4 h-4" />Backup seluruh data
              </p>
              <p className="text-[11px] text-muted-foreground">
                Mencadangkan SEMUA koleksi data + berkas (foto & dokumen unggahan) menjadi satu ZIP —
                daftar koleksi dinamis, modul baru otomatis ikut. Proses berjalan di background.
              </p>
              <div className="flex items-center gap-2 flex-wrap">
                <Button size="sm" className="h-9 text-xs" disabled={!isSuperAdmin || backupLoading}
                  onClick={mulaiBackup} data-testid="pengaturan-backup">
                  {backupLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <DatabaseBackup className="w-3.5 h-3.5 mr-1.5" />}
                  Mulai Backup Sekarang
                </Button>
                <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground cursor-pointer">
                  <input type="checkbox" checked={arsipkanBackup}
                    onChange={(e) => setArsipkanBackup(e.target.checked)}
                    className="w-3.5 h-3.5" data-testid="pengaturan-backup-arsipkan" />
                  Simpan juga ke arsip server (tidak hanya diunduh)
                </label>
              </div>
              {!isSuperAdmin && <p className="text-[10px] text-amber-600 dark:text-amber-400">
                {isAdmin
                  ? "Backup mencakup data SELURUH satker — hanya super-admin pusat (admin lintas-satker) yang dapat menjalankannya. Admin satker mengelola datanya sendiri lewat modul."
                  : "Hanya super-admin pusat (admin lintas-satker) yang dapat menjalankan backup."}
              </p>}
            </div>

            {/* ── 2. Backup otomatis terjadwal ── */}
            {isSuperAdmin && (
              <div className="rounded-xl border border-border bg-card p-3.5 space-y-2" data-testid="pengaturan-backup-otomatis">
                <p className="text-xs font-bold flex items-center gap-1.5">
                  <Clock className="w-4 h-4 text-sky-500" />Backup otomatis harian
                </p>
                <p className="text-[11px] text-muted-foreground">
                  Server membuat backup sendiri setiap hari pada jam terjadwal (WIB) dan menyimpannya
                  di arsip server; arsip terlama dihapus otomatis melebihi kuota retensi.
                </p>
                {oto === null ? (
                  <Loader2 className="w-4 h-4 animate-spin text-sky-600" />
                ) : (
                  <div className="flex items-center gap-2 gap-y-1.5 flex-wrap">
                    <label className="flex items-center gap-1.5 text-[11px] font-semibold cursor-pointer">
                      <input type="checkbox" checked={!!oto.aktif}
                        onChange={(e) => setOto((o) => ({ ...o, aktif: e.target.checked }))}
                        className="w-3.5 h-3.5" data-testid="pengaturan-oto-aktif" />
                      Aktif
                    </label>
                    <label className="flex items-center gap-1 text-[11px] text-muted-foreground">
                      Jam
                      <Input type="time" value={oto.jam || "02:00"}
                        onChange={(e) => setOto((o) => ({ ...o, jam: e.target.value }))}
                        className="h-8 w-24 text-xs" data-testid="pengaturan-oto-jam" />
                      WIB
                    </label>
                    <label className="flex items-center gap-1 text-[11px] text-muted-foreground">
                      Simpan
                      <Input type="number" min="1" max="60" value={oto.retensi ?? 7}
                        onChange={(e) => setOto((o) => ({ ...o, retensi: e.target.value }))}
                        className="h-8 w-16 text-xs" data-testid="pengaturan-oto-retensi" />
                      arsip terakhir
                    </label>
                    <Button size="sm" variant="outline" className="h-8 text-xs min-h-0" disabled={otoSaving}
                      onClick={simpanOto} data-testid="pengaturan-oto-simpan">
                      {otoSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Simpan"}
                    </Button>
                    {oto.terakhir && (
                      <span className="text-[10px] text-muted-foreground">Terakhir jalan: {oto.terakhir}</span>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ── 3. Arsip backup di server ── */}
            {isSuperAdmin && (
              <div className="rounded-xl border border-border bg-card overflow-hidden" data-testid="pengaturan-arsip">
                <div className="px-3.5 py-2.5 border-b border-border flex items-center gap-2 flex-wrap">
                  <p className="text-xs font-bold flex items-center gap-1.5 flex-1">
                    <FileDown className="w-4 h-4 text-emerald-600" />Arsip backup di server
                  </p>
                  {arsip && (
                    <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 text-[10px] font-semibold">
                      {arsip.length} berkas · {fmtUkuran((arsip || []).reduce((a, b) => a + (b.ukuran || 0), 0))}
                    </span>
                  )}
                </div>
                {arsip === null ? (
                  <div className="flex items-center justify-center py-6"><Loader2 className="w-5 h-5 animate-spin text-emerald-600" /></div>
                ) : arsip.length === 0 ? (
                  <p className="text-[11px] text-muted-foreground text-center py-5 px-4">
                    Belum ada arsip — aktifkan backup otomatis di atas, atau centang
                    &quot;Simpan juga ke arsip server&quot; saat backup manual.
                  </p>
                ) : (
                  <ul className="divide-y divide-border/60">
                    {arsip.map((a) => (
                      <li key={a.nama} className="px-3.5 py-2 flex items-center gap-2 flex-wrap" data-testid={`arsip-${a.nama}`}>
                        <div className="min-w-0 flex-1">
                          <p className="text-[11px] font-mono font-semibold text-foreground truncate">{a.nama}</p>
                          <p className="text-[10px] text-muted-foreground">
                            {String(a.waktu).slice(0, 16).replace("T", " ")} UTC · {fmtUkuran(a.ukuran)} · {a.jenis}
                          </p>
                        </div>
                        <button type="button" title="Unduh arsip" aria-label={`Unduh ${a.nama}`}
                          onClick={() => downloadFileWithProgress(`${API}/backup/arsip/${a.nama}`, a.nama, { label: a.nama }).catch(() => {})}
                          className="h-7 w-7 rounded-lg border border-border text-foreground/70 flex items-center justify-center hover:bg-muted min-h-0 min-w-0">
                          <FileDown className="w-3.5 h-3.5" />
                        </button>
                        <button type="button" title="Pulihkan data dari arsip ini" aria-label={`Pulihkan dari ${a.nama}`}
                          onClick={() => pulihkanDariArsip(a)}
                          className="h-7 w-7 rounded-lg border border-amber-500/40 text-amber-600 dark:text-amber-400 flex items-center justify-center hover:bg-amber-500/10 min-h-0 min-w-0"
                          data-testid={`arsip-restore-${a.nama}`}>
                          <RotateCcw className="w-3.5 h-3.5" />
                        </button>
                        <button type="button" title="Hapus arsip" aria-label={`Hapus ${a.nama}`}
                          onClick={() => hapusArsip(a)}
                          className="h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 min-h-0 min-w-0">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {/* ── 4. Pulihkan dari file & Reset ── */}
            <div className="rounded-xl border border-amber-500/30 bg-card p-3.5 space-y-2">
              <p className="text-xs font-bold flex items-center gap-1.5">
                <ShieldAlert className="w-4 h-4 text-amber-500" />Pulihkan (restore) & Reset data
              </p>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Kedua aksi <b>mengganti/menghapus data secara permanen</b> dengan konfirmasi berlapis.
                Restore membuat <b>safety backup</b> dulu (gagal → data kembali). Reset TIDAK menghapus
                akun, setelan, pemetaan akuntansi, dan seluruh master referensi (kodefikasi, pegawai,
                pejabat, ruangan, unit kerja) — semuanya selamat.
              </p>
              <div className="flex items-center gap-2 flex-wrap">
                <Button size="sm" variant="outline" className="h-9 text-xs gap-1.5 border-amber-500/50 text-amber-700 dark:text-amber-400 hover:bg-amber-500/10"
                  disabled={!isSuperAdmin} onClick={() => setShowRestore(true)} data-testid="pengaturan-restore">
                  <Upload className="w-3.5 h-3.5" />Pulihkan dari File Backup
                </Button>
                <Button size="sm" variant="outline" className="h-9 text-xs gap-1.5 border-red-500/50 text-red-600 hover:bg-red-500/10"
                  disabled={!isSuperAdmin} onClick={() => setShowResetAll(true)} data-testid="pengaturan-reset">
                  <Trash2 className="w-3.5 h-3.5" />Reset Seluruh Data
                </Button>
              </div>
              {!isSuperAdmin && <p className="text-[10px] text-amber-600 dark:text-amber-400">
                {isAdmin
                  ? "Restore/Reset mengganti/menghapus data SELURUH satker — khusus super-admin pusat (admin lintas-satker), bukan admin satker."
                  : "Hanya super-admin pusat (admin lintas-satker) yang dapat memulihkan/mereset data."}
              </p>}
            </div>
          </div>
        )}
      </main>

      {isSuperAdmin && (
        <ResetAllDialog open={showResetAll} onClose={() => setShowResetAll(false)}
          userId={user?.id} onSuccess={() => muatSistem()} />
      )}
      {isSuperAdmin && (
        <RestoreDialog open={showRestore} onClose={() => setShowRestore(false)}
          token={localStorage.getItem("token")} onSuccess={() => muatSistem()} />
      )}
      {confirmDialog}
    </div>
  );
}
