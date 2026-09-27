import React from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import PhotoLightboxLoader from "../PhotoLightboxLoader";
import { muatPhotoLightbox } from "../../../lib/muatPhotoLightbox";

jest.mock("../../../lib/muatPhotoLightbox", () => ({ muatPhotoLightbox: jest.fn() }));
jest.mock("../../../hooks/useBackGuard", () => ({ useBackGuard: jest.fn() }));

function tertunda() { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; }
const foto = { id: "a", asset_name: "Meja", thumbnail: "data:image/png;base64,dGVzdA==" };
const Penampil = ({ asset, onClose }) => <button onClick={onClose}>Foto {asset.asset_name}</button>;

test("pratinjau dan tombol tutup langsung tersedia selama chunk sedang dimuat", async () => {
  const d = tertunda(); muatPhotoLightbox.mockReturnValue(d.promise);
  const onClose = jest.fn(); const p = render(<PhotoLightboxLoader asset={foto} onClose={onClose} />);
  expect(screen.getByRole("img").getAttribute("src")).toBe(foto.thumbnail);
  expect(screen.getByRole("status").textContent).toContain("Memuat");
  expect(document.body.style.overflow).toBe("hidden");
  fireEvent.click(screen.getByRole("button", { name: "Tutup penampil foto" }));
  expect(onClose).toHaveBeenCalledTimes(1);
  fireEvent.keyDown(window, { key: "Escape" }); expect(onClose).toHaveBeenCalledTimes(2);
  p.unmount(); expect(document.body.style.overflow).toBe("");
  await act(async () => { d.resolve({ default: Penampil }); await d.promise; });
  expect(screen.queryByText("Foto Meja")).toBeNull();
});

test("chunk gagal dapat dicoba lagi tanpa reload, seluruh properti terbaru diteruskan", async () => {
  const d = tertunda(); muatPhotoLightbox.mockReturnValueOnce(d.promise).mockResolvedValueOnce({ default: Penampil });
  const onClose = jest.fn(); const p = render(<PhotoLightboxLoader asset={foto} onClose={onClose} />);
  await act(async () => { d.reject(new Error("Jaringan putus")); await d.promise.catch(() => {}); });
  expect(screen.getByRole("alert").textContent).toContain("Sambungkan internet");
  p.rerender(<PhotoLightboxLoader asset={{ ...foto, asset_name: "Kursi" }} onClose={onClose} />);
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Coba lagi" })); });
  expect(screen.queryByTestId("lightbox-loading-dialog")).toBeNull();
  fireEvent.click(screen.getByText("Foto Kursi")); expect(onClose).toHaveBeenCalledTimes(1);
  expect(muatPhotoLightbox).toHaveBeenCalledTimes(2);
});

test("beralih aset saat pemuatan tidak menampilkan aset sebelumnya", async () => {
  const d = tertunda(); muatPhotoLightbox.mockReturnValue(d.promise);
  const onClose = jest.fn(); const p = render(<PhotoLightboxLoader asset={foto} onClose={onClose} />);
  p.rerender(<PhotoLightboxLoader asset={{ ...foto, asset_name: "Printer" }} onClose={onClose} />);
  await act(async () => { d.resolve({ default: Penampil }); await d.promise; });
  expect(screen.getByText("Foto Printer")).toBeTruthy();
  expect(muatPhotoLightbox).toHaveBeenCalledTimes(1);
});
