import React, { useState } from "react";
import FullCameraSheet from "../assets/FullCameraSheet";
import { aturanCatatanLaporan } from "../../lib/laporanPemegang";

const input = "mt-1 w-full min-h-11 min-w-0 rounded-xl border border-input bg-background px-3 py-2 text-sm";

export default function KameraPemegang({ assignment, form, sesiAset, nama, onField, ...props }) {
  const [kode, setKode] = useState("");
  const catatan = aturanCatatanLaporan(form);
  return <FullCameraSheet {...props} modePemegang isEditing maxPhotos={3} sesiAset={sesiAset}
    formData={{ asset_name: assignment.asset_name || "Barang BMN", asset_code: assignment.asset_code, NUP: assignment.NUP,
      location: form.lokasi_laporan || assignment.location, user: nama }}
    photos={form.bukti.map(p => `data:${p.mime};base64,${p.data_base64}`)}
    panelScan={!("BarcodeDetector" in window) && <form className="space-y-1" onSubmit={e => { e.preventDefault(); props.onScanAsset(kode, kode); }}>
      <p className="text-center text-xs text-white">Scanner otomatis tidak didukung browser. Masukkan kode register atau kode-NUP pada stiker.</p>
      <div className="flex gap-2"><input aria-label="Kode stiker barang" data-testid="camera-kode-manual" className={input} maxLength={300} value={kode} onChange={e => setKode(e.target.value)} /><button type="submit" data-testid="camera-cari-kode" className="min-h-11 rounded-xl bg-teal-700 px-3 text-sm text-white">Cari</button></div>
    </form>}
    panelLaporan={<fieldset className="space-y-3" disabled={props.busy}>
      <p className="text-sm">{assignment.asset_name} · NUP {assignment.NUP}. Isi pengamatan Anda, bukan perubahan data induk.</p>
      <label className="block text-sm">Kondisi hasil pemeriksaan<select className={input} data-testid="camera-laporan-kondisi" value={form.kondisi} onChange={e => onField("kondisi", e.target.value)}>
        {["Tidak diketahui", "Baik", "Rusak Ringan", "Rusak Berat"].map(v => <option key={v}>{v}</option>)}</select></label>
      <label className="block text-sm">Keadaan operasional<select className={input} data-testid="camera-laporan-operasional" value={form.status_operasional} onChange={e => onField("status_operasional", e.target.value)}>
        {[["tidak_diketahui", "Tidak diketahui"], ["digunakan", "Sedang digunakan"], ["tidak_digunakan", "Tidak digunakan"], ["diperbaiki", "Sedang diperbaiki"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      <label className="block text-sm">Lokasi yang dilaporkan<input className={input} maxLength={300} data-testid="camera-laporan-lokasi" value={form.lokasi_laporan} onChange={e => onField("lokasi_laporan", e.target.value)} /></label>
      <label className="block text-sm">{catatan.label} ({catatan.wajib ? "wajib" : "opsional"})<textarea className={input} rows={3} maxLength={4000} aria-required={catatan.wajib} aria-describedby="camera-catatan-panduan" placeholder={catatan.panduan} data-testid="camera-laporan-catatan" value={form.catatan} onChange={e => onField("catatan", e.target.value)} /></label>
      <p id="camera-catatan-panduan" className="text-xs">{catatan.panduan}</p>
    </fieldset>} />;
}
