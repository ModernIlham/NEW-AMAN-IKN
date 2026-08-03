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

// Warna tema dibaca dari variabel CSS yang sama dengan tooltip Radix
// (`--primary` / `--primary-foreground`, ditulis sebagai komponen HSL di
// index.css). Dengan begitu kedua jenis tooltip tampak SATU keluarga — dulu
// tooltip ini gelap sendiri sementara tooltip tabel hijau.
function varTema(nama, cadangan) {
  try {
    const v = getComputedStyle(document.documentElement)
      .getPropertyValue(nama).trim();
    return v ? `hsl(${v})` : cadangan;
  } catch {
    return cadangan;
  }
}

function warnai(node) {
  // Cadangan ditulis heksa (#18675f = hsl(174 62% 25%), teal --primary bawaan)
  // agar tetap benar di mesin CSS yang tak menerima sintaks hsl bergaya spasi.
  const latar = varTema("--primary", "#18675f");
  const teks = varTema("--primary-foreground", "#ffffff");
  node.style.background = latar;
  node.style.color = teks;
  node.style.border = "1px solid rgba(0,0,0,.12)";
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

// ── Peredam tooltip NATIVE ──────────────────────────────────────────────────
// Tooltip kustom tidak cukup mencabut `title` pada elemen yang di-hover: bila
// SEL atau BARIS induknya juga punya `title` (pola umum di tabel), peramban
// memakai title leluhur itu dan menggambar tooltip native-nya BERDAMPINGAN
// dengan tooltip kustom — dua kotak dengan teks sama dan gaya berbeda.
// Karena itu seluruh rantai anchor→body dibekukan saat tooltip tampil, lalu
// dipulihkan persis saat tooltip disembunyikan (penting untuk pembaca layar).
let judulBeku = [];

function bekukanJudulLeluhur(anchor) {
  pulihkanJudulLeluhur();
  for (let n = anchor; n && n.nodeType === 1 && n !== document.body; n = n.parentElement) {
    if (n.hasAttribute && n.hasAttribute("title")) {
      judulBeku.push([n, n.getAttribute("title")]);
      n.removeAttribute("title");
    }
  }
}

function pulihkanJudulLeluhur() {
  for (const [n, judul] of judulBeku) {
    if (n && n.isConnected && !n.hasAttribute("title")) n.setAttribute("title", judul);
  }
  judulBeku = [];
}

/**
 * Sembunyikan tooltip (dan batalkan yang sedang menunggu tampil).
 *
 * `hanyaUntuk` membatasi penyembunyian pada satu elemen: dipakai saat kursor
 * MENINGGALKAN sebuah elemen. Tanpa pembatas ini, elemen yang ditinggalkan
 * ikut membunuh tooltip elemen yang BARU saja di-hover — pada tabel, pindah
 * dari satu sel terpotong ke sel sebelahnya membuat tooltip tak pernah tampil.
 */
export function sembunyikanTooltip(hanyaUntuk) {
  if (hanyaUntuk && sasaran && sasaran !== hanyaUntuk) return;
  clearTimeout(timer);
  timer = null;
  sasaran = null;
  pulihkanJudulLeluhur();
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
  bekukanJudulLeluhur(anchor);
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
  //
  // KECUALI guliran yang lahir dari animasi MARQUEE: elemen teks menggeser
  // `scrollLeft`-NYA SENDIRI dan memicu event scroll bertubi-tubi. Posisi
  // elemen tak bergeser sedikit pun, jadi tak satu pun tooltip perlu
  // disembunyikan karenanya — termasuk tooltip elemen LAIN yang sedang
  // bergulir pulang (animasinya bisa beberapa detik dan dulu membunuh tooltip
  // sel yang baru saja di-hover).
  //
  // Event itu DIHENTIKAN TOTAL, bukan sekadar diabaikan, karena Radix Tooltip
  // menutup tooltipnya begitu ada scroll yang `contains` pemicunya:
  //
  //     if (target?.contains(context.trigger)) onClose();
  //
  // Sebuah elemen selalu `contains` dirinya sendiri, jadi sel yang teksnya
  // berjalan MEMBUNUH TOOLTIPNYA SENDIRI ~12 ms setelah muncul — persis
  // gejala "teks sangat panjang, tooltipnya cuma berkedip". Penyetopan ini
  // efektif karena listener di sini dipasang saat bootstrap aplikasi
  // (src/index.js), jauh sebelum konten tooltip mana pun dibuat, sehingga ia
  // berjalan lebih dulu di simpul & fase yang sama.
  window.addEventListener("scroll", (e) => {
    const n = e.target;
    if (n && n.nodeType === 1 && n.dataset?.marqueeAktif) {
      e.stopImmediatePropagation();
      return;
    }
    if (sasaran && n === sasaran) return;
    sembunyikanTooltip();
  }, true);
  window.addEventListener("resize", sembunyikanTooltip, { passive: true });
  doc.addEventListener("keydown", (e) => {
    if (e.key === "Escape") sembunyikanTooltip();
  });
  doc.addEventListener("pointerdown", sembunyikanTooltip, { passive: true });
}
