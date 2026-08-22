/**
 * Penanggung jawab tambahan pada BAST Operasional Unit/Tempat/Tugas.
 *
 * Permintaan pemilik: tiap penanggung jawab membawa NIP/NIK-nya sendiri dan
 * daftar BMN yang melekat padanya, dipilih dari aset yang SUDAH DICENTANG
 * untuk BAST itu.
 *
 * Aturan yang dijaga berkas ini — semuanya tentang dokumen yang akan dibaca
 * orang lain, bukan tentang kerapian layar:
 *
 *   1. Satu BMN hanya boleh melekat pada SATU orang. Dua nama pada satu barang
 *      membuat pertanyaan "siapa yang memegang ini" — pertanyaan yang justru
 *      dijawab BAST — kembali tak terjawab.
 *   2. BMN yang dicabut dari daftar serah terima harus ikut lepas dari
 *      penanggung jawabnya. Kalau tidak, payload membawa aset di luar daftar
 *      dan server menolaknya dengan pesan yang menunjuk tempat yang salah —
 *      operator diberi tahu penanggung jawabnya bermasalah, padahal yang ia
 *      ubah daftar asetnya.
 *
 * MURNI: tanpa React/DOM, seluruhnya teruji unit.
 */

/** `kode·NUP — nama` untuk chip dan daftar pilihan. */
export function labelAset(a) {
  const kode = String(a?.asset_code || "").trim();
  const nup = String(a?.NUP ?? "").trim();
  const nama = String(a?.asset_name || "").trim();
  const kiri = [kode, nup].filter(Boolean).join("·");
  return [kiri, nama].filter(Boolean).join(" — ") || "-";
}

/** Baris penanggung jawab kosong. */
export function pjKosong() {
  return { nama: "", nip: "", unit_tempat_tugas: "", unit_eselon: "",
    asset_ids: [] };
}

/**
 * Isian yang diambil dari satu entri Master Pegawai saat namanya dipilih.
 *
 * `unit_kerja` sudah berisi **unit eselon TERDALAM** — server yang
 * menghitungnya (`unit_kerja_terdalam`), sengaja tidak dihitung ulang di sini.
 * Menghitung ulang aturan "eselon5 → eselon4 → … → unit_kerja" di sisi klien
 * berarti dua salinan aturan yang sama, dan salinan yang tertinggal akan
 * menuliskan unit yang SALAH ke dokumen resmi tanpa satu pun galat.
 *
 * Mengembalikan hanya kolom yang memang ada isinya: pemanggil menimpa isian
 * lama dengan hasil ini, dan nilai kosong dari Master Pegawai tak boleh
 * menghapus apa yang sudah diketik operator.
 */
export function dariPegawai(p) {
  const out = {};
  const nama = String(p?.nama || "").trim();
  const nip = String(p?.nip || "").trim();
  const unit = String(p?.unit_kerja || p?.unit_organisasi || "").trim();
  if (nama) out.nama = nama;
  if (nip) out.nip = nip;
  if (unit) out.unit_eselon = unit;
  return out;
}

/** Semua id aset yang sudah melekat pada penanggung jawab MANA PUN. */
export function asetTerpakai(pjList, kecualiIdx = -1) {
  const out = new Set();
  (pjList || []).forEach((p, i) => {
    if (i === kecualiIdx) return;
    (p?.asset_ids || []).forEach((x) => out.add(String(x)));
  });
  return out;
}

/**
 * Aset yang masih bisa dipilih untuk penanggung jawab ke-`idx`: sudah
 * dicentang untuk BAST ini DAN belum diambil penanggung jawab lain.
 */
export function asetTersedia(rows, dicentang, pjList, idx) {
  const dipakai = asetTerpakai(pjList, idx);
  return (rows || []).filter((a) => {
    const id = String(a?.id || "");
    return id && dicentang?.has?.(id) && !dipakai.has(id);
  });
}

/** Lepaskan satu id aset dari SEMUA penanggung jawab. */
export function lepasAset(pjList, assetId) {
  const id = String(assetId);
  return (pjList || []).map((p) => (
    (p?.asset_ids || []).some((x) => String(x) === id)
      ? { ...p, asset_ids: p.asset_ids.filter((x) => String(x) !== id) }
      : p));
}

/** Buang aset yang tak lagi tercentang dari seluruh penanggung jawab. */
export function selaraskanAset(pjList, dicentang) {
  return (pjList || []).map((p) => {
    const ids = (p?.asset_ids || []).filter((x) => dicentang?.has?.(String(x)));
    return ids.length === (p?.asset_ids || []).length ? p : { ...p, asset_ids: ids };
  });
}

/** Payload penanggung jawab tambahan: baris tanpa nama tidak pernah dikirim. */
export function payloadPj(pjList) {
  return (pjList || [])
    .filter((p) => String(p?.nama || "").trim())
    .map((p) => ({
      nama: String(p.nama).trim(),
      nip: String(p.nip || "").trim(),
      unit_tempat_tugas: String(p.unit_tempat_tugas || "").trim(),
      unit_eselon: String(p.unit_eselon || "").trim(),
      asset_ids: [...new Set((p.asset_ids || []).map(String))],
    }));
}
