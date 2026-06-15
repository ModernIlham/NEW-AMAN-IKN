// ============================================================================
// APP.JS - OPTIMIZED VERSION
// ============================================================================
// Code splitting with React.lazy + Suspense
// Lazy loads pages for smaller initial bundle
// ============================================================================

import React, { useState, useEffect, useCallback, lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "@/App.css";
import { Toaster } from "@/components/ui/sonner";
import { useDarkMode } from "@/hooks/useDarkMode";
import BackgroundTaskBar from "@/components/BackgroundTaskBar";
import axios from "axios";

// ============================================================================
// LAZY LOADED PAGES - Code Splitting
// Each page becomes a separate chunk, loaded only when needed
// ============================================================================
const LoginPage = lazy(() => import("./pages/LoginPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const InfoPage = lazy(() => import("./pages/InfoPage"));

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

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const { dark, toggle: toggleDark } = useDarkMode();

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
    return () => axios.interceptors.request.eject(id);
  }, []);

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

  const handleLogin = (userData, token) => {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(userData));
    setUser(userData);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
  };

  const [showInfo, setShowInfo] = useState(false);

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
                    <DashboardPage user={user} onLogout={handleLogout} dark={dark} toggleDark={toggleDark} onShowInfo={() => setShowInfo(true)} />
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
