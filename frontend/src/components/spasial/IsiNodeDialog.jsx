// Daftar ASET yang menempati sebuah node denah (Spasial Fase 9).
//
// Ini kebalikan deteksi Fase 3: kalau di sana "titik → wilayah mana", di sini
// "wilayah → barang apa saja". Bentuk itulah yang dibutuhkan opname fisik:
// petugas berdiri di sebuah ruangan dan ingin tahu apa yang seharusnya ada.
//
// Saklar `dalam` menentukan cakupan: membuka Gedung dengan `dalam` menyala
// memperlihatkan isi SELURUH lantai & ruangannya sekaligus.
import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { AlertTriangle, Boxes, Loader2, RefreshCw, X } from "lucide-react";
import { TENGGAT_BAKA, muatAndal, pesanGalat } from "@/lib/muatAndal";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function IsiNodeDialog({ node, labelLevel, onClose }) {
  const [data, setData] = useState(null);
  const [dalam, setDalam] = useState(true);
  const [memuat, setMemuat] = useState(true);
  const [galat, setGalat] = useState(null);
  const reqRef = useRef(0);

  const muat = useCallback(async (termasukKeturunan) => {
    // PENJAGA URUTAN. Saklar "termasuk isi di bawahnya" dapat diklik cepat
    // bolak-balik, dan permintaan `dalam=true` (isi SELURUH gedung) jauh lebih
    // lama daripada `dalam=false`. Tanpa penjaga ini balasan yang lama bisa
    // mendarat BELAKANGAN dan menampilkan isi seluruh gedung sebagai isi satu
    // ruangan — angka yang salah untuk opname fisik, bukan sekadar layar keliru.
    const seq = ++reqRef.current;
    setMemuat(true);
    setGalat(null);
    try {
      const r = await muatAndal(() => axios.get(
        `${API}/spasial/node/${node.id}/isi`,
        { params: { dalam: String(termasukKeturunan) }, timeout: TENGGAT_BAKA }));
      if (seq !== reqRef.current) return;
      setData(r.data);
    } catch (e) {
      if (seq !== reqRef.current) return;
      // JANGAN memalsukan hasil kosong. Versi lama menulis {items: [], jumlah: 0}
      // di sini, sehingga kegagalan jaringan terbaca sebagai "Belum ada aset
      // yang ditempatkan di sini · 0 aset" — pernyataan yang layar ini tidak
      // punya dasar untuk membuatnya, dan yang bisa membuat petugas opname
      // menyimpulkan ruangan memang kosong.
      setData(null);
      setGalat(pesanGalat(e, "Gagal memuat isi lokasi"));
    } finally {
      if (seq === reqRef.current) setMemuat(false);
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
          ) : galat ? (
            <div className="text-center py-10 px-4" data-testid="isi-node-galat">
              <AlertTriangle className="w-7 h-7 mx-auto mb-2 text-amber-500" />
              <p className="text-xs text-foreground break-words">{galat}</p>
              <p className="text-[11px] text-muted-foreground mt-1">
                Isi lokasi ini <b>tidak diketahui</b> — bukan berarti kosong.
              </p>
              <Button variant="outline" size="sm" className="mt-3 h-7 text-[11px]"
                      onClick={() => muat(dalam)} data-testid="isi-node-coba-lagi">
                <RefreshCw className="w-3 h-3 mr-1" />Coba lagi
              </Button>
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
            {/* Jangan mencetak "0 aset" saat yang terjadi adalah GAGAL memuat. */}
            {memuat || galat ? "" : `${data?.jumlah ?? 0} aset`}
            {!galat && data?.terpotong && " (dipotong pada plafon tampilan)"}
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
