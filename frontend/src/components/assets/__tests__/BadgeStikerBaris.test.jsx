/**
 * Badge/kolom STIKER di ketiga tampilan baris aset.
 *
 * Permintaan pemilik, dua tahap. Pertama: *"ketika status stiker belum
 * terpasang akan tetapi sudah terdapat informasi ukuran stikernya … jangan
 * berikan badge belum stiker saja akan tetapi tetap tulis stiker kecil,
 * sedang atau besarnya juga."* Lalu, dengan contoh gambar: *"perbagus lagi
 * dan sesuaikan dengan warna yang sudah ada di sistem … perjelas juga
 * informasi di kolom stiker di data row agar cukup dengan icon atau makna
 * icon dan warna saja dapat langsung mudah dipahami. dan pada pop up …
 * tambahkan informasi … terkait ukuran stikernya, cukup (| S, | M, | L)
 * dengan font Bold aja."*
 *
 * Keadaan "belum terpasang tetapi ukurannya sudah dipilih" bukan keadaan
 * ganjil melainkan keadaan NORMAL: ukuran dipilih dulu (itulah gunanya mode
 * cetak "sesuai pilihan tiap aset"), stikernya dicetak, baru ditempel.
 * Sepanjang jeda itu tampilan lama membuang satu-satunya keterangan yang
 * sedang dibutuhkan petugas.
 */
import React from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import AssetMobileCard from "../AssetMobileCard";
import BadgeStiker from "../BadgeStiker";

const DASAR = {
  id: "a1", asset_code: "3050102001", asset_name: "Laptop", category: "Alat",
};
const belum = (ukuran) => ({
  ...DASAR, stiker_status: "Belum Terpasang", stiker_ukuran: ukuran,
});
const sudah = (ukuran) => ({
  ...DASAR, stiker_status: "Sudah Terpasang", stiker_ukuran: ukuran,
});

describe("badge stiker", () => {
  it.each([["Kecil", "S"], ["Sedang", "M"], ["Besar", "L"]])(
    "belum terpasang: ukuran %s tampil sebagai huruf tebal %s",
    (ukuran, huruf) => {
      render(<BadgeStiker asset={belum(ukuran)} />);
      const cap = screen.getByTestId("badge-stiker-ukuran");
      expect(cap).toHaveTextContent(huruf);
      // Tebal — permintaan pemilik menyebut "font Bold" secara khusus.
      expect(cap.className).toMatch(/font-bold/);
    });

  it("ukuran tak dikenal tak memunculkan tutup huruf", () => {
    // Kolom ini pernah berupa isian bebas; satu huruf yang dipaksakan akan
    // menampilkan ukuran yang SALAH, bukan sekadar tak lengkap.
    render(<BadgeStiker asset={belum("5x3cm")} />);
    expect(screen.queryByTestId("badge-stiker-ukuran")).toBeNull();
    // …tetapi nilainya tetap disebut pada tooltip.
    expect(screen.getByTestId("badge-stiker"))
      .toHaveAttribute("title", expect.stringContaining("5x3cm"));
  });

  it("belum terpasang tanpa ukuran: hanya pil abu, tanpa tutup", () => {
    render(<BadgeStiker asset={belum("")} />);
    expect(screen.queryByTestId("badge-stiker-ukuran")).toBeNull();
    expect(screen.getByText("Belum Stiker")).toBeInTheDocument();
  });

  it("ikon label DICORET hanya saat belum terpasang", () => {
    const { unmount } = render(<BadgeStiker asset={belum("Kecil")} />);
    expect(screen.getByTestId("ikon-stiker-belum")).toBeInTheDocument();
    unmount();
    render(<BadgeStiker asset={sudah("Kecil")} />);
    expect(screen.queryByTestId("ikon-stiker-belum")).toBeNull();
  });

  it("WARNA menandai status, bukan ukuran", () => {
    // Di contoh pemilik tutup S/M/L-nya hijau. Hijau di aplikasi ini sudah
    // berarti "sudah terpasang", jadi tutup hijau pada badge "belum" akan
    // membuat satu badge mengatakan dua hal yang berlawanan.
    const { unmount } = render(<BadgeStiker asset={belum("Besar")} />);
    const badgeBelum = screen.getByTestId("badge-stiker");
    expect(badgeBelum.className + badgeBelum.innerHTML).not.toMatch(/emerald/);
    unmount();
    render(<BadgeStiker asset={sudah("Besar")} />);
    const badgeSudah = screen.getByTestId("badge-stiker");
    expect(badgeSudah.innerHTML).toMatch(/emerald/);
  });

  it("tiap bagian punya pasangan warna gelap", () => {
    // Badge dipakai di kartu yang ikut mode gelap; kelas terang tanpa
    // pasangan `dark:` menghasilkan teks gelap di atas latar gelap.
    render(<BadgeStiker asset={sudah("Kecil")} />);
    const html = screen.getByTestId("badge-stiker").innerHTML;
    expect(html).toMatch(/dark:bg-emerald/);
    expect(html).toMatch(/dark:text-emerald/);
  });
});

