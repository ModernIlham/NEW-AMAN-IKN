import React, { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import VirtualizedAssetTable from "../VirtualizedAssetTable";
import AssetGalleryCard from "../AssetGalleryCard";
import { TooltipProvider } from "@/components/ui/tooltip";
import { toggleSeleksiHalaman } from "@/lib/seleksiHalaman";

jest.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count }) => ({
    getTotalSize: () => count * 52,
    getVirtualItems: () => Array.from({ length: count }, (_, index) => ({ index, key: index, start: index * 52, size: 52 })),
  }),
}));

const ASSET = { id: "a", asset_code: "305", asset_name: "Laptop", thumbnail: "data:image/png;base64,dGVzdA==" };
const SECOND = { ...ASSET, id: "b", asset_code: "306" };
function Table({ assets = [ASSET, SECOND], initial = ["b", "outside"], onEdit, onPhoto }) {
  const [selected, setSelected] = useState(new Set(initial));
  return <TooltipProvider>
    <output data-testid="selected-ids">{JSON.stringify([...selected].sort())}</output>
    <VirtualizedAssetTable assets={assets} pageSize={10} selectedAssets={selected}
      onToggleSelectAll={() => setSelected(prev => toggleSeleksiHalaman(prev, assets.map(a => a.id)))}
      onToggleSelect={id => setSelected(prev => toggleSeleksiHalaman(prev, [id]))}
      onEdit={onEdit} onOpenPhoto={onPhoto} />
  </TooltipProvider>;
}

test("header mixed untuk overlap, lalu pilih/batalkan hanya halaman aktif", async () => {
  const user = userEvent.setup();
  render(<Table />);
  const all = screen.getByRole("checkbox", { name: "Pilih semua aset di halaman ini" });
  expect(all).not.toBeChecked();
  expect(all.indeterminate).toBe(true);
  expect(all).toHaveAttribute("aria-checked", "mixed");
  await user.click(all);
  expect(all).toBeChecked();
  expect(all.indeterminate).toBe(false);
  expect(screen.getByTestId("selected-ids")).toHaveTextContent('["a","b","outside"]');
  await user.click(all);
  expect(all).not.toBeChecked();
  expect(screen.getByTestId("selected-ids")).toHaveTextContent('["outside"]');
});

test("semua halaman tetap checked walaupun ID di luar halaman masih terpilih", () => {
  render(<Table initial={["a", "b", "outside"]} />);
  expect(screen.getByRole("checkbox", { name: "Pilih semua aset di halaman ini" })).toBeChecked();
});

test("jumlah sama tanpa keanggotaan halaman tidak checked", () => {
  render(<Table initial={["outside-a", "outside-b"]} />);
  const all = screen.getByRole("checkbox", { name: "Pilih semua aset di halaman ini" });
  expect(all).not.toBeChecked();
  expect(all.indeterminate).toBe(false);
});

test("berpindah dua halaman sama besar menjaga ID lama saat memilih atau membatalkan halaman baru", async () => {
  const user = userEvent.setup();
  const view = render(<Table assets={[ASSET]} initial={[]} />);
  const header = () => screen.getByRole("checkbox", { name: "Pilih semua aset di halaman ini" });
  await user.click(header());
  view.rerender(<Table assets={[SECOND]} initial={[]} />);
  expect(header()).not.toBeChecked();
  await user.click(header());
  expect(screen.getByTestId("selected-ids")).toHaveTextContent('["a","b"]');
  view.rerender(<Table assets={[ASSET]} initial={[]} />);
  expect(header()).toBeChecked();
  await user.click(header());
  expect(screen.getByTestId("selected-ids")).toHaveTextContent('["b"]');
});

test("Space pada checkbox hanya memilih; Enter foto hanya membuka foto; Enter baris membuka editor", async () => {
  const user = userEvent.setup(), onEdit = jest.fn(), onPhoto = jest.fn();
  render(<Table initial={[]} onEdit={onEdit} onPhoto={onPhoto} />);
  const box = screen.getByRole("checkbox", { name: "Pilih aset 305" });
  box.focus();
  await user.keyboard("[Space]");
  expect(box).toBeChecked();
  expect(onEdit).not.toHaveBeenCalled();
  const photo = screen.getByRole("button", { name: "Lihat foto 305" });
  photo.focus();
  await user.keyboard("[Enter]");
  expect(onPhoto).toHaveBeenCalledTimes(1);
  expect(onPhoto).toHaveBeenCalledWith(ASSET);
  expect(onEdit).not.toHaveBeenCalled();
  screen.getByRole("button", { name: "Edit aset 305 - Laptop" }).focus();
  await user.keyboard("[Enter]");
  expect(onEdit).toHaveBeenCalledTimes(1);
  expect(onEdit).toHaveBeenCalledWith(ASSET);
});

test("galeri memakai tombol foto bernama; checkbox dan tombol SIMAN tetap saudara", async () => {
  const user = userEvent.setup(), onPhoto = jest.fn(), onSelect = jest.fn(), onEdit = jest.fn();
  const { container } = render(<TooltipProvider><AssetGalleryCard
    asset={{ ...ASSET, siman: { status: "selisih" } }} onOpenLightbox={onPhoto}
    onToggleSelect={onSelect} onEdit={onEdit} /></TooltipProvider>);
  const photo = screen.getByRole("button", { name: "Lihat foto 305" });
  expect(container.querySelector("button button, button input")).toBeNull();
  screen.getByRole("checkbox", { name: "Pilih aset 305" }).focus();
  await user.keyboard("[Space]");
  expect(onSelect).toHaveBeenCalledWith("a");
  expect(onPhoto).not.toHaveBeenCalled();
  photo.focus();
  await user.keyboard("[Enter]");
  expect(onPhoto).toHaveBeenCalledTimes(1);
  expect(onEdit).not.toHaveBeenCalled();
});
