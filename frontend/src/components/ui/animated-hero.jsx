import { motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";

import { cn } from "@/lib/utils";

/**
 * Judul dengan SATU KATA yang berganti-ganti: kata lama terlempar ke atas,
 * kata baru masuk dari bawah dengan pegas.
 *
 * Dipakai panel kiri halaman masuk. Semua kata ditumpuk di posisi yang sama
 * (`absolute`) sehingga hanya satu yang terlihat; itulah sebabnya wadahnya
 * perlu tinggi tetap — tanpa itu barisnya berkedut tiap kali kata berganti.
 *
 * @param {Object} props
 * @param {string[]} props.kata Daftar kata yang bergantian tampil.
 * @param {number} [props.jeda] Lama satu kata bertahan (ms).
 * @param {string} [props.className] Kelas tambahan untuk wadah.
 */
export function KataBerganti({ kata, jeda = 2200, className }) {
  const daftar = useMemo(() => (Array.isArray(kata) && kata.length ? kata : [""]), [kata]);
  const [ke, setKe] = useState(0);

  useEffect(() => {
    // Satu kata saja tak perlu timer — membiarkannya berjalan hanya
    // membangunkan render tiap 2 detik tanpa mengubah apa pun.
    if (daftar.length < 2) return undefined;
    const t = setTimeout(() => setKe((i) => (i + 1) % daftar.length), jeda);
    return () => clearTimeout(t);
  }, [ke, daftar, jeda]);

  // Indeks bisa tertinggal di luar rentang bila daftarnya memendek saat
  // komponen hidup; kembalikan ke awal alih-alih merender `undefined`.
  useEffect(() => {
    setKe((i) => (i < daftar.length ? i : 0));
  }, [daftar]);

  // Penjaga tinggi = salinan TAK TERLIHAT dari kata TERPANJANG, bukan tinggi
  // tetap dalam `em`. Tinggi tetap sempat memotong huruf berekor ("g" pada
  // "Terhubung") karena kotak `overflow-hidden`-nya lebih pendek daripada
  // kotak baris font; salinan ini membuat kotaknya persis setinggi baris
  // sebenarnya, berapa pun ukuran fontnya.
  const terpanjang = daftar.reduce((a, b) => (b.length > a.length ? b : a), "");

  // Setinggi baris pun MASIH kurang. Utilitas ukuran font Tailwind membawa
  // line-height-nya sendiri (`text-5xl` = 1) dan itu bisa mengalahkan
  // `leading-tight` di elemen yang sama — kotak barisnya lalu PERSIS setinggi
  // font, sedangkan rentang ascender-descender Plus Jakarta Sans lebih tinggi
  // (terukur 6px meluber di bawah pada judul 48px), sehingga ekor "g"
  // ("Terhubung") tertahan garis potong. Kotak potong diberi kelonggaran di atas
  // dan bawah; kelonggarannya dibatalkan lagi oleh margin negatif senilai
  // sama sehingga jarak antarbaris judul tak berubah sedikit pun, dan
  // kata-katanya digeser turun sebesar padding agar tetap sebaris persis
  // dengan penjaga tinggi. Kelonggaran ini jauh lebih kecil daripada jarak
  // lempar animasi (±110px), jadi kata yang sedang keluar/masuk tetap
  // tersembunyi.
  const LEGA = "pt-[0.18em] pb-[0.18em] -mt-[0.18em] -mb-[0.18em]";

  return (
    <span className={cn("relative block w-full overflow-hidden", LEGA, className)}>
      <span className="invisible font-semibold" aria-hidden="true">{terpanjang || " "}</span>
      {daftar.map((k, i) => (
        <motion.span
          key={`${k}-${i}`}
          className="absolute inset-x-0 top-[0.18em] font-semibold"
          initial={{ opacity: 0, y: -60 }}
          transition={{ type: "spring", stiffness: 50 }}
          animate={
            ke === i
              ? { y: 0, opacity: 1 }
              : { y: ke > i ? -110 : 110, opacity: 0 }
          }
          // Hanya kata yang sedang tampil yang dibacakan pembaca layar; kata
          // lain tetap ada di DOM (untuk animasinya) tetapi tak berarti apa-apa
          // bila ikut dibacakan sebagai satu kalimat panjang.
          aria-hidden={ke !== i}
        >
          {k}
        </motion.span>
      ))}
    </span>
  );
}

export default KataBerganti;
