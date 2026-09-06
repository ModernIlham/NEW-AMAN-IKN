/**
 * Ubah Massal memakai pemilih unit yang SAMA dengan form aset.
 *
 * Sebelumnya `<select>` bawaan dengan jorokan spasi — yang tak terlihat pada
 * pemilih Android — dan akhiran "(E1)" yang tersangkut di ujung nama panjang.
 * Dua pemilih berbeda untuk satu pilihan yang sama membuat orang belajar dua
 * kali, dan yang satu sudah diperbaiki sementara yang lain tidak.
 *
 * Satu hal yang BEDA dan harus tetap beda: arti "tak memilih". Pada form aset
 * ia berarti asetnya tanpa unit; di sini ia berarti unit seluruh aset terpilih
 * TIDAK disentuh. Kata yang sama untuk dua maksud itu adalah cara tercepat
 * membuat orang menghapus unit puluhan aset padahal ia hanya ingin
 * membiarkannya — dan ubah massal tak menanyakan ulang per aset.
 */
import React from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";

import BatchEditPanel from "../BatchEditPanel";

jest.mock("axios");

const MASTER = [
  { id: "k2", nama_unit: "Kedeputian Bidang Transformasi Hijau dan Digital",
    eselon: "1", parent_id: null },
  { id: "d22", nama_unit: "Direktorat Pengembangan Ekosistem Digital",
    eselon: "2", parent_id: "k2" },
  { id: "b1", nama_unit: "Bagian Tata Usaha", eselon: "3", parent_id: "d22" },
];

function pasang(onApply = jest.fn()) {
  axios.get.mockImplementation((url) => {
    if (String(url).endsWith("/unit-kerja")) {
      return Promise.resolve({ data: { items: MASTER, level_akar: 1 } });
    }
    return Promise.resolve({ data: { items: [] } });
  });
  render(<BatchEditPanel selectedCount={3} categories={[]} onApply={onApply}
    onClose={jest.fn()} updating={false} activity={{ id: "k1" }}
    assets={[]} selectedAssets={new Set(["a1", "a2", "a3"])} />);
  return onApply;
}

// Radix mengunci `pointer-events` badan halaman selagi dialognya terbuka dan
// melepasnya SETELAH transisi tutup; klik berikutnya harus menunggu itu.
const pengguna = () => userEvent.setup({ pointerEventsCheck: 0 });

const bukaPemilih = async () => {
  await pengguna().click(await screen.findByTestId("batch-unit-pemicu"));
  return screen.findByTestId("batch-unit-daftar");
};

const pilihUnit = async (id) => {
  await pengguna().click(screen.getByTestId(`batch-unit-opsi-${id}`));
  await waitFor(() => expect(screen.queryByTestId("batch-unit-daftar"))
    .toBeNull());
};

/** Terapkan, lalu setujui konfirmasi "Kosongkan Data Massal" bila muncul —
 *  memilih unit selalu ikut mengosongkan tingkat yang tak terpakai. */
const terapkan = async () => {
  await pengguna().click(screen.getByRole("button", { name: /Terapkan/i }));
  const setuju = await screen.findByTestId("confirm-dialog-confirm");
  await pengguna().click(setuju);
};

beforeEach(() => jest.clearAllMocks());

// ── 1. Pemilih yang sama, bukan `<select>` lama ─────────────────────────

test("memakai pemilih berdialog, bukan select bawaan ber-(E1)", async () => {
  pasang();
  expect(await screen.findByTestId("batch-unit-pemicu")).toBeInTheDocument();
  expect(screen.queryByTestId("batch-unit-select")).toBeNull();
});

test("daftarnya berjenjang dengan lencana, tanpa akhiran (E1)", async () => {
  pasang();
  const daftar = await bukaPemilih();
  expect(within(daftar).getByTestId("batch-unit-opsi-k2"))
    .toHaveTextContent("Es. I");
  expect(within(daftar).getByTestId("batch-unit-opsi-b1"))
    .toHaveTextContent("Es. III");
  expect(within(daftar).queryByText(/\(E1\)/)).toBeNull();
});

