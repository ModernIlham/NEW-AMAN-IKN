import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import { toast } from "sonner";
import CategoryManagerDialog from "../CategoryManagerDialog";

jest.mock("axios", () => ({ get: jest.fn(), post: jest.fn() }));
jest.mock("sonner", () => ({
  toast: { error: jest.fn(), success: jest.fn(), warning: jest.fn() },
}));

const BATAS = 10 * 1024 * 1024;
const PESAN_BATAS = "File impor kategori maksimal 10 MB. Pecah data menjadi beberapa file.";

function berkas(ukuran) {
  const file = new File(["Kode Aset,Deskripsi Barang\n3010101001,Meja\n"], "kategori.csv", { type: "text/csv" });
  // Yang diuji di klien adalah metadata File.size, tanpa alokasi 10 MB per uji.
  Object.defineProperty(file, "size", { value: ukuran });
  return file;
}

async function buka() {
  await act(async () => {
    render(<CategoryManagerDialog open categories={[]} onClose={jest.fn()} onCategoriesChanged={jest.fn()} />);
  });
}

function unggah(cara, file) {
  if (cara === "pilih file") {
    fireEvent.change(screen.getByTestId("category-import-input"), { target: { files: [file] } });
  } else {
    fireEvent.drop(screen.getByTestId("category-dropzone"), { dataTransfer: { files: [file] } });
  }
}

beforeEach(() => {
  jest.clearAllMocks();
  axios.get.mockResolvedValue({ data: {} });
  // Hentikan tepat setelah pengiriman: uji ini tidak memulai timer polling job.
  axios.post.mockRejectedValue({ response: { data: { detail: "Server uji tidak memulai job" } } });
});

test("petunjuk menjelaskan batas, bukan menjanjikan jutaan data tanpa batas", async () => {
  await buka();
  expect(screen.getByText(/Maksimal 10 MB per file/)).toBeVisible();
  expect(screen.queryByText(/Mendukung jutaan data/)).not.toBeInTheDocument();
});

describe.each(["pilih file", "drag-and-drop"])("unggahan lewat %s", (cara) => {
  test.each([[0, "File impor kategori kosong"], [BATAS + 1, PESAN_BATAS]])(
    "menolak ukuran %i sebelum mengirim permintaan",
    async (ukuran, pesan) => {
      await buka();
      unggah(cara, berkas(ukuran));
      expect(toast.error).toHaveBeenCalledWith(pesan);
      expect(axios.post).not.toHaveBeenCalled();
      expect(screen.getByTestId("category-import-input").value).toBe("");
    },
  );

  test("file tepat 10 MB tetap dikirim utuh setelah file besar ditolak", async () => {
    await buka();
    unggah(cara, berkas(BATAS + 1));
    const file = berkas(BATAS);
    unggah(cara, file);
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Server uji tidak memulai job"));
    expect(axios.post).toHaveBeenCalledTimes(1);
    const [url, form] = axios.post.mock.calls[0];
    expect(url).toMatch(/\/categories\/import-bulk$/);
    expect(form.get("file")).toBe(file);
  });
});

test("membatalkan pemilihan tidak mengirim permintaan atau menampilkan galat", async () => {
  await buka();
  fireEvent.change(screen.getByTestId("category-import-input"), { target: { files: [] } });
  expect(axios.post).not.toHaveBeenCalled();
  expect(toast.error).not.toHaveBeenCalled();
});
