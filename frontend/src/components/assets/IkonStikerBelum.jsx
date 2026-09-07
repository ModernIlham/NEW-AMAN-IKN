import React, { memo, useId } from "react";

const BENTUK_LABEL =
  "M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 " +
  "1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 " +
  "0-3.42z";
const CORETAN = "M22 2 2 22";

/**
 * Ikon "stiker BELUM terpasang": label dengan CORETAN yang MEMUTUS labelnya.
 *
 * ── Kenapa digambar sendiri ─────────────────────────────────────────────
 * Lucide 0.507 (yang dipakai proyek ini) tak punya `TagOff`. Yang ada hanya
 * `TicketSlash` — dan tiket bukan label; pada 10px bentuknya terbaca sebagai
 * karcis bergerigi, bukan stiker.
 *
 * ── Kenapa arah coretannya berlawanan dengan kebiasaan lucide ───────────
 * Ikon `*Off` lucide selalu menambahkan garis dari pojok KIRI-ATAS ke
 * KANAN-BAWAH (`m2 2 20 20`). Untuk `Tag` justru itu yang salah: badan label
 * membentang persis pada diagonal yang sama, sehingga garisnya jatuh
 * MEMANJANG di dalam label dan terbaca sebagai garis lipatan, bukan coretan —
 * pada 10px ia nyaris tak dapat dibedakan dari label polos. Diperiksa dengan
 * merender kedua arah berdampingan pada 10/14/24/48 px sebelum dipilih.
 *
 * Karena itu coretannya memakai diagonal yang SATU LAGI (kanan-atas →
 * kiri-bawah), yang memotong badan label tegak lurus.
 *
 * ── Kenapa memakai mask, bukan sekadar menimpakan garis ─────────────────
 * Labelnya DIPUTUS di tempat coretan lewat (gaya `*Off` lucide, dan bentuk
 * yang dicontohkan pemilik). Celah itu tak dihitung dari perpotongan kurva —
 * cara itu rapuh — melainkan dengan MASK: coretan tebal melubangi bentuk
 * label, lalu coretan tipis digambar di atasnya. Mask tak bergantung warna
 * latar, jadi ikon yang sama tetap benar di badge abu, kartu, tabel, mode
 * terang maupun gelap; menutup celah dengan garis sewarna latar akan patah
 * begitu latarnya berubah.
 *
 * Bentuk labelnya diadaptasi dari lucide-react 0.507 `Tag` (lisensi ISC).
 */
const IkonStikerBelum = memo(({ className = "w-3 h-3", ...sisa }) => {
  // Mask id harus unik per instance: dua ikon dengan id sama membuat yang
  // kedua memakai mask milik yang pertama.
  const idMask = `stiker-coret-${useId()}`;
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      data-testid="ikon-stiker-belum"
      {...sisa}
    >
      <defs>
        <mask id={idMask}>
          <rect width="24" height="24" fill="white" />
          {/* Lebar 5 = celah yang masih menyisakan bentuk label pada 10px;
              6 sudah menggerogotinya sampai sulit dikenali. */}
          <path
            d={CORETAN}
            stroke="black"
            strokeWidth="5"
            strokeLinecap="round"
          />
        </mask>
      </defs>
      <g mask={`url(#${idMask})`}>
        <path d={BENTUK_LABEL} />
        <circle cx="7.5" cy="7.5" r=".5" fill="currentColor" />
      </g>
      <path d={CORETAN} />
    </svg>
  );
});

IkonStikerBelum.displayName = "IkonStikerBelum";

export default IkonStikerBelum;
