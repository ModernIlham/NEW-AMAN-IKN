import React, { memo } from "react";
import { MapPin, MapPinCheck } from "lucide-react";
import {
  diDenah, labelDenah, labelKoordinat, punyaKoordinat,
} from "@/lib/koordinatAset";

/**
 * Ikon lokasi yang membawa DUA keterangan sekaligus: titik koordinat dan
 * penempatan pada denah.
 *
 * ── Kenapa dua kanal, bukan empat ikon ──────────────────────────────────
 * Permintaan pemilik: penanda denah harus ada "di dalam ikon yang sama" dan
 * "masih dapat dilihat baik dalam posisi belum berkoordinat maupun sudah".
 * Artinya dua keterangan yang saling bebas — empat keadaan — pada glyph
 * selebar 10px di kartu galeri.
 *
 * Empat glyph berbeda tidak menjawabnya: pembaca harus menghafal empat bentuk
 * alih-alih membaca dua keterangan, dan lucide pun tak menyediakan kombinasi
 * keempatnya (tak ada pin yang sekaligus bercentang dan beralas denah).
 * Perbandingan visual pada ukuran sebenarnya juga menunjukkan `MapPinned` —
 * satu-satunya pin beralas denah — menjadi coreng tak terbaca pada 10px.
 *
 * Maka dua kanal yang saling tegak lurus:
 *
 *   BENTUK GLYPH  → titik koordinat   (MapPin ↔ MapPinCheck, abu ↔ hijau)
 *   LATAR KOTAK   → penempatan denah  (polos ↔ kotak bertepi)
 *
 * Latar dipilih untuk denah, bukan sebaliknya, karena dua alasan. Pertama,
 * bentuk glyph SUDAH bermakna koordinat sejak lama — memindahkannya akan
 * mengubah arti penanda yang sudah dikenal pemakainya. Kedua, latar adalah
 * bidang, bukan garis: ia tetap terbaca pada 10px justru ketika glyph di
 * dalamnya sudah rapat, dan ia tak bergantung pada warna semata.
 *
 * ── Warna ───────────────────────────────────────────────────────────────
 * Bentuk DAN warna berubah bersama, bukan warna saja, agar tetap terbaca oleh
 * mata yang sulit membedakan warna. Latar denah memakai biru — bidang berlatar,
 * bukan garis, sehingga tak dapat tertukar dengan hijau/abu pada goresan pin.
 *
 * WARNANYA TAK BISA DITITIPKAN PEMANGGIL. Sempat ada prop `warnaKosong` supaya
 * kartu galeri bisa mempertahankan pin cyan-nya yang lama — dan hasilnya
 * justru mengaburkan penandanya: cyan dan hijau terlalu berdekatan pada
 * goresan yang sama, sehingga pin "belum berkoordinat" terbaca seolah sudah
 * (laporan pemilik). Satu-satunya kontras yang boleh ada di ikon ini adalah
 * kontras yang MENANDAI sesuatu.
 *
 * ── Perataan ────────────────────────────────────────────────────────────
 * Pembungkusnya SELALU ada dengan padding yang sama, berlatar atau tidak.
 * Pembungkus yang hanya muncul saat beralas denah akan menggeser teks di
 * sebelahnya beberapa piksel, dan baris-baris dalam satu daftar tak lagi rata.
 */
const IkonLokasiAset = memo(({ asset, className = "w-3 h-3" }) => {
  const ada = punyaKoordinat(asset);
  const denah = diDenah(asset);
  const Ikon = ada ? MapPinCheck : MapPin;

  const judul = [
    ada ? `Titik koordinat sudah terpasang (${labelKoordinat(asset)})`
        : "Belum ada titik koordinat",
    denah ? `sudah masuk denah${labelDenah(asset) ? ` — ${labelDenah(asset)}` : ""}`
          : "belum masuk denah",
  ].join(" · ");

  return (
    <span
      className={`inline-flex flex-shrink-0 p-[2px] rounded-[4px] ${
        denah ? "bg-sky-500/15 ring-1 ring-inset ring-sky-500/50" : ""}`}
      role="img"
      title={judul}
      aria-label={judul}
      data-testid={`lokasi-penanda-${(asset || {}).id || ""}`}
      data-di-denah={denah ? "ya" : "tidak"}
    >
      {/* Glyph-nya `aria-hidden`: keterangannya sudah dibawa pembungkus, dan
          dua nama untuk satu penanda membuat pembaca layar menyebutnya dua
          kali. */}
      <Ikon
        aria-hidden="true"
        className={`${className} flex-shrink-0 ${
          ada ? "text-emerald-500" : "text-muted-foreground"}`}
        data-testid={`lokasi-ikon-${(asset || {}).id || ""}`}
        data-berkoordinat={ada ? "ya" : "tidak"}
      />
    </span>
  );
});
IkonLokasiAset.displayName = "IkonLokasiAset";

export default IkonLokasiAset;
