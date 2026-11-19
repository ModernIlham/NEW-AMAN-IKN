/**
 * Tombol ikon paginasi wajib bernama (WCAG 4.1.2) — tinjauan mutu Nov 2026
 * (F10): axe mendapati empat tombol chevron tanpa nama sama sekali, sehingga
 * pembaca layar hanya mengumumkan "tombol".
 */
import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import AssetPagination from "../AssetPagination";

test("tombol navigasi & pemilih ukuran halaman punya nama aksesibel", () => {
  const goToPage = jest.fn();
  render(<AssetPagination currentPage={3} totalPages={10} totalItems={500} pageSize={50}
    setPageSize={() => {}} goToPage={goToPage} />);
  fireEvent.click(screen.getByRole("button", { name: "Halaman pertama" }));
  fireEvent.click(screen.getByRole("button", { name: "Halaman sebelumnya" }));
  fireEvent.click(screen.getByRole("button", { name: "Halaman berikutnya" }));
  fireEvent.click(screen.getByRole("button", { name: "Halaman terakhir" }));
  expect(goToPage.mock.calls.map(([p]) => p)).toEqual([1, 2, 4, 10]);
  expect(screen.getByRole("combobox", { name: "Jumlah baris per halaman" })).toBeInTheDocument();
});
