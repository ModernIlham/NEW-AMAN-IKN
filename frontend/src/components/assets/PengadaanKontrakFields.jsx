import React, { useId } from "react";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import jenisDokumen from "../../lib/jenisDokumenPengadaan.json";

/** Kunci isian nonkontrak tanpa menghapus data sumber/historis pengguna. */
export default function PengadaanKontrakFields({ formData, onChange }) {
  const id = useId();
  const jenis = formData.jenis_dokumen_pengadaan || "";
  const nonKontrak = jenis === "Non Kontrak/Penerimaan Barang" || jenis === "Non Kontrak BLU";
  const kontrol = "w-full min-w-0 h-8 px-2 rounded-md border border-input bg-background text-sm disabled:cursor-not-allowed disabled:opacity-50";
  return <>
    <div className="space-y-1 min-w-0">
      <Label htmlFor={`${id}-jenis`} className="text-xs">Jenis Dokumen Pengadaan</Label>
      <select id={`${id}-jenis`} name="jenis_dokumen_pengadaan" value={jenis} onChange={onChange}
        className={kontrol} data-testid="asset-jenis-dokumen-pengadaan">
        <option value="">— Belum ditentukan —</option>
        {jenisDokumen.map(value => <option key={value} value={value}>{value}</option>)}
      </select>
      {nonKontrak && <p id={`${id}-bantuan`} className="text-[10px] text-muted-foreground leading-snug" data-testid="asset-non-kontrak-info">
        Isian kontrak dinonaktifkan. Nilai kontrak lama tetap disimpan; bukti perolehan dapat diisi di bawah.
      </p>}
    </div>
    <div className="space-y-1 min-w-0">
      <Label htmlFor={`${id}-nomor`} className="text-xs">Nomor Kontrak</Label>
      <Input id={`${id}-nomor`} name="nomor_kontrak" value={formData.nomor_kontrak || ""}
        onChange={onChange} disabled={nonKontrak} aria-describedby={nonKontrak ? `${id}-bantuan` : undefined}
        className="h-8" data-testid="asset-nomor-kontrak" />
    </div>
    <div className="space-y-1 min-w-0">
      <Label htmlFor={`${id}-bayar`} className="text-xs">Cara Bayar Kontrak</Label>
      <select id={`${id}-bayar`} name="cara_bayar_kontrak" value={formData.cara_bayar_kontrak || ""}
        onChange={onChange} disabled={nonKontrak} aria-describedby={nonKontrak ? `${id}-bantuan` : undefined}
        className={kontrol} data-testid="asset-cara-bayar-kontrak-select">
        <option value="">— Pilih —</option>
        <option value="Sekaligus">Sekaligus</option>
        <option value="Bertahap (Termin)">Bertahap (Termin)</option>
      </select>
    </div>
  </>;
}
