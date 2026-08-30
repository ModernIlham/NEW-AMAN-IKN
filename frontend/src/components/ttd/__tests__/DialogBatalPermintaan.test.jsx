/**
 * Kotak alasan pembatalan permintaan TTD.
 *
 * Permintaan pemilik: *"ketika diklik pembatalan permintaan di ttd
 * elektronik, munculkan kotak penjelasan alasannya kenapa."*
 *
 * Menggantikan konfirmasi ya/tidak. Konfirmasi menahan salah-tekan, tetapi
 * tak menjawab pertanyaan yang PASTI muncul sesudahnya: seluruh tautan
 * penanda tangan mati permanen, dan bila permintaan menaut BAST maka BAST
 * beserta asetnya ditandai "TT dicabut".
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import DialogBatalPermintaan, { MIN_ALASAN_BATAL } from "../DialogBatalPermintaan";

const PERMINTAAN = {
  id: "sr-1", judul: "BAST-052/SATKER-D/OIKN/VIII/2026",
  doc_type: "dokumen_unggahan",
};

function pasang(props = {}) {
  const api = { onAlasan: jest.fn(), onBatalkan: jest.fn(), onTutup: jest.fn() };
  const r = render(<DialogBatalPermintaan permintaan={PERMINTAAN} {...api} {...props} />);
  return { ...api, ...r };
}

const konfirmasi = () => screen.getByTestId("ttd-batal-konfirmasi");

describe("Kotak alasan muncul", () => {
  test("dialog memuat kotak isian alasan, bukan sekadar ya/tidak", () => {
    pasang();
    expect(screen.getByTestId("ttd-batal-alasan")).toBeInTheDocument();
    expect(screen.getByLabelText(/Alasan pembatalan/)).toBeInTheDocument();
  });

  test("judul permintaan ikut disebut agar tak salah dokumen", () => {
    pasang();
    expect(screen.getByText(/BAST-052\/SATKER-D\/OIKN\/VIII\/2026/)).toBeInTheDocument();
  });

  test("tidak muncul sama sekali tanpa permintaan", () => {
    pasang({ permintaan: null });
    expect(screen.queryByTestId("ttd-batal-alasan")).not.toBeInTheDocument();
  });
});

describe("Alasan wajib", () => {
  test("tombol pembatalan mati saat alasan kosong", () => {
    pasang({ alasan: "" });
    expect(konfirmasi()).toBeDisabled();
  });

  test("spasi saja tidak dihitung sebagai alasan", () => {
    // Lolos uji tak-kosong, tetapi tak menjelaskan apa pun.
    pasang({ alasan: "     " });
    expect(konfirmasi()).toBeDisabled();
  });

  test("alasan lebih pendek dari ambang masih ditolak", () => {
    pasang({ alasan: "x".repeat(MIN_ALASAN_BATAL - 1) });
    expect(konfirmasi()).toBeDisabled();
  });

  test("alasan memadai membuka tombol dan meneruskannya", () => {
    const { onBatalkan } = pasang({ alasan: "Dokumen salah unggah" });
    expect(konfirmasi()).toBeEnabled();
    fireEvent.click(konfirmasi());
    expect(onBatalkan).toHaveBeenCalledTimes(1);
  });

  test("mengetik meneruskan teksnya ke pemanggil", () => {
    const { onAlasan } = pasang();
    fireEvent.change(screen.getByTestId("ttd-batal-alasan"),
      { target: { value: "Penanda tangan pensiun" } });
    expect(onAlasan).toHaveBeenCalledWith("Penanda tangan pensiun");
  });
});

describe("Akibat yang disebutkan", () => {
  test("selalu menyebut tautan mati permanen", () => {
    pasang();
    expect(screen.getByText(/mati permanen/)).toBeInTheDocument();
  });

  test("permintaan ber-BAST menyebut aset ikut ditandai TT dicabut", () => {
    // Inilah satu-satunya layar tempat pengguna masih bisa mundur, jadi
    // akibat di LUAR modul e-sign harus disebut di sini.
    pasang({ permintaan: { ...PERMINTAAN, doc_type: "bast" } });
    expect(screen.getByText(/BAST yang tertaut beserta asetnya/)).toBeInTheDocument();
  });

  test("permintaan ber-LPB menyebut LPB, bukan BAST", () => {
    pasang({ permintaan: { ...PERMINTAAN, doc_type: "lpb" } });
    expect(screen.getByText(/LPB yang tertaut/)).toBeInTheDocument();
    expect(screen.queryByText(/BAST yang tertaut/)).not.toBeInTheDocument();
  });

  test("dokumen biasa tidak mengarang akibat yang tak terjadi", () => {
    pasang();
    expect(screen.queryByText(/TT dicabut/)).not.toBeInTheDocument();
  });
});

describe("Saat sedang diproses", () => {
  test("kedua tombol dikunci agar tak terkirim dua kali", () => {
    pasang({ alasan: "Dokumen salah unggah", sedangMemproses: true });
    expect(konfirmasi()).toBeDisabled();
    expect(screen.getByTestId("ttd-batal-kembali")).toBeDisabled();
  });
});

describe("Label tombol tidak ambigu", () => {
  test('tombol mundur berbunyi "Kembali", bukan "Batal"', () => {
    // Pada dialog pembatalan, "Batal" berarti dua hal yang berlawanan.
    pasang();
    const mundur = screen.getByTestId("ttd-batal-kembali");
    expect(mundur).toHaveTextContent("Kembali");
    expect(mundur).not.toHaveTextContent(/^Batal$/);
  });

  test("tombol mundur memanggil penutup", () => {
    const { onTutup } = pasang();
    fireEvent.click(screen.getByTestId("ttd-batal-kembali"));
    expect(onTutup).toHaveBeenCalledTimes(1);
  });
});
