// SCAN LURING HARUS KEMBALI KE RUANGANNYA SENDIRI (temuan audit adversarial).
//
// Ini uji atas KONTRAK antrean scan, bukan atas komponennya: setiap baris yang
// dititipkan wajib membawa node & waktu KEJADIANNYA, dan pengirim wajib
// memakai nilai itu — bukan konteks layar saat pengiriman ulang terjadi.
//
// Bug yang dijaganya: `kirim()` dulu menulis `node_id: node.id` (node dialog
// yang sedang dibuka). Petugas memindai 30 barang luring di Ruang 305, naik ke
// lantai atas, membuka Ruang 307, menekan "Kirim ulang" → ketiga puluh barang
// tercatat di Ruang 307. Antrean yang dibangun untuk melindungi data justru
// menjadi jalur data tertukar.
import {
  simpanTertunda, bacaTertunda, kosongkanAntrean,
} from "../antreanScan";

beforeEach(() => { kosongkanAntrean(); });

/**
 * Tiruan `kirim()` OpnameDialog sesudah perbaikan: node & waktu datang dari
 * PEMANGGIL. `nodeLayar` mewakili ruangan yang kebetulan sedang dibuka.
 */
function kirimTiruan(kode, scanId, assetId, nodeId, tsScan, nodeLayar) {
  return { kode, scan_id: scanId, asset_id: assetId || undefined,
           node_id: nodeId || nodeLayar,
           ts_scan: tsScan || "2026-07-27T10:00:00.000Z" };
}

describe("kontrak antrean scan luring", () => {
  test("baris tertunda menyimpan node & waktu kejadiannya", () => {
    simpanTertunda({ scan_id: "s1", kode: "3.05-12", node_id: "r305",
                     ts_scan: "2026-07-20T02:00:00.000Z" });
    const [b] = bacaTertunda();
    expect(b.node_id).toBe("r305");
    expect(b.ts_scan).toBe("2026-07-20T02:00:00.000Z");
  });

  test("kirim ulang memakai RUANGAN ASAL, bukan ruangan yang sedang dibuka", () => {
    simpanTertunda({ scan_id: "s1", kode: "A", node_id: "r305",
                     ts_scan: "2026-07-20T02:00:00.000Z" });
    simpanTertunda({ scan_id: "s2", kode: "B", node_id: "r305",
                     ts_scan: "2026-07-20T02:05:00.000Z" });
    // Petugas kini membuka Ruang 307 lalu menekan "Kirim ulang".
    const terkirim = bacaTertunda().map((it) =>
      kirimTiruan(it.kode, it.scan_id, it.asset_id, it.node_id, it.ts_scan, "r307"));
    expect(terkirim.map((m) => m.node_id)).toEqual(["r305", "r305"]);
    expect(terkirim.some((m) => m.node_id === "r307")).toBe(false);
  });

  test("kirim ulang mempertahankan waktu KEJADIAN, bukan waktu tiba", () => {
    // Bukti opname harus bertanggal hari barang benar-benar dilihat petugas,
    // bukan hari sinyal pulih.
    simpanTertunda({ scan_id: "s1", kode: "A", node_id: "r305",
                     ts_scan: "2026-07-20T02:00:00.000Z" });
    const [it] = bacaTertunda();
    const m = kirimTiruan(it.kode, it.scan_id, it.asset_id, it.node_id, it.ts_scan, "r307");
    expect(m.ts_scan).toBe("2026-07-20T02:00:00.000Z");
  });

  test("scan BARU tetap memakai ruangan yang sedang dibuka", () => {
    // Perbaikan tak boleh membalik perilaku normal: pindaian langsung memang
    // terjadi di ruangan yang terbuka di layar.
    const m = kirimTiruan("A", "s9", "", "", "", "r307");
    expect(m.node_id).toBe("r307");
  });

  test("baris dari ruangan berbeda tak saling tertukar dalam satu antrean", () => {
    simpanTertunda({ scan_id: "s1", kode: "A", node_id: "r305" });
    simpanTertunda({ scan_id: "s2", kode: "B", node_id: "gudang-1" });
    const peta = Object.fromEntries(
      bacaTertunda().map((it) => [it.scan_id, it.node_id]));
    expect(peta).toEqual({ s1: "r305", s2: "gudang-1" });
  });
});