test("pencariannya ikut terbawa", async () => {
  pasang();
  await bukaPemilih();
  await pengguna().type(screen.getByTestId("batch-unit-cari"), "tata usaha");
  expect(screen.getByTestId("batch-unit-opsi-b1")).toBeInTheDocument();
  expect(screen.queryByTestId("batch-unit-opsi-k2")).toBeNull();
});

// ── 2. Kata "tak memilih" TETAP berarti jangan ubah ─────────────────────

test("pemicunya berkata JANGAN UBAH, bukan mengajak memilih", async () => {
  pasang();
  expect(await screen.findByTestId("batch-unit-pemicu"))
    .toHaveTextContent(/jangan ubah/i);
});

test("baris peresetnya berkata jangan ubah, bukan kosongkan", async () => {
  const onApply = pasang();
  await bukaPemilih();
  await pilihUnit("d22");
  await bukaPemilih();
  const reset = screen.getByTestId("batch-unit-kosongkan");
  expect(reset).toHaveTextContent(/jangan ubah/i);
  expect(reset).not.toHaveTextContent(/kosongkan pilihan/i);
  expect(onApply).not.toHaveBeenCalled();
});

test("keterangannya menyebut SELURUH aset terpilih", async () => {
  // Ubah massal tak menanyakan ulang per aset; jangkauannya harus disebut di
  // tempat pilihannya dibuat.
  pasang();
  await bukaPemilih();
  expect(screen.getByText(/SELURUH aset terpilih/)).toBeInTheDocument();
});

// ── 3. Yang benar-benar dikirim ─────────────────────────────────────────

test("memilih unit mengisi jalur eselonnya, tingkat sisanya dikosongkan", async () => {
  // Sisa unit sebelumnya yang tertinggal terbaca sebagai unit yang tak pernah
  // ada di sana — karena itu tingkat tak terpakai dikirim sebagai "__clear__".
  const onApply = pasang();
  await bukaPemilih();
  await pilihUnit("d22");
  await terapkan();
  await waitFor(() => expect(onApply).toHaveBeenCalled());
  const kirim = onApply.mock.calls[0][0];
  expect(kirim.eselon1).toBe("Kedeputian Bidang Transformasi Hijau dan Digital");
  expect(kirim.eselon2).toBe("Direktorat Pengembangan Ekosistem Digital");
  expect(kirim.eselon3).toBe("__clear__");
  expect(kirim.eselon4).toBe("__clear__");
  expect(kirim.eselon5).toBe("__clear__");
});

test("membatalkan pilihan TIDAK mengirim perintah kosongkan", async () => {
  // Cacat yang paling mahal bila keliru: "__clear__" pada eselon1–5 akan
  // MENGHAPUS unit organisasi seluruh aset terpilih sekaligus, padahal
  // penggunanya hanya membatalkan pilihannya.
  const onApply = pasang();
  await bukaPemilih();
  await pilihUnit("d22");
  await bukaPemilih();
  await pengguna().click(screen.getByTestId("batch-unit-kosongkan"));
  await waitFor(() => expect(screen.queryByTestId("batch-unit-daftar"))
    .toBeNull());
  // Tak ada perubahan tersisa, jadi tombol Terapkan pun tak aktif.
  const tombol = screen.getByRole("button", { name: /Terapkan/i });
  expect(tombol).toBeDisabled();
});

test("pilihan terpilih terbaca lagi saat pemilihnya dibuka ulang", async () => {
  pasang();
  await bukaPemilih();
  await pilihUnit("b1");
  expect(screen.getByTestId("batch-unit-pemicu"))
    .toHaveTextContent("Bagian Tata Usaha");
  const daftar = await bukaPemilih();
  expect(within(daftar).getByTestId("batch-unit-opsi-b1"))
    .toHaveAttribute("aria-pressed", "true");
});
