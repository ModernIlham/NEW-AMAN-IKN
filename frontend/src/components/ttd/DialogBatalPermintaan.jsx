import React from "react";
import { Loader2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";

/** Panjang minimum alasan pembatalan — HARUS sama dengan `MIN_ALASAN_BATAL`
 *  di `backend/routes/ttd.py`. Angka ini menahan "x" atau satu ketukan spasi
 *  yang lolos uji tak-kosong tetapi tak menjelaskan apa pun. */
export const MIN_ALASAN_BATAL = 5;

/** Akibat pembatalan DI LUAR modul e-sign, per jenis dokumen. Ditulis di sini
 *  karena inilah satu-satunya layar tempat pengguna masih bisa mundur. */
const AKIBAT_TAUT = {
  bast: "BAST yang tertaut beserta asetnya akan ditandai TT dicabut.",
  lpb: "LPB yang tertaut akan ditandai TT dicabut.",
};

/**
 * Kotak alasan pembatalan permintaan TTD.
 *
 * Permintaan pemilik: *"ketika diklik pembatalan permintaan di ttd
 * elektronik, munculkan kotak penjelasan alasannya kenapa."*
 *
 * MENGGANTIKAN konfirmasi ya/tidak. Konfirmasi hanya menahan salah-tekan; ia
 * tak menjawab pertanyaan yang PASTI muncul sesudahnya — para penanda tangan
 * mendapati tautannya mati, dan bila permintaan ini menaut BAST maka BAST
 * beserta asetnya ikut bertanda "TT dicabut". Yang bertanya "kenapa?" bukan
 * hanya pemeriksa audit, melainkan orang-orang di dalam permintaan itu.
 */
export default function DialogBatalPermintaan({
  permintaan, alasan = "", onAlasan, onBatalkan, onTutup, sedangMemproses = false,
}) {
  const p = permintaan || null;
  const bersih = (alasan || "").trim();
  const kurang = bersih.length < MIN_ALASAN_BATAL;
  const akibat = AKIBAT_TAUT[p?.doc_type];

  return (
    <Dialog open={!!p} onOpenChange={(o) => { if (!o && !sedangMemproses) onTutup?.(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader className="text-left space-y-1">
          {/* Rata kiri + pemenggalan di mana saja: judulnya kerap nomor BAST
              panjang tanpa spasi, yang di tengah terpecah jadi dua baris
              ragged. Sejalan dengan kepala dialog detail. */}
          <DialogTitle className="text-base leading-snug [overflow-wrap:anywhere]">
            Batalkan permintaan &ldquo;{p?.judul_tampil || p?.judul}&rdquo;?
          </DialogTitle>
          <DialogDescription className="text-[11px] leading-relaxed">
            Seluruh tautan tanda tangan yang sudah dibagikan akan <b>mati permanen</b> dan
            tidak bisa dipulihkan.{akibat ? ` ${akibat}` : ""}
          </DialogDescription>
        </DialogHeader>
        <div>
          <label className="text-xs font-semibold text-muted-foreground"
            htmlFor="ttd-batal-alasan">Alasan pembatalan *</label>
          <textarea rows={3} id="ttd-batal-alasan" value={alasan}
            onChange={(e) => onAlasan?.(e.target.value)}
            placeholder="Contoh: dokumen salah unggah, akan dikirim ulang dengan lampiran yang benar"
            className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-y"
            data-testid="ttd-batal-alasan" />
          <p className="mt-1 text-[10px] text-muted-foreground">
            Tercatat dalam jejak audit dan ditampilkan pada permintaan ini.
            Minimal {MIN_ALASAN_BATAL} karakter.
          </p>
        </div>
        <DialogFooter className="flex-row flex-wrap justify-end gap-1.5 space-x-0">
          {/* "Kembali", bukan "Batal": pada dialog pembatalan, tombol berlabel
              "Batal" berarti dua hal yang berlawanan sekaligus. */}
          <Button variant="outline" onClick={() => onTutup?.()} disabled={sedangMemproses}
            className="h-9 text-xs" data-testid="ttd-batal-kembali">Kembali</Button>
          <Button onClick={() => onBatalkan?.()} data-testid="ttd-batal-konfirmasi"
            disabled={sedangMemproses || kurang}
            className="h-9 text-xs bg-red-600 hover:bg-red-700 text-white">
            {sedangMemproses ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
              : <XCircle className="w-3.5 h-3.5 mr-1.5" />}
            Batalkan Permintaan
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
