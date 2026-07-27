import { simpanGpsTerakhir, ambilGpsTerakhir, MAKS_AKURASI_PINJAM_M } from "./gpsCache";

// Fix ini dipinjam dari aset SEBELUMNYA untuk mengisi kolom aset berikutnya.
// Karena itu ia harus lolos gerbang yang ketat: koordinat yang salah tidak
// akan pernah memperbaiki dirinya sendiri, sedangkan kolom kosong pasti terisi
// beberapa detik kemudian oleh fix sungguhan.

const KUNCI = "aman_last_gps";
const T0 = 1_700_000_000_000;

beforeEach(() => localStorage.clear());

describe("simpanGpsTerakhir", () => {
  test("akurasi ikut tersimpan — tanpa itu tak ada yang bisa menilai kelayakannya", () => {
    simpanGpsTerakhir("-1.400000", "116.700000", 7.4);
    expect(JSON.parse(localStorage.getItem(KUNCI)).akurasi).toBe(7);
  });

  test("akurasi tak dilaporkan perangkat → dicatat null, bukan dikarang", () => {
    simpanGpsTerakhir("-1.4", "116.7", undefined);
    expect(JSON.parse(localStorage.getItem(KUNCI)).akurasi).toBeNull();
  });

  test("koordinat kosong tidak menimpa isi cache yang masih baik", () => {
    simpanGpsTerakhir("-1.4", "116.7", 5);
    simpanGpsTerakhir(null, null, 5);
    expect(JSON.parse(localStorage.getItem(KUNCI)).lat).toBe("-1.4");
  });
});

describe("ambilGpsTerakhir", () => {
  test("fix akurat & segar → boleh dipinjam", () => {
    simpanGpsTerakhir("-1.4", "116.7", 6);
    expect(ambilGpsTerakhir()).toMatchObject({ lat: "-1.4", lng: "116.7", akurasi: 6 });
  });

  test("fix LEBAR ditolak — inilah yang dulu lolos ke basis data", () => {
    // ±800 m khas A-GPS yang belum mengunci di dalam gedung. Rana kamera
    // menolaknya di ±8 m; jalur pinjaman dulu tak memeriksa sama sekali.
    simpanGpsTerakhir("-1.4", "116.7", 800);
    expect(ambilGpsTerakhir()).toBeNull();
  });

  test("tepat di ambang masih diterima, sedikit di atasnya ditolak", () => {
    simpanGpsTerakhir("-1.4", "116.7", MAKS_AKURASI_PINJAM_M);
    expect(ambilGpsTerakhir()).not.toBeNull();
    simpanGpsTerakhir("-1.4", "116.7", MAKS_AKURASI_PINJAM_M + 1);
    expect(ambilGpsTerakhir()).toBeNull();
  });

  test("akurasi TIDAK DIKETAHUI ditolak — bukan dianggap bagus", () => {
    simpanGpsTerakhir("-1.4", "116.7", undefined);
    expect(ambilGpsTerakhir()).toBeNull();
  });

  test("fix basi ditolak — surveyor sudah pindah tempat", () => {
    localStorage.setItem(KUNCI, JSON.stringify({ lat: "-1.4", lng: "116.7", akurasi: 5, ts: T0 }));
    expect(ambilGpsTerakhir(T0 + 60_000)).not.toBeNull();
    expect(ambilGpsTerakhir(T0 + 6 * 60_000)).toBeNull();
  });

  test("cache kosong / rusak → null, bukan meledak", () => {
    expect(ambilGpsTerakhir()).toBeNull();
    localStorage.setItem(KUNCI, "{bukan json");
    expect(ambilGpsTerakhir()).toBeNull();
    localStorage.setItem(KUNCI, JSON.stringify({ akurasi: 5, ts: T0 })); // tanpa lat/lng
    expect(ambilGpsTerakhir(T0)).toBeNull();
  });
});
