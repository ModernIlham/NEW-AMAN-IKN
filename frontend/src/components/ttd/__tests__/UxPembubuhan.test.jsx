/**
 * UX pembubuhan: klik-untuk-menaruh, navigasi di dekat tombol, input halaman.
 *
 * Permintaan pemilik: *"buat agar ttd tampil ketika diklik posisi bubuhkan di
 * sini ... berikan tombol next dan previous (cukup ikonnya saja) di samping
 * kanan kiri tombol bubuhkan ... di bagian page halaman di atas preview
 * hilangkan next dan previousnya karena sudah di bawah, ganti dengan input
 * manual jika ingin mengganti halaman langsung."*
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import AturPosisiTtd from "../AturPosisiTtd";

const PNG = "data:image/png;base64,iVBORw0KGgo=";

function muat() {
  const g = document.querySelector("img");
  if (g) fireEvent.load(g);
}

function pasang(props = {}) {
  render(
    <AturPosisiTtd jenis="ttd" banyak jumlahHalaman={4} pngTtd={PNG}
      bangunUrlHalaman={(h) => `/uji/${h}.png?token=uji`}
      onKirim={() => {}} onBatal={() => {}} {...props} />);
  muat();
}

/** jsdom memberi ukuran 0 pada semua elemen; wadah dipalsukan 200×400. */
function ukurWadah() {
  const wadah = screen.getByTestId("posisi-wadah");
  wadah.getBoundingClientRect = () => ({
    left: 0, top: 0, width: 200, height: 400, right: 200, bottom: 400,
  });
  return wadah;
}

describe("navigasi halaman", () => {
  test("◀ ▶ hadir mengapit tombol Bubuhkan", () => {
    pasang();
    expect(screen.getByTestId("posisi-prev")).toBeInTheDocument();
    expect(screen.getByTestId("posisi-next")).toBeInTheDocument();
  });

  test("panah TIDAK lagi digandakan di atas pratinjau", () => {
    // Dua tempat untuk pekerjaan yang sama hanya membuat mata memilih.
    pasang();
    expect(screen.getAllByLabelText("Halaman berikutnya")).toHaveLength(1);
    expect(screen.getAllByLabelText("Halaman sebelumnya")).toHaveLength(1);
  });

  test("input halaman melompat LANGSUNG tanpa menekan panah berkali-kali", () => {
    pasang({ jumlahHalaman: 20 });
    fireEvent.change(screen.getByTestId("posisi-halaman-input"),
      { target: { value: "17" } });
    expect(screen.getByTestId("posisi-halaman-input")).toHaveValue(17);
  });

  test("input dijepit ke rentang halaman yang ada", () => {
    pasang();
    const input = screen.getByTestId("posisi-halaman-input");
    fireEvent.change(input, { target: { value: "99" } });
    expect(input).toHaveValue(4);
    fireEvent.change(input, { target: { value: "0" } });
    expect(input).toHaveValue(1);
  });

  test("dokumen satu halaman tak menampilkan navigasi sama sekali", () => {
    pasang({ jumlahHalaman: 1 });
    expect(screen.queryByTestId("posisi-prev")).not.toBeInTheDocument();
    expect(screen.queryByTestId("posisi-halaman-input")).not.toBeInTheDocument();
  });

  test("panah terkunci di ujung-ujungnya", () => {
    pasang();                       // mulai di halaman terakhir (4)
    expect(screen.getByTestId("posisi-next")).toBeDisabled();
    fireEvent.click(screen.getByTestId("posisi-prev"));
    muat();
    expect(screen.getByTestId("posisi-next")).not.toBeDisabled();
  });
});

describe("klik untuk menaruh tanda tangan", () => {
  test("klik memindahkan kotak ke titik yang diklik", () => {
    pasang();
    const wadah = ukurWadah();
    const kotak = screen.getByTestId("posisi-kotak");
    const sebelum = kotak.style.left;
    fireEvent.click(wadah, { clientX: 20, clientY: 40 });
    expect(screen.getByTestId("posisi-kotak").style.left).not.toBe(sebelum);
  });

  test("kotak BERPUSAT pada titik klik, bukan pojoknya", () => {
    // Kalau pojoknya yang diletakkan, tanda tangan jatuh di kanan-bawah jari
    // dan orang harus mengoreksinya setiap kali.
    pasang();
    const wadah = ukurWadah();
    fireEvent.click(wadah, { clientX: 100, clientY: 200 });
    const gaya = screen.getByTestId("posisi-kotak").style;
    const lebar = parseFloat(gaya.width);
    expect(parseFloat(gaya.left) + lebar / 2).toBeCloseTo(50, 0);
  });

  test("klik SESUDAH menyeret diabaikan", () => {
    // Melepas seretan menghasilkan `click` pada wadah; tanpa penjaga, kotak
    // melompat sekali lagi dan membatalkan penempatan yang baru dikerjakan.
    pasang();
    const wadah = ukurWadah();
    const kotak = screen.getByTestId("posisi-kotak");
    fireEvent.mouseDown(kotak, { clientX: 10, clientY: 10 });
    fireEvent.mouseUp(wadah);
    const sebelum = screen.getByTestId("posisi-kotak").style.left;
    fireEvent.click(wadah, { clientX: 180, clientY: 380 });
    expect(screen.getByTestId("posisi-kotak").style.left).toBe(sebelum);
  });

  test("klik berikutnya kembali bekerja", () => {
    pasang();
    const wadah = ukurWadah();
    fireEvent.mouseDown(screen.getByTestId("posisi-kotak"), { clientX: 10, clientY: 10 });
    fireEvent.mouseUp(wadah);
    fireEvent.click(wadah, { clientX: 180, clientY: 380 });   // ditelan penjaga
    const sebelum = screen.getByTestId("posisi-kotak").style.left;
    fireEvent.click(wadah, { clientX: 20, clientY: 40 });     // ini harus jalan
    expect(screen.getByTestId("posisi-kotak").style.left).not.toBe(sebelum);
  });

  test("kotak tak pernah keluar halaman meski diklik di tepi", () => {
    pasang();
    const wadah = ukurWadah();
    fireEvent.click(wadah, { clientX: 0, clientY: 0 });
    const gaya = screen.getByTestId("posisi-kotak").style;
    expect(parseFloat(gaya.left)).toBeGreaterThanOrEqual(0);
    expect(parseFloat(gaya.top)).toBeGreaterThanOrEqual(0);
  });
});
