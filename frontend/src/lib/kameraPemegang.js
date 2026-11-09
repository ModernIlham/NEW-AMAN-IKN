import { BATAS_BUKTI } from "./portalPemegang";

// Pencocokan lokal, tepat dan tidak ambigu. QR tidak pernah membuka URL/API
// staf. Kode barang saja bisa mewakili banyak NUP: jangan pilih baris pertama.
export function cocokScanPemegang(aset, raw) {
  const kode = String(raw || "").trim().replace(/^#/, "").toLowerCase();
  if (!kode || kode.length > 300) return [];
  return aset.filter(a => a.status === "diterima" && [a.asset_id, a.kode_register,
    a.asset_code, `${a.asset_code}-${a.NUP}`, `${a.asset_code}|${a.NUP}`]
    .some(v => v && String(v).toLowerCase() === kode));
}

const AWALAN_JPEG = "data:image/jpeg;base64,";

// Validasi base64 TANPA regex. Foto kamera berukuran megabita; regex
// ber-grup tangkap di atas string sepanjang itu bisa menghabiskan stack
// backtracking V8 (tergantung perangkat/mesin) dan melempar "Maximum call
// stack size exceeded" alih-alih pesan yang bisa ditindaklanjuti pengguna.
function base64Sah(s) {
  let n = s.length;
  for (let pad = 0; pad < 2 && n > 0 && s.charCodeAt(n - 1) === 61; pad += 1) n -= 1; // "="
  if (n === 0) return false;
  for (let i = 0; i < n; i += 1) {
    const c = s.charCodeAt(i);
    const sah = (c >= 65 && c <= 90) || (c >= 97 && c <= 122) || (c >= 48 && c <= 57) || c === 43 || c === 47;
    if (!sah) return false;
  }
  return true;
}

export function buktiJepretan(dataUrl, pengambilan, existing = []) {
  const teks = typeof dataUrl === "string" ? dataUrl : "";
  if (!teks.startsWith(AWALAN_JPEG)) throw new Error("Hasil kamera tidak dapat dibaca. Ambil foto kembali.");
  const isi = teks.slice(AWALAN_JPEG.length);
  if (existing.length >= 3) throw new Error("Maksimal tiga foto per laporan.");
  const bytes = s => Math.floor(s.length * 3 / 4) - (s.endsWith("==") ? 2 : s.endsWith("=") ? 1 : 0);
  // Ukuran dicek SEBELUM isi dipindai — foto kebesaran ditolak murah & jelas.
  if (existing.reduce((n, p) => n + bytes(p.data_base64), bytes(isi)) > BATAS_BUKTI) {
    throw new Error("Total foto maksimal 3 MB. Turunkan resolusi/kualitas di setelan kamera lalu potret kembali.");
  }
  if (!base64Sah(isi)) throw new Error("Hasil kamera tidak dapat dibaca. Ambil foto kembali.");
  return { nama: `kamera-${Date.now()}-${existing.length + 1}.jpg`, mime: "image/jpeg", data_base64: isi, pengambilan };
}

export function ringkasPengambilan(p) {
  if (!p?.pengambilan) return "";
  const { waktu, gps } = p.pengambilan;
  return `${new Date(waktu).toLocaleString("id-ID")} · ${gps ? `GPS ${gps.lat}, ${gps.lng} (±${gps.accuracy ?? "—"} m)` : "Tanpa koordinat GPS"} · data perangkat, perlu pemeriksaan`;
}
