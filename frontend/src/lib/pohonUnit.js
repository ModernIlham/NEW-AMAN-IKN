/**
 * Perataan pohon unit organisasi (Eselon I–V) menjadi daftar yang dapat
 * ditampilkan — MURNI, tanpa React dan tanpa jaringan.
 *
 * Master unit datang dari server sebagai daftar RATA berisi `parent_id`.
 * Menampilkannya apa adanya membuat "Bagian Rumah Tangga" berdiri sejajar
 * dengan "Sekretariat Jenderal", padahal yang satu ada di dalam yang lain —
 * dan pemilih lingkup kegiatan justru menuntut hubungan itu terbaca, sebab
 * memilih satu unit berarti ikut memilih seluruh keturunannya.
 *
 * Tiga keputusan yang membentuk berkas ini:
 *
 * 1. **Urutannya urutan pohon, bukan urutan datang.** Induk selalu mendahului
 *    anaknya, saudara diurutkan menurut nama. Daftar yang berpindah susunan
 *    setiap kali dimuat ulang membuat pengguna kehilangan tempatnya.
 *
 * 2. **Unit yatim tetap ditampilkan, di akhir.** `parent_id` yang menunjuk
 *    unit terhapus membuat cabangnya tak terjangkau dari puncak mana pun.
 *    Menyembunyikannya berarti unit yang ada di basis data tak dapat dipilih
 *    dan tak dapat diperbaiki — hilang tanpa satu pun tanda.
 *
 * 3. **Penelusuran dibatasi.** Data pohon yang melingkar tak boleh membekukan
 *    tab peramban; simpul yang sudah dikunjungi tak pernah dikunjungi ulang.
 */

const PEMISAH = " / ";

/** Daftar rata berurut pohon: `[{...unit, depth, jalur}]`. */
export function susunPohonUnit(units) {
  const daftar = (units || []).filter((u) => u && u.id);
  const anakDari = new Map();
  const dikenal = new Set(daftar.map((u) => u.id));
  daftar.forEach((u) => {
    // Induk yang tak dikenal diperlakukan sama dengan tanpa induk: unitnya
    // tetap muncul, hanya saja sebagai akar.
    const kunci = u.parent_id && dikenal.has(u.parent_id) ? u.parent_id : "";
    if (!anakDari.has(kunci)) anakDari.set(kunci, []);
    anakDari.get(kunci).push(u);
  });
  anakDari.forEach((arr) => arr.sort((a, b) => {
    const ea = String(a.eselon || ""), eb = String(b.eselon || "");
    if (ea !== eb) return ea < eb ? -1 : 1;
    return String(a.nama_unit || "").localeCompare(String(b.nama_unit || ""));
  }));

  const keluar = [];
  const dikunjungi = new Set();
  const turun = (indukId, depth, jalurInduk) => {
    for (const u of anakDari.get(indukId) || []) {
      if (dikunjungi.has(u.id)) continue;      // pohon melingkar
      dikunjungi.add(u.id);
      const nama = String(u.nama_unit || "").trim();
      const jalur = jalurInduk ? `${jalurInduk}${PEMISAH}${nama}` : nama;
      keluar.push({ ...u, depth, jalur });
      turun(u.id, depth + 1, jalur);
    }
  };
  turun("", 0, "");

  // Sisa yang tak terjangkau dari akar mana pun (cabang melingkar).
  daftar.filter((u) => !dikunjungi.has(u.id)).forEach((u) => {
    keluar.push({ ...u, depth: 0, jalur: String(u.nama_unit || "").trim() });
  });
  return keluar;
}

/** Jalur satu unit, atau id-nya apa adanya bila tak dikenal. */
export function jalurUnit(id, pohon) {
  const u = (pohon || []).find((x) => x.id === id);
  return u ? u.jalur : String(id || "");
}

/**
 * Ringkasan lingkup untuk ditampilkan: berapa unit, dan jalurnya.
 *
 * Id yang TIDAK ada pada pohon tetap dihitung dan ditandai. Lingkup adalah
 * penyaring; id mati tidak menyaring apa pun, dan menyembunyikannya membuat
 * kegiatan yang dikira terbatas diam-diam menampilkan seluruh satker.
 */
export function ringkasLingkup(ids, pohon) {
  const daftar = (ids || []).filter(Boolean);
  const dikenal = new Set((pohon || []).map((u) => u.id));
  return {
    jumlah: daftar.length,
    jalur: daftar.map((i) => jalurUnit(i, pohon)),
    tak_dikenal: daftar.filter((i) => !dikenal.has(i)),
  };
}
