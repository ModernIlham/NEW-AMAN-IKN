import { cocokAset } from "./pencarianLokal";
import { normalkanMulti } from "@/hooks/useAssetFilters";
import { bandingkanHargaTerurai, hargaEksak } from "./hargaEksak";
import { urutkanKodeNup } from "./urutKodeNup";

export function filterSnapshotRows(rows, { search, category, filters }) {
  let out = rows;
  // Pencarian teks bebas memakai SATU semantik dengan server (lib/pencarianLokal
  // mencerminkan pencarian_utils.py): tiap kata wajib ada, boleh di field
  // berbeda, kode boleh diketik tanpa pemisah. Dulu di sini kata kunci
  // diperlakukan sebagai satu frasa utuh pada 16 field saja, sehingga hasil
  // luring berbeda dari hasil daring untuk kata kunci yang sama.
  if (search) out = out.filter(r => cocokAset(r, search));
  if (filters) {
    // Tujuh filter berbasis pilihan bernilai BANYAK: nilai dalam satu filter
    // berarti ATAU (cermin `$in` di server), antar-filter tetap DAN. Daftar
    // kosong = tanpa filter, BUKAN "tak cocok apa pun". String tunggal tetap
    // diterima supaya snapshot/pemanggil lama tak pecah.
    const eqMulti = (field, val) => {
      const v = normalkanMulti(val);
      if (v.length) out = out.filter(r => v.includes(String(r[field] ?? "")));
    };
    const subMulti = (field, val) => {
      const v = normalkanMulti(val).map(s => s.toLowerCase());
      if (v.length) out = out.filter(r => {
        const isi = String(r[field] ?? "").toLowerCase();
        return v.some(s => isi.includes(s));
      });
    };
    const sub = (field, val) => { if (val) { const v = val.toLowerCase(); out = out.filter(r => String(r[field] ?? "").toLowerCase().includes(v)); } };
    // Kategori ikut jalur multi yang sama dengan tujuh filter lain — hasil
    // luring harus identik dengan hasil daring untuk filter yang sama.
    eqMulti("category", category);
    eqMulti("condition", filters.condition);
    eqMulti("status", filters.status);
    subMulti("location", filters.location);
    subMulti("eselon1", filters.eselon1);
    subMulti("eselon2", filters.eselon2);
    subMulti("eselon3", filters.eselon3);
    subMulti("eselon4", filters.eselon4);
    subMulti("eselon5", filters.eselon5);
    eqMulti("stiker_status", filters.stiker);
    eqMulti("inventory_status", filters.inventoryStatus);
    sub("nomor_spm", filters.nomorSpm);
    sub("supplier", filters.perolehanDari);
    sub("user", filters.user);
    sub("pengguna_nip", filters.penggunaNip);
    const adaBatas = value => value !== undefined && value !== null && String(value).trim() !== "";
    if (adaBatas(filters.priceMin)) {
      const bound = hargaEksak(filters.priceMin);
      out = out.filter(r => bandingkanHargaTerurai(hargaEksak(r.purchase_price), bound) >= 0);
    }
    if (adaBatas(filters.priceMax)) {
      const bound = hargaEksak(filters.priceMax);
      out = out.filter(r => bandingkanHargaTerurai(hargaEksak(r.purchase_price), bound) <= 0);
    }
    // Rentang tanggal beli (purchase_date YYYY-MM-DD) — bukan tanggal input.
    // Selaras dengan filter server (/assets & ekspor geo) agar peta ikut tersaring.
    // Aset tanpa tanggal beli keluar dari hasil saat rentang diisi.
    if (filters.dateFrom) out = out.filter(r => String(r.purchase_date ?? "").slice(0, 10) >= filters.dateFrom && String(r.purchase_date ?? "").trim() !== "");
    if (filters.dateTo) out = out.filter(r => { const d = String(r.purchase_date ?? "").slice(0, 10); return d !== "" && d <= filters.dateTo; });
  }
  return out;
}

export function sortSnapshotRows(rows, sortBy) {
  if (sortBy === "code_nup_asc" || sortBy === "code_nup_desc") return urutkanKodeNup(rows, sortBy);
  const s = (v) => String(v ?? "");

  if (sortBy === "price_asc" || sortBy === "price_desc") {
    const parsed = new Map(rows.map(row => [row, hargaEksak(row.purchase_price)]));
    const direction = sortBy === "price_desc" ? -1 : 1;
    return [...rows].sort((a, b) => direction * bandingkanHargaTerurai(parsed.get(a), parsed.get(b)) ||
      (s(a.id) < s(b.id) ? -1 : s(a.id) > s(b.id) ? 1 : 0));
  }
  const cmp = {
    newest: (a, b) => s(b.created_at).localeCompare(s(a.created_at)),
    oldest: (a, b) => s(a.created_at).localeCompare(s(b.created_at)),
    name_asc: (a, b) => s(a.asset_name).localeCompare(s(b.asset_name)),
    name_desc: (a, b) => s(b.asset_name).localeCompare(s(a.asset_name)),
    category_asc: (a, b) => s(a.category).localeCompare(s(b.category)),
    category_desc: (a, b) => s(b.category).localeCompare(s(a.category)),
    location_asc: (a, b) => s(a.location).localeCompare(s(b.location)),
    eselon1_asc: (a, b) => s(a.eselon1).localeCompare(s(b.eselon1)),
    condition_asc: (a, b) => s(a.condition).localeCompare(s(b.condition)),
    status_asc: (a, b) => s(a.status).localeCompare(s(b.status)),
  }[sortBy];
  // Rows arrive already newest-first from getSnapshotAssets
  return cmp ? [...rows].sort((a, b) => cmp(a, b) || (s(a.id) < s(b.id) ? -1 : s(a.id) > s(b.id) ? 1 : 0)) : rows;
}
