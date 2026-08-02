/**
 * MARQUEE GLOBAL untuk teks ber-"..." — berlaku DI SEMUA TEMPAT.
 *
 * Setiap elemen yang terpotong elipsis (mis. kelas Tailwind `truncate`)
 * otomatis MENGGULIR isinya sampai ujung ("mentok") saat di-hover, lalu
 * kembali ke awal — elipsisnya muncul lagi — saat kursor pergi. Di layar
 * sentuh (tanpa hover) ketukan menjadi saklar: ketuk = jalan ke ujung,
 * ketuk lagi = kembali.
 *
 * CARA KERJA — tanpa menyentuh ratusan komponen:
 * - Listener TERDELEGASI di `document` (mouseover/mouseout/click), jadi
 *   elemen yang baru dirender React otomatis ikut tanpa perlu mendaftar.
 * - Deteksi: elemen (atau leluhur terdekatnya, maks 3 tingkat) yang
 *   `text-overflow: ellipsis` + `white-space: nowrap` + overflow-x hidden
 *   DAN isinya benar-benar meluber (scrollWidth > clientWidth).
 * - Animasi memakai `scrollLeft` elemen itu sendiri (elemen overflow:hidden
 *   tetap bisa digulir programatik) — begitu bergeser dari 0, peramban
 *   otomatis melepas elipsisnya; kembali ke 0, elipsis muncul lagi. Tidak
 *   perlu pembungkus/transform, jadi aman untuk markup apa pun.
 * - `prefers-reduced-motion` dihormati: lompat langsung tanpa animasi.
 *
 * Elemen dapat MENOLAK ikut dengan atribut `data-marquee-off`, dan elemen
 * MarqueeOnTap lama (ber-`data-marquee`) dibiarkan memakai logikanya sendiri.
 */

const KECEPATAN_PX_PER_DETIK = 55;
const DETIK_MIN = 0.6;

// Status animasi per elemen (id rAF + arah terakhir) tanpa membocorkan memori.
const status = new WeakMap();

function elemenTerpotong(mulai) {
  let el = mulai instanceof Element ? mulai : null;
  for (let i = 0; el && i < 4; i += 1) {
    if (el.hasAttribute?.("data-marquee") || el.hasAttribute?.("data-marquee-off")) {
      return null; // punya penanganan sendiri / menolak
    }
    // Saring murah dulu lewat className sebelum getComputedStyle.
    const kelas = typeof el.className === "string" ? el.className : "";
    const mungkin = kelas.includes("truncate") || kelas.includes("text-ellipsis")
      || kelas.includes("overflow-hidden");
    if (mungkin && el.scrollWidth - el.clientWidth > 2) {
      const gaya = window.getComputedStyle(el);
      if (gaya.textOverflow === "ellipsis" && gaya.whiteSpace === "nowrap"
          && (gaya.overflowX === "hidden" || gaya.overflow === "hidden")) {
        return el;
      }
    }
    el = el.parentElement;
  }
  return null;
}

function hentikan(el) {
  const st = status.get(el);
  if (st?.raf) cancelAnimationFrame(st.raf);
}

function gulirKe(el, tujuan) {
  hentikan(el);
  const kurangiGerak = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
  if (kurangiGerak) {
    el.scrollLeft = tujuan;
    status.set(el, { raf: 0, tujuan });
    return;
  }
  const awal = el.scrollLeft;
  const jarak = tujuan - awal;
  if (Math.abs(jarak) < 1) {
    status.set(el, { raf: 0, tujuan });
    return;
  }
  const durasi = Math.max(DETIK_MIN, Math.abs(jarak) / KECEPATAN_PX_PER_DETIK) * 1000;
  const t0 = performance.now();
  const langkah = (t) => {
    const p = Math.min(1, (t - t0) / durasi);
    el.scrollLeft = awal + jarak * p;
    if (p < 1) {
      status.set(el, { raf: requestAnimationFrame(langkah), tujuan });
    } else {
      status.set(el, { raf: 0, tujuan });
    }
  };
  status.set(el, { raf: requestAnimationFrame(langkah), tujuan });
}

function keUjung(el) {
  gulirKe(el, el.scrollWidth - el.clientWidth);
}

function keAwal(el) {
  gulirKe(el, 0);
}

/** Pasang sekali di bootstrap aplikasi. Aman dipanggil berulang. */
export function pasangMarqueeEllipsis(doc = document) {
  if (doc.__marqueeEllipsisTerpasang) return;
  doc.__marqueeEllipsisTerpasang = true;

  // Hover masuk → jalan ke ujung; hover keluar → kembali (elipsis pulih).
  doc.addEventListener("mouseover", (e) => {
    const el = elemenTerpotong(e.target);
    if (el && !el.contains(e.relatedTarget)) keUjung(el);
  }, { passive: true });

  doc.addEventListener("mouseout", (e) => {
    const el = elemenTerpotong(e.target);
    if (el && !el.contains(e.relatedTarget)) keAwal(el);
  }, { passive: true });

  // Sentuh/klik = saklar (perangkat tanpa hover; klik mouse pun berlaku).
  doc.addEventListener("click", (e) => {
    const el = elemenTerpotong(e.target);
    if (!el) return;
    const st = status.get(el);
    const sedangDiUjung = (st?.tujuan ?? el.scrollLeft) > 0;
    if (sedangDiUjung) keAwal(el);
    else keUjung(el);
  }, { passive: true });
}

export default pasangMarqueeEllipsis;
