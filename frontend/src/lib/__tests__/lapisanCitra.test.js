import axios from "axios";
import L from "leaflet";
import {
  ambilDaftarCitra, atribusiCitra, buatPengelolaCitra, formatTanggalCitra, isiAlamatUbin,
  lapisanSah, lupakanDaftarCitra, opsiUbinCitra, pasangKontrolCitra, periksaUbinCitra,
  PANE_CITRA, PANE_CITRA_Z, ubinUntukTitik, urutCitra, viewportMengenai, KUNCI_CITRA_AKTIF,
} from "../lapisanCitra";

jest.mock("axios", () => ({ get: jest.fn() }));

const CITRA = {
  id: "c1", nama: "Citra KIPP", sumber: "Tim Satker", tanggal_rekam: "2026-10-15",
  url_template: "/uploads/ubin/kipp/{z}/{x}/{y}.webp",
  batas: { barat: 116.69, selatan: -0.98, timur: 116.72, utara: -0.95 },
  zoom_min: 14, zoom_maks: 20, opasitas: 0.8, aktif: true,
};

function petaPalsu() {
  const pane = {};
  const sudut = { topright: document.createElement("div") };
  const pendengar = {};
  return {
    _controlCorners: sudut,
    sudut,
    lapis: new Set(),
    getPane: (n) => pane[n],
    createPane: (n) => { pane[n] = document.createElement("div"); return pane[n]; },
    pane,
    addLayer(l) { this.lapis.add(l); return this; },
    removeLayer(l) { this.lapis.delete(l); return this; },
    hasLayer(l) { return this.lapis.has(l); },
    on(ev, fn, ctx) { (pendengar[ev] ||= []).push([fn, ctx]); return this; },
    off() { return this; },
    fire(ev) { (pendengar[ev] || []).forEach(([f, ctx]) => f.call(ctx)); },
  };
}

beforeEach(() => {
  jest.clearAllMocks();
  lupakanDaftarCitra();
  localStorage.clear();
});

describe("format & validasi", () => {
  test("tanggal rekam bergaya Indonesia", () => {
    expect(formatTanggalCitra("2026-10-15")).toBe("15 Okt 2026");
    expect(formatTanggalCitra("2026-01-03")).toBe("3 Jan 2026");
    expect(formatTanggalCitra("bukan")).toBe("bukan");
  });

  test("lapisan tanpa batas/zoom wajar tidak dipasang", () => {
    expect(lapisanSah(CITRA)).toBe(true);
    expect(lapisanSah({ ...CITRA, aktif: false })).toBe(false);
    expect(lapisanSah({ ...CITRA, batas: { ...CITRA.batas, barat: 117 } })).toBe(false);
    expect(lapisanSah({ ...CITRA, zoom_min: 21 })).toBe(false);
    expect(lapisanSah({ ...CITRA, url_template: "" })).toBe(false);
  });

  test("viewport di luar batas terdeteksi", () => {
    expect(viewportMengenai(CITRA, { barat: 116.7, selatan: -0.97, timur: 116.71, utara: -0.96 })).toBe(true);
    expect(viewportMengenai(CITRA, { barat: 117, selatan: -1, timur: 117.1, utara: -0.9 })).toBe(false);
  });

  test("atribusi tak menyisipkan HTML", () => {
    expect(atribusiCitra({ ...CITRA, sumber: "<img src=x onerror=1>" })).not.toMatch(/[<>]/);
    expect(atribusiCitra(CITRA)).toBe("Citra eksisting: Tim Satker, 15 Okt 2026");
  });

  test("terbaru di atas", () => {
    const lama = { ...CITRA, id: "c0", tanggal_rekam: "2026-05-01" };
    expect(urutCitra([lama, CITRA]).map((l) => l.id)).toEqual(["c1", "c0"]);
  });
});

describe("opsi ubin menjaga performa", () => {
  test("ubin dibatasi wilayah & zoom, di pane antara OSM dan denah", () => {
    const o = opsiUbinCitra(CITRA);
    expect(o.bounds).toEqual([[-0.98, 116.69], [-0.95, 116.72]]);
    expect(o.minZoom).toBe(14);
    expect(o.maxNativeZoom).toBe(20);
    expect(o.maxZoom).toBe(22);
    expect(o.opacity).toBe(0.8);
    expect(o.pane).toBe(PANE_CITRA);
    expect(PANE_CITRA_Z).toBeGreaterThan(200); // di atas tilePane OSM
    expect(PANE_CITRA_Z).toBeLessThan(380);    // di bawah denah & pin
  });

  test("opasitas pilihan pengguna menimpa bawaan", () => {
    expect(opsiUbinCitra(CITRA, 0.4).opacity).toBe(0.4);
  });
});

describe("pengelola layer", () => {
  test("memasang, menyembunyikan, dan melepas tanpa membuat ulang layer", () => {
    const map = petaPalsu();
    const p = buatPengelolaCitra(map);
    expect(map.pane[PANE_CITRA].style.zIndex).toBe(String(PANE_CITRA_Z));
    const lain = { ...CITRA, id: "c2", url_template: "/uploads/ubin/b/{z}/{x}/{y}.webp" };
    p.atur([CITRA, lain]);
    expect(p.jumlahTerpasang()).toBe(2);
    const [pertama] = [...map.lapis];
    p.atur([CITRA, lain], { opasitas: 0.5 });
    expect(map.lapis.has(pertama)).toBe(true); // tak dibuat ulang saat opasitas berubah
    p.atur([CITRA, lain], { sembunyi: new Set(["c2"]) });
    expect(p.jumlahTerpasang()).toBe(1);
    p.lepas();
    expect(map.lapis.size).toBe(0);
  });
});

