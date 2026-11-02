// Uji BACA-GABUNG-TULIS upsertSnapshotAsset — akar TIGA temuan audit G3:
// potongan PATCH menimpa seluruh baris, respons tulis menghapus field turunan
// proyeksi list, dan baris yang tak ketemu di daftar state menjadi stub.
//
// `idb` dimock dengan penyimpan in-memory sederhana: yang diuji adalah logika
// gabung, bukan IndexedDB-nya.

const mockSimpanan = { meta: new Map(), assets: new Map(), assetReads: 0, keyReads: 0 };

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
    getAllKeysFromIndex: async (_store, _index, activityId) => {
      mockSimpanan.keyReads++;
      return [...mockSimpanan.assets.values()].filter(r => r.activity_id === activityId).map(r => r.id);
    },
    transaction: store => ({
      store: store === "meta" ? {
        get: async key => mockSimpanan.meta.get(key),
        put: async meta => mockSimpanan.meta.set(meta.activityId, meta),
      } : {
        get: async id => { mockSimpanan.assetReads++; return mockSimpanan.assets.get(id); },
        delete: async id => mockSimpanan.assets.delete(id),
        put: async row => mockSimpanan.assets.set(row.id, row),
      },
      done: Promise.resolve(),
    }),
  }),
}));
// (openDB di atas: arrow yang MENGEMBALIKAN promise objek — dipanggil sebagai
// fungsi oleh getDB; bungkusnya fungsi polos agar selamat dari resetMocks.)

import { upsertSnapshotAsset, removeSnapshotAsset, getSnapshotPage, syncSnapshot } from "./offlineSnapshot";
import axios from "axios";

beforeEach(() => {
  mockSimpanan.assetReads = 0; mockSimpanan.keyReads = 0;
  mockSimpanan.meta.clear();
  mockSimpanan.assets.clear();
  mockSimpanan.meta.set("keg1", { activityId: "keg1", lastSync: Date.now() });
});

