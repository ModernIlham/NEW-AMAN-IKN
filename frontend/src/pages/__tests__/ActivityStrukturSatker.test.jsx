/**
 * Struktur ringkas pada form Kegiatan mengikuti tingkat satkernya.
 *
 * Bentuk warisannya hanya punya DUA laci — `[{nama, eselon2: […]}]` — dan
 * keduanya dulu berarti Eselon I dan Eselon II bagi siapa pun. Bagi satker
 * Eselon III seperti Lapas, keduanya adalah tingkat milik instansi induknya:
 * mengisinya berarti mengarang dua tingkat yang tak pernah ia punya, sementara
 * strukturnya yang nyata (Eselon III–IV) tak punya tempat sama sekali.
 *
 * Maknanya kini RELATIF terhadap puncak satker. Yang dipatok di sini:
 *
 * 1. Labelnya menyebut tingkat yang sebenarnya — pada layar, pada tombol
 *    tambah, pada keadaan kosong, dan pada tombol pencocokan lingkup.
 * 2. Akarnya DIBACA, dari master unit satker pengguna maupun dari pencarian
 *    satker yang mengisi form ini.
 * 3. Satker Eselon V tak punya laci kedua — "Eselon VI" bukan tingkat mana pun.
 */
import React from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import ActivitySelectionPage from "../ActivitySelectionPage";

jest.mock("axios");

const ADMIN = { role: "admin", kode_satker: "333333", username: "admin" };

function pasangApi({ akar = 3, lookup = null } = {}) {
  axios.get.mockImplementation((url) => {
    const u = String(url);
    if (u.endsWith("/unit-kerja")) {
      return Promise.resolve({ data: { items: [],
        ...(akar == null ? {} : { level_akar: akar }) } });
    }
    if (u.includes("/satker-lookup")) {
      return Promise.resolve({ data: lookup });
    }
    // Daftar kegiatan & satker datang sebagai ARRAY, bukan {items}.
    return Promise.resolve({ data: [] });
  });
}

async function bukaFormKegiatan(opsi) {
  pasangApi(opsi);
  render(<ActivitySelectionPage user={ADMIN} onLogout={() => {}}
    onSelectActivity={() => {}} onShowInfo={() => {}} onShowModules={() => {}} />);
  await userEvent.click(
    await screen.findByRole("button", { name: /Buat Kegiatan Inventarisasi Baru/i }));
  return screen.findByTestId("label-eselon-puncak");
}

beforeEach(() => jest.clearAllMocks());

// ── 1. Label menyebut tingkat yang sebenarnya ───────────────────────────

test("satker Eselon III melihat labelnya Eselon III, bukan Eselon I", async () => {
  const label = await bukaFormKegiatan({ akar: 3 });
  expect(label).toHaveTextContent("Eselon III");
  expect(screen.getByTestId("add-eselon1-btn")).toHaveTextContent("Tambah Eselon III");
  expect(screen.getByText("Belum ada data Eselon III.")).toBeInTheDocument();
  expect(screen.getByTestId("cocokkan-lingkup-btn"))
    .toHaveTextContent("Ambil dari Eselon III di atas");
});

test("alasannya disebut, bukan hanya labelnya yang berganti", async () => {
  await bukaFormKegiatan({ akar: 3 });
  expect(screen.getByTestId("keterangan-akar-kegiatan"))
    .toHaveTextContent(/Eselon III.*instansi induk/s);
});

test("satker Eselon I tetap melihat Eselon I — persis seperti sebelumnya", async () => {
  const label = await bukaFormKegiatan({ akar: 1 });
  expect(label).toHaveTextContent("Eselon I");
  expect(screen.getByTestId("add-eselon1-btn")).toHaveTextContent("Tambah Eselon I");
  expect(screen.queryByTestId("keterangan-akar-kegiatan")).toBeNull();
});

