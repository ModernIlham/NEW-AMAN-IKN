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
 *   tetap bisa digulir programatik). SELAMA bergeser, `text-overflow`
 *   dipaksa `clip` — bila tidak, peramban tetap menggambar "…" di tepi
 *   kanan dan MENELAN huruf-huruf terakhir sehingga teks tak pernah tampil
 *   utuh sampai ujung. Saat kembali ke awal nilai semula dipulihkan dan
 *   elipsis muncul lagi. Tanpa pembungkus/transform, aman utk markup apa pun.
 * - `prefers-reduced-motion` dihormati: lompat langsung tanpa animasi.
 *
 * TOOLTIP: selama di-hover, atribut `title` DICABUT dan diganti tooltip
 * kustom (lib/tooltipTeks.js). Alasannya, peramban mematikan tooltip native
 * setiap kali isi elemen digulir — pada teks sangat panjang (nama barang,
 * eselon, lokasi) animasinya lama sehingga tooltip native berkedip lalu
 * hilang sama sekali. Tooltip kustom bertahan selama kursor di elemen dan
 * menampilkan teks penuh berbilang baris.
 *
 * Elemen dapat MENOLAK ikut dengan atribut `data-marquee-off`, dan elemen
 * MarqueeOnTap lama (ber-`data-marquee`) dibiarkan memakai logikanya sendiri.
 */
import { pasangPenyembunyiTooltip, sembunyikanTooltip, tampilkanTooltip } from "./tooltipTeks";

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
    // Elemen yang SEDANG bermarquee: elipsisnya sementara `clip` sehingga
    // saringan gaya di bawah tak lagi mengenalinya — kenali lewat penanda
    // agar mouseout/klik tetap bisa mengembalikannya ke awal.
    if (el.dataset?.marqueeAktif) return el;
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

function gulirKe(el, tujuan, selesai) {
  hentikan(el);
  // `selesai` hanya dipanggil bila animasi RAMPUNG (tidak diinterupsi
  // hentikan() oleh animasi baru) — dipakai keAwal utk memulihkan elipsis.
  const rampung = () => {
    status.set(el, { ...status.get(el), raf: 0, tujuan });
    if (selesai) selesai();
  };
  const kurangiGerak = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
  if (kurangiGerak) {
    el.scrollLeft = tujuan;
    rampung();
    return;
  }
  const awal = el.scrollLeft;
  const jarak = tujuan - awal;
  if (Math.abs(jarak) < 1) {
    rampung();
    return;
  }
  const durasi = Math.max(DETIK_MIN, Math.abs(jarak) / KECEPATAN_PX_PER_DETIK) * 1000;
  const t0 = performance.now();
  const langkah = (t) => {
    const p = Math.min(1, (t - t0) / durasi);
    el.scrollLeft = awal + jarak * p;
    if (p < 1) {
      status.set(el, { ...status.get(el), raf: requestAnimationFrame(langkah), tujuan });
    } else {
      rampung();
    }
  };
  status.set(el, { ...status.get(el), raf: requestAnimationFrame(langkah), tujuan });
}

/** Teks penuh elemen untuk tooltip: `title` bila ada, selain itu isinya. */
function teksPenuh(el) {
  const st = status.get(el);
  const judul = st?.judul ?? el.getAttribute("title");
  return (judul || el.textContent || "").trim();
}

function keUjung(el) {
  // Lepas elipsis SEBELUM bergeser: dengan `ellipsis` aktif peramban terus
  // menggambar "…" di tepi kanan sepanjang guliran dan MENELAN huruf-huruf
  // terakhir — teks tampak bergeser tapi tak pernah tampil utuh sampai
  // ujung. Nilai inline semula disimpan agar pulih persis saat kembali.
  if (!el.dataset.marqueeAktif) {
    status.set(el, { ...status.get(el), toSebelum: el.style.textOverflow });
    el.dataset.marqueeAktif = "1";
    el.style.textOverflow = "clip";
  }
  // Tooltip: cabut `title` (agar tooltip native yang selalu terbunuh oleh
  // guliran tak ikut muncul) dan tampilkan tooltip kustom yang bertahan.
  const teks = teksPenuh(el);
  if (el.hasAttribute("title")) {
    status.set(el, { ...status.get(el), judul: el.getAttribute("title") });
    el.removeAttribute("title");
  }
  tampilkanTooltip(el, teks);
  gulirKe(el, el.scrollWidth - el.clientWidth);
}

function keAwal(el) {
  sembunyikanTooltip();
  const st = status.get(el);
  if (st?.judul != null && !el.hasAttribute("title")) {
    el.setAttribute("title", st.judul);   // pulihkan untuk pembaca layar
  }
  gulirKe(el, 0, () => {
    const s = status.get(el);
    el.style.textOverflow = s?.toSebelum || "";
    delete el.dataset.marqueeAktif;
  });
}

/** Pasang sekali di bootstrap aplikasi. Aman dipanggil berulang. */
export function pasangMarqueeEllipsis(doc = document) {
  if (doc.__marqueeEllipsisTerpasang) return;
  doc.__marqueeEllipsisTerpasang = true;
  pasangPenyembunyiTooltip(doc);   // tooltip hilang saat gulir/klik/Escape

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
