import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import { FileDown, Scale } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function apiErr(e, fb) { return e?.response?.data?.detail || fb; }

const WARNA = {
  penelusuran: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  telaah: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
  tgr_ditetapkan: "bg-violet-500/15 text-violet-600 dark:text-violet-400",
  bebas_tgr: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  lunas: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  dibatalkan: "bg-muted text-muted-foreground",
};

// Field wajib per transisi keputusan (selaras tgr_utils backend).
const FIELD_TRANSISI = {
  tgr_ditetapkan: { nomor: "Nomor SKTJM/SK Pembebanan", nilai: true },
  bebas_tgr: { nomor: "Nomor surat keterangan bebas TGR", nilai: false },
  lunas: { nomor: "Nomor bukti setor pelunasan", nilai: false },
};

/**
 * Kartu TGR Aset Hilang (PP 38/2016 + PMK 83/2016) — ASET-TGR.
 *
 * SK penghapusan jalur Tidak Ditemukan DITOLAK server selama aset belum
 * punya tiket TGR berkeputusan; kartu ini tempat membuka tiket (dari usulan
 * penghapusan jalur tidak_ditemukan yang belum ber-TGR) dan menjalankan
 * telaahnya sampai keputusan.
 */
export default function KartuTgr({ isAdmin }) {
  const [data, setData] = useState(null);
  const [kandidat, setKandidat] = useState([]);   // usulan hilang tanpa TGR
  const [buka, setBuka] = useState(null);          // {asset_id, pj, nip, kronologi}
  const [aksi, setAksi] = useState(null);          // {id, ke, nomor, nilai}
  const [sibuk, setSibuk] = useState(false);

  const muat = useCallback(async () => {
    try {
      const [rt, ru] = await Promise.all([
        axios.get(`${API}/tgr`),
        axios.get(`${API}/penghapusan/usulan`),
      ]);
      setData(rt.data);
      const berTgr = new Set((rt.data?.items || [])
        .filter((t) => t.status !== "dibatalkan").map((t) => t.asset_id));
      setKandidat((ru.data?.items || []).filter(
        (u) => u.jalur === "tidak_ditemukan" && u.status !== "ditolak"
          && !berTgr.has(u.asset_id)));
    } catch (e) {
      toast.error(apiErr(e, "Gagal memuat register TGR"));
    }
  }, []);
  useEffect(() => { muat(); }, [muat]);

  const simpanTiket = async () => {
    if (!buka) return;
    setSibuk(true);
    try {
      await axios.post(`${API}/tgr`, {
        asset_id: buka.asset_id, penanggung_jawab: buka.pj,
        nip_penanggung_jawab: buka.nip || "", kronologi: buka.kronologi,
      });
      toast.success("Tiket TGR dibuka — status Penelusuran");
      setBuka(null);
      muat();
    } catch (e) {
      toast.error(apiErr(e, "Gagal membuka tiket TGR"));
    } finally {
      setSibuk(false);
    }
  };

  const kirimTransisi = async () => {
    if (!aksi) return;
    setSibuk(true);
    try {
      await axios.post(`${API}/tgr/${aksi.id}/status`, {
        status: aksi.ke, nomor_dokumen: aksi.nomor || "",
        nilai_ganti_rugi: Number(aksi.nilai || 0), catatan: "",
      });
      toast.success(`Status TGR: ${data?.label_status?.[aksi.ke] || aksi.ke}`);
      setAksi(null);
      muat();
    } catch (e) {
      toast.error(apiErr(e, "Gagal mengubah status TGR"));
    } finally {
      setSibuk(false);
    }
  };

  const items = data?.items || [];
  if (!data) return null;
  if (items.length === 0 && kandidat.length === 0) return null;

  return (
    <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden"
      data-testid="kartu-tgr">
      <div className="px-3 py-2 border-b border-border flex items-center gap-2 flex-wrap">
        <Scale className="w-4 h-4 text-muted-foreground" />
        <p className="text-xs font-bold flex-1 min-w-[180px]">
          TGR Aset Hilang (PP 38/2016) — SK penghapusan aset hilang terkunci
          sampai TGR berkeputusan
        </p>
        {items.length > 0 && (
          <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
            onClick={() => downloadFileWithProgress(`${API}/tgr/export`,
              "register_tgr.csv", { label: "Ekspor Register TGR (CSV)" }).catch(() => {})}
            data-testid="tgr-export">
            <FileDown className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">CSV</span>
          </Button>
        )}
      </div>

      {kandidat.length > 0 && (
        <div className="px-3 py-2 border-b border-border/60 space-y-1.5">
          <p className="text-[11px] font-semibold text-amber-600 dark:text-amber-400">
            Usulan penghapusan aset hilang TANPA tiket TGR ({kandidat.length}):
          </p>
          {kandidat.map((u) => (
            <div key={u.id} className="text-[11px] flex items-center gap-2 flex-wrap"
              data-testid={`tgr-kandidat-${u.id}`}>
              <span className="font-mono">{u.asset_code}/{u.NUP}</span>
              <span className="flex-1 min-w-[120px] truncate">{u.asset_name}</span>
              <Button size="sm" variant="outline" className="h-6 text-[10px] min-h-0"
                onClick={() => setBuka({ asset_id: u.asset_id, pj: "", nip: "", kronologi: "" })}
                data-testid={`tgr-buka-${u.id}`}>
                Buka tiket TGR
              </Button>
            </div>
          ))}
          {buka && (
            <div className="rounded-lg border border-border p-2 space-y-1.5">
              <Input value={buka.pj} onChange={(e) => setBuka({ ...buka, pj: e.target.value })}
                placeholder="Penanggung jawab (pemegang saat hilang) *"
                className="h-8 text-xs" data-testid="tgr-pj" />
              <Input value={buka.nip} onChange={(e) => setBuka({ ...buka, nip: e.target.value })}
                placeholder="NIP/NIK (opsional)" className="h-8 text-xs" />
              <Input value={buka.kronologi}
                onChange={(e) => setBuka({ ...buka, kronologi: e.target.value })}
                placeholder="Kronologi kehilangan (minimal 10 karakter) *"
                className="h-8 text-xs" data-testid="tgr-kronologi" />
              <div className="flex gap-1.5">
                <Button size="sm" disabled={sibuk || !buka.pj.trim() || buka.kronologi.trim().length < 10}
                  onClick={simpanTiket} data-testid="tgr-simpan">Buka Tiket</Button>
                <Button size="sm" variant="ghost" onClick={() => setBuka(null)}>Urungkan</Button>
              </div>
            </div>
          )}
        </div>
      )}

      {items.length > 0 && (
        <ul className="divide-y divide-border/60">
          {items.map((t) => (
            <li key={t.id} className="p-3 space-y-1.5" data-testid={`tgr-${t.id}`}>
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${WARNA[t.status] || "bg-muted"}`}>
                  {data.label_status?.[t.status] || t.status}
                </span>
                <span className="font-mono text-[11px]">{t.asset_code}/{t.NUP}</span>
                <p className="text-sm font-semibold flex-1 min-w-[140px] truncate">{t.asset_name}</p>
              </div>
              <p className="text-[11px] text-muted-foreground">
                {[`PJ: ${t.penanggung_jawab || "-"}`,
                  t.nomor_dokumen && `Dok ${t.nomor_dokumen}`,
                  t.nilai_ganti_rugi > 0 && `Ganti rugi Rp${Math.round(t.nilai_ganti_rugi).toLocaleString("id-ID")}`,
                  t.kronologi].filter(Boolean).join(" · ")}
              </p>
              {isAdmin && (data.transisi?.[t.status] || []).length > 0 && (
                <div className="flex gap-1.5 flex-wrap items-center">
                  {(data.transisi[t.status] || []).map((ke) => (
                    <Button key={ke} size="sm" variant="outline"
                      className="h-7 text-[11px] min-h-0"
                      onClick={() => setAksi({ id: t.id, ke, nomor: "", nilai: "" })}
                      data-testid={`tgr-ke-${t.id}-${ke}`}>
                      {data.label_status?.[ke] || ke}
                    </Button>
                  ))}
                </div>
              )}
              {aksi?.id === t.id && (
                <div className="flex gap-1.5 items-center flex-wrap rounded-lg border border-border p-2">
                  {FIELD_TRANSISI[aksi.ke]?.nomor && (
                    <Input value={aksi.nomor}
                      onChange={(e) => setAksi({ ...aksi, nomor: e.target.value })}
                      placeholder={`${FIELD_TRANSISI[aksi.ke].nomor} *`}
                      className="h-8 flex-1 min-w-[180px] text-xs" data-testid="tgr-nomor" />
                  )}
                  {FIELD_TRANSISI[aksi.ke]?.nilai && (
                    <Input type="number" value={aksi.nilai}
                      onChange={(e) => setAksi({ ...aksi, nilai: e.target.value })}
                      placeholder="Nilai ganti rugi (Rp) *"
                      className="h-8 w-44 text-xs" data-testid="tgr-nilai" />
                  )}
                  <Button size="sm" disabled={sibuk
                      || (FIELD_TRANSISI[aksi.ke]?.nomor && !aksi.nomor.trim())
                      || (FIELD_TRANSISI[aksi.ke]?.nilai && !(Number(aksi.nilai) > 0))}
                    onClick={kirimTransisi} data-testid="tgr-kirim">Simpan</Button>
                  <Button size="sm" variant="ghost" onClick={() => setAksi(null)}>Urungkan</Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
