/**
 * Perkiraan nomor booking yang BISA DISUNTING.
 *
 * Permintaan pemilik: *"setiap contoh booking perkiraan nomornya bisa diedit
 * dan di tambahkan unsur baru sesuai keinginan. ibaratnya menulis nomer manual
 * kurang lebihnya jadinya seperti dimodifikasi."*
 *
 * Dua hal yang mudah rusak dan tak terlihat dari membaca kode:
 *
 *   1. POSISI SISIPAN. Chip unsur harus mendarat di kursor, bukan di ujung —
 *      "terserah letaknya" itu justru inti permintaannya. Tombol yang mencuri
 *      fokus lebih dulu menghapus posisi kursor, dan setiap unsur akan
 *      menempel di belakang. Kodenya tetap "jalan"; fiturnya yang hilang.
 *   2. KALIMAT PENGAMANNYA. Nomor yang ditulis tangan TIDAK menggeser deret
 *      agenda. Kalau layar tak mengatakannya, operator akan mengira nomor
 *      urut ikut berubah — lalu menulis nomor urut sendiri dan melahirkan
 *      nomor kembar pada surat berikutnya.
 */
import React, { useState } from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import NomorSuntingan, { sisipUnsur } from "@/components/persuratan/NomorSuntingan";

const NOMOR = "B-003/OIKN/VIII/2026";

function Bungkus({ awal = "", unsur = [], nomor = NOMOR }) {
  const [nilai, setNilai] = useState(awal);
  return (
    <>
      <NomorSuntingan nomor={nomor} nilai={nilai} onChange={setNilai}
        unsur={unsur} testid="pra" />
      <span data-testid="nilai">{nilai}</span>
    </>
  );
}

describe("sisipUnsur — penyisipan di posisi kursor", () => {
  test("menyisip tepat di kursor", () => {
    expect(sisipUnsur("B-003/OIKN", "/UND", 5, 5))
      .toEqual({ teks: "B-003/UND/OIKN", kursor: 9 });
  });

  test("seleksi yang ada tergantikan, persis seperti mengetik", () => {
    expect(sisipUnsur("B-003/OIKN", "SETJEN", 6, 10))
      .toEqual({ teks: "B-003/SETJEN", kursor: 12 });
  });

  test("kursor tak dikenal jatuh ke AKHIR, bukan ke awal", () => {
    // Input yang belum pernah difokus melaporkan posisi yang tak bisa
    // dipercaya. Menyisip di depan nomor adalah kebalikan dari yang
    // diinginkan orang yang menekan chip.
    for (const [a, b] of [[null, null], [undefined, undefined], [-1, -1], [99, 99]]) {
      expect(sisipUnsur("B-003", "X", a, b).teks).toBe("B-003X");
    }
  });

  test("akhir sebelum mulai tidak menghapus apa pun", () => {
    expect(sisipUnsur("B-003", "X", 3, 1).teks).toBe("B-0X03");
  });

  test("teks & unsur kosong aman", () => {
    expect(sisipUnsur(null, null, 0, 0)).toEqual({ teks: "", kursor: 0 });
  });
});

describe("Kotak perkiraan nomor", () => {
  test("mula-mula menampilkan nomor otomatis, tanpa kotak isian", () => {
    render(<Bungkus />);
    expect(screen.getByTestId("pra-nomor")).toHaveTextContent(NOMOR);
    expect(screen.queryByTestId("pra-input")).not.toBeInTheDocument();
    expect(screen.getByTestId("pra-ubah")).toBeInTheDocument();
  });

  test("'Ubah nomor' MENGISI kotaknya dengan nomor otomatis", () => {
    // Kotak kosong akan memaksa operator mengetik ulang seluruh nomor —
    // padahal yang diinginkan "dimodifikasi", bukan ditulis dari nol.
    render(<Bungkus />);
    fireEvent.click(screen.getByTestId("pra-ubah"));
    expect(screen.getByTestId("pra-input")).toHaveValue(NOMOR);
    expect(screen.getByTestId("nilai")).toHaveTextContent(NOMOR);
  });

  test("mengetik mengubah nilainya", () => {
    render(<Bungkus awal={NOMOR} />);
    fireEvent.change(screen.getByTestId("pra-input"),
      { target: { value: "B-003/UND/OIKN/VIII/2026" } });
    expect(screen.getByTestId("nilai")).toHaveTextContent("B-003/UND/OIKN/VIII/2026");
  });

  test("'Kembali otomatis' mengosongkan nilainya, bukan menulis nomor", () => {
    // Nilai kosong = "ikut otomatis". Menulis nomor perkiraan ke sana akan
    // MEMBEKUKAN angka yang bisa bergeser sebelum booking benar-benar jalan.
    render(<Bungkus awal="NOMOR-TANGAN" />);
    fireEvent.click(screen.getByTestId("pra-otomatis"));
    expect(screen.getByTestId("nilai")).toHaveTextContent("");
    expect(screen.getByTestId("pra-nomor")).toHaveTextContent(NOMOR);
  });

  test("menyebutkan bahwa deret agenda tak ikut tergeser", () => {
    render(<Bungkus awal={NOMOR} />);
    const catatan = screen.getByTestId("pra-catatan-manual");
    expect(catatan).toHaveTextContent(/tidak menggeser deret/);
    // Nomor otomatisnya tetap terbaca meski kotaknya sedang disunting.
    expect(catatan).toHaveTextContent(NOMOR);
  });
});

