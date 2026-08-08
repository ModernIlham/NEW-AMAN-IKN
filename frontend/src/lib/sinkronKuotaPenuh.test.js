/* eslint-env jest */
/**
 * KURSOR DELTA vs KESEGARAN — temuan C20 tinjauan sistem 2026-08.
 *
 * Ceritanya begini. Petugas menyalakan mode inventarisasi di HP yang tinggal
 * sedikit ruang. Sinkron menarik halaman demi halaman, lalu di halaman ketiga
 * IndexedDB menolak menulis: kuota habis. Kodenya berhenti dengan anggun —
 * cache sebagian tetap dilayani, aplikasinya tidak crash, dan pengguna diberi
 * toast "kosongkan ruang lalu sinkron ulang".
 *
 * Yang RUSAK adalah nasihat di toast itu. `lastSync` terlanjur ditulis dari
 * `server_time` halaman PERTAMA, jadi "sinkron ulang" berangkat sebagai DELTA
 * dari titik itu — dan baris yang belum sempat ditarik punya `updated_at`
 * lebih tua, sehingga tak pernah ikut lagi. Lubangnya menetap sampai TTL 7
 * hari, dan tak ada satu pun layar yang bisa menunjukkannya.
 *
 * Berkas ini mengurung dua sifat yang menutup celah itu:
 *   1. Kursor delta HANYA maju saat seluruh halaman berhasil ditulis.
 *   2. Cache sebagiannya TETAP dilayani — kesegaran dibaca dari stempel
 *      terpisah, bukan dari kursor yang sengaja kita bekukan.
 *
 * Sifat kedua bukan hiasan: tanpa stempel terpisah, memperbaiki (1) akan
 * membuat snapshot parsial langsung dianggap kedaluwarsa — persis cache yang
 * tadi susah payah dipertahankan.
 */

// ——— Penyimpan in-memory yang bisa disuruh kehabisan kuota ———
const mockSimpanan = {
  meta: new Map(),
  assets: new Map(),
  // Setelah sekian kali `tx.store.put`, tulisan berikutnya melempar
  // QuotaExceededError — meniru perangkat yang penuh di tengah jalan.
  putSebelumPenuh: Infinity,
  putTerjadi: 0,
};

const mockHalaman = [];
let mockAmbil = 0;

jest.mock("axios", () => ({
  get: (...a) => globalThis.__ambilHalaman(...a),
}));

// Fungsi POLOS, bukan jest.fn(): CRA menyetel resetMocks:true dan akan
// membuang implementasinya sebelum tiap uji (pola sama dgn offlineSnapshot.test).
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
    getAllKeysFromIndex: async (_store, _index, activityId) =>
      [...mockSimpanan.assets.values()]
        .filter((r) => r.activity_id === activityId)
        .map((r) => r.id),
    transaction: () => {
      const tertunda = [];
      return {
        store: {
          put: (row) => {
            mockSimpanan.putTerjadi += 1;
            if (mockSimpanan.putTerjadi > mockSimpanan.putSebelumPenuh) {
              const e = new Error("penyimpanan penuh");
              e.name = "QuotaExceededError";
              throw e;
            }
            tertunda.push(row);
          },
          delete: (id) => { mockSimpanan.assets.delete(id); },
        },
        // `await tx.done` dipakai kode produksi; barulah barisnya mengendap.
        get done() {
          for (const r of tertunda) mockSimpanan.assets.set(r.id, r);
          return Promise.resolve();
        },
      };
    },
  }),
}));

import { syncSnapshot, snapshotMeta, isSnapshotExpired, SNAPSHOT_TTL_MS } from "./offlineSnapshot";

/** Satu halaman jawaban /assets/offline-snapshot. */
function halaman({ ids, serverTime, nextCursor = "", total }) {
  return {
    data: {
      items: ids.map((id) => ({
        id, activity_id: "keg1", asset_name: `Aset ${id}`,
        updated_at: "2026-08-01T00:00:00Z",
      })),
      deleted_ids: [], requires_full_refresh: false,
      next_cursor: nextCursor, server_time: serverTime, total,
    },
  };
}

beforeEach(() => {
  mockSimpanan.meta.clear();
  mockSimpanan.assets.clear();
  mockSimpanan.putSebelumPenuh = Infinity;
  mockSimpanan.putTerjadi = 0;
  mockHalaman.length = 0;
  mockAmbil = 0;
  globalThis.__ambilHalaman = async () => {
    const h = mockHalaman[mockAmbil];
    mockAmbil += 1;
    return h ?? halaman({ ids: [], serverTime: "2026-08-08T00:00:00Z", total: 0 });
  };
});

