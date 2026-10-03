import React, { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import PilihanRingkas from "./PilihanRingkas";

const opsi = [{ value: "p1", label: "Nama sama", description: "111 · Unit A", keywords: "satu@example.test" }, { value: "p2", label: "Nama sama", description: "222 · Unit B", searchText: "dua@example.test" }];
function Controlled(props) {
  const [value, setValue] = useState(props.value || "");
  return <PilihanRingkas options={opsi} {...props} value={value} onChange={setValue} label="Pegawai" testId="pilih" />;
}

test("pencarian ringkas memilih UUID eksplisit dan menutup setelah dipilih", () => {
  render(<Controlled />);
  expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("pilih"));
  const input = screen.getByTestId("pilih-search");
  expect(input).toHaveFocus();
  fireEvent.change(input, { target: { value: "DUA@EXAMPLE" } });
  expect(screen.queryByTestId("pilih-option-p1")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("pilih-option-p2"));
  expect(screen.getByTestId("pilih")).toHaveTextContent("Nama sama");
  expect(screen.queryByTestId("pilih-search")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("pilih"));
  expect(screen.getByTestId("pilih-option-p2")).toHaveAttribute("aria-selected", "true");
  expect(screen.getByTestId("pilih-option-p1")).toHaveAttribute("aria-selected", "false");
});

test("mengetik lalu Escape tidak mengubah pilihan tersimpan", () => {
  const onChange = jest.fn();
  render(<PilihanRingkas options={opsi} value="p1" onChange={onChange} testId="pilih" />);
  fireEvent.click(screen.getByTestId("pilih"));
  fireEvent.change(screen.getByTestId("pilih-search"), { target: { value: "Unit B" } });
  fireEvent.keyDown(screen.getByTestId("pilih-search"), { key: "Escape" });
  expect(onChange).not.toHaveBeenCalled();
  expect(screen.queryByTestId("pilih-search")).not.toBeInTheDocument();
  expect(screen.getByTestId("pilih")).toHaveTextContent("Nama sama");
});

test("keyboard ArrowDown Enter memilih dan melewati opsi disabled", () => {
  const onChange = jest.fn();
  render(<PilihanRingkas options={[{ ...opsi[0], disabled: true }, opsi[1]]} onChange={onChange} testId="pilih" />);
  fireEvent.click(screen.getByTestId("pilih"));
  fireEvent.keyDown(screen.getByTestId("pilih-search"), { key: "ArrowDown" });
  fireEvent.keyDown(screen.getByTestId("pilih-search"), { key: "Enter" });
  expect(onChange).toHaveBeenCalledWith("p2", opsi[1]);
});

test("ArrowUp pertama memilih opsi terakhir yang dapat dipilih", () => {
  const onChange = jest.fn();
  render(<PilihanRingkas options={[...opsi, { value: "disabled", label: "Tidak aktif", disabled: true }]} onChange={onChange} testId="pilih" />);
  fireEvent.click(screen.getByTestId("pilih"));
  fireEvent.keyDown(screen.getByTestId("pilih-search"), { key: "ArrowUp" });
  fireEvent.keyDown(screen.getByTestId("pilih-search"), { key: "Enter" });
  expect(onChange).toHaveBeenCalledWith("p2", opsi[1]);
});

test("nilai numerik nol tidak disamarkan sebagai mengosongkan pilihan", () => {
  const onChange = jest.fn();
  const option = { value: 0, label: "Nol" };
  render(<PilihanRingkas options={[option]} onChange={onChange} testId="pilih" />);
  fireEvent.click(screen.getByTestId("pilih"));
  fireEvent.click(screen.getByTestId("pilih-option-0"));
  expect(onChange).toHaveBeenCalledWith("0", option);
});

test("kosongkan memakai opsi semua yang disediakan, tanpa opsi kosong duplikat", () => {
  const onChange = jest.fn();
  const semua = { value: "", label: "Semua pemegang" };
  render(<PilihanRingkas options={[semua, ...opsi]} value="p1" onChange={onChange} testId="pilih" />);
  fireEvent.click(screen.getByTestId("pilih-clear"));
  expect(onChange).toHaveBeenCalledWith("", semua);
  fireEvent.click(screen.getByTestId("pilih"));
  expect(screen.queryByTestId("pilih-option-empty")).not.toBeInTheDocument();
  expect(screen.getByRole("option", { name: "Semua pemegang" })).toBeInTheDocument();
});

test("daftar panjang dibatasi tanpa menghilangkan hasil pencarian", () => {
  render(<PilihanRingkas options={Array.from({ length: 250 }, (_, i) => ({ value: String(i), label: `Pegawai ${i}` }))} onChange={jest.fn()} testId="pilih" />);
  fireEvent.click(screen.getByTestId("pilih"));
  expect(screen.queryByTestId("pilih-option-249")).not.toBeInTheDocument();
  expect(screen.getByTestId("pilih-more")).toHaveTextContent("100 dari 250");
  fireEvent.change(screen.getByTestId("pilih-search"), { target: { value: "Pegawai 249" } });
  expect(screen.getByTestId("pilih-option-249")).toBeInTheDocument();
});

test("disabled menutup pilihan dan mencegah perubahan", () => {
  const onChange = jest.fn();
  const view = render(<PilihanRingkas options={opsi} value="p1" onChange={onChange} testId="pilih" />);
  fireEvent.click(screen.getByTestId("pilih"));
  view.rerender(<PilihanRingkas options={opsi} value="p1" onChange={onChange} testId="pilih" disabled />);
  expect(screen.queryByTestId("pilih-search")).not.toBeInTheDocument();
  expect(screen.getByTestId("pilih")).toBeDisabled();
  expect(screen.getByTestId("pilih-clear")).toBeDisabled();
});
