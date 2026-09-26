import React, { useState } from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import MarkerPinEditor from "./MarkerPinEditor";
import * as pinLib from "../../lib/markerPin";

function Form({ onBusyChange } = {}) {
  const [value, setValue] = useState("");
  return <><MarkerPinEditor value={value} onChange={setValue} onBusyChange={onBusyChange} /><output data-testid="hasil">{value}</output></>;
}
test("pilih ikon, cari, filter kategori, atur lingkaran dan kembalikan polos", () => {
  render(<Form />);
  fireEvent.click(screen.getByTestId("marker-mode-icon"));
  fireEvent.change(screen.getByTestId("marker-search"), { target: { value: "laptop" } });
  expect(screen.getByTestId("marker-icon-laptop")).toBeTruthy();
  expect(screen.queryByTestId("marker-icon-monitor")).toBeNull();
  fireEvent.click(screen.getByTestId("marker-icon-laptop"));
  fireEvent.click(screen.getByTestId("marker-circle"));
  fireEvent.change(screen.getByTestId("marker-stroke"), { target: { value: "3" } });
  const r = JSON.parse(screen.getByTestId("hasil").textContent);
  expect(r).toMatchObject({ icon: "laptop", circle: false, strokeWidth: 3 });
  fireEvent.change(screen.getByTestId("marker-category"), { target: { value: "Kendaraan" } });
  expect(screen.getByText(/Ikon tidak ditemukan/)).toBeTruthy();
  fireEvent.click(screen.getByTestId("marker-mode-plain"));
  expect(screen.getByTestId("hasil").textContent).toBe("");
});
test("mode huruf mengganti desain dan tetap ada pratinjau", () => {
  render(<Form />);
  fireEvent.click(screen.getByTestId("marker-mode-text"));
  fireEvent.change(screen.getByTestId("marker-text"), { target: { value: "IKN" } });
  expect(screen.getByTestId("marker-pin-preview").textContent.trim()).toBe("IKN");
});

test("judul berikon, katalog bertahap, dan pencarian menjangkau ikon terakhir", () => {
  render(<Form />);
  expect(screen.getByTestId("marker-design-icon").getAttribute("aria-hidden")).toBe("true");
  fireEvent.click(screen.getByTestId("marker-mode-icon"));
  const grid = screen.getByRole("group", { name: "Pilihan ikon" });
  expect(within(grid).getAllByRole("button")).toHaveLength(72);
  fireEvent.click(screen.getByTestId("marker-icons-more"));
  expect(within(grid).getAllByRole("button")).toHaveLength(144);
  grid.scrollTop = 200;
  fireEvent.change(screen.getByTestId("marker-search"), { target: { value: "desain marker pin" } });
  expect(grid.scrollTop).toBe(0);
  expect(within(grid).getAllByRole("button")).toHaveLength(1);
  expect(screen.queryByTestId("marker-icons-more")).toBeNull();
  fireEvent.click(screen.getByTestId("marker-icon-designpin"));
  expect(JSON.parse(screen.getByTestId("hasil").textContent).icon).toBe("designpin");
  fireEvent.click(screen.getByRole("button", { name: "Hapus pencarian ikon" }));
  expect(within(grid).getAllByRole("button")).toHaveLength(72);
  expect(screen.getByText("Terpilih: Desain marker pin")).toBeTruthy();
  fireEvent.click(screen.getByTestId("marker-icons-more"));
  fireEvent.change(screen.getByTestId("marker-category"), { target: { value: "Kendaraan" } });
  expect(within(grid).getAllByRole("button")).toHaveLength(14);
  fireEvent.change(screen.getByTestId("marker-category"), { target: { value: "Semua" } });
  expect(within(grid).getAllByRole("button")).toHaveLength(72);
  while (screen.queryByTestId("marker-icons-more")) fireEvent.click(screen.getByTestId("marker-icons-more"));
  expect(within(grid).getAllByRole("button")).toHaveLength(421);
});

