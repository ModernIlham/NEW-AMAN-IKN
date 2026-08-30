/**
 * Tata letak halaman Pengelola Pengguna.
 *
 * Laporan pemilik: *"tombol rename nama sangat mengganggu, tolong perbaiki
 * tata letaknya, cukup taruh di samping nama dengan rapi. Dan untuk tombol
 * centang dan silang ketika rename aktif, ikon bertumpuk/overlapping dengan
 * yang lainnya. Dan tanda silang close halaman kelola pengguna dan semuanya
 * juga ketika tambah user, ukurannya bisakah buat design yang lebih baik."*
 *
 * AKAR KETUMPANGANNYA, dan kenapa ia tak terlihat di mesin pengembang.
 *
 * `frontend/src/index.css` memasang aturan tap-target global::
 *
 *     @media (max-width: 1023px) { button, a { min-height: 44px; min-width: 44px; } }
 *
 * dan `min-*` SELALU menang atas `width`/`height` — riwayat ini sudah tercatat
 * di berkas itu sendiri. Tombol ✓ dan ✗ mode ubah-nama ditulis `p-0.5` tanpa
 * pengecualian `min-w-0 min-h-0`, jadi di ponsel keduanya membengkak menjadi
 * **44×44 px** dan dijejalkan ke kolom sempit yang pada saat bersamaan masih
 * memuat indikator peran, sakelar aktif, dan panah lipat. Di layar lebar
 * aturannya tak berlaku dan semuanya tampak baik-baik saja.
 *
 * jsdom tak menghitung tata letak, jadi uji ini mengunci SEBABNYA, bukan
 * pikselnya: tombol kecil di dalam baris padat wajib membawa pengecualian,
 * dan kontrol yang tak relevan wajib menyingkir selama menyunting.
 */
import React from "react";
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import axios from "axios";
import UserManagementDialog from "../UserManagementDialog";

jest.mock("axios");
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

const ADMIN = { id: "adm-1", role: "admin", name: "Admin Satu" };
const PENGGUNA = [
  { id: "u-1", username: "budi@x.id", name: "Budi Santoso", role: "operator",
    is_active: true, is_online: true },
  { id: "u-2", username: "sari@x.id", name: "Sari Dewi", role: "viewer",
    is_active: true, is_online: false },
];

/** Tiruan API. WAJIB dipanggil sebelum render mana pun: komponen menembak
 *  `/satker` di useEffect tanpa menunggu, jadi tanpa tiruan ia meledak
 *  `Cannot read properties of undefined (reading 'then')`. */
function tiruApi(daftar = PENGGUNA) {
  axios.get.mockImplementation((url) =>
    url.includes("/users")
      ? Promise.resolve({ data: daftar })
      : Promise.resolve({ data: { items: [] } }));
  axios.put.mockResolvedValue({ data: {} });
}

function pasang(props = {}) {
  tiruApi();
  render(
    <UserManagementDialog open onClose={jest.fn()} currentUser={ADMIN}
      onRefresh={jest.fn()} {...props} />);
  return screen.findByText("Budi Santoso");
}

/** Baris pengguna sebagai elemen — induk terdekat yang memuat namanya. */
function baris(nama) {
  return screen.getByText(nama).closest("div.flex.items-center");
}

describe("Ubah nama berdiri di samping namanya", () => {
  test("tombolnya ada di baris yang sama dengan nama, tanpa membuka rincian", async () => {
    await pasang();
    const tombol = screen.getByTestId("user-ubah-nama-u-1");
    // Sebelumnya tombol ini terkubur di baris aksi yang baru muncul setelah
    // baris dilipat-buka; kini ia terlihat tanpa tindakan apa pun lebih dulu.
    expect(tombol).toBeVisible();
    expect(baris("Budi Santoso")).toContainElement(tombol);
  });

  test("menekannya membuka kolom isian, bukan melipat baris", async () => {
    await pasang();
    fireEvent.click(screen.getByTestId("user-ubah-nama-u-1"));
    const isian = screen.getByTestId("user-nama-input-u-1");
    expect(isian).toBeVisible();
    expect(isian).toHaveValue("Budi Santoso");
  });

  test("tiap baris punya tombolnya sendiri", async () => {
    await pasang();
    expect(screen.getByTestId("user-ubah-nama-u-1")).toBeInTheDocument();
    expect(screen.getByTestId("user-ubah-nama-u-2")).toBeInTheDocument();
  });
});

