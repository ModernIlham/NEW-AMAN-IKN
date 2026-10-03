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

export function buktiJepretan(dataUrl, pengambilan, existing = []) {
  const match = /^data:image\/jpeg;base64,([A-Za-z0-9+/]+={0,2})$/.exec(dataUrl || "");
  if (!match) throw new Error("Hasil kamera tidak dapat dibaca. Ambil foto kembali.");
  if (existing.length >= 3) throw new Error("Maksimal tiga foto per laporan.");
  const bytes = s => Math.floor(s.length * 3 / 4) - (s.endsWith("==") ? 2 : s.endsWith("=") ? 1 : 0);
  if (existing.reduce((n, p) => n + bytes(p.data_base64), bytes(match[1])) > BATAS_BUKTI) {
    throw new Error("Total foto maksimal 3 MB. Turunkan resolusi/kualitas di setelan kamera lalu potret kembali.");
  }
  return { nama: `kamera-${Date.now()}-${existing.length + 1}.jpg`, mime: "image/jpeg", data_base64: match[1], pengambilan };
}

export function ringkasPengambilan(p) {
  if (!p?.pengambilan) return "";
  const { waktu, gps } = p.pengambilan;
  return `${new Date(waktu).toLocaleString("id-ID")} · ${gps ? `GPS ${gps.lat}, ${gps.lng} (±${gps.accuracy ?? "—"} m)` : "Tanpa koordinat GPS"} · data perangkat, perlu pemeriksaan`;
}
