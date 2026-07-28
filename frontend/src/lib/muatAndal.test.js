import {
  JENIS, MAKS_PERCOBAAN, bolehUlang, jedaUlang, jenisGalat, muatAndal, pesanGalat,
} from "./muatAndal";

// Bentuk galat axios yang nyata, bukan karangan: inilah yang benar-benar
// sampai ke `catch` pada tiap keadaan.
const putus = () => Object.assign(new Error("Network Error"), { code: "ERR_NETWORK" });
const tenggat = () => Object.assign(new Error("timeout of 20000ms exceeded"),
                                    { code: "ECONNABORTED" });
const dibatalkan = () => Object.assign(new Error("canceled"), { code: "ERR_CANCELED" });
const status = (s, detail) => Object.assign(new Error(`Request failed ${s}`),
                                            { response: { status: s, data: { detail } } });

describe("jenisGalat — membedakan bentuk kegagalan", () => {
  test("tanpa respons = jaringan, bukan galat server", () => {
    expect(jenisGalat(putus())).toBe(JENIS.JARINGAN);
  });

  test("tenggat dikenali TERPISAH dari putus", () => {
    // Keduanya sama-sama tanpa `response`. Kalau tak dibedakan, operator
    // yang servernya lambat diberi tahu "periksa sinyal" — saran yang salah.
    expect(jenisGalat(tenggat())).toBe(JENIS.TENGGAT);
  });

  test("pembatalan sendiri bukan kegagalan jaringan", () => {
    expect(jenisGalat(dibatalkan())).toBe(JENIS.DIBATALKAN);
  });

  test("kode status dipetakan ke maknanya", () => {
    expect(jenisGalat(status(500))).toBe(JENIS.SERVER);
    expect(jenisGalat(status(503))).toBe(JENIS.SERVER);
    expect(jenisGalat(status(429))).toBe(JENIS.SIBUK);
    expect(jenisGalat(status(401))).toBe(JENIS.IZIN);
    expect(jenisGalat(status(403))).toBe(JENIS.IZIN);
    expect(jenisGalat(status(404))).toBe(JENIS.PERMINTAAN);
    expect(jenisGalat(status(400))).toBe(JENIS.PERMINTAAN);
  });
});

describe("bolehUlang — hanya kegagalan sementara", () => {
  test("yang sementara diulang", () => {
    [putus(), tenggat(), status(500), status(429)].forEach((e) =>
      expect(bolehUlang(e)).toBe(true));
  });

  test("yang permanen TIDAK diulang", () => {
    // Mengulang 404/400 hanya membuang kuota data operator dan menunda
    // pesan galat; mengulang 401 menunda logout yang seharusnya terjadi.
    [status(404), status(400), status(401), status(403), dibatalkan()].forEach((e) =>
      expect(bolehUlang(e)).toBe(false));
  });
});

describe("jedaUlang — backoff ber-jitter", () => {
  test("naik eksponensial dan berplafon", () => {
    const nol = () => 0;
    expect(jedaUlang(1, nol)).toBe(800);
    expect(jedaUlang(2, nol)).toBe(1600);
    expect(jedaUlang(3, nol)).toBe(3200);
    expect(jedaUlang(99, nol)).toBe(8000);      // plafon, tidak meledak
  });

  test("jitter membuat dua perangkat tidak serentak", () => {
    // Saat sinyal pulih di satu lokasi, seluruh regu mencoba ulang pada detik
    // yang sama. Tanpa jitter mereka menghantam server berbarengan.
    expect(jedaUlang(1, () => 0)).not.toBe(jedaUlang(1, () => 0.99));
  });
});

describe("pesanGalat — memberi tahu apa yang terjadi", () => {
  test("tiap bentuk kegagalan punya saran yang berbeda dan benar", () => {
    expect(pesanGalat(putus(), "Gagal memuat node")).toMatch(/sinyal/i);
    expect(pesanGalat(tenggat(), "Gagal memuat node")).toMatch(/tidak menjawab tepat waktu/i);
    expect(pesanGalat(status(429), "Gagal memuat node")).toMatch(/tunggu/i);
    expect(pesanGalat(status(401), "Gagal memuat node")).toMatch(/sesi/i);
  });

  test("detail dari server dipakai bila ada", () => {
    expect(pesanGalat(status(400, "Kode satker wajib diisi"))).toBe("Kode satker wajib diisi");
  });

  test("pesan selalu menyebut konteksnya, bukan 'terjadi kesalahan'", () => {
    expect(pesanGalat(putus(), "Gagal memuat hierarki spasial"))
      .toMatch(/^Gagal memuat hierarki spasial/);
  });
});