test("server lama yang belum menyebut level_akar tetap Eselon I", async () => {
  const label = await bukaFormKegiatan({ akar: null });
  expect(label).toHaveTextContent("Eselon I");
});

// ── 2. Tingkat kedua mengikuti, dan tak dikarang ────────────────────────

test("baris pertama membawa tingkat KEDUA satkernya", async () => {
  await bukaFormKegiatan({ akar: 3 });
  await userEvent.click(screen.getByTestId("add-eselon1-btn"));
  expect(await screen.findByPlaceholderText("Nama Eselon III")).toBeInTheDocument();
  expect(screen.getByText("Eselon IV")).toBeInTheDocument();
  expect(screen.getByText("Belum ada Eselon IV.")).toBeInTheDocument();
});

test("satker Eselon V tak punya laci kedua — Eselon VI tak dikarang", async () => {
  await bukaFormKegiatan({ akar: 5 });
  await userEvent.click(screen.getByTestId("add-eselon1-btn"));
  expect(await screen.findByPlaceholderText("Nama Eselon V")).toBeInTheDocument();
  expect(screen.queryByTestId("add-eselon2-btn-0")).toBeNull();
  expect(screen.queryByText(/Eselon VI/)).toBeNull();
});

// ── 3. Akar ikut pencarian satker yang mengisi form ini ─────────────────

test("pencarian satker MENIMPA akar bawaan pengguna", async () => {
  // Kegiatan boleh dibuat untuk satker yang kodenya diketik; tingkat yang
  // benar adalah tingkat satker ITU, bukan satker si pengguna.
  const label = await bukaFormKegiatan({
    akar: 1,
    lookup: { kode_satker: "333333", nama_satker: "Lapas Kelas IIA Nusantara",
      eselon_satker: 3, eselon1: [] },
  });
  expect(label).toHaveTextContent("Eselon I");
  await userEvent.type(screen.getByTestId("input-kode-satker"), "333333");
  await waitFor(() => expect(screen.getByTestId("label-eselon-puncak"))
    .toHaveTextContent("Eselon III"), { timeout: 3000 });
});

test("struktur DAN tingkat datang bersama dari satker yang dicari", async () => {
  // Isi-otomatis mengganti strukturnya dengan milik satker yang ditemukan.
  // Bila tingkatnya tak ikut, baris hasil isi-otomatis itu berlabel Eselon I
  // padahal isinya unit Eselon III — laci yang sama, arti yang bertentangan.
  await bukaFormKegiatan({
    akar: 1,
    lookup: { kode_satker: "333333", nama_satker: "Lapas Kelas IIA Nusantara",
      eselon_satker: 3,
      eselon1: [{ nama: "Lapas Kelas IIA Nusantara",
                  eselon2: ["Subbagian Tata Usaha"] }] },
  });
  await userEvent.type(screen.getByTestId("input-kode-satker"), "333333");
  await waitFor(() => expect(screen.getByTestId("label-eselon-puncak"))
    .toHaveTextContent("Eselon III"), { timeout: 3000 });
  expect(screen.getByTestId("eselon1-input-0"))
    .toHaveValue("Lapas Kelas IIA Nusantara");
  expect(screen.getByTestId("eselon2-input-0-0"))
    .toHaveValue("Subbagian Tata Usaha");
  // Barisnya kini berlabel tingkat yang benar, bukan Eselon I/II.
  expect(screen.getByText("Eselon IV")).toBeInTheDocument();
  expect(screen.queryByText("Eselon II")).toBeNull();
});

// ── 4. Panel lingkup tetap apa adanya ───────────────────────────────────

test("pemilih unit tetap menunjuk master, bukan ikut berganti tingkat", async () => {
  await bukaFormKegiatan({ akar: 3 });
  const panel = screen.getByTestId("cocokkan-lingkup-btn").closest("div");
  expect(within(panel).getByText(/Unit Organisasi untuk Pencatatan Aset/i))
    .toBeInTheDocument();
});
