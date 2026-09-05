/**
 * Pemilih PENERIMA barang persediaan dari Master Pegawai — helper MURNI.
 *
 * Sebelum ini pengeluaran barang hanya mencatat "Unit Penerima" sebagai teks
 * bebas: bukti pengeluaran tak pernah menyebut SIAPA yang menerima. Akibatnya
 * tak ada yang bisa dimintai pertanggungjawaban, dan tak ada yang bisa diminta
 * menandatangani bukti serah terimanya.
 *
 * Isian tetap berupa teks (datalist), bukan select tertutup: penerima bisa saja
 * belum ada di master, atau bukan pegawai satker ini sama sekali. Yang berubah
 * adalah teks yang COCOK kini menghasilkan NIP — dan NIP itulah yang diperiksa
 * server terhadap Master Pegawai.
 */

/** Daftar pegawai → opsi datalist. Yang tak bernama dibuang. */
export function opsiPenerima(pegawai) {
  return (pegawai || [])
    .map((p) => {
      const nama = String(p?.nama || "").trim();
      if (!nama) return null;
      const nip = String(p?.nip || "").trim();
      const unit = String(p?.unit_kerja || "").trim();
      return { label: nip ? `${nama} — ${nip}` : nama, nama, nip, unit };
    })
    .filter(Boolean);
}

/**
 * Teks isian → {nip, unit} bila cocok, atau null.
 *
 * Tiga bentuk diterima, sesuai cara orang benar-benar mengetik:
 *   1. label utuh hasil klik datalist ("Budi Santoso — 1980…"),
 *   2. NIP telanjang (disalin dari tempat lain),
 *   3. nama saja — HANYA bila tepat satu pegawai bernama itu.
 *
 * Nama yang dipakai lebih dari satu orang sengaja TIDAK dicocokkan: menebak
 * salah satunya berarti membekukan NIP orang lain ke bukti pengeluaran, dan
 * tak ada yang akan menyadarinya.
 */
export function cocokkanPenerima(teks, opsi) {
  const t = String(teks || "").trim();
  if (!t) return null;
  const daftar = opsi || [];
  const persis = daftar.find((o) => o.label === t);
  if (persis) return { nip: persis.nip, unit: persis.unit };
  const olehNip = daftar.find((o) => o.nip && o.nip === t);
  if (olehNip) return { nip: olehNip.nip, unit: olehNip.unit };
  const rendah = t.toLowerCase();
  const senama = daftar.filter((o) => o.nama.toLowerCase() === rendah);
  if (senama.length === 1) return { nip: senama[0].nip, unit: senama[0].unit };
  return null;
}
