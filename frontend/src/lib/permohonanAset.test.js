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
});
