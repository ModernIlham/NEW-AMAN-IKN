/**
 * Logika murni layar TINJAU USULAN peta kolaborasi.
 *
 * Kontribusi tamu adalah USULAN, bukan data resmi. Pengelola satker meninjau
 * lalu menyetujui (satu per satu atau "yakin semua") / menolak. Yang disetujui
 * menjadi data peta ASLI: titik → aset baru berkode barang placeholder, dan
 * komentar → komentar pada aset.
 *
 * ATURAN URUTAN yang dijaga di sini: komentar pada sebuah TITIK usulan baru
 * punya aset tujuan setelah titiknya disetujui. Layar karena itu harus
 * menampilkan komentar seperti itu sebagai "menunggu titiknya" — bukan
 * menawarkan tombol Setujui yang pasti ditolak server 409.
 */

export const LABEL_STATUS = {
  terbuka: "Belum ditinjau",
  disetujui: "Sudah diimpor",
  ditolak: "Ditolak",
};

export const WARNA_STATUS = {
  terbuka: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  disetujui: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  ditolak: "bg-red-500/15 text-red-600 dark:text-red-400",
};

/** Status usulan; dokumen era-lama tanpa field dianggap BELUM ditinjau. */
export function statusUsulan(u) {
  const s = String(u?.status_usulan || "").trim();
  return ["terbuka", "disetujui", "ditolak"].includes(s) ? s : "terbuka";
}

/**
 * Bisakah usulan ini disetujui SEKARANG?
 * @returns {{bisa: boolean, alasan: string}}
 */
export function bisaDisetujui(u, semua = []) {
  if (statusUsulan(u) === "disetujui") {
    return { bisa: false, alasan: "Sudah diimpor ke peta asli" };
  }
  if (String(u?.jenis || "") === "titik") return { bisa: true, alasan: "" };
  if (String(u?.target_jenis || "") === "aset") return { bisa: true, alasan: "" };
  // Komentar pada TITIK usulan — hanya bisa setelah titiknya jadi aset.
  const induk = (semua || []).find((x) => x?.id === u?.target_id);
  if (induk && statusUsulan(induk) === "disetujui") {
    return { bisa: true, alasan: "" };
  }
  return {
    bisa: false,
    alasan: "Setujui dulu titik yang dikomentari — komentarnya belum punya aset tujuan",
  };
}

/** Ringkasan angka untuk kepala dialog. */
export function rekapUsulan(items = []) {
  const r = { titik: 0, komentar: 0, total: 0 };
  (items || []).forEach((u) => {
    r.total += 1;
    if (String(u?.jenis || "") === "titik") r.titik += 1;
    else r.komentar += 1;
  });
  return r;
}

/** Kalimat konfirmasi "yakin semua" — menyebut angkanya, bukan "semua data". */
export function kalimatYakinSemua(items = []) {
  const r = rekapUsulan(items);
  if (!r.total) return "Tidak ada usulan yang menunggu.";
  const bagian = [];
  if (r.titik) bagian.push(`${r.titik} titik → aset baru`);
  if (r.komentar) bagian.push(`${r.komentar} komentar`);
  return `Impor ${bagian.join(" dan ")} ke peta asli sekarang?`;
}

/**
 * Ringkas hasil batch jadi satu kalimat JUJUR — yang dilewati & gagal
 * disebutkan, bukan ditelan diam-diam supaya angkanya terlihat bagus.
 */
export function ringkasHasilImpor(r) {
  const n = Number(r?.disetujui || 0);
  const dilewati = (r?.dilewati || []).length;
  const gagal = (r?.gagal || []).length;
  const bagian = [`${n} usulan diimpor`];
  if (dilewati) bagian.push(`${dilewati} dilewati`);
  if (gagal) bagian.push(`${gagal} gagal`);
  return bagian.join(" · ");
}

/** Judul singkat sebuah usulan untuk baris daftar. */
export function judulUsulan(u) {
  if (String(u?.jenis || "") === "titik") {
    return String(u?.nama_titik || "Titik tanpa nama");
  }
  const teks = String(u?.teks || "").trim();
  return teks.length > 80 ? `${teks.slice(0, 80)}…` : (teks || "Komentar kosong");
}
