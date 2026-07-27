// Uji BACA-GABUNG-TULIS upsertSnapshotAsset — akar TIGA temuan audit G3:
// potongan PATCH menimpa seluruh baris, respons tulis menghapus field turunan
// proyeksi list, dan baris yang tak ketemu di daftar state menjadi stub.
//
// `idb` dimock dengan penyimpan in-memory sederhana: yang diuji adalah logika
// gabung, bukan IndexedDB-nya.

const mockSimpanan = { meta: new Map(), assets: new Map() };

// axios (ESM murni) tak bisa diparse jest CRA dari node_modules — dan memang
// tak dipakai uji ini; upsertSnapshotAsset tak menyentuh jaringan.
jest.mock("axios", () => ({ get: jest.fn(), post: jest.fn() }));

// CATATAN: CRA menyetel resetMocks:true — implementasi jest.fn() DIBUANG
// sebelum tiap uji, membuat openDB mengembalikan undefined. Fungsi POLOS
// tidak tersentuh reset, jadi mock ini dipakai fungsi biasa.
jest.mock("idb", () => ({
  openDB: async () => ({
    get: async (store, key) =>
      (store === "meta" ? mockSimpanan.meta : mockSimpanan.assets).get(key),
    put: async (store, val) => {
      const peta = store === "meta" ? mockSimpanan.meta : mockSimpanan.assets;
      peta.set(store === "meta" ? val.activityId : val.id, val);
    },
    delete: async (store, key) =>
      (store === "meta" ? mockSimpanan.meta : mockSimpanan.assets).delete(key),
    getAll: async () => [],
    transaction: () => { throw new Error("tak dipakai uji ini"); },
  }),
}));
// (openDB di atas: arrow yang MENGEMBALIKAN promise objek — dipanggil sebagai
// fungsi oleh getDB; bungkusnya fungsi polos agar selamat dari resetMocks.)

import { upsertSnapshotAsset } from "./offlineSnapshot";

beforeEach(() => {
  mockSimpanan.meta.clear();
  mockSimpanan.assets.clear();
  mockSimpanan.meta.set("keg1", { activityId: "keg1", lastSync: Date.now() });
});

describe("upsertSnapshotAsset — baca-gabung-tulis", () => {
  test("potongan PATCH tidak menghapus field lain dari baris tersimpan", async () => {
    mockSimpanan.assets.set("a1", {
      id: "a1", activity_id: "keg1", asset_name: "Meja Rapat",
      condition: "Baik", location: "Lt. 2", doc_total: 5, doc_checked: 3,
    });
    // Edit luring atas aset yang tak ketemu di daftar state: pemanggil hanya
    // membawa potongan patch. Dulu ini MENGGANTI seluruh baris.
    await upsertSnapshotAsset("keg1", { id: "a1", condition: "Rusak Ringan" });
    const baris = mockSimpanan.assets.get("a1");
    expect(baris.condition).toBe("Rusak Ringan");   // perubahan masuk
    expect(baris.asset_name).toBe("Meja Rapat");    // yang lain SELAMAT
    expect(baris.location).toBe("Lt. 2");
    expect(baris.doc_total).toBe(5);
  });

  test("respons tulis tanpa field proyeksi list tidak menghapus nilainya", async () => {
    mockSimpanan.assets.set("a1", {
      id: "a1", activity_id: "keg1", asset_name: "Meja",
      doc_total: 4, doc_checked: 2, doc_summary: "2/4", siman: { beda: true },
    });
    // AssetResponse tak memuat doc_total/doc_checked/doc_summary/siman.
    await upsertSnapshotAsset("keg1", {
      id: "a1", asset_name: "Meja Kayu", version: 7,
    });
    const baris = mockSimpanan.assets.get("a1");
    expect(baris.asset_name).toBe("Meja Kayu");
    expect(baris.version).toBe(7);
    expect(baris.doc_total).toBe(4);                 // badge dokumen selamat
    expect(baris.siman).toEqual({ beda: true });     // badge SIMAN selamat
  });

  test("baris baru (belum ada di snapshot) tetap tertulis", async () => {
    await upsertSnapshotAsset("keg1", { id: "b2", asset_name: "Kursi", condition: "Baik" });
    expect(mockSimpanan.assets.get("b2").asset_name).toBe("Kursi");
  });

  test("tanpa meta kegiatan → tidak menulis apa pun (snapshot tak ada)", async () => {
    await upsertSnapshotAsset("keg-lain", { id: "c3", asset_name: "Lemari" });
    expect(mockSimpanan.assets.has("c3")).toBe(false);
  });

  test("field di luar proyeksi (foto besar) tetap disaring", async () => {
    await upsertSnapshotAsset("keg1", {
      id: "d4", asset_name: "Printer", photos: ["data:image/jpeg;base64,BESAR"],
    });
    const baris = mockSimpanan.assets.get("d4");
    expect(baris.asset_name).toBe("Printer");
    expect(baris.photos).toBeUndefined();            // blob tak boleh masuk snapshot
  });
});
