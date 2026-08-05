import fs from "fs";
import path from "path";
import { authMediaUrl } from "./mediaUrl";

const AKAR = path.join(__dirname, "..");

/** localStorage tiruan — jsdom menyediakannya, cukup dibersihkan tiap uji. */
beforeEach(() => { window.localStorage.clear(); });

describe("authMediaUrl", () => {
  test("menempelkan token media pada URL tanpa query", () => {
    window.localStorage.setItem("media_token", "abc123");
    expect(authMediaUrl("/api/foto/1")).toBe("/api/foto/1?token=abc123");
  });

  test("query yang sudah ada dipertahankan — pakai & bukan ?", () => {
    // Kalau ini salah, `?c=2` hilang dan pratinjau memuat halaman yang keliru
    // (atau memakai cache lama) tanpa galat apa pun.
    window.localStorage.setItem("media_token", "abc123");
    expect(authMediaUrl("/api/dok/halaman/2?c=3")).toBe("/api/dok/halaman/2?c=3&token=abc123");
  });

  test("token sesi dipakai bila media_token belum ada (login lama)", () => {
    window.localStorage.setItem("token", "sesi-lama");
    expect(authMediaUrl("/api/foto/1")).toBe("/api/foto/1?token=sesi-lama");
  });

  test("media_token diutamakan daripada token sesi", () => {
    window.localStorage.setItem("token", "sesi");
    window.localStorage.setItem("media_token", "media");
    expect(authMediaUrl("/api/foto/1")).toBe("/api/foto/1?token=media");
  });

  test("Satker Aktif super-admin ikut dititip di query `sa`", () => {
    // Header X-Satker-Aktif tak bisa ikut pada <img>; tanpa `sa` ini,
    // super-admin yang sedang act-as satker lain akan ditolak 403.
    window.localStorage.setItem("media_token", "t");
    window.localStorage.setItem("satker_aktif", "099");
    expect(authMediaUrl("/api/dok")).toBe("/api/dok?token=t&sa=099");
  });

  test("token dan satker di-encode — tanda + / spasi tak merusak query", () => {
    window.localStorage.setItem("media_token", "a b+c");
    expect(authMediaUrl("/api/x")).toBe("/api/x?token=a%20b%2Bc");
  });

  test("tanpa token sama sekali, URL dikembalikan apa adanya", () => {
    expect(authMediaUrl("/api/x?c=1")).toBe("/api/x?c=1");
  });

  test("URL kosong/undefined dikembalikan apa adanya, tidak melempar", () => {
    window.localStorage.setItem("media_token", "t");
    expect(authMediaUrl("")).toBe("");
    expect(authMediaUrl(undefined)).toBeUndefined();
  });
});

describe("penjaga: pratinjau halaman dokumen HARUS membawa auth", () => {
  /**
   * `AturPosisiTtd` menyuapkan hasil `bangunUrlHalaman` langsung ke
   * `<img src=...>`. Tag <img> TAK BISA mengirim header Authorization, jadi
   * setiap pemanggil wajib menitipkan kredensial di query — lewat
   * `authMediaUrl(...)` untuk layar operator, atau `token=` (token tanda
   * tangan) untuk halaman publik penanda tangan.
   *
   * Ini pernah terjadi di produksi: layar "Atur QR & Unduh ber-TTD" membangun
   * URL-nya dengan `?c=${c}` saja, sehingga dialognya mati dengan
   * "401 (Unauthorized)" begitu dibuka. Tak ada galat build, tak ada uji yang
   * menyentuhnya — yang menemukannya pemakai.
   */
  function berkasJsx(dir = AKAR, hasil = []) {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) berkasJsx(p, hasil);
      else if (/\.jsx$/.test(e.name)) hasil.push(p);
    }
    return hasil;
  }

  test("setiap bangunUrlHalaman memakai authMediaUrl atau menyertakan token=", () => {
    const pelanggar = [];
    let ditemukan = 0;
    for (const f of berkasJsx()) {
      const baris = fs.readFileSync(f, "utf8").split("\n");
      baris.forEach((t, i) => {
        if (!t.includes("bangunUrlHalaman={")) return;
        ditemukan += 1;
        // Ekspresi prop boleh menyebar ke beberapa baris — periksa jendelanya.
        const blok = baris.slice(i, i + 4).join("\n");
        if (!blok.includes("authMediaUrl(") && !blok.includes("token=")) {
          pelanggar.push(`${path.relative(AKAR, f)}:${i + 1}`);
        }
      });
    }
    // Kalau propnya hilang/berganti nama, uji ini diam-diam jadi tak berguna —
    // jadi jumlah pemanggilnya ikut dijaga.
    expect(ditemukan).toBeGreaterThanOrEqual(2);
    expect(pelanggar).toEqual([]);
  });
});
