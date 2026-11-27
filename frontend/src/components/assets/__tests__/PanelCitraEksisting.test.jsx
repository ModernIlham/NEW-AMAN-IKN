import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import PanelCitraEksisting from "../PanelCitraEksisting";

function citraPalsu(tambahan = {}) {
  return {
    lapis: [], memuat: false, galat: "", opasitas: 0.85,
    setOpasitas: jest.fn(), toggleLapisan: jest.fn(), menuju: jest.fn(), muatUlang: jest.fn(),
    ...tambahan,
  };
}

const L1 = { id: "c1", nama: "Citra KIPP", tanggal_rekam: "2026-10-15", tampil: true, diArea: true };
const L2 = { id: "c0", nama: "Citra Mei", tanggal_rekam: "2026-05-01", tampil: false, diArea: false };

test("tanpa citra terdaftar: arahkan admin ke tempat mendaftarkannya", () => {
  render(<PanelCitraEksisting citra={citraPalsu()} buka onLipat={() => {}} />);
  expect(screen.getByTestId("citra-kosong")).toHaveTextContent(/Hierarki Spasial/);
  expect(screen.queryByTestId("citra-opasitas")).not.toBeInTheDocument();
});

test("daftar citra: tanggal, penanda di luar layar, saklar, lompat, transparansi", () => {
  const citra = citraPalsu({ lapis: [L1, L2] });
  render(<PanelCitraEksisting citra={citra} buka onLipat={() => {}} />);
  expect(screen.getByTestId("citra-lapis-c1")).toHaveTextContent("15 Okt 2026");
  expect(screen.getByTestId("citra-lapis-c0")).toHaveTextContent("di luar layar");
  expect(screen.getByTestId("citra-saklar-c0")).toHaveAttribute("aria-pressed", "false");
  fireEvent.click(screen.getByTestId("citra-saklar-c1"));
  expect(citra.toggleLapisan).toHaveBeenCalledWith("c1");
  fireEvent.click(screen.getByTestId("citra-tuju-c0"));
  expect(citra.menuju).toHaveBeenCalledWith(L2);
  fireEvent.change(screen.getByTestId("citra-opasitas"), { target: { value: "40" } });
  expect(citra.setOpasitas).toHaveBeenCalledWith(0.4);
});

test("terlipat: hanya kepala + tanggal citra terbaru", () => {
  const onLipat = jest.fn();
  render(<PanelCitraEksisting citra={citraPalsu({ lapis: [L1] })} buka={false} onLipat={onLipat} />);
  expect(screen.queryByTestId("citra-lapis-c1")).not.toBeInTheDocument();
  expect(screen.getByTestId("citra-panel-lipat")).toHaveTextContent("15 Okt 2026");
  fireEvent.click(screen.getByTestId("citra-panel-lipat"));
  expect(onLipat).toHaveBeenCalled();
});

test("gagal memuat: pesan + coba ulang", () => {
  const citra = citraPalsu({ galat: "Daftar citra eksisting gagal dimuat" });
  render(<PanelCitraEksisting citra={citra} buka onLipat={() => {}} />);
  fireEvent.click(screen.getByTestId("citra-coba-ulang"));
  expect(citra.muatUlang).toHaveBeenCalled();
});
