import React from "react";
import { AlertTriangle, Check, CircleDashed, FileText, Info } from "lucide-react";

/** Warna per sifat butir. `muatan` sengaja netral, bukan merah: ia bukan
 *  berkas yang kurang — ia bagian isi surat permohonan. */
const WARNA_SIFAT = {
  wajib: "bg-red-500/15 text-red-700 dark:text-red-300",
  wajib_bersyarat: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  muatan: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
  anjuran: "bg-muted text-muted-foreground",
  opsional: "bg-muted text-muted-foreground",
};

/** Penanda kekuatan bukti. Ditampilkan HANYA saat bukan pasal terbaca:
 *  menempelkan lencana pada setiap baris membuat semuanya tampak sama
 *  meragukan, dan justru menghapus perbedaan yang ingin ditunjukkan. */
const WARNA_VERIFIKASI = {
  empiris_siman: "bg-violet-500/15 text-violet-700 dark:text-violet-300",
  belum_terverifikasi: "bg-muted text-muted-foreground",
};

/**
 * Daftar periksa dokumen usulan BMN — sepadan dialog "Kelengkapan Dokumen"
 * di SIMAN V2.
 *
 * Permintaan pemilik: *"agar semua keperluan dokumen untuk segala macam
 * jenis pengusulan BMN dapat ditangani aplikasi dengan baik ... agar
 * pengajuan ke SIMAN V2 dari segala pengusulan kondisi dapat dimanajemen
 * dengan baik."*
 *
 * TIGA hal yang komponen ini sengaja lakukan berbeda dari daftar sembilan
 * butir yang beredar:
 *
 * 1. **Butir yang tak berlaku tetap tampil, diredupkan.** Menyembunyikannya
 *    membuat operator tak pernah tahu ia ada — dan tak bisa menyadari bahwa
 *    jawabannya atas satu pertanyaan keadaanlah yang membuatnya hilang.
 * 2. **Kekuatan buktinya ditulis.** Sebagian butir berasal dari pasal yang
 *    sudah dibaca, sebagian dari layar SIMAN, sebagian lagi dari praktik
 *    lapangan. Menyeragamkannya jadi "wajib" akan menahan usulan atas dasar
 *    yang teksnya sendiri tak pernah minta.
 * 3. **Muatan surat dibedakan dari lampiran.** Data BMN diminta ADA DI DALAM
 *    surat permohonan, bukan sebagai berkas terpisah — menagihnya sebagai
 *    unggahan akan melaporkan "belum lengkap" untuk usulan yang sudah benar.
 */
/** Satu baris butir. Diekstrak karena dipakai dua kali — yang berlaku di
 *  daftar utama, yang tidak berlaku di dalam lipatan. */
