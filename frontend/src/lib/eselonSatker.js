/**
 * Tingkat akar pohon unit kerja sebuah satker — MURNI, tanpa React & jaringan.
 *
 * Tidak semua satker berpuncak Eselon I. Unit kantor pusat (Direktorat
 * Jenderal, Badan, Inspektorat Jenderal) memang satker Eselon I, tetapi Kantor
 * Wilayah adalah satker Eselon II, sedangkan Kantor Pelayanan Pratama, Lapas,
 * Madrasah Negeri, dan Kantor Pertanahan kabupaten/kota adalah satker Eselon
 * III/IV — semuanya satker mandiri karena memegang DIPA sendiri.
 *
 * Aturannya sendiri ditegakkan server (`backend/organisasi_utils.py`). Yang
 * dikerjakan berkas ini hanya menjaga agar LAYAR tidak menuntut lebih daripada
 * server: form yang menebak "puncak = Eselon I" akan meminta induk untuk unit
 * puncak sebuah Lapas, dan penggunanya terhenti sebelum permintaannya sempat
 * sampai ke server yang justru akan menerimanya.
 *
 * Tiga keputusan yang membentuknya:
 *
 * 1. **Akarnya DIBACA dari server, tidak dihitung ulang di sini.** Ia bagian
 *    muatan `GET /unit-kerja`. Menghitungnya sendiri dari daftar unit — mis.
 *    "akar = eselon terkecil yang ada" — membuat satker yang masternya masih
 *    kosong tak punya akar sama sekali, dan satker yang salah isi terkunci
 *    pada kesalahannya.
 *
 * 2. **Tingkat DI ATAS akar tetap DITAMPILKAN selama datanya ada.** Satker
 *    yang baru menyatakan dirinya Eselon III bisa masih menyimpan unit Eselon
 *    I/II dari sebelumnya. Menyembunyikan tabnya membuat unit itu tak dapat
 *    dilihat, dipindah, atau dihapus — hilang dari layar tetapi tetap hidup di
 *    basis data, dan tetap ikut terbawa laporan. Ditampilkan, tetapi tak boleh
 *    ditambahi.
 *
 * 3. **Akar BAGAN adalah unit tanpa induk terjangkau, bukan unit Eselon I.**
 *    Bagan yang berakar pada satu tingkat tetap akan kehilangan seluruh cabang
 *    begitu satkernya bukan Eselon I — dan diam-diam, sebab bagan kosong
 *    terbaca sebagai "master belum diisi".
 */

export const LEVEL_MIN = 1;
export const LEVEL_MAKS = 5;

/** Akar BAWAAN: satker yang belum menyatakan tingkatnya berperilaku spt dulu. */
export const AKAR_BAWAAN = 1;

const LABEL = ["Eselon I", "Eselon II", "Eselon III", "Eselon IV", "Eselon V"];

function angka(v) {
  const n = Number(String(v ?? "").trim());
  return Number.isInteger(n) ? n : null;
}

/** Tingkat yang dikenal sistem, 1–5; selain itu `null`. */
export function levelSah(level) {
  const n = angka(level);
  return n !== null && n >= LEVEL_MIN && n <= LEVEL_MAKS ? n : null;
}

/** Tingkat puncak satker; jatuh ke Eselon I bila tak dinyatakan/tak sah. */
export function levelAkar(nilai) {
  return levelSah(nilai) ?? AKAR_BAWAAN;
}

/** "Eselon III" untuk 3; '' bila tingkatnya tak dikenal. */
export function labelLevel(level) {
  const n = levelSah(level);
  return n === null ? "" : LABEL[n - 1];
}

/** Tingkat yang boleh DITAMBAH pada satker berakar `akar` (akar … V). */
export function levelTersedia(akar) {
  const a = levelAkar(akar);
  const hasil = [];
  for (let n = a; n <= LEVEL_MAKS; n += 1) hasil.push(n);
  return hasil;
}

/** Unit tingkat ini wajib punya induk? Puncak satker tidak; di bawahnya ya. */
export function butuhInduk(level, akar) {
  const n = levelSah(level);
  return n !== null && n > levelAkar(akar);
}

/** Boleh menambah unit di tingkat ini? Tingkat di atas puncak bukan miliknya. */
export function bolehTambah(level, akar) {
  const n = levelSah(level);
  return n !== null && n >= levelAkar(akar);
}

/**
 * Tingkat yang ditampilkan sebagai tab: yang tersedia, DITAMBAH yang sudah
 * terlanjur berisi meski di atas puncak (lihat keputusan 2). Menaik.
 */
export function levelTampil(akar, units) {
  const set = new Set(levelTersedia(akar));
  (units || []).forEach((u) => {
    const n = levelSah(u?.eselon);
    if (n !== null) set.add(n);
  });
  return [...set].sort((a, b) => a - b);
}

/**
 * Dua tingkat TERATAS satker — bentuk ringkas warisan `[{nama, eselon2: […]}]`
 * yang dipakai kegiatan. Bentuk itu hanya punya dua laci, dan dulu keduanya
 * berarti Eselon I dan II bagi siapa pun; kini maknanya relatif terhadap
 * puncak satkernya. Satker Eselon V hanya punya satu tingkat — laci keduanya
 * tak menunjuk tingkat mana pun, dan "Eselon VI" adalah tingkat karangan.
 */
export function levelRingkas(akar) {
  const a = levelAkar(akar);
  return a >= LEVEL_MAKS ? [a] : [a, a + 1];
}

/** Nama kolom eselon pada aset/pegawai untuk tingkat itu: 3 → "eselon3". */
export function fieldLevel(level) {
  const n = levelSah(level);
  return n === null ? "" : `eselon${n}`;
}

/** Unit yang tak punya induk terjangkau — akar bagan, apa pun eselonnya. */
export function unitAkar(units) {
  const daftar = (units || []).filter((u) => u && u.id);
  const dikenal = new Set(daftar.map((u) => u.id));
  return daftar.filter((u) => !u.parent_id || !dikenal.has(u.parent_id));
}
