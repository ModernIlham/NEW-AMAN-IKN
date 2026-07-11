// ============================================================================
// APP.JS - OPTIMIZED VERSION
// ============================================================================
// Code splitting with React.lazy + Suspense
// Lazy loads pages for smaller initial bundle
// ============================================================================

import React, { useState, useEffect, useCallback, useRef, lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "@/App.css";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { useDarkMode } from "@/hooks/useDarkMode";
import { useBackGuard } from "@/hooks/useBackGuard";
import { startUpdateCheck } from "@/lib/updateCheck";
import BackgroundTaskBar from "@/components/BackgroundTaskBar";
import { clearAllSnapshots, ensureSnapshotOwner } from "@/lib/offlineSnapshot";
import axios from "axios";

// ============================================================================
// LAZY LOADED PAGES - Code Splitting
// Each page becomes a separate chunk, loaded only when needed
// ============================================================================
const LoginPage = lazy(() => import("./pages/LoginPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const InfoPage = lazy(() => import("./pages/InfoPage"));
const ModuleHomePage = lazy(() => import("./pages/ModuleHomePage"));

// ============================================================================
// LOADING FALLBACK - Shown while lazy components load
// ============================================================================
function PageLoader() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center">
        <div className="w-10 h-10 border-3 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-3" />
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
    setUser(null);
    if (hadSession && message) toast.error(message, { duration: 6000 });
  }, []);

  // Global axios interceptor: auto-attach JWT bearer token to every request.
  // Previously only specific call-sites (heartbeat, login) sent the token,
  // which left every other endpoint un-authenticated on the wire — a hidden
  // security gap when the backend started requiring auth.
  useEffect(() => {
    const id = axios.interceptors.request.use(config => {
      const token = localStorage.getItem('token');
      if (token && !config.headers.Authorization) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
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
        if (status === 401 && !url.includes('/auth/')) {
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

  if (loading) {
    return <PageLoader />;
  }

  if (showInfo) {
    return (
      <div className="App">
        <Suspense fallback={<PageLoader />}>
          <InfoPage onBack={() => setShowInfo(false)} />
        </Suspense>
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
        <Suspense fallback={<PageLoader />}>
          <ModuleHomePage
            user={user}
            onLogout={handleLogout}
            dark={dark}
            toggleDark={toggleDark}
            onShowInfo={() => setShowInfo(true)}
            onEnterInventarisasi={enterInventarisasi}
          />
        </Suspense>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  return (
    <div className="App">
      {/* S1 — Skip link for keyboard/screen-reader users (WCAG 2.4.1 Bypass Blocks) */}
      <a href="#main-content" className="skip-link">
        Lewati ke konten utama
      </a>
      <BrowserRouter>
        <Suspense fallback={<PageLoader />}>
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
              {/* Catch all route */}
              <Route
                path="*"
                element={<Navigate to="/" replace />}
              />
            </Routes>
          </main>
        </Suspense>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
      <BackgroundTaskBar isAdmin={user?.role === "admin"} />
    </div>
  );
}

export default App;
