/**
 * Pemilih penanda tangan — layar untuk aturan tiga lapis.
 *
 * Permintaan pemilik: *"sudah aktif semua bisa memilih siapa saja yang
 * menandatagani sesuai referensi pejabat yang sudah ditetapkan"*.
 *
 * Yang paling mudah rusak diam-diam: opsi "kosong". Kalau ia hanya berbunyi
 * "— pilih —", operator tak punya cara tahu siapa yang akan menandatangani
 * bila ia tak memilih apa-apa — dan dokumen resmi terbit atas nama orang yang
 * tak pernah ia lihat di layar.
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import PemilihPenandatangan from "../PemilihPenandatangan";

const SLOT = [
  { kunci: "lpb_dibuat", label: "LPB — Dibuat oleh", peran: "pengurus_barang",
    peran_uraian: "Pengurus Barang", arti: "Petugas yang menyusun LPB" },
  { kunci: "lpb_disetujui", label: "LPB — Disetujui oleh", peran: "kuasa_pengguna_barang",
    peran_uraian: "Kuasa Pengguna Barang", arti: "KPB yang menyetujui" },
];
const PEJABAT = [
  { id: "a", nama: "Andi", jabatan: "Pengurus Barang", kode_satker: "527001" },
  { id: "c", nama: "Cici", jabatan: "KPB", kode_satker: "527999" },
];

function pasang(props = {}) {
  const onUbah = jest.fn();
  render(<PemilihPenandatangan slot={SLOT} pejabat={PEJABAT} kodeSatker="527001"
    nilai={{}} onUbah={onUbah} {...props} />);
  return onUbah;
}

it("merender satu pemilih per slot yang dikirim server", () => {
  pasang();
  expect(screen.getByTestId("ttd-slot-lpb_dibuat")).toBeInTheDocument();
  expect(screen.getByTestId("ttd-slot-lpb_disetujui")).toBeInTheDocument();
});

function pilih(testId, nilai) {
  fireEvent.change(screen.getByTestId(testId), { target: { value: nilai } });
}

it("hanya menawarkan pejabat satker ini", () => {
  pasang();
  // `select.options` sengaja dipakai — bukan query peran. Ia hanya berisi
  // <option> yang menjadi ANAK LANGSUNG select, jadi sekaligus menjaga
  // instrumentasi visual-edits tetap mati saat uji (lihat craco.config.js):
  // begitu ia menyisipkan <span> pembungkus, daftar ini kosong dan
  // `select.value` berhenti bisa disetel — persis seperti di dev server.
  const opsi = [...screen.getByTestId("ttd-slot-lpb_dibuat").options].map((o) => o.value);
  expect(opsi).toEqual(["", "a"]);
});

it("opsi kosong MENERANGKAN siapa yang akan menandatangani, bukan '— pilih —'", () => {
  pasang();
  expect(screen.getByTestId("ttd-slot-lpb_dibuat").options[0].textContent)
    .toBe("Ikut Referensi Pejabat — peran Pengurus Barang");
});

it("opsi kosong menyebut nama dari setelan satker bila ada", () => {
  pasang({ bawaan: { lpb_dibuat: "a" } });
  expect(screen.getByTestId("ttd-slot-lpb_dibuat").options[0].textContent)
    .toBe("Ikut setelan satker — Andi — Pengurus Barang");
});

it("memilih pejabat mengirim peta BARU ke induk", () => {
  const onUbah = pasang();
  pilih("ttd-slot-lpb_dibuat", "a");
  expect(onUbah).toHaveBeenCalledWith({ lpb_dibuat: "a" });
});

it("melepas pilihan mengirim peta TANPA slot itu", () => {
  const onUbah = pasang({ nilai: { lpb_dibuat: "a", lpb_disetujui: "a" } });
  pilih("ttd-slot-lpb_dibuat", "");
  expect(onUbah).toHaveBeenCalledWith({ lpb_disetujui: "a" });
});

it("nilai terpilih tercermin pada select", () => {
  pasang({ nilai: { lpb_disetujui: "a" } });
  expect(screen.getByTestId("ttd-slot-lpb_disetujui")).toHaveValue("a");
  expect(screen.getByTestId("ttd-slot-lpb_dibuat")).toHaveValue("");
});

it("registry pejabat kosong DIJELASKAN, bukan dropdown kosong tanpa sebab", () => {
  pasang({ pejabat: [] });
  expect(screen.getByText(/Belum ada pejabat terdaftar/i)).toBeInTheDocument();
  expect(screen.queryByTestId("ttd-slot-lpb_dibuat")).toBeNull();
});

it("arti tiap slot ikut ditampilkan", () => {
  pasang();
  expect(screen.getByText("Petugas yang menyusun LPB")).toBeInTheDocument();
});
