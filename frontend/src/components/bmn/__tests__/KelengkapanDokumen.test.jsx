/**
 * Daftar periksa dokumen usulan BMN.
 *
 * Permintaan pemilik: *"agar semua keperluan dokumen untuk segala macam
 * jenis pengusulan BMN dapat ditangani aplikasi dengan baik ... agar
 * pengajuan ke SIMAN V2 dari segala pengusulan kondisi dapat dimanajemen
 * dengan baik."*
 *
 * Uji ini menjaga tiga pembeda dari "daftar sembilan butir wajib" yang
 * beredar: butir tak berlaku tetap terlihat, kekuatan buktinya tertulis,
 * dan muatan surat dibedakan dari lampiran.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import KelengkapanDokumen from "../KelengkapanDokumen";

const BUTIR = (ganti = {}) => ({
  kode: "surat_permohonan", nama: "Surat Permohonan", sifat: "wajib",
  sifat_label: "Wajib", berlaku: true, wajib: true, pemicu: "",
  dasar: "PMK 40/2024 Pasal 11 ayat (1)", verifikasi: "terverifikasi",
  verifikasi_label: "Pasal terbaca", ...ganti,
});

const KELENGKAPAN = (ganti = {}) => ({
  rezim: "psp", rezim_label: "Penetapan Status Penggunaan (PSP)",
  berdasar_pasal: true, butir: [BUTIR()], jumlah_wajib: 1,
  jumlah_terpenuhi: 0, lengkap: false,
  kurang: [{ kode: "surat_permohonan", nama: "Surat Permohonan" }],
  di_luar_daftar: [], ...ganti,
});

describe("Ringkasan", () => {
  test("menyebut angka wajib dan status lengkapnya", () => {
    render(<KelengkapanDokumen kelengkapan={KELENGKAPAN()} />);
    expect(screen.getByTestId("kelengkapan-angka")).toHaveTextContent("0/1 berkas wajib");
    expect(screen.getByText("Belum lengkap")).toBeInTheDocument();
  });

  test("berubah jadi Lengkap saat semuanya terpenuhi", () => {
    render(<KelengkapanDokumen
      kelengkapan={KELENGKAPAN({ jumlah_terpenuhi: 1, lengkap: true, kurang: [] })}
      terunggah={["surat_permohonan"]} />);
    expect(screen.getByText("Lengkap")).toBeInTheDocument();
  });

  test("daftar kosong tidak menampilkan panel palsu", () => {
    render(<KelengkapanDokumen kelengkapan={KELENGKAPAN({ butir: [] })} />);
    expect(screen.getByTestId("kelengkapan-kosong")).toBeInTheDocument();
    expect(screen.queryByTestId("kelengkapan-dokumen")).not.toBeInTheDocument();
  });

  test("tanpa data sama sekali tidak meledak", () => {
    render(<KelengkapanDokumen kelengkapan={null} />);
    expect(screen.getByTestId("kelengkapan-kosong")).toBeInTheDocument();
  });
});

describe("Kejujuran bukti", () => {
  test("rezim yang pasalnya belum terbaca diberi peringatan", () => {
    // Tanpa peringatan ini, daftar tebakan tampak sama berwibawanya dengan
    // daftar yang pasalnya sudah dibaca.
    render(<KelengkapanDokumen kelengkapan={KELENGKAPAN({ berdasar_pasal: false })} />);
    expect(screen.getByTestId("kelengkapan-belum-terverifikasi")).toBeInTheDocument();
  });

  test("rezim berdasar pasal TIDAK diberi peringatan itu", () => {
    render(<KelengkapanDokumen kelengkapan={KELENGKAPAN()} />);
    expect(screen.queryByTestId("kelengkapan-belum-terverifikasi")).not.toBeInTheDocument();
  });

  test("butir dari layar SIMAN membawa lencananya sendiri", () => {
    render(<KelengkapanDokumen kelengkapan={KELENGKAPAN({
      butir: [BUTIR({ kode: "kib", nama: "Kartu Identitas Barang (KIB)",
        verifikasi: "empiris_siman", verifikasi_label: "Terbaca dari layar SIMAN V2" })],
    })} />);
    expect(screen.getByTestId("kelengkapan-verifikasi-kib"))
      .toHaveTextContent("Terbaca dari layar SIMAN V2");
  });

  test("butir berdasar pasal tidak dibubuhi lencana", () => {
    // Melencanai SEMUA baris membuat semuanya tampak sama meragukan, dan
    // justru menghapus perbedaan yang ingin ditunjukkan.
    render(<KelengkapanDokumen kelengkapan={KELENGKAPAN()} />);
    expect(screen.queryByTestId("kelengkapan-verifikasi-surat_permohonan"))
      .not.toBeInTheDocument();
  });

  test("dasar setiap butir selalu tercetak", () => {
    render(<KelengkapanDokumen kelengkapan={KELENGKAPAN()} />);
    expect(screen.getByText(/PMK 40\/2024 Pasal 11 ayat \(1\)/)).toBeInTheDocument();
  });
});

describe("Butir yang tidak berlaku", () => {
  const TAK_BERLAKU = (ganti = {}) => BUTIR({
    kode: "sertipikat", nama: "Fotokopi sertipikat",
    sifat: "wajib_bersyarat", sifat_label: "Wajib bila berlaku",
    berlaku: false, wajib: false, pemicu: "objek_tanah", ...ganti,
  });

  test("tetap ada, tetapi dilipat — bukan dihapus", () => {
    // Menyembunyikannya membuat operator tak pernah tahu ia ada, dan tak
    // bisa menyadari bahwa jawabannya sendirilah yang membuatnya hilang.
    // Menampilkannya semua membuat baris tak relevan menenggelamkan yang
    // wajib — diukur di Chromium, delapan dari 19 baris memakan hampir
    // separuh panel.
    render(<KelengkapanDokumen kelengkapan={KELENGKAPAN({
      butir: [BUTIR(), TAK_BERLAKU()],
    })} />);
    const lipatan = screen.getByTestId("kelengkapan-tak-berlaku");
    expect(lipatan).toHaveTextContent("1 butir tidak berlaku");
    expect(lipatan).toContainElement(screen.getByTestId("kelengkapan-butir-sertipikat"));
  });

  test("butir yang BERLAKU tidak ikut masuk lipatan", () => {
    // Pembanding penting: tanpa ini, "lipat semuanya" akan lolos juga.
    render(<KelengkapanDokumen kelengkapan={KELENGKAPAN({
      butir: [BUTIR(), TAK_BERLAKU()],
    })} />);
    expect(screen.getByTestId("kelengkapan-tak-berlaku"))
      .not.toContainElement(screen.getByTestId("kelengkapan-butir-surat_permohonan"));
  });

  test("lipatan tidak muncul bila semua butir berlaku", () => {
    render(<KelengkapanDokumen kelengkapan={KELENGKAPAN()} />);
    expect(screen.queryByTestId("kelengkapan-tak-berlaku")).not.toBeInTheDocument();
  });

  test("tidak ikut ditandai kurang", () => {
    render(<KelengkapanDokumen kelengkapan={KELENGKAPAN({
      butir: [TAK_BERLAKU()],
      jumlah_wajib: 0, jumlah_terpenuhi: 0, lengkap: true, kurang: [],
    })} />);
    expect(screen.getByTestId("kelengkapan-butir-sertipikat").className)
      .toMatch(/opacity-60/);
  });
});

describe("Muatan surat dibedakan dari lampiran", () => {
  test("butir muatan tidak diperlakukan sebagai berkas yang kurang", () => {
    // Data BMN diminta ADA DI DALAM surat permohonan. Menagihnya sebagai
    // unggahan akan melaporkan "belum lengkap" untuk usulan yang sudah benar.
    render(<KelengkapanDokumen kelengkapan={KELENGKAPAN({
      butir: [BUTIR({ kode: "daftar_bmn", nama: "Daftar BMN yang diusulkan",
        sifat: "muatan", sifat_label: "Muatan surat permohonan", wajib: false })],
      jumlah_wajib: 0, jumlah_terpenuhi: 0, lengkap: true, kurang: [],
    })} />);
    const baris = screen.getByTestId("kelengkapan-butir-daftar_bmn");
    expect(baris).toHaveTextContent("Muatan surat permohonan");
    expect(baris.className).not.toMatch(/border-amber-500/);
  });
});

describe("Berkas yang sudah ada", () => {
  test("butir terpenuhi tidak lagi ditandai kurang", () => {
    render(<KelengkapanDokumen kelengkapan={KELENGKAPAN()}
      terunggah={["surat_permohonan"]} />);
    expect(screen.getByTestId("kelengkapan-butir-surat_permohonan").className)
      .not.toMatch(/border-amber-500/);
  });

  test("butir wajib yang belum ada ditandai", () => {
    render(<KelengkapanDokumen kelengkapan={KELENGKAPAN()} terunggah={[]} />);
    expect(screen.getByTestId("kelengkapan-butir-surat_permohonan").className)
      .toMatch(/border-amber-500/);
  });

  test("berkas berjenis di luar daftar dilaporkan, bukan dibuang diam-diam", () => {
    render(<KelengkapanDokumen
      kelengkapan={KELENGKAPAN({ di_luar_daftar: ["sertipikat"] })} />);
    expect(screen.getByTestId("kelengkapan-di-luar"))
      .toHaveTextContent("1 berkas terunggah dengan jenis di luar daftar");
  });

  test("tanpa berkas di luar daftar barisnya tidak muncul", () => {
    render(<KelengkapanDokumen kelengkapan={KELENGKAPAN()} />);
    expect(screen.queryByTestId("kelengkapan-di-luar")).not.toBeInTheDocument();
  });
});
