import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import MarkerColorInput, { teksKontrasWarna } from "./MarkerColorInput";

test.each([["#73030d", "#ffffff"], ["#ffffff", "#000000"], ["#000000", "#ffffff"], ["#00ff00", "#000000"], ["#777777", "#000000"]])(
  "warna %s memakai teks %s agar terbaca", (color, text) => expect(teksKontrasWarna(color)).toBe(text));

test("kode dan pemilih native ada pada kotak warna yang sama, ikon tidak menutup input", () => {
  const onTextChange = jest.fn(), onColorChange = jest.fn();
  render(<MarkerColorInput label="Warna ikon / huruf" testId="uji" color="#73030d" value="#73030d"
    onTextChange={onTextChange} onColorChange={onColorChange} />);
  const field = screen.getByTestId("uji-field");
  expect(field).toHaveStyle({ backgroundColor: "#73030d", color: "#ffffff" });
  const kode = screen.getByRole("textbox", { name: "Kode warna ikon / huruf" });
  const palet = screen.getByLabelText("Pilih warna ikon / huruf");
  expect(field).toContainElement(kode);
  expect(field).toContainElement(palet);
  expect(palet).toHaveAttribute("type", "color");
  expect(palet).not.toHaveAttribute("tabindex", "-1");
  fireEvent.change(kode, { target: { value: "#abcdef" } });
  expect(onTextChange).toHaveBeenCalledWith("#abcdef");
  fireEvent.change(palet, { target: { value: "#123456" } });
  expect(onColorChange).toHaveBeenCalledWith("#123456");
});

test("draft salah tidak menjadi background dan kedua kontrol mengikuti status nonaktif", () => {
  render(<MarkerColorInput label="Warna lingkaran" testId="uji" color="#ffffff" value="#zz" invalid disabled />);
  expect(screen.getByTestId("uji-field")).toHaveStyle({ backgroundColor: "#ffffff" });
  expect(screen.getByTestId("uji-hex")).toHaveAttribute("aria-invalid", "true");
  expect(screen.getByTestId("uji-hex")).toBeDisabled();
  expect(screen.getByTestId("uji")).toBeDisabled();
});
