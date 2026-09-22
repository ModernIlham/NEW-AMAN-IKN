import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MapPin } from "lucide-react";
import SaringanPetaDicari from "../SaringanPetaDicari";
import { SEMUA } from "../../../lib/filterPetaKolaborasi";

const pilihan = Array.from({ length: 120 }, (_, i) => ({
  nilai: `lokasi-${i}`, label: `Gedung ${String(i).padStart(3, "0")}`, jumlah: i + 1,
}));
const props = { judul: "Lokasi", ikon: MapPin, pilihan, aktif: SEMUA, onPilih: jest.fn(),
  labelSemua: "Semua lokasi", jumlah: 7260, placeholder: "Cari nama lokasi…", testId: "cari-lokasi" };

test("daftar besar ditampilkan bertahap dan pencarian menjangkau pilihan di luar jendela", async () => {
  render(<SaringanPetaDicari {...props} />);
  expect(screen.getAllByRole("button", { name: /Gedung/ })).toHaveLength(50);
  await userEvent.click(screen.getByTestId("cari-lokasi-lagi"));
  expect(screen.getAllByRole("button", { name: /Gedung/ })).toHaveLength(100);
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "gedung 119" } });
  expect(screen.getByRole("button", { name: /Gedung 119/ })).toBeInTheDocument();
  expect(screen.getByText("1 dari 120 pilihan")).toBeInTheDocument();
  expect(props.onPilih).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: /Gedung 119/ }));
  expect(props.onPilih).toHaveBeenCalledWith("lokasi-119");
});

test("pencarian kosong hasilnya tidak menghapus pilihan aktif; hapus pencarian hanya mereset daftar", async () => {
  render(<SaringanPetaDicari {...props} aktif="lokasi-119" />);
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "tidak cocok" } });
  expect(screen.getByText("Tidak ada pilihan yang cocok.")).toBeInTheDocument();
  expect(screen.getByTestId("cari-lokasi-terpilih")).toHaveTextContent("Gedung 119");
  await userEvent.click(screen.getByRole("button", { name: "Hapus pencarian lokasi" }));
  expect(screen.getByRole("searchbox")).toHaveValue("");
  expect(screen.getAllByRole("button", { name: /Gedung/ })).toHaveLength(50);
  expect(props.onPilih).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: /Semua lokasi/ }));
  expect(props.onPilih).toHaveBeenCalledWith(SEMUA);
});

test("snapshot QA memakai komponen asli untuk layar sempit dan kedua tema", () => {
  render(<SaringanPetaDicari {...props} aktif="lokasi-119" />);
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "119" } });
  expect(screen.getByRole("button", { name: /Gedung 119/ })).toHaveAttribute("aria-pressed", "true");
  if (process.env.AMAN_QA_PETA_DIR) {
    const fs = require("fs"), path = require("path");
    fs.mkdirSync(process.env.AMAN_QA_PETA_DIR, { recursive: true });
    fs.writeFileSync(path.join(process.env.AMAN_QA_PETA_DIR, "saringan.html"), document.body.innerHTML);
  }
});
