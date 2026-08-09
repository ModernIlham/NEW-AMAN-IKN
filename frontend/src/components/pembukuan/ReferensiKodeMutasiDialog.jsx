import React, { useEffect, useState } from "react";
import axios from "axios";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { BookOpen } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const WARNA_ARAH = {
  bertambah: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  berkurang: "bg-red-500/15 text-red-600 dark:text-red-400",
  netral: "bg-muted text-muted-foreground",
};

/**
 * Referensi Kode Mutasi Aset Tetap — daftar resmi 99 kode SIMAK (53 mutasi
 * bertambah + 46 berkurang, mandat pemilik 2026-08-09) dari
 * GET /pembukuan/jenis-transaksi, dikelompokkan per keluarga; kode warisan
 * AMAN (203/205) tampil terpisah supaya daftar resminya tetap bersih.
 * Kembaran layar "Referensi Kode" di Persediaan.
 */
export default function ReferensiKodeMutasiDialog() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!open || data) return;
    axios.get(`${API}/pembukuan/jenis-transaksi`)
      .then((r) => setData(r.data))
      .catch(() => setData({ referensi: [], warisan: [], label_kelompok: {} }));
  }, [open, data]);

  const bagian = (arah, judul) => {
    const rows = (data?.referensi || []).filter((r) => r.arah === arah);
    // Kelompok mengikuti urutan kemunculan baris (registry sudah terurut).
    const urutan = [...new Set(rows.map((r) => r.label_kelompok))];
    return (
      <section>
        <h3 className="text-sm font-bold mt-3 mb-1"
          data-testid={`ref-mutasi-${arah}`}>
          {judul} ({rows.length} kode)
        </h3>
        {urutan.map((lk) => (
          <div key={lk} className="mb-2">
            <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">{lk}</p>
            <ul className="divide-y divide-border/60">
              {rows.filter((r) => r.label_kelompok === lk).map((r) => (
                <li key={r.kode} className="py-1 flex items-center gap-2 text-xs">
                  <code className="w-9 flex-shrink-0 font-bold">{r.kode}</code>
                  <span className="flex-1 min-w-0">{r.uraian}</span>
                  <span className={`px-1.5 py-0.5 rounded-full text-[10px] flex-shrink-0 ${WARNA_ARAH[r.arah]}`}>
                    {r.arah}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>
    );
  };

  return (
    <>
      <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 min-w-0 gap-1"
        onClick={() => setOpen(true)} data-testid="jurnal-referensi-kode">
        <BookOpen className="w-3 h-3" />Referensi Kode
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Referensi Kode Mutasi Aset Tetap (SIMAK)</DialogTitle>
          </DialogHeader>
          {!data ? (
            <p className="text-sm text-muted-foreground py-6 text-center">Memuat…</p>
          ) : (
            <>
              {bagian("bertambah", "Mutasi Bertambah")}
              {bagian("berkurang", "Mutasi Berkurang")}
              {(data.warisan || []).length > 0 && (
                <section>
                  <h3 className="text-sm font-bold mt-3 mb-1">Kode warisan AMAN</h3>
                  <p className="text-[11px] text-muted-foreground mb-1">
                    Di luar daftar resmi, dipertahankan agar jurnal lama tetap
                    terbaca (205 = padanan lama 264).
                  </p>
                  <ul className="divide-y divide-border/60">
                    {data.warisan.map((r) => (
                      <li key={r.kode} className="py-1 flex items-center gap-2 text-xs">
                        <code className="w-9 flex-shrink-0 font-bold">{r.kode}</code>
                        <span className="flex-1 min-w-0">{r.uraian}</span>
                        <span className={`px-1.5 py-0.5 rounded-full text-[10px] flex-shrink-0 ${WARNA_ARAH[r.arah] || WARNA_ARAH.netral}`}>
                          {r.arah}
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
