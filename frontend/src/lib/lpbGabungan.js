/**
 * Muatan permintaan penerbitan LPB gabungan — MURNI.
 *
 * Dipisah dari layar karena satu field yang lupa disertakan tidak menampakkan
 * gejala apa pun: dialognya tetap berhasil, LPB tetap terbit, hanya penanda
 * tangan pilihannya diam-diam hilang. Bentuk muatan yang diuji menutup itu.
 */

/** Id perolehan yang tercentang, urut sesuai peta pilihan. */
export function idTerpilih(pilih) {
  return Object.keys(pilih || {}).filter((k) => (pilih || {})[k]);
}

export function payloadLpbGabungan(lpbGab) {
  const g = lpbGab || {};
  return {
    perolehan_ids: idTerpilih(g.pilih),
    kode_klasifikasi: g.kodeKlasifikasi || "",
    // Selalu dikirim — termasuk `{}`. Backend memperlakukan field yang HILANG
    // sebagai "tanpa pilihan" juga, tetapi mengirimnya eksplisit membuat
    // maksud layar terbaca dan menjaga pengujian ini tetap berarti.
    penandatangan: g.penandatangan || {},
  };
}
