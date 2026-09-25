import React, { useState } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import MarkerPinEditor from "./MarkerPinEditor";
import * as pinLib from "../../lib/markerPin";

function Form() {
  const [value, setValue] = useState("");
  return <><MarkerPinEditor value={value} onChange={setValue} /><output data-testid="hasil">{value}</output></>;
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
