/**
 * SARINGAN TITIK ASET PETA KOLABORASI — logika murni, terpisah dari layar.
 *
 * Peta kolaborasi menyaring empat hal sekaligus: status inventarisasi, kondisi
 * barang, lokasi, dan kelompok "barang serupa". Aturannya ditaruh di sini agar
 * bisa diuji apa adanya — bukan hanya lewat tampilan — dan agar penambahan
 * saringan berikutnya punya satu tempat yang jelas.
 *
 * Array kosong berarti saringan tidak aktif. Nilai tunggal/SEMUA era lama
 * tetap dikenali; banyak nilai dalam satu saringan berarti ATAU.
 */

export const SEMUA = "__semua__";

/** Status yang dipakai bila aset belum punya status tersimpan. */
export const STATUS_BAWAAN = "Belum Diinventarisasi";

const teks = (v) => String(v ?? "").trim();

/** Bentuk seragam tanpa mengubah state; pilihan kosong = semua aset. */
export function pilihanSaringan(nilai) {
  const daftar = Array.isArray(nilai) ? nilai : [nilai];
  return Array.from(new Set(daftar.filter(v => typeof v === "string" && v && v !== SEMUA)));
}

/** Klik opsi menambah/melepas SATU pilihan; Semua mereset kelompok saja. */
export function togglePilihanSaringan(sebelumnya, nilai) {
  if (nilai === SEMUA) return [];
  const daftar = pilihanSaringan(sebelumnya);
  return daftar.includes(nilai) ? daftar.filter(v => v !== nilai) : [...daftar, nilai];
}

/** Cari label/kode tanpa regex; setiap kata wajib cocok, urutan opsi tetap. */
export function cariPilihanPeta(pilihan, pencarian) {
  const kata = teks(pencarian).toLocaleLowerCase("id").split(/\s+/).filter(Boolean);
  if (!kata.length) return pilihan || [];
  return (pilihan || []).filter(p => {
    const label = teks(p.label).toLocaleLowerCase("id");
    const kode = teks(p.kode).toLocaleLowerCase("id");
    // Kode BMN boleh diketik dengan/tanpa titik pemisah.
    const kodeRapat = kode.replace(/[.\s-]/g, "");
    return kata.every(k => label.includes(k) || kode.includes(k)
      || (/^[\d.-]+$/.test(k) && /\d/.test(k) && kodeRapat.includes(k.replace(/[.-]/g, ""))));
  });
}

/** Kunci kelompok "barang serupa": kode + nama barang. */
export function kunciGrup(a) {
  return `${a?.kode || ""}||${a?.nama || ""}`;
}

/**
 * Nilai unik sebuah field beserta jumlah asetnya, terbanyak di atas.
 * Nilai kosong dilewati, kecuali status: aset lama tanpa status termasuk
 * STATUS_BAWAAN, sama seperti aturan penyaringan titiknya.
 */
export function daftarNilai(list, field) {
  const m = new Map();
  (list || []).forEach((a) => {
    const v = teks(a?.[field]) || (field === "status" ? STATUS_BAWAAN : "");
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
 * ATAU antar pilihan dalam satu saringan, DAN antar saringan.
 * Status memakai `STATUS_BAWAAN` bila aset tak punya status — supaya aset lama
 * tanpa status tetap dapat disaring, bukan menghilang dari semua pilihan.
 */
export function saringAset(list, { status = SEMUA, kondisi = SEMUA,
  lokasi = SEMUA, grup = SEMUA } = {}) {
  let out = list || [];
  const pilih = [status, kondisi, lokasi, grup].map(v => new Set(pilihanSaringan(v)));
  if (pilih[0].size) out = out.filter(a => pilih[0].has(teks(a?.status) || STATUS_BAWAAN));
  if (pilih[1].size) out = out.filter(a => pilih[1].has(teks(a?.kondisi)));
  if (pilih[2].size) out = out.filter(a => pilih[2].has(teks(a?.lokasi)));
  if (pilih[3].size) out = out.filter(a => pilih[3].has(kunciGrup(a)));
  return out;
}

/** Berapa saringan yang sedang aktif (untuk lencana angka di tombol). */
export function hitungFilterAktif(nilai) {
  return Object.values(nilai || {}).filter(v => pilihanSaringan(v).length > 0).length;
}
