/**
 * Pemilih unit organisasi pada form aset.
 *
 * Permintaan pemilik: *"saat melakukan pemilihan unit organisasi di bagian
 * inventarisasi aset halaman edit dan tambah saya gampang kebingungan tolong
 * perbagus dan rapikan di tampilan pilihannya di mode layar apapun."*
 *
 * Yang dipatok di sini adalah sebab-sebab kebingungannya, satu per satu:
 * nama induk yang tercetak dua kali, tak adanya pencarian, penanda jenjang
 * yang tersangkut di ujung nama, dan pilihan yang tak terlihat selagi memilih.
 */
import React from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import PemilihUnitOrganisasi from "../PemilihUnitOrganisasi";
import { susunPohonUnit, unitDalamLingkup } from "@/lib/pohonUnit";

//: Struktur dari tangkapan layar pemilik — nama panjang, berawalan sama.
const MASTER = [
  { id: "k1", nama_unit: "Kedeputian Bidang Pengendalian Pembangunan",
    eselon: "1", parent_id: null },
  { id: "d11", nama_unit: "Direktorat Ketentraman dan Ketertiban Umum",
    eselon: "2", parent_id: "k1" },
  { id: "d12", nama_unit: "Direktorat Pengawasan, Pemantauan dan Evaluasi",
    eselon: "2", parent_id: "k1" },
  { id: "k2", nama_unit: "Kedeputian Bidang Transformasi Hijau dan Digital",
    eselon: "1", parent_id: null },
  { id: "d21", nama_unit: "Direktorat Data dan Kecerdasan Buatan",
    eselon: "2", parent_id: "k2" },
];
const POHON = susunPohonUnit(MASTER);

function pasang({ nilai = "", lingkup = [], onPilih = jest.fn() } = {}) {
  render(<PemilihUnitOrganisasi pohon={POHON}
    pilihan={unitDalamLingkup(POHON, lingkup)} nilai={nilai}
    onPilih={onPilih} />);
  return onPilih;
}

const bukaDialog = async () => {
  await userEvent.click(screen.getByTestId("asset-unit-pemicu"));
  return screen.findByTestId("asset-unit-daftar");
};

// ── 1. Nama induk tak lagi tercetak dua kali ────────────────────────────

test("nama Kedeputian muncul SEKALI, bukan dua kali berturut-turut", async () => {
  // Cacat aslinya: `<optgroup>` mencetaknya sekali sebagai pilihan yang dapat
  // disentuh, lalu tepat di bawahnya sebagai judul kelompok yang tidak.
  pasang();
  const daftar = await bukaDialog();
  const muncul = within(daftar).getAllByText(
    "Kedeputian Bidang Pengendalian Pembangunan");
  expect(muncul).toHaveLength(1);
});

test("tiap baris daftar dapat disentuh — tak ada judul kelompok yang mati", async () => {
  pasang();
  const daftar = await bukaDialog();
  const opsi = within(daftar).getAllByRole("button");
  expect(opsi).toHaveLength(MASTER.length);
  opsi.forEach((b) => expect(b).toBeEnabled());
});

test("induk yang TAK tampak tetap diceritakan sebagai keterangan", async () => {
  // Lingkup yang hanya mencatat Direktorat: induknya di luar daftar, jadi
  // tak ada jorokan yang dapat menyatakan hubungannya.
  pasang({ lingkup: ["d11", "d21"] });
  const daftar = await bukaDialog();
  expect(within(daftar).getByText(
    "Kedeputian Bidang Pengendalian Pembangunan")).toBeInTheDocument();
  expect(within(daftar).getByTestId("asset-unit-opsi-d11"))
    .toHaveTextContent("Direktorat Ketentraman dan Ketertiban Umum");
});

// ── 2. Pencarian ────────────────────────────────────────────────────────

test("mengetik nama menyaring daftarnya", async () => {
  pasang();
  await bukaDialog();
  await userEvent.type(screen.getByTestId("asset-unit-cari"), "kecerdasan");
  expect(screen.getByTestId("asset-unit-opsi-d21")).toBeInTheDocument();
  expect(screen.queryByTestId("asset-unit-opsi-d11")).toBeNull();
});

