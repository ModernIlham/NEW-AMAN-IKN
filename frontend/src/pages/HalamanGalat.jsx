import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, Home, Package, RefreshCw, ShieldAlert } from "lucide-react";

/**
 * Halaman galat EKSKLUSIF AMAN — 404 (tak ditemukan) & 403 (akses ditolak).
 *
 * Pusatnya tulisan besar ber-EFEK GLITCH: tiap huruf berganti-ganti simbol
 * acak dengan cepat lalu "terkunci" membentuk kata, bergantian antara kode
 * angka ("404") dan katanya ("NOT FOUND") — ditambah belahan RGB, potongan
 * slice yang meloncat, dan garis pindai ala layar rusak. Semuanya CSS +
 * satu interval JS — tanpa pustaka luar (aturan PWA offline aplikasi ini),
 * dan tunduk `prefers-reduced-motion` (teks diam bila pengguna memintanya).
 */

const SIMBOL = "█▓▒░<>/\\|#@%&$?!*+=~^§¤×÷◊∆Λ01";

function acak() {
  return SIMBOL[Math.floor(Math.random() * SIMBOL.length)];
}

/**
 * Teks ber-scramble: berganti simbol cepat → terkunci per huruf dari kiri →
 * tahan → hancur lagi → kata berikutnya. `kataKata` dipergilirkan.
 */
function useScramble(kataKata, { jedaKunci = 1800, langkah = 45 } = {}) {
  const [teks, setTeks] = useState(kataKata[0]);
  const idx = useRef(0);

  useEffect(() => {
    const kurangiGerak = window.matchMedia?.(
      "(prefers-reduced-motion: reduce)")?.matches;
    if (kurangiGerak) { setTeks(kataKata[0]); return undefined; }

    let timer = 0;
    let hidup = true;

    const mainkan = () => {
      const target = kataKata[idx.current % kataKata.length];
      const panjang = Math.max(...kataKata.map((k) => k.length));
      let tick = 0;
      // Fase 1: hujan simbol; huruf terkunci bergiliran dari kiri.
      const kunciMulai = 6;                       // tick sebelum mulai mengunci
      const perHuruf = 3;                         // tick per huruf terkunci
      const totalTick = kunciMulai + target.length * perHuruf;

      const jalan = () => {
        if (!hidup) return;
        tick += 1;
        const terkunci = Math.max(0, Math.floor((tick - kunciMulai) / perHuruf));
        let hasil = "";
        for (let i = 0; i < panjang; i += 1) {
          if (i >= target.length) { hasil += " "; continue; }
          hasil += i < terkunci ? target[i] : acak();
        }
        setTeks(hasil.trimEnd());
        if (tick < totalTick) {
          timer = window.setTimeout(jalan, langkah);
        } else {
          setTeks(target);
          idx.current += 1;
          timer = window.setTimeout(mainkan, jedaKunci);
        }
      };
      jalan();
    };

    mainkan();
    return () => { hidup = false; window.clearTimeout(timer); };
  }, [kataKata, jedaKunci, langkah]);

  return teks;
}

