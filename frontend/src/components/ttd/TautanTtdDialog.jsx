import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { bagikanWa, bagikanEmail } from "@/lib/pesanTtd";
import { teksSisaWaktu, warnaSisaWaktu, sudahKedaluwarsa } from "@/lib/sisaWaktu";
import { bisaTerbitUlang } from "@/lib/statusTtd";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Tautan tanda tangan sebuah dokumen — DIBUKA KAPAN SAJA, bukan sekali saat
 * dikirim.
 *
 * Laporan pemilik: dialog tautan yang lama hanya hidup di layar. Begitu
 * ditutup, tautannya tak bisa ditemukan lagi dari dokumennya; satu-satunya
 * jalan kembali adalah modul TTD Elektronik, dan ketika orang akhirnya ke
 * sana jendela 14 harinya kerap sudah lewat.
 *
 * Komponen ini menjadi jalan kembali itu: status per penanda tangan, sisa
 * waktu tautannya, dan tombol terbitkan ulang untuk yang sudah mati.
 *
 * TAUTAN TIDAK DITERBITKAN OTOMATIS saat dialog dibuka. Menerbitkan ulang
 * MEMATIKAN tautan lama (jti baru) — melakukannya hanya karena seseorang
 * melihat-lihat akan membatalkan tautan yang sudah telanjur dikirim ke orang
 * yang belum sempat meneken.
 */
export default function TautanTtdDialog({ srId, judul = "Dokumen", ringkas = null,
                                          onTutup, onBerubah }) {
  const [data, setData] = useState(null);
  const [muat, setMuat] = useState(false);
  const [terbit, setTerbit] = useState("");     // signer_id yang sedang diproses
  const [tautan, setTautan] = useState({});     // signer_id → link baru

  const muatDetail = useCallback(async () => {
    if (!srId) return;
    setMuat(true);
    try {
      const r = await axios.get(`${API}/ttd/permintaan/${srId}`);
      setData(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memuat permintaan TTD");
    } finally {
      setMuat(false);
    }
  }, [srId]);

  useEffect(() => { muatDetail(); }, [muatDetail]);

  const terbitkanUlang = async (s) => {
    setTerbit(s.signer_id);
    try {
      const r = await axios.post(
        `${API}/ttd/permintaan/${srId}/link/${s.signer_id}`);
      setTautan((t) => ({ ...t, [s.signer_id]: r.data?.link || "" }));
      toast.success(`Tautan baru untuk ${s.nama} — berlaku 14 hari`);
      muatDetail();
      onBerubah?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menerbitkan tautan");
    } finally {
      setTerbit("");
    }
  };

  const signers = data?.signers || [];
  const selesai = signers.filter((s) => s.status === "ditandatangani").length;

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onTutup?.(); }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Tanda tangan elektronik</DialogTitle>
          <DialogDescription>
            {judul} — {selesai}/{signers.length} sudah menandatangani. Tautan
            berlaku 14 hari dan sekali pakai; yang sudah mati bisa diterbitkan
            ulang di sini.
          </DialogDescription>
        </DialogHeader>
        {muat && !data ? (
          <div className="py-10 text-center">
            <Loader2 className="w-5 h-5 animate-spin mx-auto text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-2 max-h-[60vh] overflow-y-auto">
            {signers.length === 0 && (
              <p className="text-xs text-muted-foreground">Tidak ada penanda tangan.</p>
            )}
            {signers.map((s) => {
              const sudah = s.status === "ditandatangani";
              const link = tautan[s.signer_id];
              return (
                <div key={s.signer_id}
                  className="rounded-lg border border-border p-2.5 text-xs space-y-1.5"
                  data-testid={`ttd-signer-${s.signer_id}`}>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-semibold text-foreground min-w-0 flex-1 truncate">
                      {s.nama}
                    </span>
                    {sudah ? (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-700 dark:text-emerald-400">
                        Sudah menandatangani
                      </span>
                    ) : teksSisaWaktu(s.kedaluwarsa_info) ? (
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${warnaSisaWaktu(s.kedaluwarsa_info)}`}>
                        {sudahKedaluwarsa(s.kedaluwarsa_info)
                          ? "Tautan mati" : `Tautan ${teksSisaWaktu(s.kedaluwarsa_info)}`}
                      </span>
                    ) : null}
                  </div>
                  {s.jabatan && (
                    <p className="text-[10px] text-muted-foreground truncate">{s.jabatan}</p>
                  )}
                  {link && (
                    <p className="font-mono text-[10px] break-all text-muted-foreground"
                      data-testid={`ttd-link-baru-${s.signer_id}`}>{link}</p>
                  )}
                  {bisaTerbitUlang(s) && (
                    <div className="flex flex-wrap gap-1.5">
                      <Button size="sm" variant="outline" className="h-7 text-[11px]"
                        disabled={terbit === s.signer_id}
                        onClick={() => terbitkanUlang(s)}
                        data-testid={`ttd-terbit-ulang-${s.signer_id}`}>
                        {terbit === s.signer_id
                          ? <Loader2 className="w-3 h-3 animate-spin mr-1" />
                          : <RefreshCcw className="w-3 h-3 mr-1" />}
                        {link ? "Terbitkan ulang lagi" : "Terbitkan tautan"}
                      </Button>
                      {link && (
                        <>
                          <Button size="sm" variant="outline" className="h-7 text-[11px]"
                            onClick={() => navigator.clipboard?.writeText(link)
                              .then(() => toast.success("Tautan disalin"))
                              .catch(() => toast.error("Gagal menyalin"))}>Salin</Button>
                          <Button size="sm" variant="outline" className="h-7 text-[11px]"
                            onClick={() => bagikanWa(s.nama, judul, link, ringkas)}>WhatsApp</Button>
                          <Button size="sm" variant="outline" className="h-7 text-[11px]"
                            onClick={() => bagikanEmail(s.nama, judul, link, ringkas)}>Email</Button>
                        </>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
