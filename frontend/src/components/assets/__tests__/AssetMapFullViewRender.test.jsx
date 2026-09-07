/**
 * Uji render Peta Aset (AssetMapFullView) — backlog #346.
 *
 * Komponen inilah yang pernah tayang sebagai LAYAR KOSONG di produksi
 * ("Cannot access before initialization" — simpul TDZ melingkar) dengan lint
 * bersih, build sukses, dan 741 uji statis hijau. Uji ini me-mount-nya
 * sungguhan: Leaflet ditukar tiruan berantai, jaringan di-mock, IndexedDB
 * dipasang versi gagal-cepat (jalur snapshot luring terjaga `catch`).
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import {
  pasangIndexedDbPalsu,
  pasangWebSocketPalsu,
} from "../../../uji/lingkunganPeta";
import AssetMapFullView from "../AssetMapFullView";

jest.mock("leaflet", () => require("../../../uji/lefletPalsu"));
jest.mock("leaflet.markercluster", () => ({}));
jest.mock("axios");

const ASET = [
  { id: "aset-1", asset_name: "Kursi Rapat", asset_code: "3050104001",
    NUP: "1", lat: -1.4001, lng: 116.7001, status: "Aktif",
    condition: "Baik", inventory_status: "ditemukan" },
  { id: "aset-2", asset_name: "Meja Kerja", asset_code: "3050104002",
    NUP: "2", lat: -1.4003, lng: 116.7003, status: "Aktif",
    condition: "Baik", inventory_status: "belum_diinventarisasi" },
];

beforeAll(() => {
  pasangWebSocketPalsu();
  pasangIndexedDbPalsu();
  window.HTMLElement.prototype.scrollIntoView = () => {};
});

beforeEach(() => {
  axios.get.mockImplementation((url) => {
    const u = String(url);
    if (u.includes("/assets?")) {
      return Promise.resolve({
        data: { items: ASET, total: ASET.length, total_pages: 1 },
      });
    }
    // Komentar aset & usulan geser: kosong sudah cukup untuk mount.
    return Promise.resolve({ data: { items: [] } });
  });
  axios.post.mockResolvedValue({ data: {} });
});

function propsMinimal(tambahan = {}) {
  return {
    activityId: "keg-uji-1",
    activityName: "Inventarisasi Uji",
    onClose: jest.fn(),
    buildParams: () => new URLSearchParams(),
    clientFilter: (rows) => rows,
    ...tambahan,
  };
}

test("peta aset berdiri: wadah + kanvas + toolbar dirender, data termuat", async () => {
  render(<AssetMapFullView {...propsMinimal()} />);
  expect(screen.getByTestId("asset-map-fullview")).toBeInTheDocument();
  expect(screen.getByTestId("asset-map-canvas")).toBeInTheDocument();
  // Muatan data memakai filter dashboard (buildParams) → GET /assets?...
  // Urutan panggilan tidak dijanjikan (komentar/usulan bisa lebih dulu),
  // jadi cari di SEMUA panggilan.
  await waitFor(() => expect(
    axios.get.mock.calls.some((c) => /\/assets\?/.test(String(c[0])))
  ).toBe(true));
  // Toolbar hidup — bukan layar kosong seperti insiden TDZ.
  expect(screen.getByTestId("asset-map-cluster-toggle")).toBeInTheDocument();
});

test("mode baca-saja vs boleh-edit: kontrol edit hanya muncul saat canEdit", async () => {
  const { unmount } = render(<AssetMapFullView {...propsMinimal()} />);
  await waitFor(() => expect(axios.get).toHaveBeenCalled());
  expect(screen.queryByTestId("asset-map-drag-lock")).not.toBeInTheDocument();
  unmount();

  render(<AssetMapFullView {...propsMinimal({ canEdit: true })} />);
  await waitFor(() =>
    expect(screen.getByTestId("asset-map-drag-lock")).toBeInTheDocument());
});

test("gagal memuat data tidak merobohkan peta — toolbar tetap berdiri", async () => {
  axios.get.mockRejectedValue(new Error("jaringan putus"));
  render(<AssetMapFullView {...propsMinimal()} />);
  await waitFor(() => expect(axios.get).toHaveBeenCalled());
  expect(screen.getByTestId("asset-map-fullview")).toBeInTheDocument();
  expect(screen.getByTestId("asset-map-canvas")).toBeInTheDocument();
});

// ── Lingkup berbagi: yang dibagikan = yang TAMPIL ────────────────────────
//
// Permintaan pemilik: peta yang sedang disaring/diseleksi harus membagikan
// titik itu saja, dan jumlahnya harus terbaca. Sebelum ini tombol Bagikan tak
// membawa keterangan apa pun, sehingga tautannya selalu berisi seluruh aset
// kegiatan — tak peduli apa yang terlihat di layar.
//
// Fixture SENDIRI, dengan `koordinat_latitude`/`koordinat_longitude`: `ASET`
// di atas memakai `lat`/`lng`, dan peta membuang baris tanpa koordinat. Uji
// lingkup butuh baris yang benar-benar sampai ke peta — memakai fixture
// bersama akan menghasilkan daftar kosong yang lulus tanpa membuktikan apa pun.
const BERKOORDINAT = [
  { id: "aset-1", asset_name: "Kursi Rapat", asset_code: "3050104001", NUP: "1",
    koordinat_latitude: -1.4001, koordinat_longitude: 116.7001 },
  { id: "aset-2", asset_name: "Meja Kerja", asset_code: "3050104002", NUP: "2",
    koordinat_latitude: -1.4003, koordinat_longitude: 116.7003 },
];

function pakaiAsetBerkoordinat() {
  axios.get.mockImplementation((url) => {
    if (/\/assets\?/.test(String(url))) {
      return Promise.resolve({
        data: { items: BERKOORDINAT, total: BERKOORDINAT.length, total_pages: 1 },
      });
    }
    return Promise.resolve({ data: { items: [] } });
  });
}

/** Buka dialog bagikan & kembalikan lingkup yang dibawa tombolnya. */
async function lingkupSaatBagikan(tambahan = {}) {
  const onShare = jest.fn();
  pakaiAsetBerkoordinat();
  render(<AssetMapFullView {...propsMinimal({ canEdit: true, onShare, ...tambahan })} />);
  await waitFor(() => expect(axios.get).toHaveBeenCalled());
  await waitFor(() =>
    expect(screen.getByTestId("asset-map-share")).toBeInTheDocument());
  screen.getByTestId("asset-map-share").click();
  await waitFor(() => expect(onShare).toHaveBeenCalled());
  return onShare.mock.calls[0][0];
}

