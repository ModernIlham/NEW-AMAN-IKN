import axios from "axios";
import {
  ajukanPermohonanAset, gerbangPermohonanAsetAktif, pesanPermohonanTerkirim,
} from "./permohonanAset";

jest.mock("axios");

// CRA resetMocks: true — implementasi mock hidup per-uji, set di sini.
describe("permohonanAset", () => {
  test("gerbang aktif mengikuti setelan server", async () => {
    axios.get.mockResolvedValue({ data: { aktif: true } });
    expect(await gerbangPermohonanAsetAktif()).toBe(true);
    axios.get.mockResolvedValue({ data: { aktif: false } });
    expect(await gerbangPermohonanAsetAktif()).toBe(false);
  });

  test("gagal membaca setelan dianggap MATI (perilaku lama, tak mengunci)", async () => {
    axios.get.mockRejectedValue(new Error("jaringan"));
    expect(await gerbangPermohonanAsetAktif()).toBe(false);
  });

  test("gerbang memakai header satker dan signal milik transaksi pemanggil", async () => {
    const requestConfig = {
      headers: { "X-Satker-Aktif": "621001" }, signal: new AbortController().signal,
    };
    axios.get.mockResolvedValue({ data: { aktif: true } });

    expect(await gerbangPermohonanAsetAktif(requestConfig)).toBe(true);

    expect(axios.get).toHaveBeenCalledWith(
      expect.stringContaining("/pembukuan/permohonan-pengaturan"), requestConfig);
    expect(axios.get.mock.calls[0][1]).toBe(requestConfig);
  });

  test("gerbang yang dibatalkan saat menunggu tidak dianggap MATI lalu diteruskan", async () => {
    const controller = new AbortController();
    let rejectRequest;
    axios.get.mockImplementation(() => new Promise((_resolve, reject) => { rejectRequest = reject; }));
    const error = Object.assign(new Error("konteks satker berubah"), { code: "ERR_CANCELED" });
    const pending = gerbangPermohonanAsetAktif({
      headers: { "X-Satker-Aktif": "621001" }, signal: controller.signal,
    });
    const rejected = expect(pending).rejects.toBe(error);

    controller.abort();
    rejectRequest(error);

    await rejected;
  });

  test("ajukan mengirim jalur+asset_id+payload dan mengembalikan permohonan", async () => {
    axios.post.mockResolvedValue({ data: { permohonan: { id: "p-1" } } });
    const p = await ajukanPermohonanAset(
      "reklasifikasi", "as-1", { kode_baru: "3060102001" }, "salah golong");
    expect(p).toEqual({ id: "p-1" });
    expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining("/pembukuan/permohonan"),
      { jalur: "reklasifikasi", asset_id: "as-1",
        payload: { kode_baru: "3060102001" }, catatan: "salah golong" });
  });

  test("pesan toast menyebut persetujuan KPB dan lokasi panel", () => {
    const m = pesanPermohonanTerkirim("Reklasifikasi");
    expect(m).toMatch(/Reklasifikasi/);
    expect(m).toMatch(/persetujuan KPB/);
    expect(m).toMatch(/Pembukuan/);
  });

  test("pengajuan meneruskan konfigurasi konteks tanpa mengubah payload", async () => {
    const requestConfig = {
      headers: { "X-Satker-Aktif": "621001" }, signal: new AbortController().signal,
    };
    const payload = { fields: ["condition"], expected_version: 7 };
    axios.post.mockResolvedValue({ data: { permohonan: { id: "p-siman" } } });

    expect(await ajukanPermohonanAset(
      "siman", "as-1", payload, "sesuai satker", requestConfig,
    )).toEqual({ id: "p-siman" });

    expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining("/pembukuan/permohonan"),
      { jalur: "siman", asset_id: "as-1", payload, catatan: "sesuai satker" },
      requestConfig);
    expect(axios.post.mock.calls[0][2]).toBe(requestConfig);
  });
});
