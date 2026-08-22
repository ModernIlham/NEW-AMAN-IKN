import {
  cariPejabat, labelBawaan, labelPejabat, pejabatSatker, setelSlot,
} from "@/lib/penandatanganSlot";

const DAFTAR = [
  { id: "a", nama: "Andi", jabatan: "Pengurus Barang", kode_satker: "527001" },
  { id: "b", nama: "Budi", jabatan: "", kode_satker: "" },
  { id: "c", nama: "Cici", jabatan: "KPB", kode_satker: "527999" },
];

describe("setelSlot", () => {
  it("menyimpan pilihan baru", () => {
    expect(setelSlot({}, "lpb_dibuat", "a")).toEqual({ lpb_dibuat: "a" });
  });

  it("MENGHAPUS slot ketika pilihannya dilepas — bukan menyimpan string kosong", () => {
    // Mengirim "" akan tersimpan sebagai pilihan kosong dan operator tak
    // pernah bisa kembali mengikuti setelan satker.
    const out = setelSlot({ lpb_dibuat: "a", lpb_disetujui: "c" }, "lpb_dibuat", "");
    expect(out).toEqual({ lpb_disetujui: "c" });
    expect("lpb_dibuat" in out).toBe(false);
  });

  it("membuang sisa nilai kosong yang terlanjur ada di peta", () => {
    expect(setelSlot({ lpb_dibuat: "  ", lpb_diperiksa: "b" }, "lpb_disetujui", "c"))
      .toEqual({ lpb_diperiksa: "b", lpb_disetujui: "c" });
  });

  it("tidak mengubah peta asal", () => {
    const asal = { lpb_dibuat: "a" };
    setelSlot(asal, "lpb_dibuat", "");
    expect(asal).toEqual({ lpb_dibuat: "a" });
  });

  it("memangkas spasi pada id yang dipilih", () => {
    expect(setelSlot({}, "lpb_dibuat", " a ")).toEqual({ lpb_dibuat: "a" });
  });
});

describe("pejabatSatker", () => {
  it("meloloskan pejabat satker sendiri DAN pejabat era-lama tanpa kode", () => {
    expect(pejabatSatker(DAFTAR, "527001").map((p) => p.id)).toEqual(["a", "b"]);
  });

  it("kode kosong (lintas satker) = semua", () => {
    expect(pejabatSatker(DAFTAR, "").map((p) => p.id)).toEqual(["a", "b", "c"]);
  });

  it("tidak membocorkan pejabat satker lain", () => {
    expect(pejabatSatker(DAFTAR, "527001").some((p) => p.id === "c")).toBe(false);
  });
});

describe("labelPejabat", () => {
  it("menggabung nama dan jabatan", () => {
    expect(labelPejabat(DAFTAR[0])).toBe("Andi — Pengurus Barang");
  });
  it("tanpa jabatan hanya nama", () => {
    expect(labelPejabat(DAFTAR[1])).toBe("Budi");
  });
});

describe("labelBawaan", () => {
  const slot = { kunci: "lpb_dibuat", peran: "pengurus_barang", peran_uraian: "Pengurus Barang" };

  it("menyebut nama dari setelan satker bila pejabatnya masih ada", () => {
    expect(labelBawaan(slot, { lpb_dibuat: "a" }, DAFTAR))
      .toBe("Ikut setelan satker — Andi — Pengurus Barang");
  });

  it("jatuh ke peran bila setelan satker menunjuk pejabat yang sudah hilang", () => {
    // Cermin aturan backend: id basi TIDAK mengosongkan slot.
    expect(labelBawaan(slot, { lpb_dibuat: "sudah-dihapus" }, DAFTAR))
      .toBe("Ikut Referensi Pejabat — peran Pengurus Barang");
  });

  it("tanpa setelan satker menyebut peran cadangannya", () => {
    expect(labelBawaan(slot, null, DAFTAR))
      .toBe("Ikut Referensi Pejabat — peran Pengurus Barang");
  });
});

describe("cariPejabat", () => {
  it("id kosong tidak pernah cocok", () => {
    expect(cariPejabat(DAFTAR, "")).toBeNull();
    expect(cariPejabat(DAFTAR, null)).toBeNull();
  });
});
