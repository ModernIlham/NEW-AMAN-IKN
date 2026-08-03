/**
 * SARINGAN TITIK ASET PETA KOLABORASI — logika murni, terpisah dari layar.
 *
 * Peta kolaborasi menyaring empat hal sekaligus: status inventarisasi, kondisi
 * barang, lokasi, dan kelompok "barang serupa". Aturannya ditaruh di sini agar
 * bisa diuji apa adanya — bukan hanya lewat tampilan — dan agar penambahan
 * saringan berikutnya punya satu tempat yang jelas.
 *
 * Nilai `SEMUA` berarti saringan itu tidak aktif.
 */

export const SEMUA = "__semua__";

/** Status yang dipakai bila aset belum punya status tersimpan. */
export const STATUS_BAWAAN = "Belum Diinventarisasi";

const teks = (v) => String(v ?? "").trim();

/** Kunci kelompok "barang serupa": kode + nama barang. */
export function kunciGrup(a) {
  return `${a?.kode || ""}||${a?.nama || ""}`;
}

/**
 * Nilai unik sebuah field beserta jumlah asetnya, terbanyak di atas.
 * Nilai kosong dilewati: menawarkan saringan yang hasilnya pasti kosong hanya
 * menambah pilihan tanpa guna.
 */
export function daftarNilai(list, field) {
  const m = new Map();
  (list || []).forEach((a) => {
    const v = teks(a?.[field]);
    if (!v) return;
    m.set(v, (m.get(v) || 0) + 1);
  });
  return Array.from(m, ([nilai, jumlah]) => ({ nilai, jumlah }))
    .sort((x, y) => y.jumlah - x.jumlah || x.nilai.localeCompare(y.nilai, "id"));
}

/** Kelompok barang serupa (kode+nama) yang punya ≥2 unit, terbanyak di atas. */
export function daftarGrup(list) {
  const byKey = new Map();
  (list || []).forEach((a) => {
    const key = kunciGrup(a);
    const g = byKey.get(key) || { key, code: a?.kode || "-", name: a?.nama || "-", count: 0 };
    g.count += 1;
    byKey.set(key, g);
  });
  return Array.from(byKey.values()).filter((g) => g.count >= 2)
    .sort((a, b) => b.count - a.count);
}

/**
 * Terapkan seluruh saringan sekaligus (AND antar saringan).
 * Status memakai `STATUS_BAWAAN` bila aset tak punya status — supaya aset lama
 * tanpa status tetap dapat disaring, bukan menghilang dari semua pilihan.
 */
export function saringAset(list, { status = SEMUA, kondisi = SEMUA,
  lokasi = SEMUA, grup = SEMUA } = {}) {
  let out = list || [];
  if (status !== SEMUA) out = out.filter((a) => (teks(a?.status) || STATUS_BAWAAN) === status);
  if (kondisi !== SEMUA) out = out.filter((a) => teks(a?.kondisi) === kondisi);
  if (lokasi !== SEMUA) out = out.filter((a) => teks(a?.lokasi) === lokasi);
  if (grup !== SEMUA) out = out.filter((a) => kunciGrup(a) === grup);
  return out;
}

/** Berapa saringan yang sedang aktif (untuk lencana angka di tombol). */
export function hitungFilterAktif(nilai) {
  return Object.values(nilai || {}).filter((v) => v && v !== SEMUA).length;
}
