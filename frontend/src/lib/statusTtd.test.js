import { ringkasTtdDokumen, kelasNada, bisaTerbitUlang } from "@/lib/statusTtd";

const HARI = 86400;

describe("ringkasTtdDokumen", () => {
  it("dokumen yang belum pernah dikirim tidak punya ringkasan", () => {
    expect(ringkasTtdDokumen(null)).toBeNull();
    expect(ringkasTtdDokumen({})).toBeNull();
  });

  it("tautan mati MENYEBUT jalan keluarnya, bukan berhenti di 'kedaluwarsa'", () => {
    // Inti laporan pemilik: "selalu berakhir dengan TTD sudah kedaluwarsa".
    // Kata itu terbaca sebagai akhir cerita padahal tautannya bisa
    // diterbitkan ulang.
    const r = ringkasTtdDokumen({
      id: "sr-1", jumlah: 2, selesai_jumlah: 1, perlu_terbit_ulang: true,
      kedaluwarsa_terdekat: { sisa_detik: 0 },
    });
    expect(r.teks).toMatch(/terbitkan ulang/i);
    expect(r.perluTindakan).toBe(true);
    expect(r.nada).toBe("merah");
  });

  it("lengkap ditandatangani tidak menyuruh tindakan apa pun", () => {
    const r = ringkasTtdDokumen({
      id: "sr-1", jumlah: 2, selesai_jumlah: 2, semua_selesai: true,
    });
    expect(r.teks).toMatch(/lengkap/i);
    expect(r.perluTindakan).toBe(false);
    expect(r.nada).toBe("hijau");
  });

  it("permintaan dibatalkan dikatakan apa adanya", () => {
    const r = ringkasTtdDokumen({ id: "sr-1", status: "batal", jumlah: 2 });
    expect(r.teks).toMatch(/dibatalkan/i);
    expect(r.perluTindakan).toBe(false);
  });

  it("menunggu menyebut kemajuan DAN sisa waktu tautannya", () => {
    const r = ringkasTtdDokumen({
      id: "sr-1", jumlah: 3, selesai_jumlah: 1,
      kedaluwarsa_terdekat: { sisa_detik: 9 * HARI },
    });
    expect(r.teks).toContain("1/3");
    expect(r.teks).toMatch(/9 hari lagi/);
    expect(r.nada).toBe("biru");
  });

  it("sisa ≤ 2 hari diberi nada peringatan — bukan menunggu sampai mati", () => {
    const r = ringkasTtdDokumen({
      id: "sr-1", jumlah: 2, selesai_jumlah: 0,
      kedaluwarsa_terdekat: { sisa_detik: 1.5 * HARI },
    });
    expect(r.nada).toBe("kuning");
  });

  it("tanpa info kedaluwarsa tetap menyebut kemajuannya", () => {
    const r = ringkasTtdDokumen({ id: "sr-1", jumlah: 2, selesai_jumlah: 0 });
    expect(r.teks).toContain("0/2");
    expect(r.teks).not.toMatch(/·/);
  });

  it("selesai diprioritaskan atas tautan mati", () => {
    // Tautan yang mati setelah semua meneken bukan masalah siapa pun.
    const r = ringkasTtdDokumen({
      id: "sr-1", jumlah: 1, selesai_jumlah: 1, semua_selesai: true,
      perlu_terbit_ulang: false, kedaluwarsa_terdekat: { sisa_detik: 0 },
    });
    expect(r.nada).toBe("hijau");
  });
});

describe("kelasNada", () => {
  it("tiap nada punya kelas, dan nada asing jatuh ke biru", () => {
    ["merah", "kuning", "hijau", "biru"].forEach((n) => {
      expect(kelasNada(n)).toBeTruthy();
    });
    expect(kelasNada("ungu")).toBe(kelasNada("biru"));
  });
});

describe("bisaTerbitUlang", () => {
  it("yang sudah menandatangani tidak perlu tautan lagi", () => {
    expect(bisaTerbitUlang({ status: "ditandatangani" })).toBe(false);
    expect(bisaTerbitUlang({ status: "aktif" })).toBe(true);
    expect(bisaTerbitUlang({ status: "menunggu" })).toBe(true);
  });
});
