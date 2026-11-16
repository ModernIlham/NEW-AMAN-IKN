import { daftarPerluTindakan, jenisTindakan, labelAset } from "./perluTindakan";
import { summarizeSyncStatuses } from "./syncStatus";

const statuses = {
  a1: { status: "conflict", error: "Versi berbeda" },
  a2: { status: "failed", locked: true, error: "Kegiatan terkunci" },
  t3: { status: "failed", locked: true, error: "NUP sudah digunakan" },
  a4: { status: "failed", error: "Jaringan putus" },
  a5: { status: "queued" },
  a6: { status: "saved" },
};
const items = [
  { statusKey: "a1", isEdit: true, editId: "a1", payload: { condition: "Baik" }, state: { status: "conflict" }, queuedAt: "2026-11-16T02:00:00Z" },
  { statusKey: "a1", isEdit: true, editId: "a1", payload: { condition: "Rusak" }, state: { status: "ready" }, queuedAt: "2026-11-16T03:00:00Z" },
  { statusKey: "a2", isEdit: true, editId: "a2", payload: { activity_id: "kg-lain" }, state: { status: "locked" }, queuedAt: "2026-11-16T01:00:00Z", nama_kegiatan: "Inventarisasi 2025" },
  { statusKey: "t3", isEdit: false, tempId: "t3", payload: { activity_id: "kg1", asset_name: "Laptop", asset_code: "3100102001", NUP: 7 }, state: { status: "rejected" }, queuedAt: "2026-11-16T00:30:00Z" },
];

describe("jenisTindakan", () => {
  it("memetakan konflik, terkunci, ditolak; selain itu null", () => {
    expect(jenisTindakan(statuses.a1)).toBe("konflik");
    expect(jenisTindakan(statuses.a2, items[2])).toBe("terkunci");
    expect(jenisTindakan(statuses.t3, items[3])).toBe("ditolak");
    expect(jenisTindakan(statuses.a2)).toBe("ditolak"); // tanpa item: fallback aman
    expect(jenisTindakan(statuses.a4)).toBeNull();
    expect(jenisTindakan(statuses.a5)).toBeNull();
    expect(jenisTindakan(undefined)).toBeNull();
  });
});

describe("daftarPerluTindakan", () => {
  const cariAset = id => (id === "a1" ? { id: "a1", asset_name: "Kursi", asset_code: "3050104001", NUP: 2, activity_id: "kg1" } : undefined);
  const daftar = daftarPerluTindakan({ syncStatuses: statuses, items, activityId: "kg1", cariAset,
    adaMedia: p => "photo_ops" in p });

  it("jumlahnya SAMA dengan actionCount lencana", () => {
    expect(daftar).toHaveLength(summarizeSyncStatuses(statuses).actionCount);
  });

  it("kegiatan aktif dulu, lalu tertua; kegiatan lain di akhir", () => {
    expect(daftar.map(d => d.statusKey)).toEqual(["t3", "a1", "a2"]);
    expect(daftar[2].kegiatanLain).toBe(true);
    expect(daftar[2].namaKegiatan).toBe("Inventarisasi 2025");
  });

  it("memakai operasi TERTUA per baris & memperkaya dari baris termuat", () => {
    const a1 = daftar.find(d => d.statusKey === "a1");
    expect(a1).toMatchObject({ jenis: "konflik", nama: "Kursi", kode: "3050104001", nup: 2,
      kegiatanLain: false, bisaDibuka: true, pesan: "Versi berbeda" });
  });

  it("aset BARU tidak bisa dibuka di form edit; data dari payload", () => {
    const t3 = daftar.find(d => d.statusKey === "t3");
    expect(t3).toMatchObject({ jenis: "ditolak", bisaDibuka: false, nama: "Laptop", nup: 7, kegiatanLain: false });
  });

  it("kegiatan tak diketahui → null, bukan menebak", () => {
    const r = daftarPerluTindakan({ syncStatuses: { x: { status: "conflict" } },
      items: [{ statusKey: "x", isEdit: true, editId: "x", payload: { condition: "Baik" } }], activityId: "kg1" });
    expect(r[0].kegiatanLain).toBeNull();
  });

  it("aman untuk masukan kosong", () => {
    expect(daftarPerluTindakan()).toEqual([]);
    expect(daftarPerluTindakan({ syncStatuses: null, items: null })).toEqual([]);
  });

  it("menandai payload bermedia", () => {
    const r = daftarPerluTindakan({ syncStatuses: { x: { status: "conflict" } },
      items: [{ statusKey: "x", isEdit: true, editId: "x", payload: { photo_ops: [] } }], adaMedia: p => "photo_ops" in p });
    expect(r[0].adaMedia).toBe(true);
  });
});

describe("labelAset", () => {
  it("menyusun nama & kode", () => {
    expect(labelAset({ nama: "Kursi", kode: "305", nup: 2, isEdit: true })).toEqual({ nama: "Kursi", kode: "305 · NUP 2" });
    expect(labelAset({ nama: "", kode: "", nup: "", isEdit: false })).toEqual({ nama: "Aset baru", kode: "" });
  });
});
