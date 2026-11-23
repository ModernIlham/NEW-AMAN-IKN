import { jalankanHapusBerat, jawabanTerputus } from "../prosesHapusBerat";

describe("jawabanTerputus", () => {
  it.each([
    [{ code: "ECONNABORTED" }, true],
    [{ code: "ERR_NETWORK" }, true],
    [{ response: { status: 504 } }, true],
    [{ response: { status: 502 } }, true],
    [{}, true], // tanpa respons sama sekali
    [{ response: { status: 409 } }, false],
    [{ response: { status: 423 } }, false],
    [{ response: { status: 500 } }, false],
  ])("%j → %s", (err, harap) => expect(jawabanTerputus(err)).toBe(harap));
});

describe("jalankanHapusBerat", () => {
  it("jawaban normal → selesai tanpa memantau", async () => {
    const cek = jest.fn();
    const h = await jalankanHapusBerat(async () => ({ data: { message: "ok" } }), cek);
    expect(h).toEqual({ status: "selesai", data: { message: "ok" } });
    expect(cek).not.toHaveBeenCalled();
  });

  it("penolakan server (409) dilempar, tidak dipantau", async () => {
    const cek = jest.fn();
    await expect(jalankanHapusBerat(
      async () => { throw { response: { status: 409 } }; }, cek, { jeda: 1 },
    )).rejects.toEqual({ response: { status: 409 } });
    expect(cek).not.toHaveBeenCalled();
  });

  it("timeout → pantau sampai cekSelesai true (galat pantau sesaat diabaikan)", async () => {
    const cek = jest.fn()
      .mockResolvedValueOnce(false)
      .mockRejectedValueOnce(new Error("putus"))
      .mockResolvedValueOnce(true);
    const h = await jalankanHapusBerat(
      async () => { throw { code: "ECONNABORTED" }; }, cek, { jeda: 1, batas: 5000 },
    );
    expect(h).toEqual({ status: "selesai_latar" });
    expect(cek).toHaveBeenCalledTimes(3);
  });

  it("batas tunggu habis → belum_pasti", async () => {
    const h = await jalankanHapusBerat(
      async () => { throw { response: { status: 504 } }; }, async () => false, { jeda: 1, batas: 10 },
    );
    expect(h).toEqual({ status: "belum_pasti" });
  });
});