function GalatGlitch({ kode, kata, aksen, Icon, judul, pesan, onKembali }) {
  const kataKata = useMemo(() => [kode, kata], [kode, kata]);
  const teks = useScramble(kataKata);

  const keBeranda = () => { window.location.href = "/"; };

  return (
    <div className="galat-glitch min-h-screen bg-slate-950 text-slate-200 flex flex-col items-center justify-center px-6 relative overflow-hidden">
      {/* Pola latar + garis pindai ala layar rusak */}
      <div className="absolute inset-0 login-pattern opacity-40" aria-hidden="true" />
      <div className="galat-scanline absolute inset-0 pointer-events-none" aria-hidden="true" />

      {/* Identitas aplikasi */}
      <div className="relative z-10 flex items-center gap-3 mb-10">
        <div className="w-10 h-10 bg-gradient-to-br from-teal-600 to-teal-700 rounded-lg flex items-center justify-center shadow-lg">
          <Package className="w-6 h-6 text-white" />
        </div>
        <div className="flex flex-col leading-tight">
          <span className="text-lg font-bold text-white">AMAN</span>
          <span className="text-[10px] font-medium text-slate-400">Aplikasi Manajemen Aset Negara</span>
        </div>
      </div>

      {/* Tulisan glitch utama: teks yang sama ditumpuk 3 lapis (merah/cyan
          bergeser + lapisan slice ber-clip-path yang meloncat-loncat). */}
      <div className="relative z-10 select-none" aria-live="off">
        <div className="galat-teks relative font-mono font-black tracking-tight text-white
            text-[clamp(3.5rem,16vw,10rem)] leading-none" data-teks={teks} aria-hidden="true">
          {teks}
        </div>
        <span className="sr-only">{`${kode} — ${judul}`}</span>
      </div>

      <div className="relative z-10 mt-8 max-w-md text-center">
        <p className={`text-sm font-bold tracking-[0.3em] uppercase mb-2 ${aksen}`}>
          <Icon className="inline w-4 h-4 mr-1.5 -mt-0.5" aria-hidden="true" />{judul}
        </p>
        <p className="text-sm text-slate-400 leading-relaxed">{pesan}</p>
      </div>

      <div className="relative z-10 mt-8 flex items-center gap-3 flex-wrap justify-center">
        {onKembali ? (
          <button type="button" onClick={onKembali}
            className="h-10 px-4 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-sm font-semibold flex items-center gap-2 transition-colors"
            data-testid="galat-kembali">
            <ArrowLeft className="w-4 h-4" />Kembali
          </button>
        ) : null}
        <button type="button" onClick={keBeranda}
          className="h-10 px-4 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-sm font-semibold flex items-center gap-2 transition-colors"
          data-testid="galat-beranda">
          <Home className="w-4 h-4" />Ke Beranda
        </button>
        <button type="button" onClick={() => window.location.reload()}
          className="h-10 px-4 rounded-lg border border-slate-700 hover:border-slate-500 text-slate-300 text-sm font-semibold flex items-center gap-2 transition-colors"
          data-testid="galat-muat-ulang">
          <RefreshCw className="w-4 h-4" />Muat Ulang
        </button>
      </div>

      <p className="relative z-10 mt-10 text-[11px] text-slate-600">
        AMAN — pengelolaan BMN satu pintu · kesalahan {kode}
      </p>

      {/* Gaya glitch lokal halaman ini (tanpa menyentuh index.css) */}
      <style>{`
        .galat-teks {
          text-shadow: 0 0 14px rgba(94, 234, 212, 0.25);
          animation: galat-goyang 3.1s infinite steps(1);
        }
        .galat-teks::before, .galat-teks::after {
          content: attr(data-teks);
          position: absolute; inset: 0; overflow: hidden;
        }
        .galat-teks::before {
          color: #f43f5e; z-index: -1;
          animation: galat-slice-a 2.4s infinite linear alternate;
        }
        .galat-teks::after {
          color: #22d3ee; z-index: -2;
          animation: galat-slice-b 3.0s infinite linear alternate;
        }
        @keyframes galat-goyang {
          0%, 86%, 100% { transform: none; }
          88% { transform: translate(2px, -1px) skewX(2deg); }
          90% { transform: translate(-3px, 1px); }
          92% { transform: translate(1px, 0) skewX(-3deg); }
          94% { transform: none; }
        }
        @keyframes galat-slice-a {
          0%   { clip-path: inset(12% 0 78% 0); transform: translate(-4px, -2px); }
          20%  { clip-path: inset(64% 0 8% 0);  transform: translate(4px, 2px); }
          40%  { clip-path: inset(30% 0 52% 0); transform: translate(-3px, 1px); }
          60%  { clip-path: inset(82% 0 4% 0);  transform: translate(5px, -1px); }
          80%  { clip-path: inset(4% 0 88% 0);  transform: translate(-5px, 2px); }
          100% { clip-path: inset(48% 0 34% 0); transform: translate(3px, -2px); }
        }
        @keyframes galat-slice-b {
          0%   { clip-path: inset(70% 0 12% 0); transform: translate(4px, 1px); }
          25%  { clip-path: inset(8% 0 80% 0);  transform: translate(-5px, -1px); }
          50%  { clip-path: inset(42% 0 40% 0); transform: translate(4px, 2px); }
          75%  { clip-path: inset(88% 0 2% 0);  transform: translate(-3px, -2px); }
          100% { clip-path: inset(20% 0 64% 0); transform: translate(5px, 1px); }
        }
        .galat-scanline {
          background: repeating-linear-gradient(
            to bottom, transparent 0, transparent 3px,
            rgba(148, 163, 184, 0.05) 3px, rgba(148, 163, 184, 0.05) 4px);
        }
        .galat-scanline::after {
          content: ""; position: absolute; left: 0; right: 0; height: 90px;
          background: linear-gradient(to bottom, transparent,
            rgba(94, 234, 212, 0.06), transparent);
          animation: galat-pindai 5s infinite linear;
        }
        @keyframes galat-pindai {
          0% { top: -90px; } 100% { top: 100%; }
        }
        @media (prefers-reduced-motion: reduce) {
          .galat-teks, .galat-teks::before, .galat-teks::after,
          .galat-scanline::after { animation: none !important; }
          .galat-teks::before, .galat-teks::after { content: none; }
        }
      `}</style>
    </div>
  );
}

/** 404 — alamat tidak dikenal. */
export function Halaman404({ onKembali }) {
  return (
    <GalatGlitch
      kode="404"
      kata="NOT FOUND"
      aksen="text-teal-300"
      Icon={Package}
      judul="Halaman Tidak Ditemukan"
      pesan="Alamat yang dituju tidak ada di AMAN — mungkin salah ketik, atau tautannya sudah berpindah. Gunakan tombol di bawah untuk kembali bekerja."
      onKembali={onKembali}
    />
  );
}

/** 403 — akses ditolak (peran/satker tidak berhak). */
export function Halaman403({ onKembali }) {
  return (
    <GalatGlitch
      kode="403"
      kata="AKSES DITOLAK"
      aksen="text-rose-400"
      Icon={ShieldAlert}
      judul="Akses Ditolak"
      pesan="Akun Anda tidak berhak membuka halaman ini — data AMAN terisolasi ketat per satuan kerja dan peran. Hubungi admin satker bila merasa seharusnya punya akses."
      onKembali={onKembali}
    />
  );
}

export default Halaman404;
