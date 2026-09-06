/**
 * Nama penanggung jawab pada kartu kegiatan memakai lebar yang MEMANG ada.
 *
 * Permintaan pemilik: *"pada tampilan hp di bagian daftar kegiatan nama
 * penanggung jawab jadi disingkat, padahal areanya masih luas."*
 *
 * Baris metriknya `flex-wrap`: begitu namanya tak muat di sisa baris, ia turun
 * ke barisnya SENDIRI — dengan lebar kartu penuh di depannya. Patokan
 * `max-w-[100px]` tetap memotongnya di sana, jadi "Karlinus Ign…" berdiri di
 * tengah ruang kosong dua ratus piksel. Patokan itu memang menahan namanya
 * dari mendesak metrik lain, tetapi pembungkusan sudah melakukannya.
 */
import fs from "fs";
import path from "path";
import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";

import ActivitySelectionPage from "../ActivitySelectionPage";

jest.mock("axios");

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../ActivitySelectionPage.jsx"), "utf8");
//: Sumber tanpa komentar — prosa yang menyebut kelasnya tak boleh memuaskan
//: maupun menjatuhkan penjaga struktural.
const KODE = SRC.replace(/\{\/\*[\s\S]*?\*\/\}/g, "").replace(/^\s*\/\/.*$/gm, "");

const PJ = "Karlinus Ignasius Sadipun";
const KEGIATAN = [{
  id: "k1", nama_kegiatan: "Inventarisasi Aset Semester II Tahun 2026",
  nomor_surat: "S-1/2026", ticket_number: "INV-2026-0005",
  kode_satker: "691778", nama_satker: "SATKER D (PP-THD)",
  tanggal_mulai: "2026-01-01", tanggal_selesai: "2026-06-30",
  total_assets: 216, total_value: 2451985101, penanggung_jawab: PJ,
}];

function bukaDaftar() {
  axios.get.mockImplementation((url) => {
    if (String(url).endsWith("/inventory-activities")) {
      return Promise.resolve({ data: KEGIATAN });
    }
    if (String(url).endsWith("/unit-kerja")) {
      return Promise.resolve({ data: { items: [], level_akar: 1 } });
    }
    return Promise.resolve({ data: [] });
  });
  render(<ActivitySelectionPage user={{ role: "admin", kode_satker: "691778" }}
    onLogout={() => {}} onSelectActivity={() => {}} onShowInfo={() => {}}
    onShowModules={() => {}} />);
}

beforeEach(() => jest.clearAllMocks());

test("nama penanggung jawab tercetak UTUH, tak dipotong komponen", async () => {
  bukaDaftar();
  expect(await screen.findByTestId("activity-pj-k1")).toHaveTextContent(PJ);
});

test("tak ada lagi patokan lebar tetap pada nama penanggung jawab", async () => {
  // Yang memotong bukan CSS `truncate` melainkan patokan 100px di depannya;
  // `truncate` sendiri hanya bekerja bila memang kehabisan tempat.
  bukaDaftar();
  const nama = await screen.findByTestId("activity-pj-k1");
  expect(nama.className).not.toMatch(/max-w-\[\d+px\]/);
  expect(nama.className).toContain("truncate");
});

test("pembungkusnya boleh menyusut sampai lebar baris", async () => {
  // Tanpa `min-w-0`, sebuah item flex tak pernah menyusut di bawah lebar
  // isinya — `truncate` di dalamnya jadi mati dan namanya justru meluber.
  bukaDaftar();
  const pembungkus = (await screen.findByTestId("activity-pj-k1")).parentElement;
  expect(pembungkus.className).toContain("min-w-0");
  expect(pembungkus).toHaveAttribute("title", PJ);
});

test("barisnya tetap MEMBUNGKUS, bukan memeras semua metrik jadi sebaris", () => {
  // `flex-wrap` yang hilang membuat ketiga metrik saling menyusut dan
  // ketiganya terpotong — pertukaran yang lebih buruk daripada cacat awalnya.
  const i = KODE.indexOf('data-testid={`activity-pj-');
  expect(i).toBeGreaterThan(-1);
  const baris = KODE.lastIndexOf("<div className=", i);
  expect(KODE.slice(baris, i)).toContain("flex-wrap");
});

test("nama yang benar-benar panjang tetap punya jaring pengaman", () => {
  // `truncate` dipertahankan sebagai batas terakhir; `title` menyimpan yang
  // utuh supaya tak ada yang hilang tanpa jejak.
  const i = KODE.indexOf('data-testid={`activity-pj-');
  const potongan = KODE.slice(i - 400, i + 60);
  expect(potongan).toContain("truncate");
  expect(potongan).toContain("title={act.penanggung_jawab}");
});
