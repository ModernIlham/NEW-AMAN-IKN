/**
 * Kepadatan baris penanda tangan pada dialog detail permintaan TTD.
 *
 * Permintaan pemilik, disertai tangkapan layar: *"perbaiki tampilan ini agar
 * semuanya rapi dan terlihat memanfaatkan ruang yang ada dan sudah diatur
 * sedemikian rupa agar terlihat padat informasi yang ditampilkan."*
 *
 * DUA SEBAB tiap penanda tangan dulu menghabiskan tiga baris penuh:
 *
 * 1. Tombol "Terbitkan Link" berdiri di BARIS SENDIRI, rata kiri, dengan dua
 *    pertiga lebar di sebelahnya kosong.
 * 2. Tombol itu ditulis `h-7` TANPA `min-w-0 min-h-0`, sehingga aturan
 *    tap-target global di `index.css` — `button { min-height:44px;
 *    min-width:44px }` pada ≤1023px — membengkakkannya jadi 44 px; `min-*`
 *    selalu menang atas `height`. Saudara-saudaranya (WhatsApp, Email,
 *    Salin) sudah dikecualikan, yang ini terlewat. Cacat yang sama pernah
 *    membuat ikon ✓/✗ bertumpuk di Pengelola Pengguna (#944).
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import BarisPenandaTangan from "../BarisPenandaTangan";

const SIGNER = {
  signer_id: "s-1", urutan: 1, nama: "Karlinus Ignasius Manek",
  jabatan: "Analis Kebijakan Ahli Madya", nip: "1990",
  status: "aktif", kedaluwarsa_info: { sisa_detik: 13 * 24 * 3600 },
};

function pasang(props = {}) {
  render(<BarisPenandaTangan signer={SIGNER} labelStatus="Giliran aktif"
    onTerbitkan={jest.fn()} {...props} />);
}

describe("Kepadatan", () => {
  test("tombol Terbitkan Link SEBARIS dengan jabatan, bukan barisnya sendiri", () => {
    pasang();
    const tombol = screen.getByTestId("ttd-link-ulang-s-1");
    const jabatan = screen.getByText(/Analis Kebijakan Ahli Madya/);
    // Induk yang sama = satu baris. Dulu tombol ini punya `div` sendiri,
    // menyisakan dua pertiga lebar kosong di sebelahnya.
    expect(tombol.parentElement).toContainElement(jabatan);
  });

  test("Terbitkan Link membawa pengecualian tap-target", () => {
    // Tanpa `min-w-0 min-h-0`, aturan global membengkakkannya jadi 44 px di
    // ≤1023px — tinggi tombol tunggal itulah yang membuat barisnya menganga.
    pasang();
    const kelas = screen.getByTestId("ttd-link-ulang-s-1").className;
    expect(kelas).toContain("min-w-0");
    expect(kelas).toContain("min-h-0");
  });

  test("nama MEMBUNGKUS, tidak dipotong", () => {
    // Dua pill di sebelahnya memakan ~150 px pada layar 400 px, sehingga
    // `truncate` memangkas nama jadi "1. Karlinus Ignas…" — pada dialog yang
    // justru menentukan siapa bertanggung jawab meneken apa. Memadatkan
    // tampilan tak boleh dibayar dengan identitas orang.
    pasang({ signer: { ...SIGNER, nama: "Karlinus Ignasius Manek Wibowo" } });
    const nama = screen.getByText(/Karlinus Ignasius Manek Wibowo/);
    expect(nama.className).not.toContain("truncate");
    expect(nama.className).toContain("break-words");
    // Jabatan TETAP dipotong — ia keterangan, bukan identitas. Tanpa
    // pembanding ini, "jangan potong apa pun" akan lolos juga.
    expect(screen.getByText(/Analis Kebijakan/).className).toContain("truncate");
  });

  test("baris berbagi HANYA muncul setelah tautannya terbit", () => {
    pasang();
    expect(screen.queryByLabelText("Bagikan via WhatsApp")).not.toBeInTheDocument();
    expect(screen.queryByText(/Salin lagi/)).not.toBeInTheDocument();
  });

  test("setelah tautan terbit, tiga tombol berbagi muncul", () => {
    pasang({ link: "https://x/y" });
    expect(screen.getByLabelText("Bagikan via WhatsApp")).toBeInTheDocument();
    expect(screen.getByLabelText("Bagikan via email")).toBeInTheDocument();
    expect(screen.getByText(/Salin lagi/)).toBeInTheDocument();
  });
});

describe("Isi baris", () => {
  test("nomor urut, nama, jabatan, dan NIP tetap tampil", () => {
    pasang();
    expect(screen.getByText("1. Karlinus Ignasius Manek")).toBeInTheDocument();
    expect(screen.getByText(/Analis Kebijakan Ahli Madya · NIP 1990/)).toBeInTheDocument();
  });

  test("status dan sisa waktu berdampingan di baris pertama", () => {
    pasang();
    const nama = screen.getByText("1. Karlinus Ignasius Manek");
    const status = screen.getByText("Giliran aktif");
    expect(nama.parentElement).toContainElement(status);
    expect(nama.parentElement).toContainElement(screen.getByTestId("ttd-sisa-signer-s-1"));
  });

  test("tautan yang mati dikatakan APA ADANYA, bukan sisa waktu palsu", () => {
    pasang({ signer: { ...SIGNER, kedaluwarsa_info: { sisa_detik: -10 } } });
    expect(screen.getByTestId("ttd-sisa-signer-s-1")).toHaveTextContent("Tautan mati");
  });
});

describe("Keadaan yang menyembunyikan aksi", () => {
  test("yang SUDAH meneken tak punya tombol terbitkan maupun sisa waktu", () => {
    // Menerbitkan ulang tautan orang yang sudah meneken tak ada gunanya.
    pasang({ signer: { ...SIGNER, status: "ditandatangani" }, labelStatus: "Sudah TTD" });
    expect(screen.queryByTestId("ttd-link-ulang-s-1")).not.toBeInTheDocument();
    expect(screen.queryByTestId("ttd-sisa-signer-s-1")).not.toBeInTheDocument();
  });

  test("permintaan DIBATALKAN menyembunyikan aksi dan pratinjau TTD", () => {
    // Endpoint gambarnya menolak (410) sesudah pembatalan, sehingga <img>
    // berubah jadi ikon rusak.
    pasang({
      signer: { ...SIGNER, status: "ditandatangani", signature_file_id: "g1" },
      dibatalkan: true, gambarTtd: "/gambar.png", labelStatus: "Sudah TTD",
    });
    expect(screen.queryByTestId("ttd-link-ulang-s-1")).not.toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  test("pratinjau TTD tampil bila sudah meneken dan TIDAK dibatalkan", () => {
    pasang({
      signer: { ...SIGNER, status: "ditandatangani", signature_file_id: "g1" },
      gambarTtd: "/gambar.png", labelStatus: "Sudah TTD",
    });
    expect(screen.getByRole("img")).toBeInTheDocument();
  });
});

describe("Tindakan tersambung", () => {
  test("menekan Terbitkan Link memanggil penanganannya", () => {
    const onTerbitkan = jest.fn();
    pasang({ onTerbitkan });
    fireEvent.click(screen.getByTestId("ttd-link-ulang-s-1"));
    expect(onTerbitkan).toHaveBeenCalledTimes(1);
  });

  test("tiga tombol berbagi memanggil penanganannya masing-masing", () => {
    const onWhatsapp = jest.fn(); const onEmail = jest.fn(); const onSalin = jest.fn();
    pasang({ link: "https://x/y", onWhatsapp, onEmail, onSalin });
    fireEvent.click(screen.getByLabelText("Bagikan via WhatsApp"));
    fireEvent.click(screen.getByLabelText("Bagikan via email"));
    fireEvent.click(screen.getByText(/Salin lagi/));
    expect(onWhatsapp).toHaveBeenCalledTimes(1);
    expect(onEmail).toHaveBeenCalledTimes(1);
    expect(onSalin).toHaveBeenCalledTimes(1);
  });
});

/**
 * Fungsi yang MASUK saat baris ini dipadatkan sesudah #943/#946 mendarat di
 * main: pemeriksaan validator, deklarasi jumlah area, dan tindakan
 * validasi/buka-ulang. Pemadatan tak boleh menghilangkan satu pun.
 */
