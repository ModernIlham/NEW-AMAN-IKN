/**
 * TOOLTIP TEKS KUSTOM — pengganti tooltip bawaan peramban untuk teks ber-"…".
 *
 * MASALAH: tooltip native (atribut `title`) DIMATIKAN peramban setiap kali isi
 * elemen digulir. Karena teks terpotong kita gulirkan (marquee), tooltip pada
 * kolom nama barang / eselon / lokasi tampak BERKEDIP lalu HILANG — makin
 * panjang teksnya makin lama animasinya, jadi makin sering tooltip terbunuh
 * dan praktis tak pernah terbaca.
 *
 * SOLUSI: tooltip milik sendiri (satu elemen di <body>) yang:
 *  - muncul setelah jeda singkat dan BERTAHAN selama kursor di elemen,
 *    tak peduli isinya sedang bergulir;
 *  - menampilkan teks PENUH, boleh berbilang baris (teks sangat panjang
 *    tetap terbaca seluruhnya — tooltip native memotongnya);
 *  - mengikuti tema terang/gelap, tak menghalangi klik (`pointer-events:none`),
 *    dan menjepit diri ke dalam layar.
 *
 * Dipakai oleh lib/marqueeEllipsis.js (satu-satunya pemanggil): teks tooltip
 * diambil dari atribut `title` bila ada, selain itu dari isi elemen.
 */

const JEDA_TAMPIL_MS = 320;
const MAKS_HURUF = 600;

let el = null;          // elemen tooltip (dibuat sekali, malas)
let timer = null;
let sasaran = null;     // elemen yang sedang ditooltipkan

function buat() {
  if (el) return el;
  el = document.createElement("div");
  el.setAttribute("role", "tooltip");
  el.dataset.amanTooltip = "1";
  el.style.cssText = [
    "position:fixed", "z-index:2147483000", "pointer-events:none",
    "max-width:min(28rem,calc(100vw - 1.5rem))", "padding:6px 9px",
    "border-radius:8px", "font-size:12px", "line-height:1.45",
    "white-space:normal", "overflow-wrap:anywhere",
    "box-shadow:0 8px 24px rgba(0,0,0,.28)", "opacity:0",
    "transition:opacity .12s ease", "visibility:hidden",
  ].join(";");
  document.body.appendChild(el);
  return el;
}

function warnai(node) {
  // Ikut tema: gelap → panel terang, terang → panel gelap (kontras tinggi,
  // tak bergantung variabel CSS yang mungkin belum termuat).
  const gelap = document.documentElement.classList.contains("dark");
  node.style.background = gelap ? "#e2e8f0" : "#0f172a";
  node.style.color = gelap ? "#0f172a" : "#f8fafc";
  node.style.border = gelap ? "1px solid #cbd5e1" : "1px solid #334155";
}

function tempatkan(node, anchor) {
  const r = anchor.getBoundingClientRect();
  node.style.visibility = "hidden";
  node.style.opacity = "0";
  node.style.left = "0px";
  node.style.top = "0px";
  const t = node.getBoundingClientRect();
  const celah = 6;
  let left = r.left;
  if (left + t.width > window.innerWidth - 8) {
    left = Math.max(8, window.innerWidth - 8 - t.width);
  }
  let top = r.bottom + celah;
  if (top + t.height > window.innerHeight - 8) {
    top = Math.max(8, r.top - celah - t.height);   // balik ke atas anchor
  }
  node.style.left = `${Math.round(left)}px`;
  node.style.top = `${Math.round(top)}px`;
  node.style.visibility = "visible";
  node.style.opacity = "1";
}

/** Sembunyikan tooltip (dan batalkan yang sedang menunggu tampil). */
export function sembunyikanTooltip() {
  clearTimeout(timer);
  timer = null;
  sasaran = null;
  if (el) {
    el.style.opacity = "0";
    el.style.visibility = "hidden";
  }
}

/**
 * Tampilkan tooltip untuk `anchor` berisi `teks` (setelah jeda singkat).
 * Memanggil ulang dengan anchor yang SAMA tidak mengulang animasi — inilah
 * yang membuat tooltip berhenti berkedip saat teks di dalamnya bergulir.
 */
export function tampilkanTooltip(anchor, teks) {
  const isi = String(teks || "").trim();
  if (!anchor || !isi) return;
  if (sasaran === anchor) return;          // sudah tampil/menunggu utk elemen ini
  clearTimeout(timer);
  sasaran = anchor;
  timer = setTimeout(() => {
    if (sasaran !== anchor || !anchor.isConnected) return;
    const node = buat();
    warnai(node);
    node.textContent = isi.length > MAKS_HURUF
      ? `${isi.slice(0, MAKS_HURUF)}…` : isi;
    tempatkan(node, anchor);
  }, JEDA_TAMPIL_MS);
}

/** Pasang penyembunyi global (gulir/klik/Escape) — aman dipanggil berulang. */
export function pasangPenyembunyiTooltip(doc = document) {
  if (doc.__amanTooltipTerpasang) return;
  doc.__amanTooltipTerpasang = true;
  // `capture` agar guliran kontainer mana pun (tabel virtual) ikut tertangkap.
  // KECUALI guliran pada elemen anchor SENDIRI: animasi marquee menggeser
  // `scrollLeft` elemen itu dan memicu event scroll bertubi-tubi — kalau
  // dihiraukan, tooltip justru dibunuh oleh gerakan teksnya sendiri (persis
  // penyakit tooltip native yang hendak kita ganti).
  window.addEventListener("scroll", (e) => {
    if (sasaran && e.target === sasaran) return;
    sembunyikanTooltip();
  }, true);
  window.addEventListener("resize", sembunyikanTooltip, { passive: true });
  doc.addEventListener("keydown", (e) => {
    if (e.key === "Escape") sembunyikanTooltip();
  });
  doc.addEventListener("pointerdown", sembunyikanTooltip, { passive: true });
}