describe("Mode ubah nama tidak berdesakan", () => {
  test("kontrol lain baris itu MENYINGKIR selama menyunting", async () => {
    await pasang();
    // Sebelum: peran, sakelar, dan panah lipat semuanya hadir.
    expect(screen.getByTestId("user-rincian-u-1")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("user-ubah-nama-u-1"));
    // Sesudah: hanya isian + ✓ + ✗ yang tersisa di baris itu.
    expect(screen.queryByTestId("user-rincian-u-1")).not.toBeInTheDocument();
    // …dan baris pengguna LAIN tak ikut terpengaruh.
    expect(screen.getByTestId("user-rincian-u-2")).toBeInTheDocument();
  });

  test("✓ dan ✗ membawa pengecualian tap-target", async () => {
    // Tanpa `min-w-0 min-h-0`, aturan global membengkakkan keduanya jadi
    // 44×44 px di ≤1023px — itulah ikon yang bertumpuk. Kelas Tailwind
    // dipakai sebagai proksi: jsdom tak menghitung tata letak, dan kelas
    // memang antarmuka penataan repo ini.
    await pasang();
    fireEvent.click(screen.getByTestId("user-ubah-nama-u-1"));
    for (const id of ["user-nama-simpan-u-1", "user-nama-batal-u-1"]) {
      const kelas = screen.getByTestId(id).className;
      expect(kelas).toContain("min-w-0");
      expect(kelas).toContain("min-h-0");
    }
  });

  test("keduanya punya nama aksesibel — bukan ikon telanjang", async () => {
    await pasang();
    fireEvent.click(screen.getByTestId("user-ubah-nama-u-1"));
    expect(screen.getByLabelText("Simpan nama")).toBeInTheDocument();
    expect(screen.getByLabelText("Batal ubah nama")).toBeInTheDocument();
  });

  test("Escape membatalkan tanpa menyimpan", async () => {
    await pasang();
    fireEvent.click(screen.getByTestId("user-ubah-nama-u-1"));
    fireEvent.keyDown(screen.getByTestId("user-nama-input-u-1"), { key: "Escape" });
    await waitFor(() =>
      expect(screen.queryByTestId("user-nama-input-u-1")).not.toBeInTheDocument());
    expect(axios.put).not.toHaveBeenCalled();
  });

  test("Enter menyimpan", async () => {
    await pasang();
    fireEvent.click(screen.getByTestId("user-ubah-nama-u-1"));
    const isian = screen.getByTestId("user-nama-input-u-1");
    fireEvent.change(isian, { target: { value: "Budi S." } });
    fireEvent.keyDown(isian, { key: "Enter" });
    await waitFor(() => expect(axios.put).toHaveBeenCalled());
    expect(axios.put.mock.calls[0][1]).toEqual({ name: "Budi S." });
  });
});

describe("Tombol tutup", () => {
  test("tutup dialog TIDAK dikecualikan dari sasaran sentuh 44 px", async () => {
    // Ia tindakan utama sebuah dialog. Yang diperbaiki bentuknya, bukan
    // ukurannya — mengecilkannya justru merugikan pemakai ponsel.
    await pasang();
    const kelas = screen.getByTestId("user-mgmt-close").className;
    expect(kelas).not.toContain("min-w-0");
    expect(kelas).not.toContain("min-h-0");
  });

  test("tutup dialog punya kotak yang terlihat saat disentuh", async () => {
    // Ikon 16 px yang mengambang di kotak 44 px tanpa batas tampak hilang.
    await pasang();
    expect(screen.getByTestId("user-mgmt-close").className).toContain("hover:bg-muted");
  });

  test("tutup formulir tambah pengguna punya sorot yang BERBEDA dari diamnya", async () => {
    // Dulu `hover:text-muted-foreground` — warna yang sama persis dengan
    // keadaan diamnya, jadi sorotnya tak melakukan apa pun.
    await pasang();
    fireEvent.click(screen.getByTestId("add-user-btn"));
    const kelas = screen.getByTestId("add-user-batal").className;
    expect(kelas).not.toContain("hover:text-muted-foreground");
    expect(kelas).toContain("hover:text-foreground");
  });

  test("keduanya punya nama aksesibel", async () => {
    await pasang();
    expect(screen.getByLabelText("Tutup pengelola pengguna")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("add-user-btn"));
    expect(screen.getByLabelText("Batalkan penambahan pengguna")).toBeInTheDocument();
  });
});

describe("Teks berbahasa Indonesia", () => {
  test("judul, badan, dan tombol tak lagi berbahasa Inggris", async () => {
    await pasang();
    expect(screen.getByText("Pengelola Pengguna")).toBeInTheDocument();
    expect(screen.getByText(/Tambah pengguna/)).toBeInTheDocument();
    expect(screen.queryByText("Users")).not.toBeInTheDocument();
    expect(screen.queryByText("Tambah user")).not.toBeInTheDocument();
  });

  test("penanda diri sendiri berbunyi 'Anda', bukan 'You'", async () => {
    tiruApi([{ ...PENGGUNA[0], id: ADMIN.id }]);
    render(<UserManagementDialog open onClose={jest.fn()} currentUser={ADMIN}
      onRefresh={jest.fn()} />);
    await screen.findByText("Budi Santoso");
    expect(screen.getByText("Anda")).toBeInTheDocument();
    expect(screen.queryByText("You")).not.toBeInTheDocument();
  });

  test("layar non-admin memakai bahasa Indonesia", async () => {
    tiruApi();
    render(<UserManagementDialog open onClose={jest.fn()}
      currentUser={{ id: "x", role: "viewer" }} onRefresh={jest.fn()} />);
    expect(await screen.findByText("Khusus admin")).toBeInTheDocument();
  });
});

describe("Jumlah pengguna", () => {
  test("dicantumkan di kepala dialog", async () => {
    await pasang();
    const kepala = screen.getByText("Pengelola Pengguna").parentElement;
    expect(within(kepala).getByText("2")).toBeInTheDocument();
  });
});
