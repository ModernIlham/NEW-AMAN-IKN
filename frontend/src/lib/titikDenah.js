// Parsing ketat khusus dialog denah: kosong bukan 0, teks sisa bukan angka.
export function titikSah(t) {
  if (!Array.isArray(t) || t.length !== 2
      || t.some(v => v == null || typeof v === "boolean" || String(v).trim() === "")) return null;
  const [lon, lat] = t.map(v => Number(String(v).trim().replace(",", ".")));
  return Number.isFinite(lat) && Number.isFinite(lon)
    && Math.abs(lat) <= 90 && Math.abs(lon) <= 180 ? { lat, lon } : null;
}
