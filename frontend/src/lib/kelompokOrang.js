/**
 * Kelompok orang → ikon (rencana 3.8, PGW-08).
 *
 * SATU-SATUNYA berkas frontend yang memetakan kelompok ke gambar/warna ikon.
 * Gambarnya dibaca dari `ikonKelompok.json` — salinan byte-identik
 * `backend/data/ikon_kelompok.json` (dijaga uji `permukaanIkon.test.js`).
 */
import DATA from "./ikonKelompok.json";

export const KUNCI_IKON = DATA.urutan;

// Kelas warna per nama warna di JSON. Di sinilah warna kelompok dipilih;
// komponen lain cukup memakai `infoIkon`.
const KELAS_WARNA = {
  sky: "text-sky-600 dark:text-sky-400",
  amber: "text-amber-600 dark:text-amber-400",
  violet: "text-violet-600 dark:text-violet-400",
  emerald: "text-emerald-600 dark:text-emerald-400",
};

/** {kunci, label, alt, elemen, kelas} atau null bila kunci tak dikenal. */
export function infoIkon(kunci) {
  const d = DATA.ikon[kunci];
  if (!d) return null;
  return { kunci, label: d.label, alt: d.alt, elemen: d.elemen,
    kelas: KELAS_WARNA[d.warna] || "" };
}

/** Cermin `organisasi_luar_utils.kunci_ikon`: kelompok kosong → internal. */
export function kunciIkon(kelompok, tataran = "") {
  if (kelompok === "pihak_ketiga") return "pihak_ketiga";
  if (kelompok === "eksternal") return tataran === "daerah" ? "eksternal_daerah" : "eksternal_pusat";
  return "internal";
}

const escAttr = (v) => String(v).replace(/&/g, "&amp;").replace(/"/g, "&quot;")
  .replace(/</g, "&lt;").replace(/>/g, "&gt;");

/**
 * SVG ikon sebagai teks, untuk permukaan non-React (popup peta Leaflet).
 * Gambar & warnanya dari sumber yang sama dengan `IkonKelompok`; kunci tak
 * dikenal → "" (tanpa ikon).
 */
export function svgIkonKelompok(kunci, ukuran = 12) {
  const d = DATA.ikon[kunci];
  if (!d) return "";
  const isi = d.elemen.map(([tag, attrs]) => `<${tag} ${Object.entries(attrs)
    .map(([k, v]) => `${k}="${escAttr(v)}"`).join(" ")}/>`).join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${escAttr(d.alt)}"`
    + ` width="${ukuran}" height="${ukuran}" viewBox="0 0 24 24" fill="none"`
    + ` stroke="${escAttr(d.hex)}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"`
    + ` style="display:inline-block;vertical-align:-2px"><title>${escAttr(d.alt)}</title>${isi}</svg>`;
}

/**
 * Kunci ikon sebuah catatan. Salinan pada catatan itu sendiri (BAST,
 * penerima persediaan — dibekukan sejak PGW-06) MENANG atas jawaban server;
 * tanpa salinan, pakai jawaban penjawab kelompok. Tak ada keduanya → null
 * (tanpa ikon). Tak pernah ditebak dari nama.
 */
export function kelompokDari(catatan, jawaban) {
  const c = catatan || {};
  if (KUNCI_IKON.includes(c.kunci_ikon)) return c.kunci_ikon;
  const kel = c.kelompok || c.penerima_kelompok;
  if (kel) return kunciIkon(kel, c.tataran || c.penerima_tataran || "");
  return KUNCI_IKON.includes(jawaban) ? jawaban : null;
}

/** "Pusat"/"Daerah" untuk orang instansi eksternal; selain itu kosong. */
export function sebutTataran(kunci) {
  if (kunci === "eksternal_pusat") return "Pusat";
  if (kunci === "eksternal_daerah") return "Daerah";
  return "";
}

/**
 * Registry layar yang menampilkan ikon (7.3). Uji menagih tiap berkas di
 * sini mengimpor `IkonKelompok` (atau `svgIkonKelompok` untuk permukaan
 * non-React seperti popup peta). Nama berkas dicocokkan dengan repo saat
 * PGW-08: daftar/kartu aset dirender `VirtualizedAssetTable` dan
 * `AssetGalleryCard`, bukan `DashboardPage` sendiri.
 */
export const PERMUKAAN_IKON = [
  "pages/PegawaiPage.jsx",
  "components/pegawai/PilihKelompok.jsx",
  "components/pegawai/CariOrangLuar.jsx",
  "components/pegawai/KartuTapDialog.jsx",
  "components/assets/AssetForm.jsx",
  "components/assets/VirtualizedAssetTable.jsx",
  "components/assets/AssetGalleryCard.jsx",
  "components/assets/InventoryFieldSheet.jsx",
  "components/assets/BatchEditPanel.jsx",
  "components/assets/AssetMapFullView.jsx",
  "components/assets/AuditLogPanel.jsx",
  "components/penggunaan/PilihPegawaiBast.jsx",
  "pages/PenggunaanPage.jsx",
  "pages/PersediaanPage.jsx",
  "components/persediaan/RiwayatSppb.jsx",
  "pages/PemeliharaanPage.jsx",
  "pages/TtdPermintaanPage.jsx",
  "components/ttd/BarisPenandaTangan.jsx",
  "pages/ActivitySelectionPage.jsx",
  "pages/WasdalPage.jsx",
  "pages/PemanfaatanPage.jsx",
  "components/pegawai/IsianInstansiLuar.jsx",
];
/** Menyusul PGW-11: ikon di samping mitra/pihak yang tertaut `instansi_luar`. */
export const PERMUKAAN_IKON_MENYUSUL = [
  "pages/PemindahtangananPage.jsx",
  "pages/PengadaanPage.jsx",
];
/** Naskah & layar persuratan: tanpa ikon (K10). Akhiran "/" = seisi folder. */
export const LARANGAN_IKON = [
  "pages/PersuratanPage.jsx",
  "components/persuratan/",
  "pages/TtdPublikPage.jsx",
];
