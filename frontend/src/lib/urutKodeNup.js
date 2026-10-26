// Cermin asset_sorting.angka_identitas: jangan Number/parseInt, karena NUP
// panjang kehilangan presisi. Kode/NUP kosong atau nonnumerik tetap di akhir.
export function angkaIdentitas(value) {
  const match = /^([0-9]+)(?:\.0+)?$/.exec(String(value ?? "").trim());
  return match ? match[1].replace(/^0+/, "") || "0" : null;
}

function bandingkan(a, b, direction) {
  if (a === null || b === null) return Number(a === null) - Number(b === null);
  return direction * (a.length - b.length || (a < b ? -1 : a > b ? 1 : 0));
}

export function urutkanKodeNup(rows, sortBy) {
  const direction = sortBy === "code_nup_desc" ? -1 : 1;
  const parsed = new Map(rows.map(row => [row, [angkaIdentitas(row.asset_code), angkaIdentitas(row.NUP)]]));
  return [...rows].sort((a, b) => {
    const left = parsed.get(a), right = parsed.get(b);
    return bandingkan(left[0], right[0], direction) || bandingkan(left[1], right[1], direction) ||
      (String(a.id) < String(b.id) ? -1 : String(a.id) > String(b.id) ? 1 : 0);
  });
}
