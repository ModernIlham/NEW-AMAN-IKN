import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

/**
 * Permukaan air beriak — kanvas 2D MURNI LOKAL.
 *
 * KENAPA TIDAK memakai komponen contoh apa adanya: versi itu menyuntikkan
 * `<script type="module">` yang mengunduh `threejs-components` dari CDN publik
 * saat halaman dibuka, plus satu gambar dari penyimpanan pihak ketiga. Dua
 * alasan itu tidak bisa diterima di sini:
 *
 *  1. Halaman ini adalah layar MASUK — tempat kata sandi diketik. Skrip pihak
 *     ketiga yang dimuat saat runtime berarti siapa pun yang menguasai CDN itu
 *     menjalankan kode di halaman tersebut.
 *  2. AMAN adalah PWA yang harus tetap terpakai saat jaringan mati. Efek yang
 *     bergantung pada unduhan luar akan gagal diam-diam justru di kondisi itu.
 *
 * Jadi geraknya dibangun sendiri: beberapa lapis gelombang sinus yang berjalan
 * dengan kecepatan berbeda (memberi kesan kedalaman), kilau di puncaknya, dan
 * riak yang lahir dari sentuhan/kursor. Nol permintaan keluar.
 *
 * @param {Object} props
 * @param {string} [props.className] Kelas wadah (kanvas mengisi penuh).
 * @param {number} [props.lapis] Jumlah lapisan gelombang (2–6 wajar).
 */