describe("Chip unsur tulisan milik satker", () => {
  const UNSUR = ["UND", "SETJEN"];

  test("hanya muncul saat menyunting", () => {
    render(<Bungkus unsur={UNSUR} />);
    expect(screen.queryByTestId("pra-unsur")).not.toBeInTheDocument();
    // Menyunting dimulai dari tombolnya, bukan dari prop — `useState` tak
    // membaca ulang nilai awal saat dirender ulang.
    fireEvent.click(screen.getByTestId("pra-ubah"));
    expect(screen.getByTestId("pra-unsur")).toBeInTheDocument();
    expect(screen.getByTestId("pra-unsur-UND")).toBeInTheDocument();
    expect(screen.getByTestId("pra-unsur-SETJEN")).toBeInTheDocument();
  });

  test("tanpa unsur tersimpan, barisnya tak muncul sama sekali", () => {
    render(<Bungkus awal={NOMOR} unsur={[]} />);
    expect(screen.queryByTestId("pra-unsur")).not.toBeInTheDocument();
  });

  test("menyisip di posisi kursor, bukan di ujung", () => {
    render(<Bungkus awal={NOMOR} unsur={UNSUR} />);
    const input = screen.getByTestId("pra-input");
    input.setSelectionRange(6, 6);            // tepat setelah "B-003/"
    fireEvent.click(screen.getByTestId("pra-unsur-UND"));
    expect(screen.getByTestId("nilai")).toHaveTextContent("B-003/UNDOIKN/VIII/2026");
  });

  test("chip TIDAK mencuri fokus dari kotak nomor", () => {
    // Inilah yang membuat "terserah letaknya" benar-benar bekerja: tanpa
    // preventDefault pada mousedown, fokus (dan posisi kursor) hilang
    // sebelum klik sempat membaca posisinya.
    render(<Bungkus awal={NOMOR} unsur={UNSUR} />);
    const chip = screen.getByTestId("pra-unsur-UND");
    const dicegah = !fireEvent.mouseDown(chip);
    expect(dicegah).toBe(true);
  });
});

describe("Kotak yang belum disunting MENGIKUTI perkiraan terbaru", () => {
  /**
   * Laporan pemilik: *"pada perkiraan nomor, nomernya selalu 003, begitu pun
   * yang backdate — jangan buat statis."*
   *
   * Sekali "Ubah nomor" ditekan, kotaknya membeku pada angka saat itu. Deret
   * agenda terus maju, tanggal surat berganti, sisipan dicentang — semuanya
   * mengubah nomor yang AKAN terbit, sementara kotak itu tetap menunjukkan
   * yang lama. Dan yang lama itulah yang terkirim.
   */
  function Hidup({ awal = "", mula = NOMOR }) {
    const [nilai, setNilai] = useState(awal);
    const [nomor, setNomor] = useState(mula);
    return (
      <>
        <NomorSuntingan nomor={nomor} nilai={nilai} onChange={setNilai}
          testid="pra" />
        <span data-testid="nilai">{nilai}</span>
        <button type="button" data-testid="geser"
          onClick={() => setNomor("B-009/OIKN/VIII/2026")}>geser</button>
      </>
    );
  }

  test("perkiraan bergeser → kotak yang belum diketik ikut bergeser", () => {
    render(<Hidup />);
    fireEvent.click(screen.getByTestId("pra-ubah"));
    expect(screen.getByTestId("pra-input")).toHaveValue(NOMOR);
    fireEvent.click(screen.getByTestId("geser"));
    expect(screen.getByTestId("pra-input")).toHaveValue("B-009/OIKN/VIII/2026");
  });

  test("sekali BENAR-BENAR diketik, ia berhenti mengikuti", () => {
    // Suntingan operator itu miliknya — perkiraan yang bergeser tak boleh
    // menghapusnya.
    render(<Hidup />);
    fireEvent.click(screen.getByTestId("pra-ubah"));
    fireEvent.change(screen.getByTestId("pra-input"),
      { target: { value: "B-003/UND/OIKN/VIII/2026" } });
    fireEvent.click(screen.getByTestId("geser"));
    expect(screen.getByTestId("pra-input"))
      .toHaveValue("B-003/UND/OIKN/VIII/2026");
  });

  test("kotak tertutup tak menyimpan benih apa pun", () => {
    render(<Hidup />);
    fireEvent.click(screen.getByTestId("geser"));
    expect(screen.queryByTestId("pra-input")).not.toBeInTheDocument();
    expect(screen.getByTestId("pra-nomor"))
      .toHaveTextContent("B-009/OIKN/VIII/2026");
  });

  test("kembali otomatis lalu ubah lagi memakai perkiraan TERBARU", () => {
    render(<Hidup />);
    fireEvent.click(screen.getByTestId("pra-ubah"));
    fireEvent.click(screen.getByTestId("geser"));
    fireEvent.click(screen.getByTestId("pra-otomatis"));
    fireEvent.click(screen.getByTestId("pra-ubah"));
    expect(screen.getByTestId("pra-input")).toHaveValue("B-009/OIKN/VIII/2026");
  });
});
