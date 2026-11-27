import axios from "axios";
import L from "leaflet";
import {
  ambilDaftarCitra, atribusiCitra, buatPengelolaCitra, formatTanggalCitra,
  lapisanSah, lupakanDaftarCitra, opsiUbinCitra, pasangKontrolCitra, urlUbin,
  PANE_CITRA, PANE_CITRA_Z, PANE_GAMBAR, PANE_GAMBAR_Z, urutCitra, viewportMengenai, KUNCI_CITRA_AKTIF,
} from "../lapisanCitra";

jest.mock("axios", () => ({ get: jest.fn() }));

const CITRA = {
  id: "c1", jenis: "citra", version: 1, urutan: 2, nama: "Citra KIPP", sumber: "Tim Satker",
  tanggal_rekam: "2026-10-15", format: "webp", status: "siap",
  url_template: "/api/peta-lapisan/c1/ubin/{z}/{x}/{y}.webp?t=x",
  batas: { barat: 116.69, selatan: -0.98, timur: 116.72, utara: -0.95 },
  zoom_min: 14, zoom_maks: 20, opasitas: 0.8, aktif: true,
};
const GAMBAR = {
  id: "g1", jenis: "gambar", version: 1, urutan: 1, nama: "Jalan baru", aktif: true, label_zoom_min: 15,
  fitur: [{ id: "f1", tipe: "garis", geometri: { type: "LineString", coordinates: [[116.70, -0.96], [116.71, -0.965]] },
    gaya: { warna: "#ff0000", tebal: 4 }, label: { teks: "Jl. Baru", posisi: "tengah" } }],
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
    expect(lapisanSah({ ...CITRA, status: "memproses" })).toBe(false);
    expect(lapisanSah(GAMBAR)).toBe(true);
    expect(lapisanSah({ ...GAMBAR, fitur: null })).toBe(false);
  });

  test("viewport di luar batas terdeteksi", () => {
    expect(viewportMengenai(CITRA, { barat: 116.7, selatan: -0.97, timur: 116.71, utara: -0.96 })).toBe(true);
    expect(viewportMengenai(CITRA, { barat: 117, selatan: -1, timur: 117.1, utara: -0.9 })).toBe(false);
  });

  test("atribusi tak menyisipkan HTML", () => {
    expect(atribusiCitra({ ...CITRA, sumber: "<img src=x onerror=1>" })).not.toMatch(/[<>]/);
    expect(atribusiCitra(CITRA)).toBe("Citra eksisting: Tim Satker, 15 Okt 2026");
  });

  test("urutan panel: gambar di atas citra, lalu menurut urutan admin", () => {
    const bawah = { ...CITRA, id: "c0", urutan: 1 };
    expect(urutCitra([bawah, CITRA, GAMBAR]).map((l) => l.id)).toEqual(["g1", "c1", "c0"]);
  });

  test("viewport & batas lapisan gambar dihitung dari objeknya", () => {
    expect(viewportMengenai(GAMBAR, { barat: 116.705, selatan: -0.97, timur: 116.72, utara: -0.95 })).toBe(true);
    expect(viewportMengenai(GAMBAR, { barat: 117, selatan: -1, timur: 117.1, utara: -0.9 })).toBe(false);
  });

  test("alamat ubin memuat token", () => {
    expect(urlUbin(CITRA, "1.ab")).toMatch(/\/peta-lapisan\/c1\/ubin\/\{z\}\/\{x\}\/\{y\}\.webp\?t=1\.ab$/);
  });
});

describe("opsi ubin menjaga performa", () => {
  test("ubin dibatasi wilayah & zoom, di pane antara OSM dan denah", () => {
    const o = opsiUbinCitra(CITRA);
    expect(o.bounds).toEqual([[-0.98, 116.69], [-0.95, 116.72]]);
    expect(o.minZoom).toBe(9);           // ubin z14 diperkecil s.d. 5 level di bawahnya
    expect(o.minNativeZoom).toBe(14);
    expect(o.maxNativeZoom).toBe(20);
    expect(o.maxZoom).toBe(22);
    expect(o.opacity).toBe(0.8);
    expect(o.zIndex).toBe(2);            // urutan admin
    expect(o.pane).toBe(PANE_CITRA);
    expect(PANE_CITRA_Z).toBeGreaterThan(200); // di atas tilePane OSM
    expect(PANE_CITRA_Z).toBeLessThan(380);    // di bawah denah & pin
    expect(PANE_GAMBAR_Z).toBeGreaterThan(380);  // gambar di atas denah…
    expect(PANE_GAMBAR_Z).toBeLessThan(600);     // …tapi di bawah pin aset
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
    const lain = { ...CITRA, id: "c2" };
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

test("pengelola memasang lapisan gambar & membuat ulang saat versinya berubah", () => {
  const map = petaPalsu();
  map.getZoom = () => 16;
  map.latLngToLayerPoint = () => ({ x: 0, y: 0 });
  const p = buatPengelolaCitra(map);
  expect(map.pane[PANE_GAMBAR].style.zIndex).toBe(String(PANE_GAMBAR_Z));
  p.atur([GAMBAR]);
  const grup = [...map.lapis].find((l) => l instanceof L.FeatureGroup);
  expect(grup.getLayers()).toHaveLength(1);
  // label "tengah" dipasang sebagai penanda teks
  expect([...map.lapis].some((l) => l instanceof L.Marker)).toBe(true);
  p.atur([{ ...GAMBAR, version: 2 }]);
  expect(map.lapis.has(grup)).toBe(false);
  p.lepas();
  expect(map.lapis.size).toBe(0);
});

describe("daftar lapisan", () => {
  test("diambil sekali per sesi dan menyaring yang tak sah", async () => {
    axios.get.mockResolvedValue({ data: { ubin_token: "9.zz", items: [CITRA, { ...CITRA, id: "rusak", batas: null }, GAMBAR] } });
    const a = await ambilDaftarCitra();
    const b = await ambilDaftarCitra();
    expect(a.map((l) => l.id)).toEqual(["c1", "g1"]);
    expect(a[0].url_template).toMatch(/\?t=9\.zz$/);
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
    expect(pesan).toHaveBeenCalledWith(expect.stringMatching(/Belum ada lapisan/));
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
