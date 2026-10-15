import React, { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as pdfCompression from "../../../lib/pdfCompression";
import { toast } from "sonner";
import { DocumentChecklist } from "../DocumentChecklist";

const photo = 'data:image/svg+xml;base64,' + btoa('<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160"><rect width="160" height="160" fill="#d9e9e5"/><path d="M20 100h120v30H20zM40 70h65l25 30H30z" fill="#14877a"/><circle cx="45" cy="130" r="13" fill="#334155"/><circle cx="115" cy="130" r="13" fill="#334155"/></svg>');
const pdfName = "Dokumen STNK Mobil Pemadam Kebakaran Tahun 2026.pdf";
const initial = [
  { name: "BPKB", checked: false, photos: [], documents: [] },
  { name: "STNK", checked: true, photos: [photo, photo], documents: [{ name: pdfName, data: "__existing__:0" }] },
];

function Form({ onChange = () => {}, onSubmit = () => {} }) {
  const [items, setItems] = useState(initial);
  return <form onSubmit={onSubmit}><DocumentChecklist checklist={items} assetId="a1" onChange={next => { setItems(next); onChange(next); }} /></form>;
}

test("lampiran tetap terlihat dan tersimpan ketika centang kelengkapan dibatalkan", async () => {
  const onChange = jest.fn();
  render(<Form onChange={onChange} />);
  if (process.env.AMAN_QA_UI_DIR) {
    const fs = require("fs");
    fs.mkdirSync(process.env.AMAN_QA_UI_DIR, { recursive: true });
    fs.writeFileSync(`${process.env.AMAN_QA_UI_DIR}/documents.html`, document.body.innerHTML);
  }
  await userEvent.click(screen.getByRole("button", { name: "Kelengkapan STNK" }));
  expect(screen.getByText(pdfName)).toBeVisible();
  expect(screen.getByRole("button", { name: "Lihat foto 1 STNK" })).toBeVisible();
  expect(onChange.mock.calls[0][0][1]).toMatchObject({ checked: false, photos: [photo, photo], documents: initial[1].documents });
});

test("hapus foto dan PDF hanya menghapus lampiran yang dipilih", async () => {
  const onChange = jest.fn();
  render(<Form onChange={onChange} />);
  await userEvent.click(screen.getByRole("button", { name: "Hapus foto 1 STNK" }));
  expect(onChange.mock.lastCall[0][1].photos).toHaveLength(1);
  expect(screen.getByText(pdfName)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: `Hapus PDF ${pdfName}` }));
  expect(onChange.mock.lastCall[0][1].documents).toHaveLength(0);
  expect(onChange.mock.lastCall[0][1].photos).toHaveLength(1);
  expect(screen.getByRole("button", { name: "Kelengkapan STNK" })).toHaveAttribute("aria-pressed", "true");
});

test("menambah item dengan Enter tidak mengirim form aset dan menolak nama duplikat", async () => {
  const onSubmit = jest.fn(e => e.preventDefault());
  render(<Form onSubmit={onSubmit} />);
  expect(screen.getByRole("button", { name: "Tambah item kelengkapan" })).toBeDisabled();
  await userEvent.type(screen.getByRole("textbox", { name: "Nama item kelengkapan baru" }), "Kunci cadangan{Enter}");
  expect(screen.getByRole("button", { name: "Kelengkapan Kunci cadangan" })).toBeVisible();
  expect(onSubmit).not.toHaveBeenCalled();
  await userEvent.type(screen.getByRole("textbox", { name: "Nama item kelengkapan baru" }), "STNK{Enter}");
  expect(screen.getAllByRole("button", { name: "Kelengkapan STNK" })).toHaveLength(1);
});

test("pratinjau foto bisa ditutup tanpa menghapus foto atau mengirim form", async () => {
  const onChange = jest.fn();
  const onSubmit = jest.fn(e => e.preventDefault());
  render(<Form onChange={onChange} onSubmit={onSubmit} />);
  await userEvent.click(screen.getByRole("button", { name: "Lihat foto 1 STNK" }));
  await userEvent.click(screen.getByRole("button", { name: "Tutup pratinjau foto" }));
  expect(onChange).not.toHaveBeenCalled();
  expect(onSubmit).not.toHaveBeenCalled();
});

test("PDF tersimpan dibuka melalui endpoint media dengan versi aset", () => {
  const open = jest.spyOn(window, "open").mockReturnValue({});
  render(<Form />);
  fireEvent.click(screen.getByTestId("checklist-doc-view-1-0"));
  expect(open.mock.calls[0][0]).toContain("/assets/a1/checklist/1/documents/0?v=1");
  open.mockRestore();
});


test("PDF hasil kompresi di atas 8MB ditolak sebelum masuk draf", async () => {
  const compression = jest.spyOn(pdfCompression, "compressPdfFile").mockResolvedValue({ dataUrl: "data:application/pdf;base64,YQ==", originalBytes: 10 * 1024 * 1024, compressedBytes: 9 * 1024 * 1024, savingsPercent: 10, method: "test" });
  const error = jest.spyOn(toast, "error"); const onChange = jest.fn();
  render(<DocumentChecklist checklist={[{ name: "STNK", checked: true, photos: [], documents: [] }]} onChange={onChange} />);
  fireEvent.change(screen.getByLabelText("Tambah foto atau PDF STNK"), { target: { files: [new File(["pdf"], "besar.pdf", { type: "application/pdf" })] } });
  await waitFor(() => expect(error).toHaveBeenCalledWith(expect.stringContaining("melebihi 8 MB"), expect.anything()));
  expect(onChange).not.toHaveBeenCalled(); compression.mockRestore(); error.mockRestore();
});

test.each([false, true])("urutan visual tidak mengubah URL foto/PDF asal, dengan thumbnail=%s", thumbnail => {
  const open = jest.spyOn(window, "open").mockReturnValue({});
  const stored = { id: "stnk-id", name: "STNK", checked: true, _serverItemIndex: 0,
    photos: ["__existing__:2"], photo_thumbnails: thumbnail ? ["", "", photo] : [],
    documents: [{ id: "pdf-id", name: "Asli.pdf", data: "__existing__:1" }] };
  const other = { name: "Rekomendasi", checked: false, photos: [], documents: [] };
  const view = render(<DocumentChecklist checklist={[other, stored]} assetId="a1" assetVersion={9} onChange={jest.fn()} />);
  try {
    for (const items of [[other, stored], [stored, other]]) {
      view.rerender(<DocumentChecklist checklist={items} assetId="a1" assetVersion={9} onChange={jest.fn()} />);
      expect(screen.getByRole("img", { name: "STNK foto 1" })).toHaveAttribute("src", thumbnail ? photo : expect.stringContaining("/checklist/0/photos/2?v=9"));
      fireEvent.click(screen.getByRole("button", { name: "Lihat foto 1 STNK" }));
      expect(screen.getByRole("img", { name: "Preview" })).toHaveAttribute("src", expect.stringContaining("/checklist/0/photos/2?v=9"));
      fireEvent.click(screen.getByRole("button", { name: "Tutup pratinjau foto" }));
      fireEvent.click(screen.getByRole("button", { name: "Lihat PDF Asli.pdf" }));
      expect(open.mock.lastCall[0]).toContain("/checklist/0/documents/1?v=9");
    }
  } finally { open.mockRestore(); }
});
