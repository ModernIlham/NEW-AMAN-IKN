/**
 * Plafon Kartu Inventaris — temuan C25a.
 *
 * `POST /assets/cards/bulk` menjalankan SELURUH kerjanya di event loop: decode
 * foto Pillow, QR, ReportLab. Diukur pada JPEG 1600×1200 hasil kamera, biayanya
 * 79 ms/aset dan linier — jadi 1000 aset ≈ 79 detik SELURUH aplikasi berhenti,
 * bukan sekadar "permintaan ini lambat". Petugas lain yang sedang menyimpan
 * aset ikut menunggu.
 *
 * Berkas ini menjaga tiga hal yang gampang lepas satu per satu:
 *
 *   1. Plafonnya ada dan MENOLAK, bukan memotong diam-diam.
 *   2. Angkanya SAMA dengan backend — plafon frontend yang lebih longgar
 *      berarti pengguna tetap ditolak server tapi baru setelah mengunggah
 *      seluruh seleksi; yang lebih ketat berarti fitur dipangkas diam-diam.
 *   3. Pesan tolakannya BISA DIBACA dari respons blob.
 */
import fs from "fs";
import path from "path";

import { MAKS_KARTU_CETAK, galatPlafonKartu, idsCetakKartu } from "./cakupanCetak";
import { pesanGalatRespons } from "./downloadFile";

const SUMBER_BACKEND = path.resolve(__dirname, "../../../backend/routes/cards.py");

describe("galatPlafonKartu", () => {
  test("di bawah plafon lolos tanpa pesan", () => {
    expect(galatPlafonKartu(1)).toBeNull();
    expect(galatPlafonKartu(299)).toBeNull();
  });

  test("tepat di plafon masih lolos", () => {
    // Batasnya inklusif di kedua sisi (backend: `len(...) > MAKS_KARTU`).
    // Kalau salah satu sisi memakai `>=`, 300 aset ditolak di satu tempat dan
    // diterima di tempat lain — persis jenis selisih satu yang membingungkan.
    expect(galatPlafonKartu(MAKS_KARTU_CETAK)).toBeNull();
  });

  test("di atas plafon ditolak", () => {
    expect(galatPlafonKartu(MAKS_KARTU_CETAK + 1)).toBeTruthy();
  });

  test("pesannya menyebut jumlah NYATA dan plafonnya", () => {
    // "Terlalu banyak" tanpa angka tak bisa ditindaklanjuti: pengguna tak tahu
    // ia harus membuang berapa.
    const m = galatPlafonKartu(812);
    expect(m).toContain("812");
    expect(m).toContain(String(MAKS_KARTU_CETAK));
  });

  test("pesannya memberi tahu APA yang harus dilakukan", () => {
    expect(galatPlafonKartu(500)).toMatch(/persempit|bertahap/i);
  });

  test("masukan aneh tidak menghalangi cetak yang sah", () => {
    // Gagal-terbuka disengaja: penjaga ini kenyamanan, penegaknya server.
    // Salah baca angka tak boleh mengunci fitur yang sebenarnya boleh jalan.
    expect(galatPlafonKartu(0)).toBeNull();
    expect(galatPlafonKartu(null)).toBeNull();
    expect(galatPlafonKartu(undefined)).toBeNull();
    expect(galatPlafonKartu("bukan angka")).toBeNull();
  });

  test("seleksi lintas halaman yang besar tetap tertangkap", () => {
    // "Pilih semua N aset" mengisi id dari SELURUH hasil filter, bukan hanya
    // halaman yang tampil — itulah jalur yang membuat 1000 id bisa terkirim.
    const banyak = Array.from({ length: 900 }, (_, i) => `aset-${i}`);
    const ids = idsCetakKartu(banyak, []);
    expect(ids).toHaveLength(900);
    expect(galatPlafonKartu(ids.length)).toBeTruthy();
  });
});