describe("daftar lapisan", () => {
  test("diambil sekali per sesi dan menyaring yang tak sah", async () => {
    axios.get.mockResolvedValue({ data: { items: [CITRA, { ...CITRA, id: "rusak", batas: null }] } });
    const a = await ambilDaftarCitra();
    const b = await ambilDaftarCitra();
    expect(a.map((l) => l.id)).toEqual(["c1"]);
    expect(b).toBe(a);
    expect(axios.get).toHaveBeenCalledTimes(1);
  });

  test("kegagalan tidak dikunci — panggilan berikut mencoba lagi", async () => {
    axios.get.mockRejectedValueOnce(new Error("jaringan"));
    await expect(ambilDaftarCitra()).rejects.toThrow();
    axios.get.mockResolvedValue({ data: { items: [] } });
    await expect(ambilDaftarCitra()).resolves.toEqual([]);
    expect(axios.get).toHaveBeenCalledTimes(2);
  });
});

describe("kontrol citra untuk peta lain", () => {
  test("MATI = nol permintaan; dinyalakan → ambil daftar & pasang", async () => {
    axios.get.mockResolvedValue({ data: { items: [CITRA] } });
    const map = petaPalsu();
    pasangKontrolCitra(map);
    expect(axios.get).not.toHaveBeenCalled();
    const tombol = map.sudut.topright.querySelector('[data-testid="peta-citra-toggle"]');
    expect(tombol.getAttribute("aria-pressed")).toBe("false");
    tombol.click();
    expect(tombol.getAttribute("aria-pressed")).toBe("true");
    await new Promise((r) => setTimeout(r, 0));
    expect(localStorage.getItem(KUNCI_CITRA_AKTIF)).toBe("1");
    expect(axios.get).toHaveBeenCalledTimes(1);
    expect(tombol.getAttribute("aria-pressed")).toBe("true");
    expect([...map.lapis].some((l) => l instanceof L.TileLayer)).toBe(true);
    tombol.click();
    expect(map.lapis.size).toBe(0);
  });

  test("tanpa citra terdaftar memberi tahu pengguna", async () => {
    axios.get.mockResolvedValue({ data: { items: [] } });
    localStorage.setItem(KUNCI_CITRA_AKTIF, "1");
    const pesan = jest.fn();
    pasangKontrolCitra(petaPalsu(), { onPesan: pesan });
    await new Promise((r) => setTimeout(r, 0));
    expect(pesan).toHaveBeenCalledWith(expect.stringMatching(/Belum ada citra/));
  });

  test("peta dilepas sebelum daftar tiba → tak ada layer dipasang", async () => {
    let lepas;
    axios.get.mockReturnValue(new Promise((r) => { lepas = r; }));
    localStorage.setItem(KUNCI_CITRA_AKTIF, "1");
    const map = petaPalsu();
    pasangKontrolCitra(map);
    map.fire("unload");
    lepas({ data: { items: [CITRA] } });
    await new Promise((r) => setTimeout(r, 0));
    expect([...map.lapis].some((l) => l instanceof L.TileLayer)).toBe(false);
  });
});

describe("pemeriksaan ubin", () => {
  test("koordinat ubin sesuai skema XYZ", () => {
    expect(ubinUntukTitik(0, 0, 1)).toEqual({ z: 1, x: 1, y: 1 });
    expect(ubinUntukTitik(-180, 85, 2)).toEqual({ z: 2, x: 0, y: 0 });
    expect(isiAlamatUbin("https://{s}.a/{z}/{x}/{y}.png", { z: 3, x: 4, y: 5 })).toBe("https://a.a/3/4/5.png");
  });

  const jawab = (status, jenis) => jest.fn(async () => ({
    status, ok: status >= 200 && status < 300, headers: { get: () => jenis },
  }));

  test("fallback SPA (HTML 200) dikenali sebagai belum disajikan", async () => {
    const r = await periksaUbinCitra(CITRA, { fetchFn: jawab(200, "text/html; charset=utf-8") });
    expect(r.status).toBe("html");
    expect(r.url).toMatch(/^\/uploads\/ubin\/kipp\/20\/\d+\/\d+\.webp$/);
  });

  test("gambar → ok, 404 → hilang, alamat luar → tak diambil", async () => {
    expect((await periksaUbinCitra(CITRA, { fetchFn: jawab(200, "image/webp") })).status).toBe("ok");
    expect((await periksaUbinCitra(CITRA, { fetchFn: jawab(404, "text/html") })).status).toBe("hilang");
    const f = jawab(200, "image/png");
    const luar = await periksaUbinCitra({ ...CITRA, url_template: "https://ubin.contoh.id/{z}/{x}/{y}.png" }, { fetchFn: f });
    expect(luar.status).toBe("luar");
    expect(f).not.toHaveBeenCalled();
  });
});
