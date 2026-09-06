import React, { memo } from "react";
import {
  diDenah, labelDenah, labelKoordinat, punyaKoordinat,
} from "@/lib/koordinatAset";

/**
 * Ikon lokasi yang membawa DUA keterangan sekaligus: titik koordinat dan
 * penempatan pada denah — masing-masing pada BENTUK dan WARNA sendiri.
 *
 * ── Kenapa digambar sendiri, bukan memakai ikon lucide apa adanya ───────
 * Permintaan pemilik: penanda denah harus ada di dalam ikon yang sama dan
 * tetap terbaca pada kedua posisi koordinat. Percobaan pertama memakai LATAR
 * kotak untuk denah, dan pemiliknya menolaknya dengan alasan yang tepat: pada
 * keadaan "sudah di denah tetapi belum berkoordinat", pin abu-abu di dalam
 * kotak biru menjadi SARU — dua warna bertumpuk pada satu bidang yang sama,
 * dan mata membacanya sebagai satu penanda setengah menyala alih-alih dua
 * keterangan.
 *
 * Yang dipakai sekarang memisahkan keduanya menjadi dua bagian gambar yang
 * tak pernah bertumpuk, masing-masing berwarna sendiri:
 *
 *   PIN (+ centang)  → titik koordinat   · abu-abu ↔ hijau
 *   ALAS DENAH       → penempatan denah  · muncul ↔ tak ada, biru
 *
 * Karena itu keempat keadaannya terbaca tanpa saling mengaburkan, termasuk
 * yang dikeluhkan: pin ABU di atas alas BIRU. Dan ketika belum ada keduanya,
 * tak ada alas sama sekali dan seluruhnya abu-abu.
 *
 * Lucide tak menyediakan kombinasi keempatnya — tak ada pin yang sekaligus
 * bercentang DAN beralas denah — sehingga bentuknya disusun di sini dari
 * potongan yang sama (MapPin, MapPinCheck, MapPinned; ISC, lucide 0.507).
 * Menyusunnya sendiri juga yang memungkinkan tiap bagian diberi warna
 * terpisah; ikon lucide mewarnai seluruh goresannya sekaligus.
 *
 * ── Kenapa letak centangnya berpindah ───────────────────────────────────
 * Tanpa alas denah, centang berada di kanan-bawah (persis `MapPinCheck`) —
 * di sanalah ia paling lega, dan itulah sebabnya ia masih terbaca pada 10px.
 * Dengan alas denah, ruang itu sudah terpakai alasnya, jadi centang pindah ke
 * DALAM kepala pin (`MapPinCheckInside`). Bukan ketidakkonsistenan yang
 * kelupaan: memaksa satu letak untuk kedua keadaan berarti mengorbankan
 * keterbacaan keadaan yang paling sering muncul.
 *
 * ── Warna ───────────────────────────────────────────────────────────────
 * Bentuk DAN warna berubah bersama, bukan warna saja, agar tetap terbaca oleh
 * mata yang sulit membedakan warna.
 *
 * WARNANYA TAK BISA DITITIPKAN PEMANGGIL. Sempat ada prop `warnaKosong` supaya
 * kartu galeri bisa mempertahankan pin cyan-nya yang lama — dan hasilnya
 * justru mengaburkan penandanya: cyan dan hijau terlalu berdekatan pada
 * goresan yang sama, sehingga pin "belum berkoordinat" terbaca seolah sudah
 * (laporan pemilik).
 */

