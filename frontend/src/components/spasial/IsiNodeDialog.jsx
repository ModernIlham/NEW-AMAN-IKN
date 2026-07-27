// Daftar ASET yang menempati sebuah node denah (Spasial Fase 9).
//
// Ini kebalikan deteksi Fase 3: kalau di sana "titik → wilayah mana", di sini
// "wilayah → barang apa saja". Bentuk itulah yang dibutuhkan opname fisik:
// petugas berdiri di sebuah ruangan dan ingin tahu apa yang seharusnya ada.
//
// Saklar `dalam` menentukan cakupan: membuka Gedung dengan `dalam` menyala
// memperlihatkan isi SELURUH lantai & ruangannya sekaligus.
import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Boxes, Loader2, X } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function IsiNodeDialog({ node, labelLevel, onClose }) {
  const [data, setData] = useState(null);
  const [dalam, setDalam] = useState(true);
  const [memuat, setMemuat] = useState(true);

  const muat = useCallback(async (termasukKeturunan) => {
    setMemuat(true);
    try {
      const r = await axios.get(`${API}/spasial/node/${node.id}/isi`, {
        params: { dalam: String(termasukKeturunan) }, timeout: 20000,
      });
      setData(r.data);
    } catch (e) {
      setData({ items: [], jumlah: 0 });
      toast.error(e?.response?.data?.detail || "Gagal memuat isi lokasi");
    } finally {
      setMemuat(false);
    }
  }, [node.id]);

  useEffect(() => { muat(dalam); }, [muat, dalam]);

  const items = data?.items || [];

  return (
    <Dialog open onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent className="max-w-lg" data-testid="isi-node-dialog">
        <DialogHeader>
          <DialogTitle className="text-sm flex items-center gap-1.5">
            <Boxes className="w-4 h-4 text-teal-600" />
            Isi: {node.nama}
          </DialogTitle>
          <DialogDescription className="text-xs">
            {(labelLevel?.[node.tipe] || node.tipe)} — aset yang tercatat
            menempati lokasi ini.
          </DialogDescription>
        </DialogHeader>

        <label className="flex items-center gap-2 text-xs">
          <input type="checkbox" checked={dalam}
                 onChange={(e) => setDalam(e.target.checked)}
                 data-testid="isi-node-dalam" />
          <span>Termasuk seluruh isi di bawahnya (lantai, ruangan, …)</span>
        </label>

        <div className="rounded-lg border border-border max-h-[46vh] overflow-y-auto">
          {memuat ? (
            <div className="flex items-center justify-center py-10 text-muted-foreground">
              <Loader2 className="w-5 h-5 animate-spin mr-2" /> Memuat…
            </div>
          ) : items.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-10 px-4">
              Belum ada aset yang ditempatkan di sini. Tempatkan lewat detail
              aset → Lokasi Denah.
            </p>
          ) : (
            <ul className="divide-y divide-border/60" data-testid="isi-node-daftar">
              {items.map((a) => (
                <li key={a.id} className="px-3 py-2">
                  <p className="text-xs font-semibold truncate">{a.asset_name}</p>
                  <p className="text-[11px] text-muted-foreground truncate">
                    {[a.asset_code && `${a.asset_code}${a.NUP ? ` · ${a.NUP}` : ""}`,
                      a.condition, a.user && `dipegang ${a.user}`,
                      // Saat melihat isi GEDUNG, penting tahu ruangan tepatnya.
                      dalam && a.lokasi_spasial?.node_nama]
                      .filter(Boolean).join(" · ")}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex items-center gap-2 pt-1">
          <p className="text-xs text-muted-foreground flex-1">
            {memuat ? "" : `${data?.jumlah ?? 0} aset`}
            {data?.terpotong && " (dipotong pada plafon tampilan)"}
          </p>
          <Button variant="outline" size="sm" onClick={() => onClose?.()}
                  data-testid="isi-node-tutup">
            <X className="w-3.5 h-3.5 mr-1" />Tutup
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
