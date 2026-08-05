/**
 * Laci "Alat" peta kolaborasi — usulan, seleksi, alat ukur dalam satu tombol.
 *
 * Mandat pemilik: di layar HP yang sempit, toolbar peta tak muat sehingga
 * tombol paling kiri terpotong. Tiga alat dilebur jadi satu tombol.
 *
 * BAHAYA YANG DIJAGA DI SINI. Dua dari tiga alat itu adalah SAKLAR yang tetap
 * menyala setelah lacinya ditutup. Selama tombolnya berdiri sendiri, warna
 * amber-nya yang memberi tahu "mode ini masih hidup". Begitu dilipat ke dalam
 * laci, isyarat itu ikut hilang — pemakainya mengetuk peta, titik ukur
 * bertambah, dan ia tak tahu kenapa. Karena itu tombol lacinya WAJIB
 * menyuarakan alat mana yang sedang aktif, dan kalimat itu disusun di sini
 * supaya bisa diuji.
 */

export const ALAT_PETA = {
  USULAN: "usulan",     // tinjau kontribusi tamu (operator saja)
  SELEKSI: "seleksi",   // mode moderasi — pilih titik untuk dihapus (operator saja)
  UKUR: "ukur",         // alat ukur jarak & luas (semua orang)
};

/** Alat yang tersedia bagi pemakai ini, sesuai izinnya. */
export function daftarAlatPeta(izin) {
  const alat = [];
  if (izin && izin.bolehModerasi) alat.push(ALAT_PETA.USULAN, ALAT_PETA.SELEKSI);
  alat.push(ALAT_PETA.UKUR);
  return alat;
}

/**
 * true bila alatnya layak dilipat jadi satu tombol.
 *
 * Tamu hanya punya alat ukur. Melipat SATU tombol ke dalam laci tidak
 * menghemat ruang sama sekali (lebar lacinya sama dengan lebar tombolnya)
 * tetapi menambah satu ketukan untuk memakainya — jadi jangan.
 */
export function perluLaciAlat(izin) {
  return daftarAlatPeta(izin).length > 1;
}

/**
 * Ringkasan saklar yang sedang menyala, untuk label & penanda tombol laci.
 * @returns {{adaAktif: boolean, daftar: string[], label: string}}
 */
export function ringkasAlatAktif(status) {
  const daftar = [];
  if (status && status.moderasi) daftar.push("Seleksi");
  if (status && status.ukur) daftar.push("Alat ukur");
  return {
    adaAktif: daftar.length > 0,
    daftar,
    label: daftar.length
      ? `Alat — ${daftar.join(" & ")} sedang aktif`
      : "Alat peta — usulan, seleksi, ukur",
  };
}