test("tanpa penyempit: lingkup TIDAK membekukan daftar id", async () => {
  const l = await lingkupSaatBagikan();
  // ids null = server memakai perilaku "seluruh kegiatan" yang tetap HIDUP;
  // mengirim daftar id lengkap akan membekukannya tanpa diminta.
  expect(l.ids).toBeNull();
  expect(l.disempitkan).toBe(false);
  expect(l.jumlah).toBe(BERKOORDINAT.length);
});

test("seleksi aktif: lingkup hanya memuat aset terpilih", async () => {
  const l = await lingkupSaatBagikan({ selectedIds: new Set(["aset-2"]) });
  expect(l.ids).toEqual(["aset-2"]);
  expect(l.jumlah).toBe(1);
  expect(l.disempitkan).toBe(true);
  expect(l.sebab).toBe("seleksi");
  // Totalnya tetap disebut agar operator tahu berapa yang TIDAK ikut.
  expect(l.total).toBe(BERKOORDINAT.length);
});

test("filter aktif tanpa seleksi: lingkup memuat hasil filter", async () => {
  const l = await lingkupSaatBagikan({ activeFilterCount: 2 });
  expect(l.disempitkan).toBe(true);
  expect(l.sebab).toBe("filter");
  expect(l.ids).toEqual(BERKOORDINAT.map((a) => a.id));
});


// ── Label nama aset di samping marker ─────────────────────────────────────
//
// Permintaan pemilik: *"tambahkan fitur label yang menampilkan nama-nama
// asetnya … dan juga berikan tombol aktif tidak aktif dalam memberikan
// labelnya di samping marker."*

test("tombol label ADA, dan menyalakannya mengubah keadaannya", async () => {
  // Pilihan label disimpan di localStorage; tanpa dibersihkan, uji ini
  // mewarisi keadaan uji sebelumnya dan lulus/gagal karena hal lain.
  localStorage.removeItem("aman_map_label");
  render(<AssetMapFullView {...propsMinimal()} />);
  await waitFor(() => expect(axios.get).toHaveBeenCalled());
  const tombol = screen.getByTestId("asset-map-label-toggle");
  // Mati secara bawaan: pada peta padat, label yang menyala tanpa diminta
  // menutupi petanya sendiri.
  expect(tombol.getAttribute("aria-pressed")).toBe("false");
  tombol.click();
  await waitFor(() =>
    expect(screen.getByTestId("asset-map-label-toggle")
      .getAttribute("aria-pressed")).toBe("true"));
});

test("pilihan label BERTAHAN antar sesi", async () => {
  // Pemakai yang menyalakan label lalu menutup peta tak seharusnya
  // menyalakannya lagi setiap kali kembali.
  localStorage.removeItem("aman_map_label");
  const { unmount } = render(<AssetMapFullView {...propsMinimal()} />);
  await waitFor(() => expect(axios.get).toHaveBeenCalled());
  screen.getByTestId("asset-map-label-toggle").click();
  await waitFor(() =>
    expect(localStorage.getItem("aman_map_label")).toBe("1"));
  unmount();

  render(<AssetMapFullView {...propsMinimal()} />);
  await waitFor(() =>
    expect(screen.getByTestId("asset-map-label-toggle")
      .getAttribute("aria-pressed")).toBe("true"));
});

test("label TIDAK menangkap klik — pin di bawahnya tetap dapat diketuk", () => {
  // Di peta padat label menutupi marker tetangganya; label yang menangkap
  // klik membuat pin di bawahnya tak bisa dibuka sama sekali.
  const css = require("fs").readFileSync(
    require("path").join(__dirname, "../../../index.css"), "utf8");
  const awal = css.indexOf(".aman-peta-label {");
  expect(awal).toBeGreaterThan(-1);
  const aturan = css.slice(awal, css.indexOf("}", awal));
  expect(aturan).toMatch(/pointer-events:\s*none/);
  // Putih ber-stroke gelap, dan strokenya digambar DI BELAKANG huruf —
  // tanpa `paint-order`, stroke menggerogoti huruf 11px dari dalam.
  expect(aturan).toMatch(/color:\s*#fff/);
  expect(aturan).toMatch(/-webkit-text-stroke:/);
  expect(aturan).toMatch(/paint-order:\s*stroke/);
  // Gelembung bawaan tooltip Leaflet dimatikan: yang diminta label, bukan balon.
  expect(aturan).toMatch(/background:\s*none/);
  expect(aturan).toMatch(/border:\s*0/);
});
