import { idPenggunaAktif, bolehReplay } from "./pemilikAntrean";

beforeEach(() => localStorage.clear());

describe("idPenggunaAktif", () => {
  test("membaca id (atau username) akun yang login", () => {
    localStorage.setItem("user", JSON.stringify({ id: "u-1", username: "sari" }));
    expect(idPenggunaAktif()).toBe("u-1");
    localStorage.setItem("user", JSON.stringify({ username: "sari" }));
    expect(idPenggunaAktif()).toBe("sari");
  });

  test("tanpa sesi / JSON rusak → string kosong, bukan meledak", () => {
    expect(idPenggunaAktif()).toBe("");
    localStorage.setItem("user", "{rusak");
    expect(idPenggunaAktif()).toBe("");
  });
});

describe("bolehReplay", () => {
  test("rekaman milik akun LAIN ditolak — inilah cacat yang ditutup", () => {
    // Perangkat dinas bersama: simpanan si A tak boleh dikirim memakai token
    // dan identitas audit si B yang kebetulan login berikutnya.
    expect(bolehReplay({ pemilik: "u-A" }, "u-B")).toBe(false);
  });

  test("rekaman milik sendiri di-replay", () => {
    expect(bolehReplay({ pemilik: "u-A" }, "u-A")).toBe(true);
  });

  test("rekaman era lama tanpa stempel tetap di-replay — jangan buang pekerjaan orang", () => {
    expect(bolehReplay({}, "u-B")).toBe(true);
    expect(bolehReplay({ pemilik: "" }, "u-B")).toBe(true);
  });

  test("identitas login tak diketahui → jangan menyandera rekaman", () => {
    expect(bolehReplay({ pemilik: "u-A" }, "")).toBe(true);
  });
});
