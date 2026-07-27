import { buatTempId, apakahTempId } from "./idAntrean";

// Yang diuji di sini BUKAN "id-nya berupa string", melainkan justru dua cara
// gagal yang dulu benar-benar bisa terjadi di lapangan: banyak simpanan dalam
// satu milidetik, dan jam HP yang MUNDUR di tengah survei luring.

describe("buatTempId", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  test("awalan temp_ dipertahankan — beberapa guard bergantung padanya", () => {
    expect(buatTempId().startsWith("temp_")).toBe(true);
    expect(apakahTempId(buatTempId())).toBe(true);
    expect(apakahTempId("a1b2c3")).toBe(false);
    expect(apakahTempId(null)).toBe(false);
  });

  test("1.000 id dalam SATU milidetik semuanya berbeda", () => {
    // Jam dibekukan: kalau keunikan masih bergantung pada Date.now(), seluruh
    // id akan identik dan Set-nya menyusut jadi 1.
    jest.spyOn(Date, "now").mockReturnValue(1_700_000_000_000);
    const ids = new Set();
    for (let i = 0; i < 1000; i++) ids.add(buatTempId());
    expect(ids.size).toBe(1000);
  });

  test("jam MUNDUR tidak menghasilkan id yang sudah dipakai", () => {
    // Skenario lapangan: survei luring berjam-jam, HP menyinkronkan waktu ke
    // jaringan dan mengoreksi jam ke BELAKANG. Antrean bertahan di IndexedDB,
    // jadi id lama masih dipegang aset lain yang belum tersinkron.
    const spy = jest.spyOn(Date, "now");
    const ids = new Set();

    spy.mockReturnValue(1_700_000_010_000);
    for (let i = 0; i < 50; i++) ids.add(buatTempId());
    const sebelumMundur = ids.size;

    spy.mockReturnValue(1_700_000_000_000); // jam mundur 10 detik
    for (let i = 0; i < 50; i++) ids.add(buatTempId());

    expect(sebelumMundur).toBe(50);
    expect(ids.size).toBe(100); // tak satu pun id terpakai ulang
  });

  test("tetap unik tanpa crypto.randomUUID (WebView Android lawas)", () => {
    // Jalur cadangan garam-sesi + penghitung monoton harus sama kuatnya; kalau
    // tidak, justru perangkat paling tua di lapangan yang kehilangan data.
    const asli = global.crypto;
    // eslint-disable-next-line no-global-assign
    global.crypto = { getRandomValues: asli?.getRandomValues?.bind(asli) };
    try {
      jest.spyOn(Date, "now").mockReturnValue(1_700_000_000_000);
      const ids = new Set();
      for (let i = 0; i < 500; i++) ids.add(buatTempId());
      expect(ids.size).toBe(500);
    } finally {
      // eslint-disable-next-line no-global-assign
      global.crypto = asli;
    }
  });

  test("tetap unik tanpa crypto sama sekali", () => {
    const asli = global.crypto;
    // eslint-disable-next-line no-global-assign
    global.crypto = undefined;
    try {
      jest.spyOn(Date, "now").mockReturnValue(1_700_000_000_000);
      const ids = new Set();
      for (let i = 0; i < 500; i++) ids.add(buatTempId());
      expect(ids.size).toBe(500);
    } finally {
      // eslint-disable-next-line no-global-assign
      global.crypto = asli;
    }
  });
});