export function LiquidEffectAnimation({ className, lapis = 4 }) {
  const kanvasRef = useRef(null);

  useEffect(() => {
    const kanvas = kanvasRef.current;
    if (!kanvas) return undefined;
    const ctx = kanvas.getContext("2d");
    if (!ctx) return undefined;

    let lebar = 0;
    let tinggi = 0;
    let rafId = 0;
    let berhenti = false;
    const riak = [];

    // Rasio piksel dibatasi 2: di layar 3x, kanvas selebar panel menjadi
    // ±3600 px dan pengecatan tiap frame mulai terasa pada perangkat lemah —
    // sementara mata tak lagi bisa membedakan hasilnya.
    const dpr = () => Math.min(window.devicePixelRatio || 1, 2);

    const kurangGerak = window.matchMedia
      ? window.matchMedia("(prefers-reduced-motion: reduce)")
      : null;

    // Permukaan sengaja ditaruh di SEPERTIGA BAWAH. Versi pertama memulainya di
    // 0,42 tinggi panel dan garis airnya memotong tepat di tengah paragraf +
    // daftar fitur — terbaca masih bisa, tapi tulisannya jadi berenang di
    // dalam air alih-alih berdiri di atasnya.
    const LAPIS = Array.from({ length: Math.max(1, Math.min(6, lapis)) }, (_, i) => ({
      dasar: 0.72 + i * 0.075,     // posisi permukaan (fraksi tinggi)
      amplitudo: 14 - i * 2.2,     // tinggi ombak (px)
      panjang: 420 + i * 160,      // panjang gelombang (px)
      laju: 0.00042 - i * 0.00007, // makin dalam makin lambat → kesan kedalaman
      alfa: 0.14 + i * 0.07,
    }));

    function ukur() {
      const r = kanvas.getBoundingClientRect();
      lebar = r.width;
      tinggi = r.height;
      const p = dpr();
      kanvas.width = Math.max(1, Math.round(lebar * p));
      kanvas.height = Math.max(1, Math.round(tinggi * p));
      ctx.setTransform(p, 0, 0, p, 0, 0);
    }

    function permukaan(l, x, t) {
      const k = (Math.PI * 2) / l.panjang;
      return (
        tinggi * l.dasar +
        l.amplitudo * Math.sin(k * x + t * l.laju * 1000) +
        l.amplitudo * 0.45 * Math.sin(k * 1.9 * x - t * l.laju * 1400)
      );
    }

    function gambar(t) {
      ctx.clearRect(0, 0, lebar, tinggi);

      for (const l of LAPIS) {
        ctx.beginPath();
        ctx.moveTo(0, tinggi);
        // Langkah 6 px sudah mulus untuk gelombang sepanjang ≥420 px, dan
        // seperenam biaya menggambar tiap piksel.
        for (let x = 0; x <= lebar; x += 6) ctx.lineTo(x, permukaan(l, x, t));
        ctx.lineTo(lebar, tinggi);
        ctx.closePath();

        const grad = ctx.createLinearGradient(0, tinggi * l.dasar - 40, 0, tinggi);
        grad.addColorStop(0, `rgba(45, 212, 191, ${l.alfa})`);   // teal-400
        grad.addColorStop(1, `rgba(30, 64, 175, ${l.alfa * 0.5})`); // blue-800
        ctx.fillStyle = grad;
        ctx.fill();

        // Garis kilau tipis di permukaan — yang membuatnya terbaca sebagai AIR
        // dan bukan sekadar bidang berwarna.
        ctx.beginPath();
        for (let x = 0; x <= lebar; x += 6) {
          const y = permukaan(l, x, t);
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = `rgba(148, 233, 226, ${Math.min(0.5, l.alfa + 0.12)})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // Riak sentuhan: cincin yang melebar sambil memudar.
      for (let i = riak.length - 1; i >= 0; i--) {
        const r = riak[i];
        // Dijepit ke >= 0. `t` adalah cap waktu AWAL frame dari
        // requestAnimationFrame, sedangkan `r.mulai` diambil `performance.now()`
        // saat pointer bergerak — yang bisa terjadi SETELAH frame dimulai.
        // Selisih negatif sekejap itu membuat `arc()` menerima jari-jari minus
        // dan melempar; gejalanya: efek air mati total begitu kursor digerakkan.
        const umur = Math.max(0, t - r.mulai);
        const jari = umur * 0.22;
        const alfa = 1 - umur / 1400;
        if (alfa <= 0 || jari > Math.max(lebar, tinggi)) {
          riak.splice(i, 1);
          continue;
        }
        ctx.beginPath();
        ctx.arc(r.x, r.y, jari, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(165, 243, 252, ${alfa * 0.45})`;
        ctx.lineWidth = 2 * alfa + 0.5;
        ctx.stroke();
      }
    }

    function bingkai(t) {
      if (berhenti) return;
      gambar(t);
      rafId = window.requestAnimationFrame(bingkai);
    }

    function mulai() {
      // Lebar/tinggi nol = elemen sedang `display:none` (panel kiri hanya hidup
      // di ≥lg). Menjalankan loop di keadaan itu membakar CPU tanpa satu piksel
      // pun sampai ke layar.
      if (berhenti || lebar <= 0 || tinggi <= 0 || rafId) return;
      rafId = window.requestAnimationFrame(bingkai);
    }
    function jeda() {
      if (rafId) window.cancelAnimationFrame(rafId);
      rafId = 0;
    }

    ukur();
    if (kurangGerak?.matches) {
      // Hormati "kurangi gerak": satu bingkai diam, bukan animasi berjalan.
      gambar(0);
    } else {
      mulai();
    }

    const pengamat = typeof ResizeObserver !== "undefined"
      ? new ResizeObserver(() => {
        ukur();
        if (kurangGerak?.matches) gambar(0);
        else if (lebar > 0 && tinggi > 0) mulai();
        else jeda();
      })
      : null;
    pengamat?.observe(kanvas);

    // Tab tersembunyi: rAF memang sudah dijeda peramban, tetapi menjeda sendiri
    // membuat perilakunya pasti (dan aman bila peramban tak menjeda).
    const onVisibilitas = () => {
      if (document.hidden) jeda();
      else if (!kurangGerak?.matches) mulai();
    };
    document.addEventListener("visibilitychange", onVisibilitas);

    const onGerak = (e) => {
      if (kurangGerak?.matches) return;
      const r = kanvas.getBoundingClientRect();
      const x = (e.touches ? e.touches[0].clientX : e.clientX) - r.left;
      const y = (e.touches ? e.touches[0].clientY : e.clientY) - r.top;
      const akhir = riak[riak.length - 1];
      // Jangan lahirkan riak tiap piksel gerakan tetikus — cukup tiap 60 px,
      // kalau tidak layar penuh cincin dan efeknya jadi berisik.
      if (akhir && Math.hypot(akhir.x - x, akhir.y - y) < 60) return;
      riak.push({ x, y, mulai: performance.now() });
      if (riak.length > 12) riak.shift();
    };
    kanvas.addEventListener("pointermove", onGerak);
    kanvas.addEventListener("pointerdown", onGerak);

    return () => {
      berhenti = true;
      jeda();
      pengamat?.disconnect();
      document.removeEventListener("visibilitychange", onVisibilitas);
      kanvas.removeEventListener("pointermove", onGerak);
      kanvas.removeEventListener("pointerdown", onGerak);
    };
  }, [lapis]);

  return (
    <canvas
      ref={kanvasRef}
      className={cn("h-full w-full", className)}
      // Hiasan murni: tak ada informasi di sini yang perlu dibacakan.
      aria-hidden="true"
    />
  );
}

export default LiquidEffectAnimation;
