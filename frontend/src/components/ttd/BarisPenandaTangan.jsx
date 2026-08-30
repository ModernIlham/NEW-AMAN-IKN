import React from "react";
import { Copy, Link2, Mail, MessageCircle, RotateCcw, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { teksSisaWaktu, warnaSisaWaktu, sudahKedaluwarsa } from "@/lib/sisaWaktu";

/** Status yang MASIH boleh diterbitkan tautannya. Sengaja daftar-putih:
 *  "belum ditandatangani" saja tidak cukup — orang yang sudah mengunggah
 *  bubuhan dan sedang menunggu validasi TIDAK boleh dikirimi tautan baru,
 *  sebab tautan baru mematikan yang lama. */
const BOLEH_TERBIT = ["aktif", "menunggu"];

/** Status yang sudah lewat tahap penekenan — sisa waktu tautannya tak lagi
 *  jadi dasar keputusan apa pun. */
const SUDAH_LEWAT = ["menunggu_validasi", "terverifikasi", "ditandatangani"];

/**
 * Satu baris penanda tangan pada dialog detail permintaan TTD.
 *
 * DIPADATKAN atas permintaan pemilik: *"perbaiki tampilan ini agar semuanya
 * rapi dan terlihat memanfaatkan ruang yang ada ... agar terlihat padat
 * informasi yang ditampilkan."*
 *
 * DUA SEBAB baris ini dulu menghabiskan tiga baris penuh per orang:
 *
 * 1. Tombol "Terbitkan Link" berdiri di BARIS SENDIRI, rata kiri, dengan
 *    dua pertiga lebar di sebelahnya kosong.
 * 2. Tombol itu ditulis `h-7` TANPA `min-w-0 min-h-0`, sehingga aturan
 *    tap-target global di `index.css` (`button { min-height:44px;
 *    min-width:44px }` pada ≤1023px) membengkakkannya jadi 44 px — `min-*`
 *    selalu menang atas `height`. Saudara-saudaranya (WhatsApp, Email,
 *    Salin) sudah dikecualikan; yang ini terlewat.
 *
 * Susunan sekarang, dua baris pada keadaan lazim:
 *
 *     1. Nama Penanda Tangan          [Giliran aktif] [13 hari lagi]
 *        Jabatan · NIP …                     [🔗 Terbitkan Link]
 *
 * Baris berikutnya hanya muncul bila memang ada isinya: baris berbagi
 * SETELAH tautannya terbit, deklarasi jumlah area, tindakan validator, dan
 * catatan hasil verifikasi.
 */
export default function BarisPenandaTangan({
  signer, dibatalkan = false, gambarTtd = "", link = "",
  bisaValidasi = false,
  onTerbitkan, onWhatsapp, onEmail, onSalin, onValidasi, onBukaUlang,
  labelStatus = "", warnaStatus = "",
}) {
  const s = signer || {};
  const bisaTerbit = !dibatalkan && BOLEH_TERBIT.includes(s.status);
  const tampilkanSisa = !dibatalkan && !SUDAH_LEWAT.includes(s.status);
  const sisa = teksSisaWaktu(s.kedaluwarsa_info);
  const tahapValidasi = ["menunggu_validasi", "terverifikasi"].includes(s.status);

  return (
    <div className="rounded-xl border border-border px-2.5 py-2 space-y-1 min-w-0 overflow-hidden"
      data-testid={`ttd-baris-signer-${s.signer_id}`}>
      {/* Baris 1 — nama + penanda keadaan */}
      <div className="flex items-center gap-2 min-w-0">
        {/* Nama MEMBUNGKUS, tidak dipotong. Dua pill di sebelahnya memakan
            ~150 px pada layar 400 px, sehingga `truncate` memangkas nama
            orang jadi "1. Karlinus Ignas…" — pada dialog yang justru
            menentukan siapa bertanggung jawab meneken apa. Jabatan di baris
            bawah tetap dipotong: ia keterangan, bukan identitas. */}
        <p className="text-sm font-semibold leading-snug flex-1 min-w-0 break-words">
          {s.urutan}. {s.nama}
        </p>
        {/* Pratinjau TTD disembunyikan bila permintaan DIBATALKAN — endpoint
            gambarnya menolak (410) sehingga <img> jadi ikon rusak. */}
        {s.signature_file_id && !dibatalkan && gambarTtd ? (
          <img alt={`TTD ${s.nama}`} src={gambarTtd}
            className="h-8 max-w-[72px] object-contain bg-white rounded border border-border p-0.5 shrink-0" />
        ) : null}
        <span className={`shrink-0 px-2 py-0.5 rounded-full text-[10px] font-bold ${warnaStatus || "bg-muted text-muted-foreground"}`}>
          {labelStatus || s.status}
        </span>
        {/* Sisa waktu tautan ORANG INI — dasar keputusan apakah tautannya
            perlu diterbitkan ulang. Tak relevan bagi yang sudah meneken. */}
        {tampilkanSisa && sisa && (
          <span className={`shrink-0 px-2 py-0.5 rounded-full text-[10px] font-bold ${warnaSisaWaktu(s.kedaluwarsa_info)}`}
            data-testid={`ttd-sisa-signer-${s.signer_id}`}>
            {sudahKedaluwarsa(s.kedaluwarsa_info) ? "Tautan mati" : sisa}
          </span>
        )}
      </div>

      {/* Baris 2 — jabatan MEMAKAI SISA LEBAR, tombol menempel di kanannya.
          Dulu tombol ini punya barisnya sendiri; menaruhnya di sini
          menghapus satu baris penuh per penanda tangan tanpa menghilangkan
          apa pun. */}
      <div className="flex items-center gap-2 min-w-0">
        <p className="text-[11px] text-muted-foreground truncate flex-1 min-w-0">
          {s.jabatan || "-"}{s.nip ? ` · NIP ${s.nip}` : ""}
          {s.signed_at ? ` · ${s.signed_at_teks || ""}` : ""}
        </p>
        {bisaTerbit && (
          <Button type="button" variant="outline" size="sm"
            className="shrink-0 h-8 px-2.5 text-[11px] min-w-0 min-h-0"
            title="Buat link baru (link lama otomatis mati) lalu salin"
            onClick={onTerbitkan} data-testid={`ttd-link-ulang-${s.signer_id}`}>
            <Link2 className="w-3.5 h-3.5 mr-1" />Terbitkan Link
          </Button>
        )}
      </div>

      {/* Deklarasi jumlah area — pengakuan penanda tangan bahwa area TTD
          miliknya lebih sedikit dari yang diminta. Dasar keputusan validator,
          jadi TIDAK ikut dipadatkan. */}
      {s.deklarasi_tanpa_area && (
        <div className="rounded-lg bg-amber-500/10 border border-amber-500/25 p-2 text-[10px] text-amber-800 dark:text-amber-200"
          data-testid={`ttd-deklarasi-${s.signer_id}`}>
          <b>Deklarasi jumlah:</b> penanda tangan sudah memeriksa seluruh dokumen dan hanya menemukan
          {` ${s.deklarasi_jumlah_aktual || 0} dari ${s.deklarasi_jumlah_diminta || s.jumlah_ttd || 1} `}
          area TTD miliknya.
          {s.deklarasi_catatan ? ` Catatan: ${s.deklarasi_catatan}` : ""}
        </div>
      )}

      {/* Baris berbagi — HANYA setelah tautannya terbit; di sinilah tiga
          tombol berbagi memang butuh tempat sendiri. */}
      {bisaTerbit && link && (
        <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
          <Button type="button" variant="outline" size="sm"
            className="h-8 w-8 p-0 min-h-0 min-w-0 text-emerald-600"
            title="Bagikan via WhatsApp" aria-label="Bagikan via WhatsApp"
            onClick={onWhatsapp}>
            <MessageCircle className="w-3.5 h-3.5" />
          </Button>
          <Button type="button" variant="outline" size="sm"
            className="h-8 w-8 p-0 min-h-0 min-w-0"
            title="Bagikan via email" aria-label="Bagikan via email"
            onClick={onEmail}>
            <Mail className="w-3.5 h-3.5" />
          </Button>
          <Button type="button" variant="outline" size="sm"
            className="h-8 px-2.5 text-[11px] min-h-0 min-w-0"
            title={link} onClick={onSalin}>
            <Copy className="w-3.5 h-3.5 mr-1" />Salin lagi
          </Button>
        </div>
      )}

      {/* Tindakan validator atas ORANG INI. `bisaValidasi` datang dari status
          PERMINTAAN (bukan status orang): permintaan yang batal atau sudah
          selesai tak lagi bisa divalidasi maupun dibuka ulang. */}
      {tahapValidasi && bisaValidasi && (
        <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
          {s.status === "menunggu_validasi" && (
            <Button type="button" size="sm" className="h-8 px-2.5 text-[11px] min-w-0 min-h-0"
              onClick={onValidasi} data-testid={`ttd-validasi-${s.signer_id}`}>
              <ShieldCheck className="w-3.5 h-3.5 mr-1" />Validasi Sesuai
            </Button>
          )}
          <Button type="button" variant="outline" size="sm"
            className="h-8 px-2.5 text-[11px] min-w-0 min-h-0 text-amber-700 border-amber-500/40"
            onClick={onBukaUlang} data-testid={`ttd-buka-ulang-${s.signer_id}`}>
            <RotateCcw className="w-3.5 h-3.5 mr-1" />Buka Ulang Orang Ini
          </Button>
        </div>
      )}

      {s.validated_at && (
        <p className="text-[10px] text-emerald-700 dark:text-emerald-300 break-words">
          Diverifikasi {s.validated_at_teks || ""}{s.validated_by ? ` oleh ${s.validated_by}` : ""}
          {s.validation_note ? ` · ${s.validation_note}` : ""}
        </p>
      )}
    </div>
  );
}
