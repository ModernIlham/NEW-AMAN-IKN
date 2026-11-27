import L from "leaflet";
import {
  batasFitur, buatLabelPeta, buatLayerFitur, geometriDariLayer, jalurLabel, lengkapiFitur,
  opsiGaya, titikLabelArea, titikTengahGaris,
} from "../gambarPeta";

const GARIS = { id: "g", geometri: { type: "LineString", coordinates: [[0, 0], [10, 0], [10, 10]] },
  gaya: { warna: "#ff0000", tebal: 4, putus: true }, label: { teks: "Jl. Baru", posisi: "ikut" } };
const AREA = { id: "a", geometri: { type: "Polygon", coordinates: [[[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]] } };
const TITIK = { id: "t", geometri: { type: "Point", coordinates: [116.7, -0.96] }, label: { teks: "<b>Pos</b>", posisi: "kanan" } };

describe("gaya & kelengkapan", () => {
  test("bawaan diisi, posisi label tak sah dikoreksi per tipe", () => {
    const f = lengkapiFitur({ ...TITIK, label: { teks: "x", posisi: "ikut" } });
    expect(f.tipe).toBe("titik");
    expect(f.label.posisi).toBe("atas");
    expect(f.gaya.isi_warna).toBe(f.gaya.warna);
  });
  test("opsi Leaflet dari gaya: putus-putus & isi hanya untuk area", () => {
    const o = opsiGaya(lengkapiFitur(GARIS));
    expect(o).toMatchObject({ color: "#ff0000", weight: 4, fillOpacity: 0 });
    expect(o.dashArray).toBeTruthy();
    expect(opsiGaya(lengkapiFitur(AREA)).fillOpacity).toBe(0.25);
  });
});

describe("geometri label", () => {
  test("titik tengah garis di separuh panjang", () => {
    expect(titikTengahGaris([[0, 0], [10, 0], [10, 10]])).toEqual([10, 0]);
    expect(titikTengahGaris([[0, 0], [4, 0]])).toEqual([2, 0]);
  });
  test("label area: centroid untuk bentuk cembung", () => {
    const [x, y] = titikLabelArea([[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]);
    expect(x).toBeCloseTo(2, 9);
    expect(y).toBeCloseTo(2, 9);
  });
  test("label area: bentuk U (centroid di luar) tetap jatuh di dalam", () => {
    const u = [[0, 0], [6, 0], [6, 6], [4, 6], [4, 2], [2, 2], [2, 6], [0, 6], [0, 0]];
    const [x, y] = titikLabelArea(u);
    const dalam = (x < 2 || x > 4) || y < 2;
    expect(dalam).toBe(true);
  });
  test("jalur label dibalik bila garis mengarah ke kiri (teks tak terbalik)", () => {
    expect(jalurLabel([{ x: 10, y: 0 }, { x: 0, y: 0 }])).toBe("M0.0 0.0 L10.0 0.0");
    expect(jalurLabel([{ x: 0, y: 5 }, { x: 10, y: 5 }])).toBe("M0.0 5.0 L10.0 5.0");
  });
  test("label garis berbelok ditaruh di ruas terpanjang bila teks muat", () => {
    const pts = [{ x: 0, y: 100 }, { x: 40, y: 60 }, { x: 300, y: 80 }];
    expect(jalurLabel(pts, 100)).toBe("M40.0 60.0 L300.0 80.0");
    expect(jalurLabel(pts, 400)).toBe("M0.0 100.0 L40.0 60.0 L300.0 80.0");   // tak muat → seluruh garis
  });
  test("batas semua fitur", () => {
    expect(batasFitur([GARIS, AREA])).toEqual([[0, 0], [10, 10]]);
    expect(batasFitur([])).toBeNull();
  });
});

describe("Leaflet", () => {
  test("layer & geometri bolak-balik untuk ketiga tipe", () => {
    for (const f of [GARIS, AREA, TITIK]) {
      const ly = buatLayerFitur(f);
      expect(ly._fitur.id).toBe(f.id);
      expect(geometriDariLayer(ly)).toEqual(f.geometri);
    }
  });

  test("label teks dirender sebagai TEKS, bukan HTML", () => {
    const tambah = [];
    const map = {
      getZoom: () => 16, latLngToLayerPoint: () => ({ x: 0, y: 0 }), on() {}, off() {},
      addLayer(l) { tambah.push(l); return this; }, removeLayer() { return this; },
    };
    const label = buatLabelPeta(map, { renderer: null, paneLabel: "p", zoomMin: 15 });
    label.atur([TITIK]);
    const m = tambah.find((l) => l instanceof L.Marker);
    const el = m.options.icon.options.html;
    expect(el.textContent).toBe("<b>Pos</b>");
    expect(el.querySelector("b")).toBeNull();
    expect(el.style.transform).toMatch(/translate\(\d+px, -50%\)/);   // posisi kanan
  });
});