describe("Tahap validasi tetap utuh", () => {
  const MENUNGGU = { ...SIGNER, status: "menunggu_validasi",
    signature_file_id: "f-1", kedaluwarsa_info: { sisa_detik: 3600 } };

  test("tautan TIDAK boleh diterbitkan ulang saat menunggu validasi", () => {
    // Tautan baru mematikan yang lama. Orang yang bubuhannya sudah masuk dan
    // sedang menunggu validator justru akan kehilangan bubuhan itu, jadi
    // "belum ditandatangani" bukan syarat yang benar — daftar-putih-lah.
    pasang({ signer: MENUNGGU, bisaValidasi: true });
    expect(screen.queryByTestId("ttd-link-ulang-s-1")).not.toBeInTheDocument();
    // Pembanding: pada status `aktif` tombolnya memang ada.
    expect(screen.queryByTestId("ttd-sisa-signer-s-1")).not.toBeInTheDocument();
  });

  test("tombol Validasi Sesuai dan Buka Ulang muncul lalu terpanggil", () => {
    const onValidasi = jest.fn();
    const onBukaUlang = jest.fn();
    pasang({ signer: MENUNGGU, bisaValidasi: true, onValidasi, onBukaUlang });
    fireEvent.click(screen.getByTestId("ttd-validasi-s-1"));
    fireEvent.click(screen.getByTestId("ttd-buka-ulang-s-1"));
    expect(onValidasi).toHaveBeenCalledTimes(1);
    expect(onBukaUlang).toHaveBeenCalledTimes(1);
  });

  test("tindakan validator hilang saat permintaannya batal/selesai", () => {
    pasang({ signer: MENUNGGU, bisaValidasi: false });
    expect(screen.queryByTestId("ttd-validasi-s-1")).not.toBeInTheDocument();
    expect(screen.queryByTestId("ttd-buka-ulang-s-1")).not.toBeInTheDocument();
  });

  test("yang sudah terverifikasi hanya boleh dibuka ulang, bukan divalidasi lagi", () => {
    pasang({ signer: { ...MENUNGGU, status: "terverifikasi" }, bisaValidasi: true });
    expect(screen.queryByTestId("ttd-validasi-s-1")).not.toBeInTheDocument();
    expect(screen.getByTestId("ttd-buka-ulang-s-1")).toBeInTheDocument();
  });

  test("tombol validator ikut dikecualikan dari tap-target 44 px", () => {
    pasang({ signer: MENUNGGU, bisaValidasi: true });
    for (const id of ["ttd-validasi-s-1", "ttd-buka-ulang-s-1"]) {
      const kelas = screen.getByTestId(id).className;
      expect(kelas).toMatch(/\bmin-w-0\b/);
      expect(kelas).toMatch(/\bmin-h-0\b/);
    }
  });

  test("deklarasi jumlah area tetap ditampilkan utuh", () => {
    // Dasar keputusan validator — sengaja TIDAK ikut dipadatkan.
    pasang({
      signer: { ...MENUNGGU, deklarasi_tanpa_area: true,
        deklarasi_jumlah_aktual: 1, deklarasi_jumlah_diminta: 3,
        deklarasi_catatan: "Halaman 4 tak ada kolomnya" },
      bisaValidasi: true,
    });
    const kotak = screen.getByTestId("ttd-deklarasi-s-1");
    expect(kotak).toHaveTextContent("1 dari 3");
    expect(kotak).toHaveTextContent("Halaman 4 tak ada kolomnya");
  });

  test("catatan hasil verifikasi ikut tampil", () => {
    pasang({
      signer: { ...MENUNGGU, status: "terverifikasi",
        validated_at: "2026-08-30T10:00:00Z", validated_at_teks: "30 Agu 2026 17.00",
        validated_by: "Ilham", validation_note: "Sesuai" },
      bisaValidasi: true,
    });
    expect(screen.getByText(/Diverifikasi 30 Agu 2026 17\.00 oleh Ilham · Sesuai/))
      .toBeInTheDocument();
  });

  test("pratinjau bubuhan tampil sejak menunggu validasi, bukan hanya setelah selesai", () => {
    // Justru DI SINI validator perlu melihatnya.
    pasang({ signer: MENUNGGU, gambarTtd: "/gambar.png", bisaValidasi: true });
    expect(screen.getByAltText(/TTD Karlinus/)).toBeInTheDocument();
  });
});
