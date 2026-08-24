/**
 * Penanda koordinat HADIR di setiap tampilan baris aset.
 *
 * Permintaan pemilik menyebut tempatnya secara eksplisit: *"baik tampilan di
 * list maupun di galeri, dan baik di mode tampilan ukuran layar apa pun."*
 * Komponen ikonnya sendiri sudah diuji tersendiri; yang dijaga DI SINI adalah
 * bahwa ketiga tampilan benar-benar memakainya — uji komponen yang lulus
 * sementara tak satu pun layar memasangnya tidak menjaga apa pun.
 *
 * Termasuk kasus yang paling mudah terlewat: aset yang SUDAH berkoordinat
 * tetapi nama lokasinya masih kosong. Dulu seluruh baris lokasi hanya dirender
 * `if (asset.location)`, sehingga penandanya takkan pernah terlihat justru
 * pada aset yang paling sering belum diisi lokasinya.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import AssetGalleryCard from "../AssetGalleryCard";
import AssetMobileCard from "../AssetMobileCard";

const BERKOORDINAT = {
  id: "a1", asset_code: "3050102001", asset_name: "Laptop", category: "Alat",
  location: "Ruang 101",
  koordinat_latitude: "-1.234567", koordinat_longitude: "116.700000",
};
const TANPA_LOKASI = {
  ...BERKOORDINAT, id: "a2", location: "",
};
const TANPA_APAPUN = {
  ...BERKOORDINAT, id: "a3", location: "",
  koordinat_latitude: "", koordinat_longitude: "",
};

const TAMPILAN = [
  ["galeri", (asset) => <AssetGalleryCard asset={asset} />],
  ["list mobile", (asset) => <AssetMobileCard asset={asset} />],
];

describe.each(TAMPILAN)("tampilan %s", (_nama, buat) => {
  test("aset berkoordinat memakai pin bercentang", () => {
    render(buat(BERKOORDINAT));
    expect(screen.getByTestId("lokasi-ikon-a1"))
      .toHaveAttribute("data-berkoordinat", "ya");
  });

  test("aset tanpa koordinat memakai pin biasa", () => {
    render(buat({ ...BERKOORDINAT, id: "a9",
                  koordinat_latitude: "", koordinat_longitude: "" }));
    expect(screen.getByTestId("lokasi-ikon-a9"))
      .toHaveAttribute("data-berkoordinat", "tidak");
  });

  test("pin tanpa koordinat ABU-ABU, tak berwarna seperti yang sudah", () => {
    // Laporan pemilik atas tampilan galeri: pin cyan lama terbaca seolah
    // hijau, sehingga aset yang BELUM berkoordinat tampak sudah. Diuji di
    // SEMUA tampilan supaya tak ada satu layar pun yang kembali menyimpang.
    render(buat({ ...BERKOORDINAT, id: "a8",
                  koordinat_latitude: "", koordinat_longitude: "" }));
    const kelas = screen.getByTestId("lokasi-ikon-a8").getAttribute("class");
    expect(kelas).toContain("text-muted-foreground");
    expect(kelas).not.toContain("text-emerald-500");
    expect(kelas).not.toContain("text-cyan-500");
  });

  test("berkoordinat TANPA nama lokasi tetap menampilkan penandanya", () => {
    render(buat(TANPA_LOKASI));
    expect(screen.getByTestId("lokasi-ikon-a2"))
      .toHaveAttribute("data-berkoordinat", "ya");
    expect(screen.getByText("Berkoordinat")).toBeInTheDocument();
  });

  test("tanpa lokasi DAN tanpa koordinat: barisnya tetap tak dirender", () => {
    // Penanda bukan alasan menambah baris kosong pada aset yang memang belum
    // punya keterangan lokasi apa pun.
    render(buat(TANPA_APAPUN));
    expect(screen.queryByTestId("lokasi-ikon-a3")).not.toBeInTheDocument();
  });
});


// Tabel desktop memakai @tanstack/react-virtual, yang mengukur tinggi elemen
// gulir sungguhan — di jsdom tingginya 0, jadi TAK SATU BARIS PUN dirender dan
// uji apa pun terhadap isinya akan lulus tanpa arti. Virtualizer-nya diganti
// dengan yang mengembalikan seluruh baris; yang diuji tetap kode perenderan
// barisnya sendiri, bukan pustaka virtualisasinya.
jest.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count }) => ({
    getTotalSize: () => count * 44,
    getVirtualItems: () => Array.from({ length: count }, (_, index) => ({
      index, key: index, start: index * 44, size: 44,
    })),
  }),
}));

describe("tampilan list desktop (tabel)", () => {
  const { TooltipProvider } = require("@/components/ui/tooltip");
  const VirtualizedAssetTable = require("../VirtualizedAssetTable").default;

  const pasang = (assets) => render(
    <TooltipProvider>
      <VirtualizedAssetTable assets={assets} pageSize={10} />
    </TooltipProvider>);

  test("aset berkoordinat memakai pin bercentang", () => {
    pasang([BERKOORDINAT]);
    const ikon = screen.getAllByTestId("lokasi-ikon-a1");
    expect(ikon.length).toBeGreaterThan(0);
    ikon.forEach((el) => expect(el).toHaveAttribute("data-berkoordinat", "ya"));
  });

  test("penanda ringkas dan pin kolom Lokasi TIDAK tampil bersamaan", () => {
    // Kolom Lokasi baru muncul di xl; penanda ringkas mengisi rentang lg..xl.
    // Keduanya memang dirender ke DOM, tetapi `xl:hidden` memastikan hanya
    // SATU yang terlihat pada lebar berapa pun — kalau penjaga itu hilang,
    // satu keterangan akan punya dua penanda di layar lebar.
    pasang([BERKOORDINAT]);
    const ikon = screen.getAllByTestId("lokasi-ikon-a1");
    expect(ikon).toHaveLength(2);
    const ringkas = ikon.filter((el) => el.getAttribute("class").includes("xl:hidden"));
    expect(ringkas).toHaveLength(1);
  });

  test("aset tanpa koordinat: penanda ringkas tak dirender sama sekali", () => {
    // Pin abu-abu di setiap baris hanyalah kebisingan; penanda positif saja,
    // sejalan dengan penanda PSP di sebelahnya.
    pasang([TANPA_APAPUN]);
    const ikon = screen.queryAllByTestId("lokasi-ikon-a3");
    expect(ikon.filter((el) => el.getAttribute("class").includes("xl:hidden")))
      .toHaveLength(0);
  });
});