test("mengetik nama INDUK memunculkan Direktorat di bawahnya", async () => {
  // Yang diingat orang kerap Kedeputiannya, bukan nama Direktorat yang
  // panjang dan berawalan sama.
  pasang();
  await bukaDialog();
  await userEvent.type(screen.getByTestId("asset-unit-cari"), "transformasi");
  expect(screen.getByTestId("asset-unit-opsi-d21")).toBeInTheDocument();
  expect(screen.getByTestId("asset-unit-opsi-k2")).toBeInTheDocument();
  expect(screen.queryByTestId("asset-unit-opsi-k1")).toBeNull();
});

test("pencarian tanpa hasil BERKATA, bukan menampilkan daftar kosong", async () => {
  pasang();
  await bukaDialog();
  await userEvent.type(screen.getByTestId("asset-unit-cari"), "hantu");
  expect(screen.getByText(/Tak ada unit yang cocok/)).toBeInTheDocument();
});

// ── 3. Jenjang jadi lencana di DEPAN nama ───────────────────────────────

test("jenjang tercetak sebagai lencana Romawi, bukan (E1) di ujung nama", async () => {
  // "(E1)" tersangkut di ujung nama yang membungkus, jadi ia mendarat di
  // tengah baris ketiga dan berhenti menjadi penanda.
  pasang();
  const daftar = await bukaDialog();
  expect(within(daftar).getByTestId("asset-unit-opsi-k1"))
    .toHaveTextContent("Es. I");
  expect(within(daftar).getByTestId("asset-unit-opsi-d11"))
    .toHaveTextContent("Es. II");
  expect(within(daftar).queryByText(/\(E1\)/)).toBeNull();
});

// ── 4. Yang terpilih terlihat, dan dapat dikosongkan ────────────────────

test("pemicunya menyebut unit terpilih beserta jalur induknya", async () => {
  pasang({ nilai: "d21" });
  const pemicu = screen.getByTestId("asset-unit-pemicu");
  expect(pemicu).toHaveTextContent("Direktorat Data dan Kecerdasan Buatan");
  expect(pemicu).toHaveTextContent("Kedeputian Bidang Transformasi Hijau dan Digital");
});

test("tanpa pilihan, pemicunya mengajak memilih", async () => {
  pasang();
  expect(screen.getByTestId("asset-unit-pemicu"))
    .toHaveTextContent("Pilih unit organisasi");
});

test("baris terpilih bertanda di dalam daftar", async () => {
  pasang({ nilai: "d21" });
  const daftar = await bukaDialog();
  expect(within(daftar).getByTestId("asset-unit-opsi-d21"))
    .toHaveAttribute("aria-pressed", "true");
  expect(within(daftar).getByTestId("asset-unit-opsi-d11"))
    .toHaveAttribute("aria-pressed", "false");
});

test("memilih mengembalikan id-nya lalu menutup dialog", async () => {
  const onPilih = pasang();
  await bukaDialog();
  await userEvent.click(screen.getByTestId("asset-unit-opsi-d12"));
  expect(onPilih).toHaveBeenCalledWith("d12");
  expect(screen.queryByTestId("asset-unit-daftar")).toBeNull();
});

test("mengosongkan hanya ditawarkan saat ADA yang terpilih", async () => {
  pasang();
  await bukaDialog();
  expect(screen.queryByTestId("asset-unit-kosongkan")).toBeNull();
});

test("mengosongkan mengirim nilai kosong, bukan membiarkan yang lama", async () => {
  const onPilih = pasang({ nilai: "d21" });
  await bukaDialog();
  await userEvent.click(screen.getByTestId("asset-unit-kosongkan"));
  expect(onPilih).toHaveBeenCalledWith("");
});

test("pencarian direset saat dialog ditutup", async () => {
  // Kalau tidak, membukanya lagi menampilkan daftar yang sudah tersaring
  // tanpa sebab yang terlihat — daftarnya terbaca seperti kehilangan isi.
  pasang();
  await bukaDialog();
  await userEvent.type(screen.getByTestId("asset-unit-cari"), "kecerdasan");
  await userEvent.click(screen.getByTestId("asset-unit-opsi-d21"));
  await bukaDialog();
  expect(screen.getByTestId("asset-unit-cari")).toHaveValue("");
  expect(screen.getByTestId("asset-unit-opsi-d11")).toBeInTheDocument();
});