describe("baris HP memakai badge itu", () => {
  it("badge terpasang di kartu HP, bukan hanya lulus tersendiri", () => {
    render(<AssetMobileCard asset={belum("Sedang")} />);
    const badge = screen.getByTestId("badge-stiker");
    expect(within(badge).getByTestId("badge-stiker-ukuran")).toHaveTextContent("M");
    expect(within(badge).getByTestId("ikon-stiker-belum")).toBeInTheDocument();
  });
});

// ── Tabel desktop & kartu galeri ────────────────────────────────────────
//
// Tabel desktop memakai @tanstack/react-virtual, yang mengukur tinggi elemen
// gulir sungguhan — di jsdom tingginya 0, jadi TAK SATU BARIS PUN dirender dan
// uji apa pun terhadap isinya akan lulus tanpa arti.
jest.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count }) => ({
    getTotalSize: () => count * 44,
    getVirtualItems: () => Array.from({ length: count }, (_, index) => ({
      index, key: index, start: index * 44, size: 44,
    })),
  }),
}));

describe("kolom stiker di tabel desktop", () => {
  const { TooltipProvider } = require("@/components/ui/tooltip");
  const VirtualizedAssetTable = require("../VirtualizedAssetTable").default;
  const pasang = (assets) => render(
    <TooltipProvider>
      <VirtualizedAssetTable assets={assets} pageSize={10} />
    </TooltipProvider>);

  it("belum terpasang memakai ikon label DICORET, bukan tanda '-'", () => {
    // Dulu selnya berbunyi "Ya"/"-", dan "-" tak mengatakan apakah stikernya
    // belum dipasang atau datanya memang belum diisi.
    pasang([belum("Kecil")]);
    const sel = screen.getByTestId("stiker-sel-a1");
    expect(within(sel).getByTestId("ikon-stiker-belum")).toBeInTheDocument();
    expect(sel.textContent).not.toMatch(/-/);
  });

  it("ukuran tampil sebagai huruf tebal di selnya", () => {
    pasang([belum("Besar")]);
    expect(screen.getByTestId("stiker-sel-a1")).toHaveTextContent("L");
  });

  it("makna ikon tetap terbaca pembaca layar (status + ukuran)", () => {
    pasang([sudah("Sedang")]);
    expect(screen.getByTestId("stiker-sel-a1"))
      .toHaveAttribute("aria-label", "Stiker: Sudah Terpasang, ukuran Sedang");
  });

  it("sudah terpasang hijau, belum terpasang tidak", () => {
    const { unmount } = pasang([sudah("Kecil")]);
    expect(screen.getByTestId("stiker-sel-a1").className).toMatch(/emerald/);
    unmount();
    pasang([belum("Kecil")]);
    expect(screen.getByTestId("stiker-sel-a1").className).not.toMatch(/emerald/);
  });
});

describe("popup stiker di kartu galeri", () => {
  const AssetGalleryCard = require("../AssetGalleryCard").default;

  // TooltipKetuk (Popover) dibuka hover TETIKUS: `pointerType` selain "mouse"
  // sengaja diabaikan supaya ketukan layar sentuh tak menutup apa yang baru
  // saja dibukanya.
  // Dibuka dengan KLIK, bukan hover: jalur hover TooltipKetuk menyaring
  // `pointerType === "mouse"` lewat onPointerEnter, dan React menyintesis
  // peristiwa itu dari `pointerover` berikut relatedTarget — yang tak
  // dibentuk `fireEvent`. Klik pula yang dipakai pengguna layar sentuh.
  const bukaPopup = async (testid) => {
    fireEvent.click(screen.getByTestId(testid));
    return screen.findByRole("dialog");
  };

  it.each([["Kecil", "S"], ["Sedang", "M"], ["Besar", "L"]])(
    "menyebut ukuran %s sebagai huruf TEBAL %s", async (ukuran, huruf) => {
      render(<AssetGalleryCard asset={belum(ukuran)} />);
      const popup = await bukaPopup("gallery-stiker-a1");
      expect(popup).toHaveTextContent("Stiker: Belum Terpasang");
      // "font Bold" diminta pemilik secara khusus — bukan sekadar hurufnya ada.
      expect(within(popup).getByText(huruf, { selector: "b" }))
        .toBeInTheDocument();
    });

  it("ukuran tak dikenal tetap disebut UTUH, bukan dipaksa jadi huruf", async () => {
    render(<AssetGalleryCard asset={belum("5x3cm")} />);
    const popup = await bukaPopup("gallery-stiker-a1");
    expect(within(popup).getByText("5x3cm", { selector: "b" }))
      .toBeInTheDocument();
  });

  it("tanpa ukuran, popup tak menyisakan pemisah menggantung", async () => {
    render(<AssetGalleryCard asset={belum("")} />);
    const popup = await bukaPopup("gallery-stiker-a1");
    expect(popup.textContent).toBe("Stiker: Belum Terpasang");
  });
});