describe("plafon frontend == plafon backend", () => {
  const src = fs.readFileSync(SUMBER_BACKEND, "utf8");

  test("MAKS_KARTU backend ada dan angkanya sama", () => {
    const m = src.match(/^MAKS_KARTU = (\d+)$/m);
    expect(m).not.toBeNull();
    expect(Number(m[1])).toBe(MAKS_KARTU_CETAK);
  });

  test("backend MENOLAK, bukan memotong", () => {
    // Memotong diam-diam pada dokumen fisik per barang = aset tanpa kartu
    // tanpa satu pun tanda di PDF-nya.
    expect(src).toMatch(/len\(asset_ids\) > MAKS_KARTU/);
    expect(src).not.toMatch(/asset_ids\[:MAKS_KARTU\]/);
  });

  test("endpoint massalnya ber-rate-limit", () => {
    const i = src.indexOf('@cards_router.post("/assets/cards/bulk")');
    expect(i).toBeGreaterThan(-1);
    expect(src.slice(i, i + 200)).toMatch(/@limiter\.limit\(/);
  });
});

describe("pesanGalatRespons membaca badan galat blob", () => {
  test("detail JSON di dalam Blob terbaca", async () => {
    const blob = new Blob([JSON.stringify({ detail: "maks 300 kartu" })]);
    const pesan = await pesanGalatRespons({ response: { data: blob } }, "cadangan");
    expect(pesan).toBe("maks 300 kartu");
  });

  test("blob berisi teks biasa dikembalikan apa adanya", async () => {
    const blob = new Blob(["Rate limit exceeded"]);
    expect(await pesanGalatRespons({ response: { data: blob } }, "cadangan"))
      .toBe("Rate limit exceeded");
  });

  test("objek JSON biasa tetap terbaca", async () => {
    expect(await pesanGalatRespons({ response: { data: { detail: "X" } } }, "c"))
      .toBe("X");
  });

  test("tanpa detail jatuh ke pesan umum, bukan string kosong", async () => {
    // Argumen kedua adalah pesan KHUSUS TIMEOUT, bukan cadangan umum —
    // ekspektasi pertama saya keliru soal ini dan uji inilah yang menangkap.
    // Yang penting bagi pengguna: selalu ada teks, tak pernah kosong.
    expect(await pesanGalatRespons({}, "khusus timeout")).toBe("Terjadi kesalahan");
    expect(await pesanGalatRespons({ response: { status: 429 } }, "x")).toBe("HTTP 429");
  });

  test("badan 429 slowapi (kunci `error`, bukan `detail`) terbaca", async () => {
    // Bentuk PERSIS yang dikirim server: handler 429 bawaan slowapi
    // (terdaftar di backend/server.py) membalas {"error": "Rate limit
    // exceeded: ..."}. Versi pertama uji ini memakai Blob teks polos —
    // bentuk yang tak pernah dikirim server — sehingga justru mengunci
    // asumsi yang salah dan menyembunyikan celahnya: JSON.parse berhasil,
    // ?.detail = undefined, layar cuma berbunyi "HTTP 429". Padahal pesan
    // plafon baru saja menyuruh pengguna "cetak bertahap per kelompok" —
    // yang menurut aturan malah yang paling cepat menabrak limit 3/menit.
    const badan429 = JSON.stringify({ error: "Rate limit exceeded: 3 per 1 minute" });
    expect(await pesanGalatRespons(
      { response: { status: 429, data: new Blob([badan429]) } }, "c"))
      .toContain("Rate limit exceeded: 3 per 1 minute");
    // Varian non-blob (pemanggil tanpa responseType blob).
    expect(await pesanGalatRespons(
      { response: { status: 429, data: { error: "Rate limit exceeded: 3 per 1 minute" } } }, "c"))
      .toContain("Rate limit");
  });

  test("`detail` tetap MENANG atas `error` bila keduanya ada", async () => {
    // Pusat Unduhan memakai `detail` untuk 409/429-nya; ?? tak boleh terbalik.
    expect(await pesanGalatRespons(
      { response: { data: { detail: "X", error: "Y" } } }, "c")).toBe("X");
    const blob = new Blob([JSON.stringify({ detail: "X", error: "Y" })]);
    expect(await pesanGalatRespons({ response: { data: blob } }, "c")).toBe("X");
  });

  test("blob tetap terbaca tanpa Blob.prototype.text (WebView lama)", async () => {
    // Justru KONDISI BAWAAN di jsdom — dan pada WebView Android lama.
    // Tanpa jalur mundur FileReader, cabang blob melempar diam-diam dan
    // seluruh perbaikan ini tak berbekas di layar.
    expect(typeof Blob.prototype.text).toBe("undefined");
    const blob = new Blob([JSON.stringify({ detail: "maks 300 kartu" })]);
    expect(await pesanGalatRespons({ response: { data: blob } }, "c"))
      .toBe("maks 300 kartu");
  });
});

describe("pemanggil di DashboardPage", () => {
  const src = fs.readFileSync(
    path.resolve(__dirname, "../pages/DashboardPage.jsx"), "utf8");
  // Komentar DIKUPAS dulu. Penjaga struktural yang membaca sumber mentah bisa
  // dipuaskan — atau seperti di sini, dijatuhkan — oleh PROSA: komentar yang
  // menjelaskan "BUKAN getApiError" mengandung kata yang sedang dilarang.
  const fn = src
    .slice(src.indexOf("const handlePrintBulkCards"), src.indexOf("const handleExport"))
    .replace(/^\s*\/\/.*$/gm, "");

  test("plafon dicek SEBELUM axios.post", () => {
    // Setelahnya berarti seluruh seleksi tetap diunggah dan satu jatah
    // rate-limit tetap terbakar untuk permintaan yang pasti ditolak.
    //
    // KEBERADAAN diperiksa lebih dulu, baru urutannya. Versi pertama uji ini
    // hanya membandingkan dua `indexOf`, dan ketika ceknya dihapus sama sekali
    // `indexOf` mengembalikan −1 — yang lebih kecil dari posisi mana pun,
    // sehingga uji "urutan" tetap hijau atas kode yang tak punya urutan.
    // Mutasi "hapus cek pra-kirim" lolos justru karena itu.
    const iCek = fn.indexOf("galatPlafonKartu");
    const iPost = fn.indexOf("axios.post");
    expect(iCek).toBeGreaterThan(-1);
    expect(iPost).toBeGreaterThan(-1);
    expect(iCek).toBeLessThan(iPost);
  });

  test("galat dibaca lewat pembaca yang sadar blob", () => {
    expect(fn).toContain("pesanGalatRespons");
    expect(fn).not.toContain("getApiError");
  });
});
