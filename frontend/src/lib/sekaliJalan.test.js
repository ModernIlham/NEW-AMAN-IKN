import { sekaliJalan } from "./sekaliJalan";

// Yang dijaga: seeding hanya TERBANG SEKALI per kunci walau dipanggil
// serentak — dan kegagalan tidak menyandera kuncinya selamanya.

describe("sekaliJalan", () => {
  test("dua pemanggil serentak menumpang SATU penerbangan", async () => {
    const peta = {};
    let jalan = 0;
    const fn = () => new Promise((res) => setTimeout(() => { jalan += 1; res("hasil"); }, 10));
    const [a, b] = await Promise.all([
      sekaliJalan(peta, "k", fn),
      sekaliJalan(peta, "k", fn),
    ]);
    expect(jalan).toBe(1);
    expect(a).toBe("hasil");
    expect(b).toBe("hasil");
  });

  test("kunci berbeda terbang sendiri-sendiri", async () => {
    const peta = {};
    let jalan = 0;
    const fn = async () => { jalan += 1; };
    await Promise.all([sekaliJalan(peta, "k1", fn), sekaliJalan(peta, "k2", fn)]);
    expect(jalan).toBe(2);
  });

  test("setelah selesai, panggilan berikutnya terbang lagi (bukan hasil beku)", async () => {
    const peta = {};
    let jalan = 0;
    const fn = async () => { jalan += 1; return jalan; };
    expect(await sekaliJalan(peta, "k", fn)).toBe(1);
    expect(await sekaliJalan(peta, "k", fn)).toBe(2);
  });

  test("kegagalan melepas kunci — percobaan berikutnya tidak tersandera", async () => {
    const peta = {};
    let percobaan = 0;
    const fn = async () => {
      percobaan += 1;
      if (percobaan === 1) throw new Error("gagal dulu");
      return "pulih";
    };
    await expect(sekaliJalan(peta, "k", fn)).rejects.toThrow("gagal dulu");
    expect(await sekaliJalan(peta, "k", fn)).toBe("pulih");
  });
});
