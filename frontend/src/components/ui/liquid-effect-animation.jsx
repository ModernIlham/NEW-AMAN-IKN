import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";
import { AirKanvas2D } from "@/components/ui/air-kanvas-2d";
import teksturCair from "@/assets/tekstur-cair-login.jpg";

/**
 * Permukaan LOGAM CAIR (three.js) — efek `liquid1` dari `threejs-components`.
 *
 * BEDA PENTING dari komponen contoh: pustakanya DIPASANG sebagai dependensi
 * npm dan diikutkan saat build, BUKAN diunduh dari CDN lewat `<script>` yang
 * disuntikkan saat halaman dibuka. Dua alasan, dan keduanya berlaku khusus di
 * layar ini:
 *
 *  1. Ini halaman MASUK — tempat kata sandi diketik. Skrip pihak ketiga yang
 *     diambil saat runtime berarti siapa pun yang menguasai CDN itu
 *     menjalankan kode di halaman tersebut, tanpa satu pun tinjauan kode.
 *  2. AMAN adalah PWA yang harus tetap terpakai saat jaringan mati. Skrip dan
 *     gambar dari luar gagal diam-diam justru di kondisi itu.
 *
 * Gambar permukaannya pun lokal (`assets/tekstur-cair-login.jpg`, dibuat oleh
 * `scripts/buat_tekstur_login.py`), bukan blob penyimpanan pihak ketiga.
 *
 * Berkas efeknya ±500 kB (three.js ikut di dalamnya), jadi ia diambil lewat
 * `import()` DINAMIS — potongannya baru diunduh setelah komponen memutuskan
 * benar-benar akan memakainya. Di HP/tablet keputusan itu "tidak", sehingga
 * mereka tak mengunduh sebyte pun.
 *
 * @param {Object} props
 * @param {string} [props.className] Kelas wadah.
 */
export function LiquidEffectAnimation({ className }) {
  const kanvasRef = useRef(null);
  // "menimbang" → belum diputuskan; "webgl" → efek cair jalan;
  // "2d" → cadangan bergerak; "diam" → cadangan SATU BINGKAI (kurangi gerak).
  const [mode, setMode] = useState("menimbang");

  useEffect(() => {
    const kanvas = kanvasRef.current;
    let app = null;
    let dibatalkan = false;

    // Panel kiri hanya hidup di ≥lg (`hidden lg:flex`). Memuat 500 kB untuk
    // elemen yang `display:none` adalah pemborosan murni pada koneksi lapangan.
    const lebar = window.matchMedia?.("(min-width: 1024px)");
    const kurangGerak = window.matchMedia?.("(prefers-reduced-motion: reduce)");

    function adaWebGL() {
      try {
        const c = document.createElement("canvas");
        return !!(c.getContext("webgl2") || c.getContext("webgl"));
      } catch {
        return false;
      }
    }

    // "Kurangi gerak" dijawab dengan bingkai DIAM, bukan sekadar turun ke
    // kanvas 2D: menukar animasi WebGL dengan animasi 2D tetap saja animasi,
    // dan permintaan pengguna itu soal gerak — bukan soal teknologinya.
    if (kurangGerak?.matches) {
      setMode("diam");
      return undefined;
    }
    if (!kanvas || !lebar?.matches || !adaWebGL()) {
      setMode("2d");
      return undefined;
    }

    (async () => {
      try {
        const mod = await import(
          /* webpackChunkName: "efek-cair" */
          "threejs-components/build/backgrounds/liquid1.min.js"
        );
        if (dibatalkan) return;
        const LiquidBackground = mod.default || mod;
        app = LiquidBackground(kanvas);
        // Nilai bahan mengikuti contoh resmi komponen: logam mengilap dengan
        // pantulan tajam, dan gelombang yang cukup dalam untuk terbaca sebagai
        // cairan alih-alih kain.
        app.liquidPlane.material.metalness = 0.75;
        app.liquidPlane.material.roughness = 0.25;
        app.liquidPlane.uniforms.displacementScale.value = 5;
        app.setRain(false);
        await app.loadImage(teksturCair);
        if (dibatalkan) {
          app.dispose?.();
          app = null;
          return;
        }
        setMode("webgl");
      } catch (e) {
        // Gagal memuat/menginisialisasi BUKAN alasan menampilkan panel kosong.
        // Turun ke kanvas 2D, dan jangan menelan galatnya diam-diam.
        if (!dibatalkan) {
          console.warn("Efek cair tak dapat dimuat, memakai kanvas 2D:", e);
          setMode("2d");
        }
      }
    })();

    return () => {
      dibatalkan = true;
      // `dispose` melepas konteks WebGL. Tanpa ini, berpindah halaman
      // berulang-ulang menumpuk konteks sampai peramban membuang yang tertua
      // dan kanvas lain di aplikasi ikut mati.
      try {
        app?.dispose?.();
      } catch {
        /* konteks sudah hilang — tak ada yang perlu dibereskan */
      }
      app = null;
    };
  }, []);

  return (
    <div className={cn("relative h-full w-full", className)} aria-hidden="true">
      {/* Kanvas WebGL selalu ada di DOM: pustaka membutuhkannya SEBELUM tahu
          apakah inisialisasinya berhasil. Ia disembunyikan sampai berhasil,
          supaya kotak hitam kosong tak sempat berkedip. */}
      <canvas
        ref={kanvasRef}
        className={cn(
          "absolute inset-0 h-full w-full transition-opacity duration-700",
          mode === "webgl" ? "opacity-100" : "opacity-0",
        )}
      />
      {(mode === "2d" || mode === "diam") && (
        <AirKanvas2D className="absolute inset-0" diam={mode === "diam"} />
      )}
    </div>
  );
}

export default LiquidEffectAnimation;
