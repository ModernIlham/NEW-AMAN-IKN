import { gabungPatch, gabungPhotoOps, bolehGabung } from "./gabungPatch";

// Skenario lapangan yang menjadi alasan berkas ini ada:
// surveyor luring menambah FOTO ke aset A → gagal kirim → lalu menggeser pin
// aset A di peta. Dulu simpanan kedua menimpa yang pertama dan fotonya lenyap
// tanpa satu pesan pun. Uji di bawah menjaga agar itu tak terulang.

describe("gabungPatch", () => {
  test("FOTO dari simpanan pertama selamat saat simpanan kedua hanya koordinat", () => {
    const tambahFoto = { photo_ops: { keep: [0, 1], add: ["data:image/jpeg;base64,AAA"], thumbnail_index: 0 } };
    const geserPin = { koordinat_latitude: "-1.400000", koordinat_longitude: "116.700000" };
    const hasil = gabungPatch(tambahFoto, geserPin);
    expect(hasil.photo_ops.add).toEqual(["data:image/jpeg;base64,AAA"]);
    expect(hasil.koordinat_latitude).toBe("-1.400000");
  });

  test("kehendak terakhir menang untuk field yang sama", () => {
    expect(gabungPatch({ condition: "Baik" }, { condition: "Rusak Ringan" }).condition)
      .toBe("Rusak Ringan");
  });

  test("field yang hanya ada di simpanan lama tetap terbawa", () => {
    const hasil = gabungPatch({ asset_name: "Meja", notes: "catatan" }, { condition: "Baik" });
    expect(hasil).toEqual({ asset_name: "Meja", notes: "catatan", condition: "Baik" });
  });

  test("masukan kosong / tak sah tidak meledak", () => {
    expect(gabungPatch(null, { a: 1 })).toEqual({ a: 1 });
    expect(gabungPatch({ a: 1 }, null)).toEqual({ a: 1 });
    expect(gabungPatch(undefined, undefined)).toBe(undefined);
  });

  test("tidak memutasi masukan — pemanggil masih boleh memakai objek aslinya", () => {
    const lama = { photo_ops: { keep: [0], add: ["A"] }, notes: "x" };
    const baru = { photo_ops: { keep: [], add: ["B"] } };
    const salinanLama = JSON.parse(JSON.stringify(lama));
    gabungPatch(lama, baru);
    expect(lama).toEqual(salinanLama);
  });
});

describe("gabungPhotoOps", () => {
  test("foto baru dari KEDUA simpanan selamat", () => {
    // Tak satu pun sudah diterapkan ke server, jadi keduanya benar-benar foto
    // yang belum pernah ada di sana. Kehilangan salah satunya = kehilangan
    // bukti lapangan.
    const r = gabungPhotoOps({ keep: [0], add: ["A"] }, { keep: [0], add: ["B"] });
    expect(r.add).toEqual(["A", "B"]);
  });

  test("keep mengikuti yang TERBARU — keadaan server belum bergeser", () => {
    // Patch kedua dihitung terhadap keadaan server yang sama persis (patch
    // pertama belum diterapkan), jadi keputusan terakhir soal foto lama-lah
    // yang berlaku.
    const r = gabungPhotoOps({ keep: [0, 1, 2], add: [] }, { keep: [0, 2], add: [] });
    expect(r.keep).toEqual([0, 2]);
  });

  test("sampul pilihan lama dipertahankan bila patch baru tak menyebutkannya", () => {
    const r = gabungPhotoOps({ keep: [0], add: [], thumbnail_index: 2 }, { keep: [0], add: [] });
    expect(r.thumbnail_index).toBe(2);
  });

  test("sampul 0 yang DISENGAJA tidak dianggap kosong", () => {
    // Jebakan klasik `||`: indeks 0 itu sah, bukan "tidak diisi".
    const r = gabungPhotoOps({ keep: [0], add: [], thumbnail_index: 3 }, { keep: [0], add: [], thumbnail_index: 0 });
    expect(r.thumbnail_index).toBe(0);
  });

  test("salah satu sisi kosong → pakai yang ada", () => {
    expect(gabungPhotoOps(null, { keep: [1], add: ["B"] })).toEqual({ keep: [1], add: ["B"] });
    expect(gabungPhotoOps({ keep: [1], add: ["A"] }, null)).toEqual({ keep: [1], add: ["A"] });
  });

  test("base_version ikut terbawa — patch gabungan tetap terikat versinya", () => {
    // Kedua patch dihitung terhadap keadaan server yang sama; ikatan versi
    // milik yang LAMA yang dipertahankan (selaras If-Match patch gabungan).
    const r = gabungPhotoOps(
      { keep: [0], add: ["A"], base_version: 4 },
      { keep: [0], add: ["B"], base_version: 4 }
    );
    expect(r.base_version).toBe(4);
    // Patch baru tanpa ikatan (payload lama) → ikatan lama tetap dipakai.
    const r2 = gabungPhotoOps({ keep: [0], add: [], base_version: 4 }, { keep: [0], add: [] });
    expect(r2.base_version).toBe(4);
  });
});

describe("bolehGabung", () => {
  const patchA = { isEdit: true, usePatch: true, editId: "a1" };

  test("dua PATCH atas aset yang sama → boleh", () => {
    expect(bolehGabung(patchA, { ...patchA })).toBe(true);
  });

  test("aset berbeda → JANGAN gabung", () => {
    expect(bolehGabung(patchA, { ...patchA, editId: "a2" })).toBe(false);
  });

  test("PUT (dokumen utuh) → JANGAN gabung", () => {
    // PUT sudah membawa segalanya; menggabungnya justru bisa menghidupkan
    // kembali field yang sengaja dikosongkan pengguna.
    expect(bolehGabung({ ...patchA, usePatch: false }, patchA)).toBe(false);
    expect(bolehGabung(patchA, { ...patchA, usePatch: false })).toBe(false);
  });

  test("CREATE → JANGAN gabung (aset yang berbeda sama sekali)", () => {
    expect(bolehGabung({ isEdit: false, usePatch: false }, patchA)).toBe(false);
  });

  test("masukan kosong → JANGAN gabung", () => {
    expect(bolehGabung(null, patchA)).toBe(false);
    expect(bolehGabung(patchA, undefined)).toBe(false);
  });
});
