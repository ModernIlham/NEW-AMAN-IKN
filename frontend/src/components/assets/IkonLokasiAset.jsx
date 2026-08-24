import React, { memo } from "react";
import { MapPin, MapPinCheck } from "lucide-react";
import { labelKoordinat, punyaKoordinat } from "@/lib/koordinatAset";

/**
 * Ikon lokasi yang SEKALIGUS menjadi penanda status koordinat.
 *
 * Permintaan pemilik: *"berikan badge centang hijau kecil di sudut bawah ikon
 * pin lokasi ... atau ganti dengan icon lokasi yang memiliki tanda centang
 * sehingga tinggal berganti icon saja."*
 *
 * Dipilih yang KEDUA — mengganti ikon, bukan menempelkan badge. Alasannya
 * ukuran: pin di kartu galeri berukuran 10px (`w-2.5`), dan badge di sudutnya
 * akan menjadi titik 4px yang tak terbaca mata, apalagi bertumpuk dengan
 * garis pin di belakangnya. `MapPinCheck` membawa centangnya DI DALAM bentuk
 * pin, jadi ia tetap terbaca pada ukuran berapa pun — itulah yang membuat
 * "di ukuran layar apa pun" benar-benar terpenuhi, bukan sekadar tersedia.
 *
 * Warnanya pun ikut berubah (hijau) supaya penandanya terbaca tanpa harus
 * membedakan bentuk ikon sekecil itu — bentuk DAN warna, bukan warna saja,
 * agar tetap terbaca oleh mata yang sulit membedakan warna.
 */
const IkonLokasiAset = memo(({ asset, className = "w-3 h-3",
                              warnaKosong = "text-muted-foreground" }) => {
  const ada = punyaKoordinat(asset);
  const Ikon = ada ? MapPinCheck : MapPin;
  const judul = ada
    ? `Titik koordinat sudah terpasang (${labelKoordinat(asset)})`
    : "Belum ada titik koordinat";
  return (
    <Ikon
      className={`${className} flex-shrink-0 ${
        ada ? "text-emerald-500" : warnaKosong}`}
      title={judul}
      aria-label={judul}
      data-testid={`lokasi-ikon-${(asset || {}).id || ""}`}
      data-berkoordinat={ada ? "ya" : "tidak"}
    />
  );
});
IkonLokasiAset.displayName = "IkonLokasiAset";

export default IkonLokasiAset;
