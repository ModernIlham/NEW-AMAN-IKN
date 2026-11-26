/**
 * Reload dashboard langsung memakai kegiatan tersimpan milik akun yang sama.
 *
 * Dulu `selectedActivity` diawali null: halaman Pilih Kegiatan ter-mount
 * sekejap dan menembakkan 5 request (termasuk agregasi seluruh aset satker)
 * yang langsung dibuang. Salinan kini diikat ke pemiliknya karena logout
 * otomatis sengaja menyisakan kegiatan terakhir di peramban.
 */
import fs from "fs";
import path from "path";
import { bacaKegiatanTersimpan, cadanganKegiatanLuring, hapusKegiatanTersimpan, simpanKegiatanTersimpan } from "./kegiatanTersimpan";

const KEG = { id: "keg-1", name: "Inventarisasi 2026", status_pengesahan: "draft" };

beforeEach(() => localStorage.clear());

test("salinan milik akun yang sama dipakai seketika", () => {
  simpanKegiatanTersimpan(KEG, "u1");
  expect(bacaKegiatanTersimpan("u1")).toEqual(KEG);
});

test("salinan milik akun LAIN tidak pernah dipakai — seketika maupun cadangan luring", () => {
  simpanKegiatanTersimpan(KEG, "u1");
  expect(bacaKegiatanTersimpan("u2")).toBeNull();
  expect(cadanganKegiatanLuring("keg-1", "u2")).toBeNull();
  expect(bacaKegiatanTersimpan(undefined)).toBeNull();
});

test("salinan era lama tanpa pemilik: tidak tampil seketika, tetap jadi cadangan luring", () => {
  localStorage.setItem("currentActivityId", "keg-1");
  localStorage.setItem("currentActivity", JSON.stringify(KEG));
  expect(bacaKegiatanTersimpan("u1")).toBeNull();
  expect(cadanganKegiatanLuring("keg-1", "u1")).toEqual(KEG);
});

test("id dan salinan tak cocok / rusak → null tanpa melempar", () => {
  simpanKegiatanTersimpan(KEG, "u1");
  localStorage.setItem("currentActivityId", "keg-lain");
  expect(bacaKegiatanTersimpan("u1")).toBeNull();
  localStorage.setItem("currentActivityId", "keg-1");
  localStorage.setItem("currentActivity", "{rusak");
  expect(bacaKegiatanTersimpan("u1")).toBeNull();
  expect(cadanganKegiatanLuring("keg-1", "u1")).toBeNull();
});

test("hapus membersihkan ketiga kunci", () => {
  simpanKegiatanTersimpan(KEG, "u1");
  hapusKegiatanTersimpan();
  expect(localStorage.getItem("currentActivityId")).toBeNull();
  expect(localStorage.getItem("currentActivity")).toBeNull();
  expect(localStorage.getItem("currentActivityOwner")).toBeNull();
});

describe("pembungkus DashboardPage", () => {
  const src = fs.readFileSync(path.resolve(__dirname, "../pages/DashboardPage.jsx"), "utf8");
  const pembungkus = src.slice(src.indexOf("export default function DashboardPage"));

  test("state awal dari salinan, bukan null (tanpa mount sekejap halaman Pilih Kegiatan)", () => {
    expect(pembungkus).toContain("useState(() => bacaKegiatanTersimpan(user?.id))");
    expect(pembungkus).not.toMatch(/const \[selectedActivity, setSelectedActivity\] = useState\(null\)/);
  });

  test("hanya jawaban pasti server yang menghapus pilihan; gangguan sementara tidak", () => {
    expect(pembungkus).toContain("[400, 403, 404, 410].includes(status)");
    expect(pembungkus).toContain("cadanganKegiatanLuring(storedId, user?.id)");
  });

  test("jawaban usang tak menimpa pilihan baru, objek identik dipertahankan", () => {
    expect(pembungkus).toContain("masihBerlaku()");
    expect(pembungkus).toContain("JSON.stringify(prev) === JSON.stringify(r.data) ? prev : r.data");
  });
});