// Potongan bentuk — diadaptasi dari lucide-react 0.507 (lisensi ISC).
const PIN_LEBAR = "M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0";
// Pin yang sama, ekornya dipotong agar tak menabrak centang di kanan-bawah.
const PIN_LEBAR_BERCENTANG = "M19.43 12.935c.357-.967.57-1.955.57-2.935a8 8 0 0 0-16 0c0 4.993 5.539 10.193 7.399 11.799a1 1 0 0 0 1.202 0 32.197 32.197 0 0 0 .813-.728";
const CENTANG_LUAR = "m16 18 2 2 4-4";
// Pin yang lebih ringkas, menyisakan ruang bawah untuk alas denah.
const PIN_RINGKAS = "M18 8c0 3.613-3.869 7.429-5.393 8.795a1 1 0 0 1-1.214 0C9.87 15.429 6 11.613 6 8a6 6 0 0 1 12 0";
const CENTANG_DALAM = "m10.1 8.1 1.3 1.3 2.7-2.7";
const ALAS_DENAH = "M8.714 14h-3.71a1 1 0 0 0-.948.683l-2.004 6A1 1 0 0 0 3 22h18a1 1 0 0 0 .948-1.316l-2-6a1 1 0 0 0-.949-.684h-3.712";

const IkonLokasiAset = memo(({ asset, className = "w-3 h-3" }) => {
  const ada = punyaKoordinat(asset);
  const denah = diDenah(asset);

  const judul = [
    ada ? `Titik koordinat sudah terpasang (${labelKoordinat(asset)})`
        : "Belum ada titik koordinat",
    denah ? `sudah masuk denah${labelDenah(asset) ? ` — ${labelDenah(asset)}` : ""}`
          : "belum masuk denah",
  ].join(" · ");

  // Pin memakai bentuk ringkas HANYA saat beralas denah — pin lebar akan
  // menembus alasnya.
  const pin = denah ? PIN_RINGKAS
    : (ada ? PIN_LEBAR_BERCENTANG : PIN_LEBAR);
  // Diturunkan dari pin yang BENAR-BENAR digambar, bukan dihitung ulang dari
  // `denah`. Atribut penanda yang sekadar menyatakan ulang masukannya tak
  // membuktikan apa pun: mutasi yang memakai pin lebar di atas alas denah —
  // sehingga pinnya menembus alasnya — sempat lolos karena atribut ini tetap
  // berkata "ringkas".
  const bentukPin = pin === PIN_RINGKAS ? "ringkas" : "lebar";

  return (
    <span
      className="inline-flex flex-shrink-0"
      role="img"
      title={judul}
      aria-label={judul}
      data-testid={`lokasi-penanda-${(asset || {}).id || ""}`}
      data-di-denah={denah ? "ya" : "tidak"}
    >
      <svg
        viewBox="0 0 24 24" fill="none" strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round"
        aria-hidden="true"
        className={`${className} flex-shrink-0`}
        data-testid={`lokasi-ikon-${(asset || {}).id || ""}`}
        data-berkoordinat={ada ? "ya" : "tidak"}
        data-bentuk={`${bentukPin}-${ada ? "cek" : "titik"}`}
      >
        {/* Bagian KOORDINAT — warnanya sendiri, tak pernah menyentuh alas. */}
        <g className={ada ? "stroke-emerald-500" : "stroke-muted-foreground"}
          data-bagian="koordinat">
          <path d={pin} />
          {/* Titik di kepala pin TETAP ada kecuali saat centangnya masuk ke
              dalam kepala — di sanalah centang MENGGANTIKAN titik (idiom
              `MapPinCheckInside`). Tanpa aturan itu, pin bercentang di luar
              kehilangan titiknya dan tersisa sebagai tapal kuda: bentuk yang
              tak lagi terbaca sebagai pin lokasi. */}
          {ada && denah
            ? <path d={CENTANG_DALAM} />
            : (
              <>
                <circle cx="12" cy={denah ? "8" : "10"} r={denah ? "2" : "3"} />
                {ada && <path d={CENTANG_LUAR} />}
              </>
            )}
        </g>
        {/* Bagian DENAH — hanya ada bila memang ditempatkan, dan berwarna
            sendiri. Inilah yang memisahkannya dari warna koordinat. */}
        {denah && (
          <g className="stroke-sky-500" data-bagian="denah">
            <path d={ALAS_DENAH} />
          </g>
        )}
      </svg>
    </span>
  );
});
IkonLokasiAset.displayName = "IkonLokasiAset";

export default IkonLokasiAset;
