import axios from "axios";
import { bacaCache, muatPreferensi, simpanPreferensi } from "./preferensiKameraApi";
import { PREFERENSI_BAWAAN as dasar } from "./preferensiKamera";
jest.mock("axios");
let id = 0;
beforeEach(() => { localStorage.clear(); localStorage.setItem("user", JSON.stringify({ id: `uji-${++id}` })); });
function janji() { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; }
test("respons GET usang tidak menimpa rasio baru", async () => {
  const d = janji(); axios.get.mockReturnValue(d.promise); axios.put.mockImplementation(async (_url, p) => ({ data: p }));
  const get = muatPreferensi(); await simpanPreferensi({ ...dasar, rasio: "1:1" });
  d.resolve({ data: dasar }); expect((await get).rasio).toBe("1:1"); expect(bacaCache().rasio).toBe("1:1");
});
test("pilihan cepat langsung masuk cache dan permintaan PUT berurutan", async () => {
  const d = janji(); axios.put.mockReturnValueOnce(d.promise).mockImplementation(async (_url, p) => ({ data: p }));
  const pertama = simpanPreferensi({ ...dasar, rasio: "3:4" }); await Promise.resolve(); await Promise.resolve();
  const kedua = simpanPreferensi({ ...dasar, rasio: "9:16" });
  expect(bacaCache().rasio).toBe("9:16"); expect(axios.put).toHaveBeenCalledTimes(1);
  d.resolve({ data: { ...dasar, rasio: "3:4" } }); await pertama; await kedua;
  expect(bacaCache().rasio).toBe("9:16"); expect(axios.put).toHaveBeenCalledTimes(2);
});
test("rasio luring dipakai lagi dan disinkronkan saat kamera dibuka daring", async () => {
  axios.put.mockRejectedValueOnce(Error("luring"));
  expect((await simpanPreferensi({ ...dasar, rasio: "full" })).tersimpanKeAkun).toBe(false);
  axios.put.mockImplementation(async (_url, p) => ({ data: p }));
  expect((await muatPreferensi()).rasio).toBe("full"); expect(axios.get).not.toHaveBeenCalled();
});
test("respons akun lama tidak ditulis ke cache akun yang baru login", async () => {
  const d = janji(); axios.get.mockReturnValue(d.promise); const get = muatPreferensi();
  localStorage.setItem("user", JSON.stringify({ id: "akun-lain" }));
  d.resolve({ data: { ...dasar, rasio: "1:1" } }); await get;
  expect(bacaCache().rasio).toBe("asli");
});