function baris(b, punya) {
  const ada = punya.has(b.kode);
  const kurang = b.wajib && !ada;
  return (
    <li key={b.kode}
      className={`rounded-lg border p-2 space-y-1 min-w-0 ${
        kurang ? "border-amber-500/40 bg-amber-500/5"
          : b.berlaku ? "border-border" : "border-border/50 opacity-60"}`}
      data-testid={`kelengkapan-butir-${b.kode}`}>
      <div className="flex items-start gap-2 min-w-0">
        <span className="shrink-0 mt-0.5">
          {ada ? <Check className="w-3.5 h-3.5 text-emerald-600" />
            : kurang ? <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
              : b.sifat === "muatan" ? <FileText className="w-3.5 h-3.5 text-sky-600" />
                : <CircleDashed className="w-3.5 h-3.5 text-muted-foreground" />}
        </span>
        <p className="text-xs font-medium flex-1 min-w-0 break-words leading-snug">
          {b.nama}
        </p>
        <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-bold ${
          WARNA_SIFAT[b.sifat] || WARNA_SIFAT.anjuran}`}>
          {b.sifat_label}
        </span>
      </div>
      {/* Dasarnya selalu tertulis: butir yang tak bisa dijelaskan saat
          ditanya KPKNL sama saja dengan tidak ada. */}
      <p className="text-[10px] text-muted-foreground break-words pl-[22px]">
        {b.dasar}
      </p>
      {b.verifikasi !== "terverifikasi" && (
        <div className="pl-[22px]">
          <span className={`px-1.5 py-0.5 rounded text-[10px] ${
            WARNA_VERIFIKASI[b.verifikasi] || ""}`}
            data-testid={`kelengkapan-verifikasi-${b.kode}`}>
            {b.verifikasi_label}
          </span>
        </div>
      )}
    </li>
  );
}

export default function KelengkapanDokumen({ kelengkapan, terunggah = [] }) {
  const k = kelengkapan || null;
  if (!k || !(k.butir || []).length) {
    return (
      <p className="text-xs text-muted-foreground text-center py-3"
        data-testid="kelengkapan-kosong">
        Daftar dokumen belum tersedia untuk jenis usulan ini.
      </p>
    );
  }
  const punya = new Set((terunggah || []).filter(Boolean));
  const persen = k.jumlah_wajib
    ? Math.round((k.jumlah_terpenuhi / k.jumlah_wajib) * 100) : 100;
  const berlaku = k.butir.filter((b) => b.berlaku);
  const takBerlaku = k.butir.filter((b) => !b.berlaku);

  return (
    <div className="space-y-2 min-w-0" data-testid="kelengkapan-dokumen">
      {/* Ringkasan — angka dulu, kalimat kemudian. */}
      <div className="rounded-lg border border-border p-2.5 space-y-1.5">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs font-bold shrink-0" data-testid="kelengkapan-angka">
            {k.jumlah_terpenuhi}/{k.jumlah_wajib} berkas wajib
          </span>
          <span className={`shrink-0 px-2 py-0.5 rounded-full text-[10px] font-bold ${
            k.lengkap ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
              : "bg-amber-500/15 text-amber-700 dark:text-amber-300"}`}>
            {k.lengkap ? "Lengkap" : "Belum lengkap"}
          </span>
        </div>
        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
          <div className={`h-full rounded-full ${k.lengkap ? "bg-emerald-500" : "bg-amber-500"}`}
            style={{ width: `${persen}%` }} />
        </div>
        {/* Peringatan kekuatan bukti. Muncul HANYA pada rezim yang pasalnya
            belum terbaca — di sana daftar ini anjuran, bukan gerbang. */}
        {!k.berdasar_pasal && (
          <p className="text-[10px] text-muted-foreground flex items-start gap-1"
            data-testid="kelengkapan-belum-terverifikasi">
            <Info className="w-3 h-3 shrink-0 mt-0.5" />
            <span>Daftar untuk jenis usulan ini <b>belum terverifikasi dari teks
              peraturan</b> — pakai sebagai anjuran, bukan syarat. Pastikan ke
              KPKNL sebelum berkas dikirim.</span>
          </p>
        )}
      </div>

      <ul className="space-y-1">
        {berlaku.map((b) => baris(b, punya))}
      </ul>

      {/* Butir yang keadaannya tidak menghendaki TETAP ada, tetapi dilipat.
          Menyembunyikannya sama sekali membuat operator tak pernah tahu ia
          ada — dan tak bisa menyadari bahwa jawabannya atas satu pertanyaan
          keadaanlah yang membuatnya hilang. Menampilkannya semua membuat
          delapan baris tak relevan memakan separuh panel dan menenggelamkan
          empat yang wajib. Dilipat menjawab keduanya. */}
      {takBerlaku.length > 0 && (
        <details className="rounded-lg border border-border/50" data-testid="kelengkapan-tak-berlaku">
          <summary className="cursor-pointer px-2.5 py-2 text-[11px] text-muted-foreground">
            {takBerlaku.length} butir tidak berlaku untuk keadaan yang dipilih
          </summary>
          <ul className="space-y-1 p-2 pt-0">
            {takBerlaku.map((b) => baris(b, punya))}
          </ul>
        </details>
      )}

      {(k.di_luar_daftar || []).length > 0 && (
        <p className="text-[10px] text-muted-foreground" data-testid="kelengkapan-di-luar">
          {k.di_luar_daftar.length} berkas terunggah dengan jenis di luar daftar
          ini — tidak dihitung sebagai pemenuhan butir wajib.
        </p>
      )}
    </div>
  );
}
