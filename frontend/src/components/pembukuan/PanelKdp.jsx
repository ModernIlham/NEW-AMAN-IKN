import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Construction, PlusCircle, CheckCircle2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const fmtRp = (v) => `Rp${Math.round(Number(v || 0)).toLocaleString("id-ID")}`;

function apiErr(e, fb) { return e?.response?.data?.detail || fb; }

/**
 * Panel KDP (Konstruksi Dalam Pengerjaan) — daftar aset golongan 7 dengan
 * dua aksi siklusnya: Pengembangan (termin, jurnal 503) dan Penyelesaian
 * menjadi aset definitif (pasangan jurnal 505+105, kode barang berganti
 * in-place). Perolehan KDP-nya sendiri lewat pencatatan aset biasa dengan
 * kode barang golongan 7 (jurnal 502 otomatis).
 */
export default function PanelKdp() {
  const [data, setData] = useState(null);
  const [aksi, setAksi] = useState(null);   // {id, jenis: "kembang"|"selesai"}
  const [nilai, setNilai] = useState("");
  const [ket, setKet] = useState("");
  const [kodeBaru, setKodeBaru] = useState("");
  const [sibuk, setSibuk] = useState(false);

  const muat = useCallback(() => {
    axios.get(`${API}/pembukuan/kdp`)
      .then((r) => setData(r.data))
      .catch((e) => toast.error(apiErr(e, "Gagal memuat daftar KDP")));
  }, []);
  useEffect(() => { muat(); }, [muat]);

  const bukaAksi = (id, jenis) => {
    setAksi({ id, jenis });
    setNilai(""); setKet(""); setKodeBaru("");
  };

  const kirim = async () => {
    if (!aksi) return;
    setSibuk(true);
    try {
      // Gerbang ASET-GERBANG-1: bila wajib-persetujuan aktif, transaksi
      // diajukan sebagai permohonan (eksekusi menunggu persetujuan KPB).
      const { ajukanPermohonanAset, gerbangPermohonanAsetAktif,
              pesanPermohonanTerkirim } = await import("@/lib/permohonanAset");
      const lewatPermohonan = await gerbangPermohonanAsetAktif();
      if (aksi.jenis === "kembang") {
        const payload = { nilai: Number(nilai || 0), keterangan: ket };
        if (lewatPermohonan) {
          await ajukanPermohonanAset("kdp_pengembangan", aksi.id, payload);
          toast.success(pesanPermohonanTerkirim("Pengembangan KDP"));
        } else {
          const r = await axios.post(`${API}/pembukuan/kdp/${aksi.id}/pengembangan`, payload);
          toast.success(`Pengembangan tercatat (503) — nilai berjalan ${fmtRp(r.data?.nilai_berjalan)}`);
        }
      } else {
        const payload = { kode_baru: kodeBaru, alasan: ket };
        if (lewatPermohonan) {
          await ajukanPermohonanAset("kdp_selesai", aksi.id, payload);
          toast.success(pesanPermohonanTerkirim("Penyelesaian KDP"));
        } else {
          const r = await axios.post(`${API}/pembukuan/kdp/${aksi.id}/selesaikan`, payload);
          toast.success(`KDP selesai → ${r.data?.kode_baru}/${r.data?.nup_baru} (jurnal 505+105)`);
        }
      }
      setAksi(null);
      muat();
    } catch (e) {
      toast.error(apiErr(e, "Gagal menyimpan"));
    } finally {
      setSibuk(false);
    }
  };

  return (
    <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="pembukuan-panel-kdp">
      <div className="px-3 py-2 border-b border-border flex items-center gap-2 flex-wrap">
        <Construction className="w-4 h-4 text-muted-foreground" />
        <p className="text-xs font-bold flex-1 min-w-[180px]">
          Konstruksi Dalam Pengerjaan (golongan 7) — perolehan 502 otomatis,
          pengembangan 503, penyelesaian 505+105
        </p>
        {data && (
          <span className="text-[11px] text-muted-foreground">
            Total berjalan: <b>{fmtRp(data.total_nilai)}</b>
          </span>
        )}
      </div>
      {!data ? (
        <p className="text-sm text-muted-foreground py-8 text-center">Memuat…</p>
      ) : data.items.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center px-4" data-testid="kdp-kosong">
          Belum ada KDP. Catat aset baru dengan kode barang golongan 7
          (mis. lewat form aset / Pengadaan jenis pembangunan) — jurnal 502
          tercatat otomatis, lalu kelola termin & penyelesaiannya di sini.
        </p>
      ) : (
        <ul className="divide-y divide-border">
          {data.items.map((it) => (
            <li key={it.id} className="p-3 space-y-2" data-testid={`kdp-item-${it.id}`}>
              <div className="flex items-start gap-2 flex-wrap">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold">{it.asset_name}</p>
                  <p className="text-[11px] text-muted-foreground">
                    {it.asset_code}/{it.NUP}
                    {it.location ? <> · {it.location}</> : null}
                    {" "}· nilai berjalan <b>{fmtRp(it.nilai)}</b>
                  </p>
                </div>
                <div className="flex gap-1.5">
                  <Button size="sm" variant="outline" onClick={() => bukaAksi(it.id, "kembang")}
                    data-testid={`kdp-pengembangan-${it.id}`}>
                    <PlusCircle className="w-3.5 h-3.5 mr-1" />Pengembangan
                  </Button>
                  <Button size="sm" onClick={() => bukaAksi(it.id, "selesai")}
                    data-testid={`kdp-selesaikan-${it.id}`}>
                    <CheckCircle2 className="w-3.5 h-3.5 mr-1" />Selesaikan
                  </Button>
                </div>
              </div>
              {aksi?.id === it.id && (
                <div className="flex gap-1.5 items-center flex-wrap rounded-lg border border-border p-2">
                  {aksi.jenis === "kembang" ? (
                    <>
                      <Input type="number" value={nilai} onChange={(e) => setNilai(e.target.value)}
                        placeholder="Nilai termin (Rp)" className="h-8 w-40 text-xs"
                        data-testid="kdp-nilai" />
                      <Input value={ket} onChange={(e) => setKet(e.target.value)}
                        placeholder="Keterangan (mis. termin II)" className="h-8 flex-1 min-w-[140px] text-xs" />
                    </>
                  ) : (
                    <>
                      <Input value={kodeBaru} onChange={(e) => setKodeBaru(e.target.value)}
                        placeholder="Kode barang definitif 10 digit (bukan 7xxx)"
                        className="h-8 w-64 text-xs" maxLength={10}
                        data-testid="kdp-kode-baru" />
                      <Input value={ket} onChange={(e) => setKet(e.target.value)}
                        placeholder="Alasan/berita acara" className="h-8 flex-1 min-w-[140px] text-xs" />
                    </>
                  )}
                  <Button size="sm" disabled={sibuk
                      || (aksi.jenis === "kembang"
                        ? !(Number(nilai) > 0) : kodeBaru.length !== 10)}
                    onClick={kirim} data-testid="kdp-kirim">Simpan</Button>
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