describe("upsertSnapshotAsset — baca-gabung-tulis", () => {
  test("jenis dokumen pengadaan bertahan saat PATCH luring parsial", async () => {
    await upsertSnapshotAsset("keg1", { id: "pengadaan", version: 1,
      jenis_dokumen_pengadaan: "Non Kontrak BLU", nomor_kontrak: "K-arsip" });
    await upsertSnapshotAsset("keg1", { id: "pengadaan", version: 2, notes: "Diperiksa" });
    expect(mockSimpanan.assets.get("pengadaan")).toMatchObject({
      jenis_dokumen_pengadaan: "Non Kontrak BLU", nomor_kontrak: "K-arsip", notes: "Diperiksa",
    });
  });
  test("nilai barang bersejarah dan pengosongan tersimpan pada snapshot", async () => {
    await upsertSnapshotAsset("keg1", { id: "sejarah", version: 1, barang_bersejarah: "Ya" });
    expect(mockSimpanan.assets.get("sejarah").barang_bersejarah).toBe("Ya");
    await upsertSnapshotAsset("keg1", { id: "sejarah", version: 2, barang_bersejarah: "" });
    expect(mockSimpanan.assets.get("sejarah").barang_bersejarah).toBe("");
  });
  test("referensi BAST terapan tersimpan dan tidak mundur setelah revisi", async () => {
    await upsertSnapshotAsset("keg1", { id: "a1", version: 4, bast_terakhir: { id: "lama" }, amanah_bast: { bast_id: "lama" } });
    await upsertSnapshotAsset("keg1", { id: "a1", version: 5, bast_terakhir: { id: "baru" }, amanah_bast: { bast_id: "baru" } });
    await upsertSnapshotAsset("keg1", { id: "a1", version: 4, amanah_bast: { bast_id: "lama" } });
    expect(mockSimpanan.assets.get("a1")).toMatchObject({ bast_terakhir: { id: "baru" }, amanah_bast: { bast_id: "baru" } });
  });
  test("respons versi lama tidak memundurkan snapshot hasil simpan terbaru", async () => {
    await upsertSnapshotAsset("keg1", { id: "a1", version: 8, asset_name: "Baru" });
    await upsertSnapshotAsset("keg1", { id: "a1", version: 7, asset_name: "Lama" });
    expect(mockSimpanan.assets.get("a1")).toMatchObject({ version: 8, asset_name: "Baru" });
  });
  test("desain marker tersimpan offline dan tidak hilang oleh patch field lain", async () => {
    const marker_pin = '{"v":1,"mode":"text","text":"A1"}';
    await upsertSnapshotAsset("keg1", { id: "a1", marker_pin });
    await upsertSnapshotAsset("keg1", { id: "a1", location: "Ruang" });
    expect(mockSimpanan.assets.get("a1").marker_pin).toBe(marker_pin);
    await upsertSnapshotAsset("keg1", { id: "a1", marker_pin: "" });
    expect(mockSimpanan.assets.get("a1").marker_pin).toBe("");
  });
  test("ringkasan denah masuk cache dan pencabutan membersihkan penempatan sebelumnya", async () => {
    await upsertSnapshotAsset("keg1", { id: "a1", location: "Manual", di_denah: true,
      denah_nama: "Ruang", denah_jalur: "Gedung / Ruang", denah_titik: [116.9, -1.5] });
    expect(mockSimpanan.assets.get("a1").denah_jalur).toBe("Gedung / Ruang");
    await upsertSnapshotAsset("keg1", { id: "a1", di_denah: false,
      denah_nama: "", denah_jalur: "", denah_titik: null });
    const baris = mockSimpanan.assets.get("a1");
    expect(baris.location).toBe("Manual");
    expect(baris.denah_titik).toBeNull();
    expect(baris.denah_jalur).toBe("");
  });

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

  test("proyeksi otoritatif null membersihkan badge SIMAN dan PSP lama di cache", async () => {
    mockSimpanan.assets.set("a1", {
      id: "a1", activity_id: "keg1", version: 7, asset_name: "Meja",
      siman: { status: "selisih", import_id: "import-satker-lama" },
      psp: { no_psp: "SK-SATKER-LAMA" }, doc_total: 4,
    });

    await upsertSnapshotAsset("keg1", { id: "a1", version: 8, siman: null, psp: null });

    expect(mockSimpanan.assets.get("a1")).toMatchObject({
      id: "a1", version: 8, asset_name: "Meja", doc_total: 4,
      siman: null, psp: null,
    });
  });

  test("patch tanpa proyeksi SIMAN atau PSP mempertahankan kedua badge yang tersimpan", async () => {
    const siman = { status: "cocok", import_id: "import-satker-aktif" };
    const psp = { no_psp: "SK-SATKER-AKTIF" };
    mockSimpanan.assets.set("a1", {
      id: "a1", activity_id: "keg1", version: 7, asset_name: "Meja", siman, psp,
    });

    await upsertSnapshotAsset("keg1", { id: "a1", version: 8, asset_name: "Meja Kayu" });

    expect(mockSimpanan.assets.get("a1")).toMatchObject({
      version: 8, asset_name: "Meja Kayu", siman, psp,
    });
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


test("paged IDB: halaman berikutnya membaca hanya halaman, upsert/delete/fullsync menginvalidasi index", async () => {
  const activityId = "query-cache";
  mockSimpanan.meta.set(activityId, { activityId, userId: "u", lastSync: new Date().toISOString(), revision: 1 });
  for (let i = 0; i < 1000; i++) {
    mockSimpanan.assets.set(`q-${i}`, { id: `q-${i}`, activity_id: activityId, purchase_price: String(i), thumbnail: "data:image/jpeg;base64,thumbnail" });
  }
  const first = await getSnapshotPage(activityId, { ownerId: "u", sort: "price_asc" });
  expect(first.total).toBe(1000); expect(first.items[0].id).toBe("q-0");
  const reads = mockSimpanan.assetReads;
  const second = await getSnapshotPage(activityId, { ownerId: "u", sort: "price_asc", page: 2 });
  expect(second.timing.scanned).toBe(0); expect(mockSimpanan.assetReads - reads).toBe(50);
  expect(mockSimpanan.keyReads).toBe(1);
  await upsertSnapshotAsset(activityId, { id: "q-999", purchase_price: "-1" });
  const changed = await getSnapshotPage(activityId, { ownerId: "u", sort: "price_asc" });
  expect(changed.items[0].id).toBe("q-999"); expect(mockSimpanan.keyReads).toBe(2);
  await removeSnapshotAsset(activityId, "q-999");
  expect((await getSnapshotPage(activityId, { ownerId: "u" })).total).toBe(999);
  expect(await getSnapshotPage(activityId, { ownerId: "other" })).toBeNull();
  axios.get.mockResolvedValue({ data: { items: [{ id: "only", activity_id: activityId, asset_name: "Hasil full sync" }], total: 1,
    server_time: new Date().toISOString() } });
  await syncSnapshot(activityId, "u", undefined, { forceFull: true });
  const afterFull = await getSnapshotPage(activityId, { ownerId: "u" });
  expect(afterFull.total).toBe(1); expect(afterFull.items.map(r => r.id)).toEqual(["only"]);
});

test("proyeksi v2 menarik penuh badge terverifikasi meski versi aset tetap, lalu kembali delta", async () => {
  const activityId = "projection-upgrade";
  const oldCursor = new Date(Date.now() - 60000).toISOString();
  const firstCursor = new Date().toISOString();
  const original = {
    id: "unchanged", activity_id: activityId, version: 7, updated_at: oldCursor,
    asset_name: "Laptop lapangan", NUP: "1", marker_pin: "pin asli", location: "Ruang A",
    thumbnail: "data:image/png;base64,thumbnail", doc_total: 4, doc_checked: 2,
    siman: { status: "cocok", import_id: "impor-lama" }, psp: { no_psp: "PSP-LAMA" },
  };
  mockSimpanan.meta.set(activityId, {
    activityId, userId: "u", versiProyeksi: 2, lastSync: oldCursor, disegarkanPada: firstCursor,
  });
  mockSimpanan.assets.set(original.id, original);
  const otherActivity = { id: "other", activity_id: "kegiatan-lain", asset_name: "Cache kegiatan lain" };
  mockSimpanan.assets.set(otherActivity.id, otherActivity);
  axios.get.mockResolvedValueOnce({ data: {
    items: [{ id: original.id, activity_id: activityId, version: 7, updated_at: oldCursor,
      siman: null, psp: null }], total: 1, server_time: firstCursor,
  } });

  await syncSnapshot(activityId, "u");

  expect(new URL(axios.get.mock.calls[0][0], "http://localhost").searchParams.has("since")).toBe(false);
  expect(mockSimpanan.assets.get(original.id)).toEqual({ ...original, siman: null, psp: null });
  expect(mockSimpanan.assets.get(otherActivity.id)).toEqual(otherActivity);
  expect(mockSimpanan.meta.get(activityId)).toMatchObject({ versiProyeksi: 3, lastSync: firstCursor });

  axios.get.mockResolvedValueOnce({ data: { items: [], total: 1, server_time: firstCursor } });
  await syncSnapshot(activityId, "u");
  expect(new URL(axios.get.mock.calls[1][0], "http://localhost").searchParams.get("since")).toBe(firstCursor);
  expect(mockSimpanan.assets.get(original.id)).toEqual({ ...original, siman: null, psp: null });
});
