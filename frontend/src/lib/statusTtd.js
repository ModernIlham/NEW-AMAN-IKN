/**
 * Ringkasan status tanda tangan elektronik sebuah DOKUMEN — helper MURNI.
 *
 * Laporan pemilik: *"Riwayat BAST di bagian kirim tanda tangan selalu berakhir
 * dengan TTD sudah kedaluwarsa dan seperti tidak terhubung dengan modul TTD
 * elektronik."*
 *
 * Bentuk kalimatnya penting. "Kedaluwarsa" saja terbaca sebagai AKHIR CERITA —
 * padahal tautannya bisa diterbitkan ulang kapan saja. Karena itu status yang
 * masih bisa ditindaklanjuti selalu menyebut tindakannya, bukan hanya
 * keadaannya.
 */
import { teksSisaWaktu, mendesak } from "@/lib/sisaWaktu";

/**
 * {teks, nada, perluTindakan} untuk satu ringkasan `ttd` dari server.
 * `null` bila dokumen belum pernah dikirim ke TTD elektronik.
 */
export function ringkasTtdDokumen(ttd) {
  if (!ttd || !ttd.id) return null;
  const jumlah = Number(ttd.jumlah || 0);
  const selesai = Number(ttd.selesai_jumlah || 0);

  if (ttd.status === "batal") {
    return { teks: "TTD elektronik dibatalkan", nada: "merah", perluTindakan: false };
  }
  if (ttd.semua_selesai) {
    return { teks: `Ditandatangani lengkap (${selesai}/${jumlah})`,
             nada: "hijau", perluTindakan: false };
  }
  if (ttd.perlu_terbit_ulang) {
    // INTI laporan pemilik: sebut jalan keluarnya, jangan berhenti di
    // "kedaluwarsa".
    return { teks: `Tautan mati — terbitkan ulang (${selesai}/${jumlah} diteken)`,
             nada: "merah", perluTindakan: true };
  }
  const sisa = teksSisaWaktu(ttd.kedaluwarsa_terdekat);
  const inti = `Menunggu tanda tangan (${selesai}/${jumlah})`;
  return {
    teks: sisa ? `${inti} · tautan ${sisa}` : inti,
    nada: mendesak(ttd.kedaluwarsa_terdekat) ? "kuning" : "biru",
    perluTindakan: false,
  };
}

const KELAS = {
  merah: "bg-red-500/15 text-red-600 dark:text-red-400",
  kuning: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  hijau: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  biru: "bg-sky-500/15 text-sky-700 dark:text-sky-400",
};

export function kelasNada(nada) {
  return KELAS[nada] || KELAS.biru;
}

/** Penanda tangan yang tautannya masih berguna untuk diterbitkan ulang. */
export function bisaTerbitUlang(signer) {
  return String(signer?.status || "") !== "ditandatangani";
}
