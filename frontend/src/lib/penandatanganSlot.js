/**
 * Pemilih penanda tangan — helper MURNI (tanpa React/axios).
 *
 * Permintaan pemilik: *"sudah aktif semua bisa memilih siapa saja yang
 * menandatagani sesuai referensi pejabat yang sudah ditetapkan"*. Aturan tiga
 * lapisnya hidup di backend (`penandatangan_dokumen.py`); berkas ini hanya
 * merapikan apa yang DIKIRIM layar dan apa yang DIBACA layar, supaya kedua
 * layar (Master Satker & LPB gabungan) berperilaku sama persis.
 */

/** Peta slot→id yang bersih: slot tanpa pilihan DIBUANG, bukan dikirim "".
 *
 * Backend memperlakukan `penandatangan: null` sebagai "jangan sentuh" dan
 * `{}` sebagai "kosongkan". Karena itu layar harus tetap mengirim `{}` ketika
 * operator melepas semua pilihan — mengirim `null` akan membuat pelepasan
 * pilihan diam-diam tidak tersimpan.
 */
export function setelSlot(peta, slot, pejabatId) {
  const keluar = {};
  Object.entries(peta || {}).forEach(([k, v]) => {
    const s = String(v || "").trim();
    if (s) keluar[k] = s;
  });
  const baru = String(pejabatId || "").trim();
  if (baru) keluar[slot] = baru;
  else delete keluar[slot];
  return keluar;
}

/** Pejabat pada daftar berdasarkan id, atau null. */
export function cariPejabat(daftar, pejabatId) {
  const pid = String(pejabatId || "").trim();
  if (!pid) return null;
  return (daftar || []).find((p) => String(p?.id || "") === pid) || null;
}

/** Pejabat yang boleh menandatangani dokumen satker `kode`.
 *
 * Cermin `_q_pejabat_satker` di backend: pejabat era-lama tanpa kode satker
 * ikut lolos, dan kode kosong (super-admin lintas satker) berarti semua.
 */
export function pejabatSatker(daftar, kode) {
  const k = String(kode || "").trim();
  if (!k) return [...(daftar || [])];
  return (daftar || []).filter((p) => {
    const ks = String(p?.kode_satker || "").trim();
    return !ks || ks === k;
  });
}

/** Label satu pejabat pada dropdown: nama + jabatan bila ada. */
export function labelPejabat(p) {
  const nama = String(p?.nama || "").trim() || "(tanpa nama)";
  const jab = String(p?.jabatan || "").trim();
  return jab ? `${nama} — ${jab}` : nama;
}

/**
 * Teks opsi "kosong" pada satu slot — menerangkan APA yang terjadi bila
 * operator tidak memilih apa-apa, bukan sekadar "— pilih —".
 *
 * `bawaan` = lapis di bawahnya (untuk layar dokumen: setelan satker). Bila
 * lapis itu menunjuk pejabat yang masih ada, namanya disebut; kalau tidak,
 * jaring terakhirnya adalah peran pada Referensi Pejabat.
 */
export function labelBawaan(slot, bawaan, daftar) {
  const p = cariPejabat(daftar, (bawaan || {})[slot?.kunci]);
  if (p) return `Ikut setelan satker — ${labelPejabat(p)}`;
  const peran = String(slot?.peran_uraian || slot?.peran || "").trim();
  return peran ? `Ikut Referensi Pejabat — peran ${peran}` : "Ikut Referensi Pejabat";
}
