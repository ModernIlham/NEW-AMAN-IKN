// ============================================================================
// APP.JS - OPTIMIZED VERSION
// ============================================================================
// Code splitting with React.lazy + Suspense
// Lazy loads pages for smaller initial bundle
//
// Setiap halaman dibungkus <HalamanLazy> = BatasGalat + Suspense. Tanpa batas
// galat, satu potongan kode yang gagal diunduh (luring / versi baru ter-deploy)
// melepas SELURUH pohon React dan menyisakan layar putih polos.
// ============================================================================

import React, { useState, useEffect, useCallback, useRef, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "@/App.css";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { useDarkMode } from "@/hooks/useDarkMode";
import { useBackGuard } from "@/hooks/useBackGuard";
import { startUpdateCheck } from "@/lib/updateCheck";
import BackgroundTaskBar from "@/components/BackgroundTaskBar";
import PusatUnduhan from "@/components/PusatUnduhan";
import { clearAllSnapshots, ensureSnapshotOwner } from "@/lib/offlineSnapshot";
import axios from "axios";
import { TENGGAT_BAKA } from "@/lib/muatAndal";
import { terapkanHeaderSatker } from "./lib/satkerAktif";
import SatkerAktifBar from "@/components/SatkerAktifBar";
import { HalamanLazy } from "@/components/BatasGalat";

// ============================================================================
// LAZY LOADED PAGES - Code Splitting
// Each page becomes a separate chunk, loaded only when needed
// ============================================================================
const LoginPage = lazy(() => import("./pages/LoginPage"));
const HalamanGalat = lazy(() => import("./pages/HalamanGalat"));
const Halaman403Lazy = lazy(() => import("./pages/HalamanGalat").then((m) => ({ default: m.Halaman403 })));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const InfoPage = lazy(() => import("./pages/InfoPage"));
const ModuleHomePage = lazy(() => import("./pages/ModuleHomePage"));
const KodefikasiPage = lazy(() => import("./pages/KodefikasiPage"));
const PejabatPage = lazy(() => import("./pages/PejabatPage"));
const RuanganPage = lazy(() => import("./pages/RuanganPage"));
const SpasialMasterPage = lazy(() => import("./pages/SpasialMasterPage"));
const PelacakanPage = lazy(() => import("./pages/PelacakanPage"));
const ReferensiAkunPage = lazy(() => import("./pages/ReferensiAkunPage"));
const PegawaiPage = lazy(() => import("./pages/PegawaiPage"));
const PersediaanPage = lazy(() => import("./pages/PersediaanPage"));
const PelaporanPage = lazy(() => import("./pages/PelaporanPage"));
const PersuratanPage = lazy(() => import("./pages/PersuratanPage"));
const PenggunaanPage = lazy(() => import("./pages/PenggunaanPage"));
const PengamananPage = lazy(() => import("./pages/PengamananPage"));
const PemeliharaanPage = lazy(() => import("./pages/PemeliharaanPage"));
const PerencanaanPage = lazy(() => import("./pages/PerencanaanPage"));
const PenilaianPage = lazy(() => import("./pages/PenilaianPage"));
const PenghapusanPage = lazy(() => import("./pages/PenghapusanPage"));
const PemanfaatanPage = lazy(() => import("./pages/PemanfaatanPage"));
const PemusnahanPage = lazy(() => import("./pages/PemusnahanPage"));
const PemindahtangananPage = lazy(() => import("./pages/PemindahtangananPage"));
const WasdalPage = lazy(() => import("./pages/WasdalPage"));
const PenganggaranPage = lazy(() => import("./pages/PenganggaranPage"));
const PengadaanPage = lazy(() => import("./pages/PengadaanPage"));
const TtdPublikPage = lazy(() => import("./pages/TtdPublikPage"));
const LacakPage = lazy(() => import("./pages/LacakPage"));
const PetaKolaborasiPage = lazy(() => import("./pages/PetaKolaborasiPage"));
const TtdPermintaanPage = lazy(() => import("./pages/TtdPermintaanPage"));
const TautanPendekPage = lazy(() => import("./pages/TautanPendekPage"));
const SatkerPage = lazy(() => import("./pages/SatkerPage"));
const PengaturanPage = lazy(() => import("./pages/PengaturanPage"));
const PembukuanPage = lazy(() => import("./pages/PembukuanPage"));

// ============================================================================
// LOADING FALLBACK - Shown while lazy components load
// ============================================================================
function PageLoader() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center">
        <div className="w-10 h-10 border-[3px] border-muted border-t-primary rounded-full animate-spin mx-auto mb-3" />
        <p className="text-sm text-muted-foreground">Memuat halaman...</p>
      </div>
    </div>
  );
}

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

