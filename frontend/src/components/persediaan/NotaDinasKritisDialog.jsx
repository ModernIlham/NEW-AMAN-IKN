import React, { useMemo, useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import { FileDown } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Dialog pemilihan barang untuk Nota Dinas Usulan Pengadaan (stok
 * kritis/habis) — permintaan pemilik: tidak semua yang habis/kritis harus
 * diusulkan pengadaan ulang, jadi operator MEMILIH dulu barang mana yang
 * masuk nota, baru mengunduh. Default semua tercentang (perilaku lama =
 * satu klik lagi), dan server tetap memvalidasi pilihan terhadap daftar
 * peringatan aslinya.
 */
export default function NotaDinasKritisDialog({ items }) {
  const [open, setOpen] = useState(false);
  // Set id yang TIDAK dicentang — default kosong berarti semua terpilih,
  // dan pilihan tak perlu diinisialisasi ulang saat daftar peringatan segar.
  const [batal, setBatal] = useState(() => new Set());

  const terpilih = useMemo(
    () => items.filter((it) => !batal.has(it.id)), [items, batal]);

  const toggle = (id) => setBatal((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const unduh = () => {
    const ids = terpilih.map((it) => it.id).join(",");
    const param = terpilih.length === items.length
      ? "" : `&ids=${encodeURIComponent(ids)}`;
    downloadFileWithProgress(
      `${API}/persediaan/nota-dinas?jenis=kritis${param}`,
      "Nota_Dinas_Stok_Kritis.pdf",
      { label: "Nota Dinas Stok Kritis" }).catch(() => {});
    setOpen(false);
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="h-8 px-2.5 rounded-lg border border-amber-400 dark:border-amber-600 text-[11px] font-semibold text-amber-800 dark:text-amber-300 flex items-center gap-1 hover:bg-amber-100 dark:hover:bg-amber-900/40 min-w-0 min-h-0"
        data-testid="persediaan-nota-kritis"
      >
        <FileDown className="w-3.5 h-3.5" />Nota Dinas Kritis
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Pilih Barang untuk Nota Dinas</DialogTitle>
          </DialogHeader>
          <p className="text-xs text-muted-foreground">
            Centang barang yang akan diusulkan pengadaannya — yang tidak
            dicentang tidak masuk nota dinas.
          </p>
          <div className="flex gap-1.5">
            <Button size="sm" variant="outline" onClick={() => setBatal(new Set())}
              data-testid="nota-kritis-semua">
              Pilih semua
            </Button>
            <Button size="sm" variant="outline"
              onClick={() => setBatal(new Set(items.map((it) => it.id)))}
              data-testid="nota-kritis-kosongkan">
              Kosongkan
            </Button>
          </div>
          <ul className="divide-y divide-border">
            {items.map((it) => (
              <li key={it.id}>
                <label className="flex items-center gap-2.5 py-2 cursor-pointer">
                  <input type="checkbox" checked={!batal.has(it.id)}
                    onChange={() => toggle(it.id)}
                    className="min-w-0 min-h-0"
                    data-testid={`nota-kritis-item-${it.id}`} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm text-foreground truncate">
                      {it.nama_barang}
                    </span>
                    <span className="block text-[11px] text-muted-foreground">
                      {it.kode_barang} · stok {it.stok}
                      {" "}/ batas {it.batas_kritis || 0} {it.satuan || ""}
                    </span>
                  </span>
                  <span className={`px-2 py-0.5 rounded-full text-[11px] flex-shrink-0 ${
                    it.stok <= 0
                      ? "bg-red-500/15 text-red-600 dark:text-red-400"
                      : "bg-amber-500/15 text-amber-600 dark:text-amber-400"}`}>
                    {it.stok <= 0 ? "habis" : "kritis"}
                  </span>
                </label>
              </li>
            ))}
          </ul>
          <Button disabled={terpilih.length === 0} onClick={unduh}
            data-testid="nota-kritis-unduh">
            <FileDown className="w-4 h-4 mr-1.5" />
            Unduh Nota Dinas ({terpilih.length} barang)
          </Button>
        </DialogContent>
      </Dialog>
    </>
  );
}
