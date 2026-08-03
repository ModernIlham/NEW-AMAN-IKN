/** Uji preferensi kamera: normalisasi nilai + geometri potong/perkecil foto. */
import {
  KUALITAS_MAX, PREFERENSI_BAWAAN, RESOLUSI_MAX, RESOLUSI_MIN,
  hitungBidang, normalkanPreferensi, resolusiTersedia,
} from "./preferensiKamera";

test("nilai sah dipertahankan apa adanya", () => {
  expect(normalkanPreferensi({ orientasi: "potret", resolusi: 2560, kualitas: 92 }))
    .toEqual({ orientasi: "potret", resolusi: 2560, kualitas: 92 });
});

test("nilai rusak/kosong jatuh ke bawaan, bukan menggagalkan kamera", () => {
  expect(normalkanPreferensi(null)).toEqual(PREFERENSI_BAWAAN);
  expect(normalkanPreferensi({ orientasi: "miring", resolusi: "abc", kualitas: NaN }))
    .toEqual(PREFERENSI_BAWAAN);
});

test("angka di luar batas dijepit, bukan ditolak", () => {
  const p = normalkanPreferensi({ resolusi: 99999, kualitas: 500 });
  expect(p.resolusi).toBe(RESOLUSI_MAX);
  expect(p.kualitas).toBe(KUALITAS_MAX);
  expect(normalkanPreferensi({ resolusi: 10 }).resolusi).toBe(RESOLUSI_MIN);
});

test("pilihan resolusi dibatasi kemampuan kamera", () => {
  expect(resolusiTersedia(1920)).toEqual([1280, 1920]);
  expect(resolusiTersedia(4000)).toEqual([1280, 1920, 2560, 3840]);
  // Kamera tak memberitahukan kemampuannya → tawarkan semua.
  expect(resolusiTersedia(undefined)).toEqual([1280, 1920, 2560, 3840]);
  // Kamera sangat kecil tetap dapat satu pilihan — panel tak boleh kosong.
  expect(resolusiTersedia(800)).toEqual([800]);
});

test("auto memakai bingkai apa adanya, hanya diperkecil", () => {
  const b = hitungBidang(3840, 2160, "auto", 1920);
  expect([b.sx, b.sy, b.sw, b.sh]).toEqual([0, 0, 3840, 2160]);
  expect([b.lebar, b.tinggi]).toEqual([1920, 1080]);
});

test("potret memotong dari TENGAH bingkai lebar dan hasilnya tegak", () => {
  const b = hitungBidang(1920, 1080, "potret", 1920);
  expect(b.sw).toBe(810);              // 1080 × 3/4
  expect(b.sh).toBe(1080);
  expect(b.sx).toBe(555);              // terpotong seimbang kiri-kanan
  expect(b.tinggi).toBeGreaterThan(b.lebar);
});

test("lanskap memotong bingkai tegak jadi melebar", () => {
  const b = hitungBidang(1080, 1920, "lanskap", 1920);
  expect(b.sw).toBe(1080);
  expect(b.sh).toBe(810);              // 1080 × 3/4
  expect(b.sy).toBe(555);
  expect(b.lebar).toBeGreaterThan(b.tinggi);
});

test("foto tak pernah diperBESAR dari bingkai aslinya", () => {
  const b = hitungBidang(640, 480, "auto", 3840);
  expect([b.lebar, b.tinggi]).toEqual([640, 480]);
});

test("bingkai tak masuk akal tak membuat perhitungan meledak", () => {
  const b = hitungBidang(0, 0, "potret", 1920);
  expect(b.lebar).toBeGreaterThan(0);
  expect(b.tinggi).toBeGreaterThan(0);
});

test("boolean bukan angka yang sah (Number(true) === 1 menyesatkan)", () => {
  // Tanpa penjagaan ini `{resolusi: true}` diam-diam jadi 640 px — foto kecil
  // tanpa sebab yang kelihatan.
  const p = normalkanPreferensi({ resolusi: true, kualitas: false });
  expect(p.resolusi).toBe(PREFERENSI_BAWAAN.resolusi);
  expect(p.kualitas).toBe(PREFERENSI_BAWAAN.kualitas);
});