test.each(["iconColor", "circleColor", "strokeColor"])("kode HEX %s sinkron dua arah, tidak menyimpan kode salah", key => {
  const onBusyChange = jest.fn();
  render(<Form onBusyChange={onBusyChange} />);
  fireEvent.click(screen.getByTestId("marker-mode-icon"));
  const kode = screen.getByTestId(`marker-${key}-hex`);
  const palet = screen.getByTestId(`marker-${key}`);
  fireEvent.change(kode, { target: { value: "A1B2C3" } });
  fireEvent.blur(kode);
  expect(kode.value).toBe("#a1b2c3");
  expect(palet.value).toBe("#a1b2c3");
  fireEvent.change(kode, { target: { value: "#zz" } });
  expect(kode.getAttribute("aria-invalid")).toBe("true");
  expect(JSON.parse(screen.getByTestId("hasil").textContent)[key]).toBe("#a1b2c3");
  expect(onBusyChange).toHaveBeenLastCalledWith(true);
  fireEvent.change(palet, { target: { value: "#123456" } });
  expect(kode.value).toBe("#123456");
  expect(onBusyChange).toHaveBeenLastCalledWith(false);
});

test("kode tidak valid dibuang saat ganti aset dan kontrol nonaktif tidak menghambat simpan", () => {
  const onBusyChange = jest.fn();
  const value = JSON.stringify(pinLib.PIN_BAWAAN);
  const { rerender } = render(<MarkerPinEditor value={value} scopeKey="a" onChange={jest.fn()} onBusyChange={onBusyChange} />);
  fireEvent.change(screen.getByTestId("marker-circleColor-hex"), { target: { value: "#" } });
  expect(onBusyChange).toHaveBeenLastCalledWith(true);
  rerender(<MarkerPinEditor value={value} scopeKey="b" onChange={jest.fn()} onBusyChange={onBusyChange} />);
  expect(screen.getByTestId("marker-circleColor-hex").value).toBe("#ffffff");
  expect(onBusyChange).toHaveBeenLastCalledWith(false);
  rerender(<MarkerPinEditor value={JSON.stringify({ ...pinLib.PIN_BAWAAN, circle: false })} scopeKey="b" onChange={jest.fn()} onBusyChange={onBusyChange} />);
  expect(screen.getByTestId("marker-circleColor-hex").disabled).toBe(true);
});

test("hasil unggahan terlambat tidak mengubah aset berikutnya", async () => {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  const mock = jest.spyOn(pinLib, "siapkanIkonPin").mockReturnValue(promise);
  const onChange = jest.fn(), onBusyChange = jest.fn();
  const { rerender } = render(<MarkerPinEditor scopeKey="a1" onChange={onChange} onBusyChange={onBusyChange} />);
  fireEvent.change(screen.getByTestId("marker-upload"), { target: { files: [new File(["png"], "logo.png", { type: "image/png" })] } });
  await waitFor(() => expect(onBusyChange).toHaveBeenLastCalledWith(true));
  rerender(<MarkerPinEditor scopeKey="a2" onChange={onChange} onBusyChange={onBusyChange} />);
  await act(async () => { resolve("data:image/png;base64,AAAA"); await promise; });
  expect(onChange).not.toHaveBeenCalled();
  expect(onBusyChange).toHaveBeenLastCalledWith(false);
  mock.mockRestore();
});

test("unggahan valid mengganti desain, unggahan gagal tidak menghapus desain lama", async () => {
  const mock = jest.spyOn(pinLib, "siapkanIkonPin").mockResolvedValue("data:image/png;base64,AAAA");
  render(<Form />);
  fireEvent.change(screen.getByTestId("marker-upload"), { target: { files: [new File(["png"], "logo.png", { type: "image/png" })] } });
  await waitFor(() => expect(JSON.parse(screen.getByTestId("hasil").textContent).mode).toBe("custom"));
  const prev = screen.getByTestId("hasil").textContent;
  mock.mockRejectedValue(new Error("Gambar rusak"));
  fireEvent.change(screen.getByTestId("marker-upload"), { target: { files: [new File(["bad"], "bad.png", { type: "image/png" })] } });
  await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("Gambar rusak"));
  expect(screen.getByTestId("hasil").textContent).toBe(prev);
  mock.mockRestore();
});
