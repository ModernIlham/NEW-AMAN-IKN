import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  RadioTower, Play, Square, ShieldCheck, ShieldAlert, Loader2, Wifi, WifiOff,
  Satellite, Info, LogOut,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const KUNCI_ANTREAN = "aman_lacak_antrean";
const KUNCI_TOKEN = "aman_lacak_token";

// Kadensi ADAPTIF — perangkat diam tak perlu dilaporkan tiap menit. Angka dari
// docs/ARSITEKTUR-SPASIAL-IOT.md §8.4 #20 (kuota data mahal di lapangan).
const JEDA_BERGERAK_MS = 60_000;
const JEDA_DIAM_MS = 900_000;          // 15 menit
const AMBANG_DIAM_M = 25;              // pergeseran di bawah ini = masih diam
const JEDA_KIRIM_MS = 120_000;         // coba kirim antrean tiap 2 menit
const MAKS_ANTREAN = 500;              // selaras plafon batch server

function getApiError(err, fallback) {
  return err?.response?.data?.detail || fallback;
}

/** Jarak kasar antar dua titik dalam meter (proyeksi lokal, cukup untuk ambang). */
function jarakM(a, b) {
  if (!a || !b) return Infinity;
  const mLat = 111_320;
  const mLon = mLat * Math.cos((a.lat * Math.PI) / 180);
  return Math.hypot((b.lon - a.lon) * mLon, (b.lat - a.lat) * mLat);
}

function bacaAntrean() {
  try {
    const v = JSON.parse(localStorage.getItem(KUNCI_ANTREAN) || "[]");
    return Array.isArray(v) ? v : [];
  } catch { return []; }
}

function tulisAntrean(xs) {
  try {
    // Dipotong dari DEPAN: bila antrean penuh, yang paling layak dibuang adalah
    // yang paling tua — posisi terbaru jauh lebih berguna untuk mencari barang.
    localStorage.setItem(KUNCI_ANTREAN, JSON.stringify(xs.slice(-MAKS_ANTREAN)));
  } catch { /* kuota penuh: antrean di memori tetap jalan */ }
}

/**
 * PENDAMPING PELACAKAN — HP yang sudah dipegang orang menjadi pelacak (Fase 15).
 *
 * Dokumen arsitektur §9.1 menandai jalur ini "paling direkomendasikan, biaya
 * Rp 0": tak ada perangkat yang perlu dibeli, dan repo ini memang sudah
 * offline-first. Halaman dibuka TANPA LOGIN — token perangkat yang menjadi
 * kredensialnya, sama seperti halaman TTD publik.
 *
 * PEMBERITAHUAN KE PEMEGANG BARANG ADALAH BAGIAN DARI FITUR, bukan hiasan.
 * UU PDP mewajibkan subjek data diberi tahu; kewajiban itu paling sulit
 * dibantah bila pemberitahuannya muncul di layar orangnya sendiri, dibaca dari
 * kode penegaknya, tepat sebelum ia menekan "Mulai". Karena itu tombol Mulai
 * TIDAK muncul sebelum kebijakan berhasil dimuat dan ditampilkan.
 *
 * BATAS YANG DINYATAKAN TERUS TERANG, bukan disembunyikan: peramban
 * MENGHENTIKAN JavaScript saat tab berpindah ke latar belakang atau layar mati.
 * Halaman ini karena itu bukan pengganti pelacak khusus untuk pemantauan 24
 * jam — ia berguna untuk perjalanan dinas yang diawasi, kendaraan bertablet
 * terpasang, dan pencarian barang hilang. Menjanjikan lebih dari itu hanya
 * akan membuat orang mengandalkan sesuatu yang diam-diam berhenti bekerja.
 */
