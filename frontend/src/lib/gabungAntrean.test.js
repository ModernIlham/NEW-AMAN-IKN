import { tertundaUntukEnqueue, tertundaUntukKegagalan } from "./gabungAntrean";

// Audit adversarial: SELURUH perkabelan integritas antrean yang ditambahkan
// PR #642/#643 tak tersentuh uji apa pun — berkas bernama
// `useOptimisticQueue.test.js` bahkan tak mengimpor hook-nya. Aturannya kini
// dipisah ke sini supaya bisa dijebak dengan benar.

const PATCH = { isEdit: true, usePatch: true, editId: "a1" };
const simpanan = (antreanId, extra = {}) => ({
  ...PATCH, antreanId, payload: { photo_ops: { keep: [0], add: ["A"] } },
  ...extra,
});

describe("tertundaUntukEnqueue", () => {
  test("simpanan tertunda atas aset yang sama digabung", () => {
    const failed = { a1: simpanan("q1") };
    expect(tertundaUntukEnqueue(failed, "a1", PATCH, false)).toBe(failed.a1);
  });

  test("TIDAK digabung saat simpanan lama masih TERBANG", () => {
    // Kalau yang lama ternyata sampai ke server, menggabung isinya ke simpanan
    // kedua berarti `photo_ops.add` diterapkan DUA KALI — foto kembar.
    const failed = { a1: simpanan("q1") };
    expect(tertundaUntukEnqueue(failed, "a1", PATCH, true)).toBeNull();
  });

  test("aset lain tak ikut tergabung", () => {
    const failed = { a1: simpanan("q1") };
    expect(tertundaUntukEnqueue(failed, "a2", PATCH, false)).toBeNull();
  });

  test("PUT (dokumen utuh) tak digabung", () => {
    // PUT sudah membawa segalanya; menggabungnya bisa menghidupkan kembali
    // field yang sengaja dikosongkan pengguna.
    const failed = { a1: simpanan("q1", { usePatch: false }) };
    expect(tertundaUntukEnqueue(failed, "a1", PATCH, false)).toBeNull();
  });

  test("tak ada yang tertunda → null", () => {
    expect(tertundaUntukEnqueue({}, "a1", PATCH, false)).toBeNull();
    expect(tertundaUntukEnqueue(undefined, "a1", PATCH, false)).toBeNull();
  });
});

describe("tertundaUntukKegagalan", () => {
  test("dua simpanan BERBEDA yang sama-sama gagal digabung", () => {
    // Di sini yang lama TERBUKTI belum diterapkan (ia ada di daftar gagal),
    // sehingga penggabungan aman DAN wajib: keduanya berebut satu statusKey,
    // dan tanpa digabung yang belakangan menghapus foto yang pertama.
    const lama = simpanan("q1");
    expect(tertundaUntukKegagalan(lama, simpanan("q2"))).toBe(lama);
  });

  test("percobaan ulang simpanan yang SAMA tidak digabung dengan dirinya", () => {
    // antreanId identik = ini muatan yang itu-itu juga; menggabungnya
    // menambahkan `photo_ops.add` dua kali ke muatan yang sama.
    const lama = simpanan("q1");
    expect(tertundaUntukKegagalan(lama, simpanan("q1"))).toBeNull();
  });

  test("PUT tak digabung walau keduanya gagal", () => {
    expect(tertundaUntukKegagalan(simpanan("q1", { usePatch: false }),
                                  simpanan("q2"))).toBeNull();
  });

  test("aset berbeda tak digabung", () => {
    expect(tertundaUntukKegagalan(simpanan("q1"),
                                  simpanan("q2", { editId: "a2" }))).toBeNull();
  });

  test("masukan kosong tak meledak", () => {
    expect(tertundaUntukKegagalan(null, simpanan("q2"))).toBeNull();
    expect(tertundaUntukKegagalan(simpanan("q1"), null)).toBeNull();
  });
});
