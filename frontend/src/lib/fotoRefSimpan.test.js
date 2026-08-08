/* eslint-env jest */
/**
 * FOTO MODE KAMERA PENUH TIDAK BOLEH HILANG — temuan C1 tinjauan 2026-08.
 *
 * `handleSubmit` di AssetForm adalah `useCallback` yang larik dep-nya TIDAK
 * memuat `photoItems`, dan itu disengaja: memasukkannya membuat identitas
 * handler berubah tiap jepretan, padahal handler itulah yang dipegang alur
 * beruntun Mode Kamera Penuh. Konsekuensinya closure-nya bisa BASI.
 *
 * Yang membuatnya berbahaya adalah asimetri dua jalur foto:
 *   - jalur GALERI cabang edit memanggil setPhotoItems DAN setFormData,
 *     sehingga closure kebetulan ikut segar — di sini bugnya tak terlihat;
 *   - jalur KAMERA cabang edit hanya setPhotoItems lalu return — closure
 *     tetap memegang larik lama, `photo_ops.add` terkirim KOSONG, chip
 *     barisnya berakhir "saved", dan byte fotonya sudah tak ada di perangkat
 *     karena snapshot luring memang membuang foto.
 *
 * Intermiten seperti itu tidak akan pernah tertangkap oleh uji alur biasa.
 * Yang bisa mengurungnya adalah aturannya sendiri: DUA bacaan di dalam
 * handleSubmit wajib lewat ref, dan yang di luar tetap lewat state (karena di
 * sanalah re-render memang dibutuhkan).
 */
import fs from "fs";
import path from "path";

const SUMBER = fs.readFileSync(
  path.join(__dirname, "..", "components", "assets", "AssetForm.jsx"), "utf8");

/** Badan handleSubmit: dari deklarasinya sampai baris larik dep penutupnya. */
function badanHandleSubmit(src) {
  const mulai = src.indexOf("const handleSubmit = useCallback(");
  expect(mulai).toBeGreaterThan(-1);
  const sisa = src.slice(mulai);
  const tutup = sisa.search(/\n {2}\}, \[/);
  expect(tutup).toBeGreaterThan(-1);
  return sisa.slice(0, tutup);
}

/**
 * Buang komentar. Aturannya tentang KODE: berkas ini penuh penjelasan panjang
 * yang menyebut `photoItems` sebagai konsep, dan menghitungnya sebagai bacaan
 * state akan membuat penjaga ini menghukum dokumentasi yang justru berharga.
 */
function tanpaKomentar(teks) {
  return teks
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split("\n")
    .filter((b) => !b.trimStart().startsWith("//"))
    .join("\n");
}

/** Kemunculan `photoItems` yang BUKAN bagian dari `photoItemsRef`. */
function bacaanState(teks) {
  return tanpaKomentar(teks).match(/\bphotoItems\b(?!Ref)/g) || [];
}

describe("handleSubmit membaca foto lewat ref, bukan state yang bisa basi", () => {
  test("cermin ref-nya ada dan disinkronkan dari state", () => {
    expect(SUMBER).toMatch(/const photoItemsRef = useRef\(photoItems\);/);
    expect(SUMBER).toMatch(/photoItemsRef\.current = photoItems;/);
  });

  test("NOL bacaan state `photoItems` di dalam handleSubmit", () => {
    // Inilah penjaganya. Mengembalikan salah satu bacaan ke state akan
    // menghidupkan lagi bug foto-hilang yang intermiten itu.
    expect(bacaanState(badanHandleSubmit(SUMBER))).toEqual([]);
  });

  test("kedua bacaan itu memang ada — lewat ref", () => {
    const badan = badanHandleSubmit(SUMBER);
    // (1) penentu hasPhoto → auto-promosi status inventarisasi
    expect(badan).toMatch(/photoItemsRef\.current/);
    // (2) pembangun photo_ops.add — yang benar-benar mengirim fotonya
    expect(badan).toMatch(/for \(const item of photoItemsRef\.current\)/);
    expect((badan.match(/photoItemsRef\.current/g) || []).length).toBeGreaterThanOrEqual(2);
  });

  test("di LUAR handleSubmit, state tetap dipakai — render harus ikut berubah", () => {
    // Kalau seluruh berkas dialihkan ke ref, jumlah foto & grid pratinjau
    // berhenti ikut berubah saat foto ditambah/dihapus. Yang diperbaiki hanya
    // dua bacaan di handleSubmit, bukan seluruh komponen.
    const luar = SUMBER.replace(badanHandleSubmit(SUMBER), "");
    expect(bacaanState(luar).length).toBeGreaterThan(5);
    expect(luar).toMatch(/currentPhotoCount = isEditing \? photoItems\.length/);
  });
});