// Auto-logout after this long without any user interaction. 30 minutes is the
// common industry default for business apps (well under the 24h token TTL).
const IDLE_TIMEOUT_MS = 30 * 60 * 1000;

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const { dark, toggle: toggleDark } = useDarkMode();

  // Deteksi versi baru pasca-deploy: pengguna diberi tombol "Muat Ulang"
  // alih-alih harus menghapus cache manual (lihat lib/updateCheck.js).
  useEffect(() => startUpdateCheck(), []);

  // Penjaga Back/Forward TINGKAT APLIKASI (lantai dasar tumpukan guard).
  // Sebelumnya guard hanya terpasang saat halaman dashboard ter-mount, sehingga
  // di halaman login (atau sebelum halaman siap) Back/Forward bisa keluar dari
  // aplikasi. Dipasang di root: sentinel ditanam sejak aplikasi dibuka —
  // pushState sekaligus MEMANGKAS riwayat maju, jadi Forward tidak lagi bisa
  // membawa keluar; Back tanpa handler halaman = tetap diam di aplikasi.
  useBackGuard(useCallback(() => { /* tetap di aplikasi */ }, []));

  // Session teardown shared by manual logout, 401 auto-logout, and idle
  // timeout. Stable identity (useCallback []) so interceptors/timers can
  // close over it safely. Deliberately keeps 'currentActivityId' so an
  // expired session resumes in the same activity after re-login (the manual
  // Keluar button clears it separately in DashboardPage).
  const forceLogout = useCallback((message) => {
    const hadSession = !!localStorage.getItem('token');
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    // Satker Aktif jangan bocor ke sesi berikutnya di peramban bersama.
    localStorage.removeItem('satker_aktif');
    setUser(null);
    if (hadSession && message) toast.error(message, { duration: 6000 });
  }, []);

  // Global axios interceptor: auto-attach JWT bearer token to every request.
  // Previously only specific call-sites (heartbeat, login) sent the token,
  // which left every other endpoint un-authenticated on the wire — a hidden
  // security gap when the backend started requiring auth.
  useEffect(() => {
    // LANTAI TENGGAT GLOBAL. Sebelumnya `axios.defaults.timeout` tak pernah
    // dipasang di mana pun, dan hanya 14 dari 227 pemanggil `axios.get`
    // menyetel timeout sendiri. Di jaringan lapangan bentuk kegagalan yang
    // paling sering BUKAN "koneksi ditolak" — itu cepat dan tertangkap catch —
    // melainkan koneksi MENGGANTUNG. Tanpa tenggat, `await` pada keadaan itu
    // tak pernah selesai: catch tak jalan, finally tak membereskan spinner,
    // dan operator menatap loading tanpa akhir lalu menyimpulkan aplikasinya
    // rusak. Penjaga yang sudah ada pun ikut mandul — pagar "8 kegagalan
    // beruntun" hanya menghitung permintaan yang SELESAI.
    //
    // Ini LANTAI, bukan plafon: pemanggil yang memang berat (unggah/ekspor)
    // tetap boleh menaikkannya sendiri lewat `{ timeout: ... }` per-request,
    // dan nilai per-request selalu menang atas default ini.
    axios.defaults.timeout = TENGGAT_BAKA;
    const id = axios.interceptors.request.use(config => {
      const token = localStorage.getItem('token');
      if (token && !config.headers.Authorization) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      // "Satker Aktif" super-admin (act-as): backend menyuntikkan kode ini
      // sehingga stempel & scoping data mengikuti satker terpilih.
      return terapkanHeaderSatker(config);
    });
    // Global 401 handler: an expired/invalid session logs the user out and
    // routes to /login (via the user-state redirect). Skips /auth/ requests
    // so a wrong password on the login form isn't treated as session expiry.
    // 403 is intentionally NOT handled here — it includes legitimate RBAC
    // denials (non-admin hitting an admin action) that must not log out.
    const resId = axios.interceptors.response.use(
      res => res,
      error => {
        const status = error?.response?.status;
        const url = error?.config?.url || '';
        // /ttd/tandatangan & /ttd/verifikasi dipakai TAMU e-sign (token link,
        // bukan sesi) — 401 di sana berarti link invalid/kedaluwarsa, BUKAN
        // sesi berakhir; jangan paksa logout user yang kebetulan login.
        if (status === 401 && !url.includes('/auth/')
            && !url.includes('/ttd/tandatangan') && !url.includes('/ttd/verifikasi')
            && !url.includes('/ttd/olah-foto')
            && !url.includes('/peta/kolaborasi')) {
          forceLogout("Sesi Anda telah berakhir. Silakan login kembali.");
        }
        return Promise.reject(error);
      }
    );
    return () => {
      axios.interceptors.request.eject(id);
      axios.interceptors.response.eject(resId);
    };
  }, [forceLogout]);

  // Idle timeout: logout after IDLE_TIMEOUT_MS without interaction. Activity
  // is sampled cheaply (timestamp ref + a 1-minute check interval) instead of
  // resetting a timer on every mousemove.
  const lastActivityRef = useRef(Date.now());
  useEffect(() => {
    if (!user) return;
    lastActivityRef.current = Date.now();
    const markActivity = () => { lastActivityRef.current = Date.now(); };
    const events = ['mousedown', 'keydown', 'touchstart', 'scroll', 'mousemove'];
    events.forEach(evt => window.addEventListener(evt, markActivity, { passive: true }));
    const check = setInterval(() => {
      if (Date.now() - lastActivityRef.current >= IDLE_TIMEOUT_MS) {
        forceLogout("Anda keluar otomatis karena tidak ada aktivitas selama 30 menit.");
      }
    }, 60 * 1000);
    return () => {
      events.forEach(evt => window.removeEventListener(evt, markActivity));
      clearInterval(check);
    };
  }, [user, forceLogout]);

  // Heartbeat for online/offline tracking
  const sendHeartbeat = useCallback(async () => {
    const token = localStorage.getItem('token');
    if (!token) return;
    try {
      await axios.post(`${BACKEND_URL}/api/auth/heartbeat`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
    } catch (e) {
      // Heartbeat failures are non-fatal (network blip, token expired) —
      // the next interval or a re-login will recover.
      if (process.env.NODE_ENV !== "production") {
        console.warn("[app] Heartbeat failed:", e?.response?.status || e?.message);
      }
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    sendHeartbeat();
    const interval = setInterval(sendHeartbeat, 2 * 60 * 1000); // Every 2 minutes
    return () => clearInterval(interval);
  }, [user, sendHeartbeat]);

  useEffect(() => {
    // Check if user is already logged in
    const token = localStorage.getItem('token');
    const userData = localStorage.getItem('user');
    
    if (token && userData) {
      try {
        setUser(JSON.parse(userData));
      } catch (error) {
        console.error("Error parsing user data:", error);
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        localStorage.removeItem('satker_aktif');
      }
    }
    setLoading(false);
  }, []);

  const handleLogin = (userData, token, mediaToken) => {
    // A DIFFERENT account logging in on this device must never see the
    // previous user's cached offline snapshot — wipe it before the new
    // session starts. Same-user re-login keeps the cache (best-effort async;
    // the snapshot lib also refuses to delta-sync across user ids).
    ensureSnapshotOwner(userData?.id);
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(userData));
    // Token media (30 hari) menstabilkan URL <img> antar login sehingga cache
    // foto browser tetap hidup. PERTAHANKAN yang lama bila masih milik user
    // yang sama & masih segar (>7 hari) — mengganti token = URL berubah =
    // seluruh cache foto ter-bust; itu justru yang mau kita hindari.
    if (mediaToken) {
      try {
        const old = localStorage.getItem('media_token');
        let keepOld = false;
        if (old) {
          const p = JSON.parse(atob(old.split('.')[1] || '') || '{}');
          keepOld = p.user_id === userData?.id && (p.exp || 0) * 1000 - Date.now() > 7 * 86400e3;
        }
        if (!keepOld) localStorage.setItem('media_token', mediaToken);
      } catch { localStorage.setItem('media_token', mediaToken); }
    }
    // Login baru selalu mendarat di Beranda Modul (rumah Siklus BMN) —
    // pilihan modul bersifat per-sesi tab (sessionStorage), jadi reload di
    // tengah pekerjaan lapangan TIDAK melempar user keluar dari modulnya.
    sessionStorage.removeItem('aman_module');
    setModuleChosen(false);
    setUser(userData);
  };

  // SNAPSHOT CLEAR POLICY — manual logout only.
  // This handler runs ONLY for the explicit "Keluar" button (DashboardPage
  // handleLogout → onLogout → here): the user is done with the device, so the
  // offline read cache is wiped (shared-device protection). Automatic
  // logouts — 401 session expiry and the 30-minute idle timeout — call
  // forceLogout(message) directly WITHOUT clearing snapshots: a surveyor in
  // the field whose session expires offline must not lose the cached asset
  // list (field data protection); it stays scoped to their userId and expires
  // via the 7-day TTL anyway.
  const handleLogout = () => {
    clearAllSnapshots();
    // Logout EKSPLISIT (perangkat berbagi): cabut juga token media agar tidak
    // ada akses baca foto tersisa. Auto-logout (401/idle) sengaja MEMBIARKAN
    // token media hidup supaya cache foto surveyor tak ter-bust tiap hari.
    localStorage.removeItem('media_token');
    sessionStorage.removeItem('aman_module');
    setModuleChosen(false);
    forceLogout();
  };

  const [showInfo, setShowInfo] = useState(false);
  // "Rumah modul" Siklus BMN: login mendarat di Beranda Modul; masuk ke
  // Inventarisasi menandai pilihan per-tab (sessionStorage) sehingga reload
  // kembali ke modul yang sama, tab/login baru kembali ke beranda.
  const [moduleChosen, setModuleChosen] = useState(() => sessionStorage.getItem('aman_module') === 'inventarisasi');
  const enterInventarisasi = useCallback(() => {
    sessionStorage.setItem('aman_module', 'inventarisasi');
    setModuleChosen(true);
  }, []);
  const showModuleHome = useCallback(() => {
    sessionStorage.removeItem('aman_module');
    setModuleChosen(false);
  }, []);
  // Halaman Referensi Kodefikasi (perkakas Penatausahaan dari Beranda Modul)
  const [showKodefikasi, setShowKodefikasi] = useState(false);
  const [showPejabat, setShowPejabat] = useState(false);
  const [showRuangan, setShowRuangan] = useState(false);
  const [showSpasial, setShowSpasial] = useState(false);
  const [showPelacakan, setShowPelacakan] = useState(false);
  // Referensi Akun BAS gabungan (segmen akun + pemetaan aset & persediaan)
  const [showReferensiAkun, setShowReferensiAkun] = useState(false);
  const [showPegawai, setShowPegawai] = useState(false);
  // Halaman Master Persediaan (modul Inventarisasi Persediaan — sebagian aktif)
  const [showPersediaan, setShowPersediaan] = useState(false);
  // Halaman hub Pelaporan (arsip laporan lintas kegiatan)
  const [showPelaporan, setShowPelaporan] = useState(false);
  // Halaman Registrasi Persuratan (buku agenda & booking nomor surat)
  const [showPersuratan, setShowPersuratan] = useState(false);
  // Halaman Penggunaan (rekap aset per pemegang)
  const [showPenggunaan, setShowPenggunaan] = useState(false);
  // Halaman Pengamanan (dasbor tertib administrasi + sengketa)
  const [showPengamanan, setShowPengamanan] = useState(false);
  // Halaman Pemeliharaan (catatan riwayat + biaya per aset)
  const [showPemeliharaan, setShowPemeliharaan] = useState(false);
  // Halaman Perencanaan (kandidat RKBMN pemeliharaan)
  const [showPerencanaan, setShowPerencanaan] = useState(false);
  // Halaman Penilaian (posisi penyusutan)
  const [showPenilaian, setShowPenilaian] = useState(false);
  // Halaman Penghapusan (kandidat usul hapus)
  const [showPenghapusan, setShowPenghapusan] = useState(false);
  // Halaman Pemanfaatan (register perjanjian)
  const [showPemanfaatan, setShowPemanfaatan] = useState(false);
  // Halaman Pemusnahan (register BA)
  const [showPemusnahan, setShowPemusnahan] = useState(false);
  // Halaman Pemindahtanganan (register usulan)
  const [showPemindahtanganan, setShowPemindahtanganan] = useState(false);
  // Halaman Wasdal (dasbor pemantauan)
  const [showWasdal, setShowWasdal] = useState(false);
  // Halaman Penganggaran (register usulan)
  const [showPenganggaran, setShowPenganggaran] = useState(false);
  // Halaman Pengadaan (register perolehan)
  const [showPengadaan, setShowPengadaan] = useState(false);
  // Halaman dasbor Tanda Tangan Elektronik (permintaan e-sign via link)
  const [showTtd, setShowTtd] = useState(false);
  // Halaman Master Satker (profil & kop per-satker)
  const [showSatker, setShowSatker] = useState(false);
  // Halaman Pengaturan terpadu (universal / per-satker / sistem)
  const [showPengaturan, setShowPengaturan] = useState(false);
  // Asal navigasi: bila sub-halaman (Satker/ReferensiAkun/Persuratan/
  // Pelaporan) DIBUKA DARI Pengaturan, tombol Kembali-nya balik ke Pengaturan
  // (bukan terlempar ke Beranda Modul). Ref agar tak memicu render.
  const asalPengaturan = useRef(false);
  const bukaDariPengaturan = (buka) => {
    asalPengaturan.current = true;
    setShowPengaturan(false);
    buka();
  };
  const kembaliSubHalaman = (tutup) => {
    tutup();
    if (asalPengaturan.current) {
      asalPengaturan.current = false;
      setShowPengaturan(true);
    }
  };
  // Halaman Pembukuan (DBKP global + Buku Barang)
  const [showPembukuan, setShowPembukuan] = useState(false);

  // ── HALAMAN PUBLIK E-SIGN ──────────────────────────────────────────────
  // /ttd/:id (link tanda tangan yang dibagikan) & /ttd/verifikasi/:id (QR)
  // harus bisa dibuka SIAPA PUN TANPA LOGIN — diperiksa SEBELUM gate auth
  // dan seluruh early-return modul, murni dari pathname.
  // TANPA SatkerAktifBar — alasan sama dengan peta kolaboratif di bawah.
  // ── TAUTAN PENDEK /s/{kode} ────────────────────────────────────────────
  // Diperiksa SEBELUM gate auth: yang membukanya tamu tanpa akun (penanda
  // tangan, pemindai QR). Halaman ini hanya menukar kode lalu mengalihkan.
  if (window.location.pathname.startsWith('/s/')) {
    return (
      <div className="App">
        <HalamanLazy fallback={<PageLoader />}>
          <TautanPendekPage />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  if (window.location.pathname.startsWith('/ttd/')) {
    return (
      <div className="App">
        <HalamanLazy fallback={<PageLoader />}>
          <TtdPublikPage />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // ── HALAMAN PUBLIK PENDAMPING PELACAKAN ────────────────────────────────
  // /lacak dibuka pemegang barang TANPA LOGIN — token perangkat yang jadi
  // kredensialnya. Sengaja diperiksa sebelum gate auth: pemegang barang
  // umumnya bukan pengguna aplikasi ini sama sekali.
  if (window.location.pathname.startsWith('/lacak')) {
    return (
      <div className="App">
        <HalamanLazy fallback={<PageLoader />}>
          <LacakPage />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // ── HALAMAN PUBLIK PETA KOLABORATIF ────────────────────────────────────
  // /peta/kolaborasi/:id?token= dibuka SIAPA PUN saat masa tayang aktif; user
  // login satker terkait juga pasca-kedaluwarsa — sama gate publik e-sign.
  // TANPA SatkerAktifBar: halaman publik bukan tempat memilih satker aktif —
  // pemilih itu mengatur satker mana yang sedang dikelola di DALAM aplikasi,
  // sementara peta ini hanya menampilkan satu kegiatan milik satu satker yang
  // sudah ditetapkan oleh linknya. Bandingkan /lacak yang memang sudah bersih.
  if (window.location.pathname.startsWith('/peta/kolaborasi/')) {
    return (
      <div className="App">
        <HalamanLazy fallback={<PageLoader />}>
          <PetaKolaborasiPage />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  if (loading) {
    return <PageLoader />;
  }

  if (showInfo) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <InfoPage onBack={() => setShowInfo(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Referensi Kodefikasi — perkakas Penatausahaan, dibuka dari Beranda Modul.
  if (user && showKodefikasi) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <KodefikasiPage user={user} onBack={() => setShowKodefikasi(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Referensi Pejabat Penatausahaan — perkakas Penatausahaan, dibuka dari Beranda Modul.
  if (user && showPejabat) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <PejabatPage user={user} onBack={() => setShowPejabat(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Hierarki Spasial — denah kawasan berlapis (Fase 2), dari Beranda Modul.
  if (user && showSpasial) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <SpasialMasterPage user={user} onBack={() => setShowSpasial(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Pelacakan Aset — muka pipeline IoT (Fase 11) + geofence (Fase 12).
  if (user && showPelacakan) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <PelacakanPage user={user} onBack={() => setShowPelacakan(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Referensi Ruangan — perkakas Penatausahaan, dibuka dari Beranda Modul.
  if (user && showRuangan) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <RuanganPage user={user} onBack={() => setShowRuangan(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Referensi Akun Neraca (BAS) — perkakas Penatausahaan, dibuka dari Beranda Modul.
  if (user && showReferensiAkun) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <ReferensiAkunPage user={user} onBack={() => kembaliSubHalaman(() => setShowReferensiAkun(false))} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Master Pegawai — data kepegawaian menyeluruh, dibuka dari Beranda Modul.
  if (user && showPegawai) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <PegawaiPage user={user} onBack={() => setShowPegawai(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Master Persediaan — modul Inventarisasi Persediaan (sebagian aktif).
  if (user && showPersediaan) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <PersediaanPage user={user} onBack={() => setShowPersediaan(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Registrasi Persuratan — buku agenda & booking nomor naskah dinas.
  if (user && showPersuratan) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <PersuratanPage user={user} onBack={() => kembaliSubHalaman(() => setShowPersuratan(false))} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Hub Pelaporan — arsip laporan lintas kegiatan (sebagian aktif).
  if (user && showPelaporan) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <PelaporanPage user={user} onBack={() => kembaliSubHalaman(() => setShowPelaporan(false))} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Penggunaan — rekap aset per pemegang (Fase 3 tahap awal).
  if (user && showPenggunaan) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <PenggunaanPage user={user} onBack={() => setShowPenggunaan(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Pengamanan — dasbor tertib administrasi + sengketa (Fase 3 tahap awal).
  if (user && showPengamanan) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <PengamananPage user={user} onBack={() => setShowPengamanan(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Pemeliharaan — catatan riwayat + biaya per aset (Fase 3 tahap awal).
  if (user && showPemeliharaan) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <PemeliharaanPage user={user} onBack={() => setShowPemeliharaan(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Perencanaan — kandidat RKBMN pemeliharaan (Fase 4 tahap awal).
  if (user && showPerencanaan) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <PerencanaanPage user={user} onBack={() => setShowPerencanaan(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Penilaian — posisi penyusutan aset tetap (Fase 5 tahap awal).
  if (user && showPenilaian) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <PenilaianPage user={user} onBack={() => setShowPenilaian(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Penghapusan — kandidat usul hapus (Fase 6 tahap awal).
  if (user && showPenghapusan) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <PenghapusanPage user={user} onBack={() => setShowPenghapusan(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Pemanfaatan — register perjanjian (Fase 5 tahap awal).
  if (user && showPemanfaatan) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <PemanfaatanPage user={user} onBack={() => setShowPemanfaatan(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Pemusnahan — register BA (Fase 6 tahap awal).
  if (user && showPemusnahan) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <PemusnahanPage user={user} onBack={() => setShowPemusnahan(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Pemindahtanganan — register usulan (Fase 6 tahap awal).
  if (user && showPemindahtanganan) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <PemindahtangananPage user={user} onBack={() => setShowPemindahtanganan(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Wasdal — dasbor pemantauan (PMK 207/2021, tahap awal).
  if (user && showWasdal) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <WasdalPage user={user} onBack={() => setShowWasdal(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Penganggaran — register usulan (Fase 4 tahap awal).
  if (user && showPenganggaran) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <PenganggaranPage user={user} onBack={() => setShowPenganggaran(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Pengadaan — register perolehan (Fase 4 tahap awal).
  if (user && showPengadaan) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <PengadaanPage user={user} onBack={() => setShowPengadaan(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Tanda Tangan Elektronik — dasbor permintaan e-sign via link.
  if (user && showTtd) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <TtdPermintaanPage user={user} onBack={() => setShowTtd(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Pengaturan terpadu — satu pintu setelan universal/per-satker/sistem.
  if (user && showPengaturan) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <PengaturanPage
            user={user}
            dark={dark}
            toggleDark={toggleDark}
            onBack={() => setShowPengaturan(false)}
            onOpenSatker={() => bukaDariPengaturan(() => setShowSatker(true))}
            onOpenReferensiAkun={() => bukaDariPengaturan(() => setShowReferensiAkun(true))}
            onOpenPersuratan={() => bukaDariPengaturan(() => setShowPersuratan(true))}
            onOpenPelaporan={() => bukaDariPengaturan(() => setShowPelaporan(true))}
          />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Pembukuan — DBKP global + Buku Barang (jurnal mutasi).
  if (user && showPembukuan) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <PembukuanPage user={user} onBack={() => setShowPembukuan(false)} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Master Satker — profil & kop per-satker (multi-satker DB bersama).
  if (user && showSatker) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <SatkerPage user={user} onBack={() => kembaliSubHalaman(() => setShowSatker(false))} />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  // Beranda Modul — rumah Siklus Pengelolaan BMN. Tampil setelah login
  // sampai user memilih modul; modul selain Inventarisasi menampilkan
  // konsep "Segera Hadir" di dalam halaman ini.
  if (user && !moduleChosen) {
    return (
      <div className="App">
      <SatkerAktifBar user={user} />
        <HalamanLazy fallback={<PageLoader />}>
          <ModuleHomePage
            user={user}
            onLogout={handleLogout}
            dark={dark}
            toggleDark={toggleDark}
            onShowInfo={() => setShowInfo(true)}
            onEnterInventarisasi={enterInventarisasi}
            onOpenKodefikasi={() => setShowKodefikasi(true)}
            onOpenPejabat={() => setShowPejabat(true)}
            onOpenRuangan={() => setShowRuangan(true)}
            onOpenSpasial={() => setShowSpasial(true)}
            onOpenPelacakan={() => setShowPelacakan(true)}
            onOpenReferensiAkun={() => setShowReferensiAkun(true)}
            onOpenPegawai={() => setShowPegawai(true)}
            onOpenPersediaan={() => setShowPersediaan(true)}
            onOpenPelaporan={() => setShowPelaporan(true)}
            onOpenPersuratan={() => setShowPersuratan(true)}
            onOpenPenggunaan={() => setShowPenggunaan(true)}
            onOpenPengamanan={() => setShowPengamanan(true)}
            onOpenPemeliharaan={() => setShowPemeliharaan(true)}
            onOpenPerencanaan={() => setShowPerencanaan(true)}
            onOpenPenilaian={() => setShowPenilaian(true)}
            onOpenPenghapusan={() => setShowPenghapusan(true)}
            onOpenPemanfaatan={() => setShowPemanfaatan(true)}
            onOpenPemusnahan={() => setShowPemusnahan(true)}
            onOpenPemindahtanganan={() => setShowPemindahtanganan(true)}
            onOpenWasdal={() => setShowWasdal(true)}
            onOpenPenganggaran={() => setShowPenganggaran(true)}
            onOpenPengadaan={() => setShowPengadaan(true)}
            onOpenTtd={() => setShowTtd(true)}
            onOpenPengaturan={() => setShowPengaturan(true)}
            onOpenPembukuan={() => setShowPembukuan(true)}
          />
        </HalamanLazy>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  return (
    <div className="App">
      <SatkerAktifBar user={user} />
      {/* S1 — Skip link for keyboard/screen-reader users (WCAG 2.4.1 Bypass Blocks) */}
      <a href="#main-content" className="skip-link">
        Lewati ke konten utama
      </a>
      <BrowserRouter>
        <HalamanLazy fallback={<PageLoader />}>
          <main id="main-content" role="main" aria-label="Konten utama aplikasi AMAN">
            <Routes>
              <Route
                path="/login"
                element={
                  user ? <Navigate to="/" replace /> : <LoginPage onLogin={handleLogin} dark={dark} toggleDark={toggleDark} onShowInfo={() => setShowInfo(true)} />
                }
              />
              <Route
                path="/"
                element={
                  user ? (
                    <DashboardPage user={user} onLogout={handleLogout} dark={dark} toggleDark={toggleDark} onShowInfo={() => setShowInfo(true)} onShowModules={showModuleHome} />
                  ) : (
                    <Navigate to="/login" replace />
                  )
                }
              />
              {/* 403 eksplisit (dipakai saat akses ditolak) */}
              <Route path="/403" element={<Halaman403Lazy />} />
              {/* Alamat tak dikenal → halaman 404 ber-glitch (bukan lagi
                  redirect diam-diam ke beranda yang membingungkan) */}
              <Route path="*" element={<HalamanGalat />} />
            </Routes>
          </main>
        </HalamanLazy>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
      {/* Widget latar kanan-bawah (backup). Pusat Unduhan TIDAK lagi ikut
          tumpukan ini: ia kini gelembung mengambang ber-posisi sendiri yang
          menempel di dinding kiri/kanan sesuai pilihan pengguna. */}
      <div className="fixed bottom-4 right-4 z-[90] flex flex-col items-end gap-2">
        <BackgroundTaskBar isAdmin={user?.role === "admin"} />
      </div>
      <PusatUnduhan aktif={!!user} />
    </div>
  );
}

export default App;