export default function LacakPage() {
  const [token, setToken] = useState("");
  const [dev, setDev] = useState(null);
  const [memuat, setMemuat] = useState(false);
  const [jalan, setJalan] = useState(false);
  const [antrean, setAntrean] = useState(() => bacaAntrean());
  const [terakhir, setTerakhir] = useState(null);
  const [online, setOnline] = useState(navigator.onLine);
  const [statistik, setStatistik] = useState({ terkirim: 0, gagal: 0 });
  const watchRef = useRef(null);
  const wakeRef = useRef(null);
  const acuanRef = useRef(null);      // posisi terakhir yang DIREKAM
  const antreanRef = useRef(antrean); // dibaca timer tanpa memicu render ulang

  useEffect(() => { antreanRef.current = antrean; }, [antrean]);

  useEffect(() => {
    const naik = () => setOnline(true);
    const turun = () => setOnline(false);
    window.addEventListener("online", naik);
    window.addEventListener("offline", turun);
    return () => {
      window.removeEventListener("online", naik);
      window.removeEventListener("offline", turun);
    };
  }, []);

  // Token boleh datang lewat ?token= (link/QR dari admin) — tetapi SEGERA
  // dibersihkan dari address bar. URL tersimpan di riwayat peramban, ikut
  // terkirim sebagai Referer, dan gampang ter-screenshot; token yang menetap di
  // sana sama saja dengan token yang ditempel di badan barang.
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const t = q.get("token") || localStorage.getItem(KUNCI_TOKEN) || "";
    if (q.get("token")) {
      window.history.replaceState({}, "", window.location.pathname);
    }
    if (t) { setToken(t); masuk(t); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const masuk = useCallback(async (t) => {
    const tok = (t || token || "").trim();
    if (!tok) { toast.error("Tempelkan token perangkat"); return; }
    setMemuat(true);
    try {
      const r = await axios.get(`${API}/iot/perangkat/saya`,
                                { headers: { "X-Device-Token": tok } });
      setDev(r.data);
      setToken(tok);
      localStorage.setItem(KUNCI_TOKEN, tok);
    } catch (e) {
      setDev(null);
      toast.error(getApiError(e, "Token tidak dikenali"));
    } finally { setMemuat(false); }
  }, [token]);

  const keluar = () => {
    hentikan();
    localStorage.removeItem(KUNCI_TOKEN);
    setDev(null); setToken("");
  };

  // ── Kirim antrean ─────────────────────────────────────────────────────────

  const kirimAntrean = useCallback(async () => {
    const isi = antreanRef.current;
    if (!isi.length || !navigator.onLine || !token) return;
    const batch = isi.slice(0, MAKS_ANTREAN);
    try {
      const r = await axios.post(`${API}/iot/observasi`, { observasi: batch },
                                 { headers: { "X-Device-Token": token } });
      // Baru dibuang SETELAH server mengaku menerima. Membuang lebih dulu
      // berarti kehilangan posisi saat jaringan putus di tengah kirim — dan
      // duplikat sudah aman ditolak indeks unik di server (at-least-once).
      const sisa = isi.slice(batch.length);
      antreanRef.current = sisa;
      setAntrean(sisa);
      tulisAntrean(sisa);
      setStatistik((s) => ({ ...s, terkirim: s.terkirim + (r.data?.disimpan || 0) }));
      if (r.data?.akses_darurat && dev && !dev.akses_darurat_aktif) {
        setDev((d) => ({ ...d, akses_darurat_aktif: true }));
      }
    } catch (e) {
      setStatistik((s) => ({ ...s, gagal: s.gagal + 1 }));
    }
  }, [token, dev]);

  useEffect(() => {
    if (!jalan) return undefined;
    const id = setInterval(kirimAntrean, JEDA_KIRIM_MS);
    return () => clearInterval(id);
  }, [jalan, kirimAntrean]);

  // ── Rekam posisi ──────────────────────────────────────────────────────────

  const mulai = async () => {
    if (!navigator.geolocation) {
      toast.error("Peramban ini tak menyediakan layanan lokasi");
      return;
    }
    let terakhirRekam = 0;
    watchRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        const c = pos.coords;
        const titik = { lon: c.longitude, lat: c.latitude };
        const bergerak = jarakM(acuanRef.current, titik) > AMBANG_DIAM_M;
        const jeda = bergerak ? JEDA_BERGERAK_MS : JEDA_DIAM_MS;
        const kini = Date.now();
        if (acuanRef.current && kini - terakhirRekam < jeda) return;
        terakhirRekam = kini;
        acuanRef.current = titik;

        const obs = {
          lat: c.latitude, lon: c.longitude,
          ts_device: new Date(pos.timestamp).toISOString(),
          akurasi_m: c.accuracy == null ? undefined : Math.round(c.accuracy),
          kecepatan_kmh: c.speed == null || c.speed < 0
            ? undefined : Math.round(c.speed * 3.6),
          arah_deg: c.heading == null || Number.isNaN(c.heading)
            ? undefined : Math.round(c.heading),
        };
        const baru = [...antreanRef.current, obs].slice(-MAKS_ANTREAN);
        antreanRef.current = baru;
        setAntrean(baru);
        tulisAntrean(baru);
        setTerakhir({ ...titik, akurasi: c.accuracy, pada: kini });
      },
      (err) => {
        toast.error(err.code === err.PERMISSION_DENIED
          ? "Izin lokasi ditolak — buka pengaturan peramban untuk mengizinkannya"
          : "Sinyal lokasi tak diperoleh");
      },
      { enableHighAccuracy: true, maximumAge: 15_000, timeout: 30_000 },
    );
    setJalan(true);
    // Layar tetap menyala selama merekam. Tanpa ini peramban menghentikan
    // JavaScript begitu layar mati — dan pelacakan yang berhenti diam-diam
    // lebih buruk daripada pelacakan yang tak pernah dinyalakan.
    try {
      if ("wakeLock" in navigator) {
        wakeRef.current = await navigator.wakeLock.request("screen");
      }
    } catch { /* ditolak peramban/baterai hemat — perekaman tetap jalan */ }
  };

  const hentikan = () => {
    if (watchRef.current != null) {
      navigator.geolocation.clearWatch(watchRef.current);
      watchRef.current = null;
    }
    try { wakeRef.current?.release?.(); } catch { /* sudah lepas */ }
    wakeRef.current = null;
    setJalan(false);
  };

  useEffect(() => () => {
    if (watchRef.current != null) navigator.geolocation.clearWatch(watchRef.current);
    try { wakeRef.current?.release?.(); } catch { /* abaikan */ }
  }, []);

  // ── Tampilan ──────────────────────────────────────────────────────────────

  if (!dev) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="w-full max-w-sm space-y-3">
          <div className="text-center">
            <RadioTower className="w-8 h-8 text-emerald-500 mx-auto" />
            <h1 className="mt-2 text-base font-bold">Pendamping Pelacakan AMAN</h1>
            <p className="text-[11px] text-muted-foreground mt-1">
              Tempelkan token perangkat yang diberikan pengelola BMN.
            </p>
          </div>
          <Input value={token} onChange={(e) => setToken(e.target.value)}
                 placeholder="Token perangkat" className="text-xs"
                 onKeyDown={(e) => e.key === "Enter" && masuk()}
                 data-testid="lacak-token" />
          <Button className="w-full min-h-0" size="sm" onClick={() => masuk()}
                  disabled={memuat} data-testid="lacak-masuk">
            {memuat && <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />}
            Lanjut
          </Button>
          <p className="text-[10px] text-muted-foreground text-center">
            Token ini hanya bisa MENGIRIM posisi. Ia tak bisa dipakai membaca
            riwayat perjalanan maupun data lain.
          </p>
        </div>
      </div>
    );
  }

  const wilayahSaja = dev.kebijakan?.presisi === "wilayah";

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card">
        <div className="max-w-sm mx-auto px-4 h-12 flex items-center gap-2">
          <RadioTower className="w-4 h-4 text-emerald-500 flex-shrink-0" />
          <div className="min-w-0 flex-1">
            <p className="text-xs font-bold truncate">{dev.nama}</p>
            {dev.asset_name && (
              <p className="text-[10px] text-muted-foreground truncate">{dev.asset_name}</p>
            )}
          </div>
          <Button variant="ghost" size="sm" className="min-w-0 min-h-0 px-2"
                  onClick={keluar} data-testid="lacak-keluar">
            <LogOut className="w-4 h-4" />
          </Button>
        </div>
      </header>

      <main className="max-w-sm mx-auto px-4 py-4 space-y-3">
        {/* PEMBERITAHUAN — tampil SEBELUM tombol mulai, bukan sesudah. */}
        <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-3">
          <div className="flex items-start gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />
            <div className="min-w-0">
              <p className="text-xs font-semibold">Yang direkam tentang Anda</p>
              <ul className="mt-1.5 space-y-1 text-[11px] text-muted-foreground">
                <li>
                  <b>Ketelitian:</b>{" "}
                  {wilayahSaja
                    ? "hanya NAMA GEDUNG/KAWASAN — titik koordinat Anda dibuang sebelum disimpan"
                    : "koordinat penuh (perangkat ini bukan pegangan perorangan)"}
                </li>
                <li>
                  <b>Waktu:</b> {dev.kebijakan?.jam_aktif}
                  {dev.kebijakan?.hari_kerja_saja ? ", hari kerja saja" : ""}
                  {wilayahSaja
                    ? " — di luar jam itu tak ada yang disimpan sama sekali"
                    : ""}
                </li>
                <li><b>Lama simpan:</b> {dev.kebijakan?.retensi_hari} hari, lalu terhapus otomatis</li>
              </ul>
              <p className="text-[10px] text-muted-foreground mt-1.5">
                Sistem ini melacak BARANG NEGARA, bukan orang. Angka di atas
                dibaca langsung dari kode yang menegakkannya di server.
              </p>
            </div>
          </div>
        </div>

        {dev.akses_darurat_aktif && (
          <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 flex items-start gap-2">
            <ShieldAlert className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
            <div className="min-w-0">
              <p className="text-xs font-semibold">Pembukaan presisi darurat sedang aktif</p>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                Barang ini dilaporkan hilang, dan koordinat penuh sedang direkam
                atas persetujuan pejabat serta tercatat. Anda diberi tahu karena
                berhak mengetahuinya, bukan setelahnya dari orang lain.
              </p>
            </div>
          </div>
        )}

        <div className="rounded-xl border border-border bg-card p-3 space-y-2">
          <div className="flex items-center gap-2 text-[11px]">
            {online ? <Wifi className="w-3.5 h-3.5 text-emerald-500" />
                    : <WifiOff className="w-3.5 h-3.5 text-amber-500" />}
            <span className="text-muted-foreground">
              {online ? "Daring" : "Luring — posisi ditahan di HP dulu"}
            </span>
            <span className="ml-auto text-muted-foreground" data-testid="lacak-antrean">
              antre {antrean.length}
            </span>
          </div>
          <div className="flex items-center gap-2 text-[11px]">
            <Satellite className={`w-3.5 h-3.5 ${jalan ? "text-emerald-500" : "text-muted-foreground"}`} />
            <span className="text-muted-foreground">
              {terakhir
                ? `Terakhir ±${Math.round(terakhir.akurasi || 0)} m`
                : jalan ? "Menunggu sinyal…" : "Belum merekam"}
            </span>
            <span className="ml-auto text-muted-foreground">
              terkirim {statistik.terkirim}
            </span>
          </div>
          {!jalan ? (
            <Button className="w-full min-h-0" size="sm" onClick={mulai}
                    data-testid="lacak-mulai">
              <Play className="w-3.5 h-3.5 mr-1" />Mulai kirim posisi
            </Button>
          ) : (
            <Button className="w-full min-h-0" size="sm" variant="outline"
                    onClick={hentikan} data-testid="lacak-henti">
              <Square className="w-3.5 h-3.5 mr-1" />Hentikan
            </Button>
          )}
          {antrean.length > 0 && online && (
            <Button className="w-full min-h-0" size="sm" variant="ghost"
                    onClick={kirimAntrean} data-testid="lacak-kirim-sekarang">
              Kirim {antrean.length} yang tertahan sekarang
            </Button>
          )}
        </div>

        {/* Batas dinyatakan terus terang — bukan di catatan kaki. */}
        <div className="rounded-lg border border-border bg-muted/40 px-3 py-2 flex items-start gap-2">
          <Info className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0 mt-0.5" />
          <p className="text-[10px] text-muted-foreground">
            <b>Halaman ini harus tetap terbuka.</b> Peramban menghentikan
            perekaman saat layar mati atau Anda berpindah aplikasi — itu batasan
            peramban, bukan setelan yang bisa diubah. Untuk pemantauan 24 jam
            tanpa layar menyala, diperlukan pelacak GPS khusus. Posisi yang
            sempat terekam saat luring tetap tersimpan di HP dan terkirim
            sendiri begitu jaringan kembali.
          </p>
        </div>
      </main>
    </div>
  );
}
