import React from "react";
import { Button } from "@/components/ui/button";

const LABEL = {
  menunggu_keabsahan: "Menunggu dokumen sah dan lengkap", selesai: "BMN Saya tersinkron",
  perlu_tinjauan: "Perlu ditinjau petugas", sebagian: "Sebagian penugasan perlu ditinjau",
};
const HASIL = { aktif: "Amanah tercatat", ditutup: "Penugasan ditutup", perlu_tinjauan: "Perlu ditinjau" };

export default function StatusOtomasiBast({ bast, onSinkronkan, sibuk = false }) {
  const data = bast?.portal_otomasi;
  const namaBarang = Object.fromEntries((bast?.aset || []).map(a => [a.id, [a.asset_name, a.NUP ? `NUP ${a.NUP}` : ""].filter(Boolean).join(" · ")]));
  return <div className="mt-2 space-y-1 rounded-lg border border-border bg-muted/30 p-2 text-xs" data-testid={`bast-portal-status-${bast.id}`}>
    <p className="font-semibold">BMN Saya · {data ? (LABEL[data.status] || "Perlu diperiksa") : "Dokumen lama — belum diperiksa untuk otomasi"}</p>
    {data?.alasan && <p className="break-words text-muted-foreground">{data.alasan}</p>}
    <p className="text-[10px] text-muted-foreground">Penugasan mengikuti BAST sah dan lengkap; tidak perlu dipetakan atau diterima ulang. Email kosong/ganda, identitas berubah atau akses pernah dicabut perlu tinjauan admin.</p>
    {!data && <p className="text-[10px] text-muted-foreground">Dokumen lama tidak diterapkan otomatis lewat tombol sinkronisasi. Petugas dapat memeriksa dasar sah melalui penugasan lama di Portal Pemegang; perubahan isi harus menggunakan revisi resmi.</p>}
    {!!data?.hasil?.length && <details><summary className="cursor-pointer py-2" data-testid={`bast-portal-rincian-${bast.id}`}>Rincian {data.hasil.length} barang</summary><ul className="space-y-1">{data.hasil.map((h, i) => <li key={`${h.asset_id}-${i}`} className="rounded border p-2"><span className="font-medium">{h.asset_name || namaBarang[h.asset_id] || h.asset_id} · {HASIL[h.status] || "Perlu diperiksa"}</span>{h.alasan ? <p className="break-words">{h.alasan}</p> : null}</li>)}</ul></details>}
    {data && onSinkronkan && <Button type="button" size="sm" variant="outline" className="min-h-[44px] text-xs" disabled={sibuk}
      data-testid={`bast-portal-sinkron-${bast.id}`} onClick={() => onSinkronkan(bast)}>{sibuk ? "Memeriksa…" : "Periksa / sinkronkan BMN Saya"}</Button>}
  </div>;
}
