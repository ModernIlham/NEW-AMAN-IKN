import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Gerbang permohonan aset (ASET-GERBANG-1) — dipakai tiga pintu transaksi
 * pembukuan (PanelKdp, dialog reklasifikasi Pelaporan, SimanSyncCard).
 *
 * Setelan dibaca SAAT submit (bukan disimpan di state komponen) supaya
 * saklar yang baru dinyalakan admin langsung berlaku tanpa muat ulang
 * halaman; gagal membaca setelan dianggap MATI (perilaku lama) agar
 * transaksi tidak terkunci oleh galat jaringan sesaat.
 */
export async function gerbangPermohonanAsetAktif() {
  try {
    const r = await axios.get(`${API}/pembukuan/permohonan-pengaturan`);
    return !!r.data?.aktif;
  } catch {
    return false;
  }
}

/** Ajukan permohonan transaksi aset — mengembalikan dokumen permohonan. */
export async function ajukanPermohonanAset(jalur, assetId, payload, catatan = "") {
  const r = await axios.post(`${API}/pembukuan/permohonan`, {
    jalur, asset_id: assetId, payload, catatan,
  });
  return r.data?.permohonan;
}

/** Pesan toast seragam setelah permohonan terkirim. */
export function pesanPermohonanTerkirim(label) {
  return `${label} diajukan sebagai permohonan — menunggu persetujuan KPB `
    + "(panel Permohonan di halaman Pembukuan)";
}