describe("muatAndal — orkestrasi coba-ulang", () => {
  const tanpaTidur = { tidur: () => Promise.resolve(), acak: () => 0 };

  test("berhasil di percobaan pertama = satu panggilan saja", async () => {
    const kerja = jest.fn().mockResolvedValue("ok");
    await expect(muatAndal(kerja, tanpaTidur)).resolves.toBe("ok");
    expect(kerja).toHaveBeenCalledTimes(1);
  });

  test("satu kedip jaringan tidak lagi terlihat sebagai kegagalan", async () => {
    // INI INTI PERBAIKANNYA. Sebelumnya satu kedip = layar kosong dan operator
    // harus keluar-masuk halaman.
    const kerja = jest.fn()
      .mockRejectedValueOnce(putus())
      .mockResolvedValue({ items: [1, 2] });
    await expect(muatAndal(kerja, tanpaTidur)).resolves.toEqual({ items: [1, 2] });
    expect(kerja).toHaveBeenCalledTimes(2);
  });

  test("menyerah setelah MAKS_PERCOBAAN dan melempar galat ASLI", async () => {
    // Galat asli, bukan bungkusan: pemanggil masih memeriksa err.response.
    const kerja = jest.fn().mockRejectedValue(status(500));
    await expect(muatAndal(kerja, tanpaTidur)).rejects.toMatchObject(
      { response: { status: 500 } });
    expect(kerja).toHaveBeenCalledTimes(MAKS_PERCOBAAN);
  });

  test("galat permanen gagal SEKETIKA, tidak menunggu tiga putaran", async () => {
    const kerja = jest.fn().mockRejectedValue(status(404));
    await expect(muatAndal(kerja, tanpaTidur)).rejects.toBeTruthy();
    expect(kerja).toHaveBeenCalledTimes(1);
  });

  test("pembatalan tidak dihidupkan kembali", async () => {
    // Dibatalkan = keputusan KITA (unmount / ganti node). Mengulanginya
    // menghidupkan permintaan yang sengaja dimatikan — dan pada layar denah
    // itu berarti node lama menimpa node yang baru dibuka.
    const kerja = jest.fn().mockRejectedValue(dibatalkan());
    await expect(muatAndal(kerja, tanpaTidur)).rejects.toBeTruthy();
    expect(kerja).toHaveBeenCalledTimes(1);
  });

  test("benar-benar MENUNGGU di antara percobaan", async () => {
    // Tanpa jeda, tiga percobaan terjadi dalam milidetik yang sama dan
    // ketiganya menemui jaringan yang masih putus — coba-ulang jadi teater.
    const jeda = [];
    const kerja = jest.fn()
      .mockRejectedValueOnce(putus())
      .mockRejectedValueOnce(putus())
      .mockResolvedValue("ok");
    await muatAndal(kerja, { tidur: (ms) => { jeda.push(ms); return Promise.resolve(); },
                             acak: () => 0 });
    expect(jeda).toEqual([800, 1600]);
  });

  test("memberi tahu layar bahwa ia sedang mencoba lagi", async () => {
    const kabar = [];
    const kerja = jest.fn().mockRejectedValueOnce(putus()).mockResolvedValue("ok");
    await muatAndal(kerja, { ...tanpaTidur, padaUlang: (n) => kabar.push(n) });
    expect(kabar).toEqual([1]);
  });

  test("nomor percobaan diteruskan ke kerja", async () => {
    const dilihat = [];
    const kerja = jest.fn((n) => {
      dilihat.push(n);
      return n < 3 ? Promise.reject(putus()) : Promise.resolve("ok");
    });
    await muatAndal(kerja, tanpaTidur);
    expect(dilihat).toEqual([1, 2, 3]);
  });
});
