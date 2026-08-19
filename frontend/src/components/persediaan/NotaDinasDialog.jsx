import React, { useMemo, useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import { FileDown } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Dialog pemilihan barang untuk Nota Dinas persediaan — stok kritis/habis
 * MAUPUN kedaluwarsa.
 *
 * Permintaan pemilik: tidak semua yang habis/kritis harus diusulkan pengadaan
 * ulang, dan hal yang sama berlaku untuk nota kedaluwarsa — jadi SETIAP nota
 * dinas memilih barangnya sendiri. Default semua tercentang (perilaku lama =
 * satu klik lagi), dan server tetap memvalidasi pilihan terhadap daftar
 * peringatan aslinya: id di luar daftar diabaikan, bukan disisipkan.
 *
 * SATU HAL YANG MENENTUKAN BENTUK LAYAR INI: pada nota kedaluwarsa, satu
 * barang bisa punya BEBERAPA baris — tiap layer (batch) punya tanggal
 * kedaluwarsa sendiri — sementara penyaring server bekerja per `id` BARANG.
 * Maka pilihannya disajikan per barang, bukan per layer; mencentang satu
 * barang berarti seluruh layer-nya ikut. Menyajikan per layer akan menipu:
 * melepas satu layer diam-diam melepas layer lain milik barang yang sama.
 */

/** Ringkas baris peringatan → satu entri per BARANG (layer digabung). */
export function kelompokkanPerBarang(rows) {
  const peta = new Map();
  for (const r of rows || []) {
    if (!r || !r.id) continue;
    const ada = peta.get(r.id);
    const qty = Number(r.qty) || 0;
    if (!ada) {
      peta.set(r.id, {
        ...r, n_layer: 1, total_qty: qty,
        // Tanggal terdekat = yang paling mendesak; itulah yang pantas
        // ditampilkan saat beberapa layer diringkas jadi satu baris.
        expired_terdekat: r.expired || "",
      });
      continue;
    }
    ada.n_layer += 1;
    ada.total_qty += qty;
    if (r.expired && (!ada.expired_terdekat || r.expired < ada.expired_terdekat)) {
      ada.expired_terdekat = r.expired;
    }
  }
  return [...peta.values()];
}

const JUDUL = {
  kritis: "NOTA DINAS — Usulan Pengadaan (Stok Kritis/Habis)",
  kedaluwarsa: "NOTA DINAS — Persediaan Kedaluwarsa",
};
const LABEL_TOMBOL = {
  kritis: "Nota Dinas Kritis",
  kedaluwarsa: "Nota Dinas Kedaluwarsa",
};
const NAMA_BERKAS = {
  kritis: "Nota_Dinas_Stok_Kritis.pdf",
  kedaluwarsa: "Nota_Dinas_Kedaluwarsa.pdf",
};

export default function NotaDinasDialog({ items, jenis = "kritis" }) {
  const [open, setOpen] = useState(false);
  // Set id yang TIDAK dicentang — default kosong berarti semua terpilih,
  // dan pilihan tak perlu diinisialisasi ulang saat daftar peringatan segar.
  const [batal, setBatal] = useState(() => new Set());

  const daftar = useMemo(
    () => (jenis === "kedaluwarsa" ? kelompokkanPerBarang(items) : (items || [])),
    [items, jenis]);
  const terpilih = useMemo(
    () => daftar.filter((it) => !batal.has(it.id)), [daftar, batal]);

  const toggle = (id) => setBatal((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const unduh = () => {
    const ids = terpilih.map((it) => it.id).join(",");
    const param = terpilih.length === daftar.length
      ? "" : `&ids=${encodeURIComponent(ids)}`;
    downloadFileWithProgress(
      `${API}/persediaan/nota-dinas?jenis=${jenis}${param}`,
      NAMA_BERKAS[jenis],
      { label: LABEL_TOMBOL[jenis] }).catch(() => {});
    setOpen(false);
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="h-8 px-2.5 rounded-lg border border-amber-400 dark:border-amber-600 text-[11px] font-semibold text-amber-800 dark:text-amber-300 flex items-center gap-1 hover:bg-amber-100 dark:hover:bg-amber-900/40 min-w-0 min-h-0"
        data-testid={`persediaan-nota-${jenis}`}
      >
        <FileDown className="w-3.5 h-3.5" />{LABEL_TOMBOL[jenis]}
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Pilih Barang untuk {JUDUL[jenis]}</DialogTitle>
          </DialogHeader>
          <p className="text-xs text-muted-foreground">
            {jenis === "kedaluwarsa"
              ? "Centang barang yang akan dimasukkan ke nota dinas. Satu barang bisa punya beberapa layer bertanggal berbeda — memilih barang berarti SELURUH layer-nya ikut."
              : "Centang barang yang akan diusulkan pengadaannya — yang tidak dicentang tidak masuk nota dinas."}
          </p>
          <div className="flex gap-1.5">
            <Button size="sm" variant="outline" onClick={() => setBatal(new Set())}
              data-testid={`nota-${jenis}-semua`}>
              Pilih semua
            </Button>
            <Button size="sm" variant="outline"
              onClick={() => setBatal(new Set(daftar.map((it) => it.id)))}
              data-testid={`nota-${jenis}-kosongkan`}>
              Kosongkan
            </Button>
          </div>
          <ul className="divide-y divide-border">
            {daftar.map((it) => (
              <li key={it.id}>
                <label className="flex items-center gap-2.5 py-2 cursor-pointer">
                  <input type="checkbox" checked={!batal.has(it.id)}
                    onChange={() => toggle(it.id)}
                    className="min-w-0 min-h-0"
                    data-testid={`nota-${jenis}-item-${it.id}`} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm text-foreground truncate">
                      {it.nama_barang}
                    </span>
                    <span className="block text-[11px] text-muted-foreground">
                      {jenis === "kedaluwarsa" ? (
                        <>
                          {it.kode_barang} · {it.total_qty} {it.satuan || ""}
                          {it.n_layer > 1 ? ` · ${it.n_layer} layer` : ""}
                          {it.expired_terdekat ? ` · terdekat ${it.expired_terdekat}` : ""}
                        </>
                      ) : (
                        <>
                          {it.kode_barang} · stok {it.stok}
                          {" "}/ batas {it.batas_kritis || 0} {it.satuan || ""}
                        </>
                      )}
                    </span>
                  </span>
                  <span className={`px-2 py-0.5 rounded-full text-[11px] flex-shrink-0 ${
                    (jenis === "kedaluwarsa" ? it.lewat : it.stok <= 0)
                      ? "bg-red-500/15 text-red-600 dark:text-red-400"
                      : "bg-amber-500/15 text-amber-600 dark:text-amber-400"}`}>
                    {jenis === "kedaluwarsa"
                      ? (it.lewat ? "kedaluwarsa" : "segera")
                      : (it.stok <= 0 ? "habis" : "kritis")}
                  </span>
                </label>
              </li>
            ))}
          </ul>
          <Button disabled={terpilih.length === 0} onClick={unduh}
            data-testid={`nota-${jenis}-unduh`}>
            <FileDown className="w-4 h-4 mr-1.5" />
            Unduh Nota Dinas ({terpilih.length} barang)
          </Button>
        </DialogContent>
      </Dialog>
    </>
  );
}