// PAGE_LIMIT produksi = 1000. Halaman "penuh" tak praktis dibuat di uji, jadi
// kelanjutan halaman dikendalikan lewat `next_cursor`… yang HANYA dibaca bila
// `items.length >= PAGE_LIMIT`. Karena itu multi-halaman disimulasikan dengan
// satu halaman besar yang kuotanya habis di tengah — cukup untuk sifat yang
// diuji: putusnya penulisan, bukan mekanisme pagingnya.
describe("kursor delta berhenti saat kuota perangkat penuh", () => {
  test("sinkron MULUS: kursor maju ke server_time halaman pertama", async () => {
    mockHalaman.push(halaman({
      ids: ["a1", "a2", "a3"], serverTime: "2026-08-08T10:00:00Z", total: 3,
    }));
    const hasil = await syncSnapshot("keg1", "u1");
    expect(hasil.partial).toBe(false);
    expect(hasil.count).toBe(3);
    expect((await snapshotMeta("keg1")).lastSync).toBe("2026-08-08T10:00:00Z");
  });

  test("kuota penuh di tengah: kursor TIDAK maju — tetap kursor lama", async () => {
    // Sinkron sebelumnya sudah menetapkan kursor ini.
    mockSimpanan.meta.set("keg1", {
      activityId: "keg1", userId: "u1", count: 1,
      lastSync: "2026-08-01T00:00:00Z",
      disegarkanPada: new Date().toISOString(),
    });
    mockSimpanan.putSebelumPenuh = 0; // tulisan pertama pun ditolak
    mockHalaman.push(halaman({
      ids: ["b1", "b2"], serverTime: "2026-08-08T10:00:00Z", total: 2,
    }));

    const hasil = await syncSnapshot("keg1", "u1");
    expect(hasil.partial).toBe(true);
    // INI inti temuannya: kursor 08-08 akan membuat b1/b2 (updated_at 08-01)
    // tak pernah ikut delta berikutnya. Ia harus tetap di 08-01.
    expect((await snapshotMeta("keg1")).lastSync).toBe("2026-08-01T00:00:00Z");
    expect(hasil.lastSync).toBe("2026-08-01T00:00:00Z");
  });

  test("kuota penuh pada sinkron PENUH pertama: kursor kosong → sinkron berikutnya full", async () => {
    mockSimpanan.putSebelumPenuh = 0;
    mockHalaman.push(halaman({
      ids: ["c1"], serverTime: "2026-08-08T10:00:00Z", total: 1,
    }));

    const hasil = await syncSnapshot("keg1", "u1");
    expect(hasil.partial).toBe(true);
    // Kosong, BUKAN 08-08: `since` kosong berarti sinkron berikutnya full.
    // Kalau di sini terisi, kegiatan itu tak akan pernah punya cache lengkap.
    expect((await snapshotMeta("keg1")).lastSync).toBe("");
  });

  test("cache sebagian TETAP dilayani — kesegaran bukan dari kursor beku", async () => {
    // Kursor lama sengaja dibuat jauh melewati TTL. Bila kesegaran dibaca dari
    // kursor, snapshot parsial ini langsung dianggap kedaluwarsa dan tak
    // dilayani sama sekali — perbaikan kursornya justru merugikan pengguna.
    const jadul = new Date(Date.now() - SNAPSHOT_TTL_MS - 60_000).toISOString();
    mockSimpanan.meta.set("keg1", {
      activityId: "keg1", userId: "u1", count: 1, lastSync: jadul, disegarkanPada: jadul,
    });
    mockSimpanan.putSebelumPenuh = 1; // satu baris masuk, sisanya ditolak
    mockHalaman.push(halaman({
      ids: ["d1", "d2"], serverTime: "2026-08-08T10:00:00Z", total: 2,
    }));

    await syncSnapshot("keg1", "u1");
    const meta = await snapshotMeta("keg1");
    expect(meta.lastSync).toBe(jadul);          // kursor tetap beku
    expect(isSnapshotExpired(meta)).toBe(false); // tapi cache-nya masih hidup
  });

  test("rekaman LAMA tanpa `disegarkanPada` masih dinilai dari lastSync", async () => {
    // Kompatibilitas mundur: snapshot yang ditulis versi sebelum perbaikan ini.
    const jadul = new Date(Date.now() - SNAPSHOT_TTL_MS - 60_000).toISOString();
    expect(isSnapshotExpired({ activityId: "keg1", lastSync: jadul })).toBe(true);
    expect(isSnapshotExpired({ activityId: "keg1", lastSync: new Date().toISOString() })).toBe(false);
  });
});
