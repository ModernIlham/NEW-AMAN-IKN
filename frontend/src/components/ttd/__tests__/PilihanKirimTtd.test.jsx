/**
 * Pilihan urutan teken & sifat urgensi saat "Kirim TTD".
 *
 * Permintaan pemilik: *"di saat mengklik 'kirim ttd' juga dapat memilih jenis
 * urutan tanda tangan apakah ingin paralel atau berurutan, dan berikan juga
 * opsi pemilihan sifat urgensi suratnya."*
 *
 * Sebelumnya keduanya dipatok diam-diam ("paralel", "biasa"), sehingga
 * pengirim tak pernah bisa menyatakan bahwa dokumen ini harus berurutan atau
 * mendesak.
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import PilihanKirimTtd from "../PilihanKirimTtd";

function pasang(props = {}) {
  const onKirim = jest.fn();
  const onTutup = jest.fn();
  render(<PilihanKirimTtd terbuka onKirim={onKirim} onTutup={onTutup}
    judul="BAST B-1/2026" {...props} />);
  return { onKirim, onTutup };
}

const pilih = (testid, nilai) =>
  fireEvent.change(screen.getByTestId(testid), { target: { value: nilai } });

it("menawarkan kedua urutan tanda tangan", () => {
  pasang();
  // `select.options` sengaja dipakai: ia hanya berisi <option> anak langsung,
  // sekaligus menjaga instrumentasi visual-edits tetap mati saat uji.
  const opsi = [...screen.getByTestId("ttd-pilih-mode").options].map((o) => o.value);
  expect(opsi).toEqual(["paralel", "berurutan"]);
});

it("menawarkan ketiga sifat urgensi", () => {
  pasang();
  const opsi = [...screen.getByTestId("ttd-pilih-urgensi").options].map((o) => o.value);
  expect(opsi).toEqual(["biasa", "segera", "sangat_segera"]);
});

it("bawaannya sama dengan perilaku lama", () => {
  const { onKirim } = pasang();
  fireEvent.click(screen.getByTestId("ttd-kirim-lanjut"));
  expect(onKirim).toHaveBeenCalledWith({ mode: "paralel", sifat_urgensi: "biasa" });
});

it("pilihan pengguna benar-benar terkirim", () => {
  const { onKirim } = pasang();
  pilih("ttd-pilih-mode", "berurutan");
  pilih("ttd-pilih-urgensi", "sangat_segera");
  fireEvent.click(screen.getByTestId("ttd-kirim-lanjut"));
  expect(onKirim).toHaveBeenCalledWith(
    { mode: "berurutan", sifat_urgensi: "sangat_segera" });
});

it("arti mode berubah mengikuti pilihannya", () => {
  // Istilahnya saja tak cukup bagi orang yang baru pertama kali mengirim.
  pasang();
  expect(screen.getByTestId("ttd-arti-mode")).toHaveTextContent(/sekaligus/i);
  pilih("ttd-pilih-mode", "berurutan");
  expect(screen.getByTestId("ttd-arti-mode")).toHaveTextContent(/giliran|sebelumnya/i);
});

it("Batal menutup tanpa mengirim apa pun", () => {
  const { onKirim, onTutup } = pasang();
  fireEvent.click(screen.getByText("Batal"));
  expect(onKirim).not.toHaveBeenCalled();
  expect(onTutup).toHaveBeenCalled();
});

it("selagi mengirim, tombolnya terkunci", () => {
  pasang({ mengirim: true });
  expect(screen.getByTestId("ttd-kirim-lanjut")).toBeDisabled();
});

it("judul dokumen ikut ditampilkan", () => {
  pasang();
  expect(screen.getByText("BAST B-1/2026")).toBeInTheDocument();
});
