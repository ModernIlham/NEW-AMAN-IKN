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
