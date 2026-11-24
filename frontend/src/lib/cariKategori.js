// Pencarian kategori/kode barang untuk panel Edit Info di Mode Kamera Penuh.
// Murni (tanpa React) agar mudah diuji. Pencocokan:
//  - tiap kata kunci harus cocok (AND) di kode ATAU uraian;
//  - kode dicocokkan juga tanpa titik/spasi ("3.05.01" == "30501");
//  - urutan: kode diawali kueri → uraian diawali kueri → sisanya, lalu kode.

/** Kode barang bawaan (usulan/belum diklasifikasi) bila kategori dummy tidak punya kode. */
export const KODE_BARANG_BAWAAN = "0000000000";

const hanyaDigit = (s) => String(s || "").replace(/[^0-9a-z]/gi, "").toLowerCase();

export function cariKategori(categories, kueri, batas = 60) {
  const cats = Array.isArray(categories) ? categories : [];
  const q = String(kueri || "").trim().toLowerCase();
  if (!q) return cats.slice(0, batas);
  const kata = q.split(/\s+/).filter(Boolean);
  const qKode = hanyaDigit(q);
  const hasil = [];
  for (const c of cats) {
    const label = String(c.label || "").toLowerCase();
    const kode = String(c.kode_aset || "").toLowerCase();
    const kodeRata = hanyaDigit(kode);
    const cocok = kata.every((k) => {
      const kRata = hanyaDigit(k);
      return label.includes(k) || kode.includes(k) || (kRata && kodeRata.includes(kRata));
    });
    if (!cocok) continue;
    let skor = 2;
    if (qKode && kodeRata.startsWith(qKode)) skor = 0;
    else if (label.startsWith(q)) skor = 1;
    hasil.push([skor, c]);
  }
  hasil.sort((a, b) => a[0] - b[0] || String(a[1].kode_aset || "").localeCompare(String(b[1].kode_aset || "")));
  return hasil.slice(0, batas).map((h) => h[1]);
}
