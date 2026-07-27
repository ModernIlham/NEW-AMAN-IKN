// SBSK BERBASIS RUANG NYATA (Spasial Fase 15).
//
// Selama ini tabel SBSK berdiri sendiri: angka "247 m² untuk pimpinan" tanpa
// satu pun ruangan nyata untuk dibandingkan. Denah poligon mengubah itu — luas
// dihitung DARI GAMBARNYA, bukan dari angka yang diketik ulang seseorang.
//
// YANG PALING BERGUNA DI LAYAR INI bukan kolom "sesuai", melainkan dua angka
// yang biasanya tak ada di mana pun: ruangan yang sudah tergambar tetapi belum
// ditetapkan peruntukannya, dan ruangan yang tak berperuntukan SEKALIGUS tak
// berisi aset apa pun — ruang menganggur. Itulah bukti yang menahan usulan
// pengadaan ruang baru, dan karena itu ia ditaruh sebagai kartu, bukan
// disembunyikan di kolom tabel.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Ruler, Loader2, Download, DoorOpen } from "lucide-react";
import { Button } from "@/components/ui/button";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const WARNA_STATUS = {
  sesuai: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  di_bawah: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  melebihi: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
  tanpa_standar: "bg-muted text-muted-foreground",
};
const LABEL_STATUS = {
  sesuai: "sesuai", di_bawah: "di bawah", melebihi: "melebihi",
  tanpa_standar: "tanpa acuan",
};

const angka = (n) => Number(n || 0).toLocaleString("id-ID",
  { maximumFractionDigits: 2 });

// CSV dibuat DI KLIEN: datanya sudah ada di layar, jadi memutar ulang lewat
// server hanya menambah bolak-balik untuk tabel yang sama.
function simpanBlob(data, namaFile) {
  const url = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = url;
  a.download = namaFile;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

export default function SbskRuangPanel() {
  const [gedung, setGedung] = useState([]);
  const [pilih, setPilih] = useState("");
  const [data, setData] = useState(null);
  const [memuat, setMemuat] = useState(false);

  // Node yang LAYAK jadi lingkup: yang punya keturunan ruangan. Menawarkan
  // seluruh pohon (termasuk ruangan itu sendiri) hanya membuat pengguna
  // memilih lingkup yang isinya dirinya sendiri.
  useEffect(() => {
    let batal = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/spasial/node`, { timeout: 20000 });
        if (batal) return;
        const items = (r.data?.items || []).filter(
          (n) => ["TAPAK", "GEDUNG", "LANTAI", "SAYAP"].includes(n.tipe));
        setGedung(items);
        if (items.length) setPilih((p) => p || items[0].id);
      } catch {
        // Denah belum dibangun bukan galat yang perlu diteriakkan di halaman
        // Perencanaan — panel cukup menampilkan ajakan membuka Master Denah.
        if (!batal) setGedung([]);
      }
    })();
    return () => { batal = true; };
  }, []);

  const muat = useCallback(async (nodeId) => {
    if (!nodeId) { setData(null); return; }
    setMemuat(true);
    try {
      const r = await axios.get(`${API}/perencanaan/sbsk-ruang`, {
        params: { node_id: nodeId, dalam: "true", tipe: "RUANGAN" },
        timeout: 30000,
      });
      setData(r.data);
    } catch (e) {
      setData(null);
      toast.error(e?.response?.data?.detail || "Gagal memuat SBSK ruang");
    } finally { setMemuat(false); }
  }, []);

  useEffect(() => { muat(pilih); }, [muat, pilih]);

  const items = useMemo(() => data?.items || [], [data]);
  const rekap = data?.rekap || {};

  const unduhCsv = () => {
    if (!items.length) return;
    const kolom = ["Lokasi", "Ruangan", "Peruntukan", "Luas (m2)",
                   "Standar (m2)", "Selisih (m2)", "Status", "Jumlah aset",
                   "Pemegang", "Menganggur"];
    // Pemisah titik-koma + BOM: Excel Indonesia memakai koma sebagai desimal,
    // sehingga CSV berkoma memecah angka ke kolom berikutnya.
    const baris = items.map((b) => [
      b.jalur_nama, b.nama, b.peruntukan, b.luas_m2,
      b.standar_m2 ?? "", b.selisih_m2 ?? "", LABEL_STATUS[b.status] || b.status,
      b.jumlah_aset, (b.pemegang || []).join(" / "),
      b.menganggur ? "ya" : "",
    ].map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(";"));
    simpanBlob(new Blob(["﻿" + [kolom.join(";"), ...baris].join("\r\n")],
      { type: "text/csv;charset=utf-8" }),
      `sbsk-ruang-${(data?.node?.nama || "denah").replace(/\s+/g, "-")}.csv`);
  };

  return (
    <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden"
         data-testid="sbsk-ruang-panel">
      <div className="px-3 py-2 border-b border-border flex items-center gap-2">
        <Ruler className="w-4 h-4 text-teal-600 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="text-xs font-bold">SBSK Ruang — luas nyata dari denah</p>
          <p className="text-[10px] text-muted-foreground">
            Luas dihitung dari poligon denah, bukan angka ketikan (PMK 138/2024).
          </p>
        </div>
        <Button variant="outline" size="sm" className="h-8 px-2 text-[11px] shrink-0"
                disabled={!items.length} onClick={unduhCsv}
                data-testid="sbsk-ruang-csv">
          <Download className="w-3.5 h-3.5 sm:mr-1" />
          <span className="hidden sm:inline">CSV</span>
        </Button>
      </div>

      {gedung.length === 0 ? (
        <p className="text-[11px] text-muted-foreground px-3 py-6 text-center">
          Belum ada gedung/lantai bergeometri. Gambar denahnya lebih dulu di
          Master Denah (Referensi &amp; Master Data → Hierarki Spasial).
        </p>
      ) : (
        <div className="p-3 space-y-3">
          <select value={pilih} onChange={(e) => setPilih(e.target.value)}
                  className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                  data-testid="sbsk-ruang-lingkup">
            {gedung.map((n) => (
              <option key={n.id} value={n.id}>
                {n.nama}{n.kode ? ` · ${n.kode}` : ""} ({n.tipe})
              </option>
            ))}
          </select>

          {memuat ? (
            <div className="flex items-center justify-center py-8 text-muted-foreground">
              <Loader2 className="w-5 h-5 animate-spin mr-2" /> Memuat…
            </div>
          ) : !data ? null : (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 text-center">
                {[["Ruangan", rekap.jumlah_ruangan ?? 0],
                  ["Luas total", `${angka(rekap.luas_total_m2)} m²`],
                  ["Tanpa peruntukan", rekap.tanpa_peruntukan ?? 0],
                  ["Menganggur", rekap.menganggur ?? 0]].map(([l, v]) => (
                  <div key={l} className="rounded-lg border border-border py-1.5">
                    <p className="text-sm font-bold tabular-nums">{v}</p>
                    <p className="text-[10px] text-muted-foreground">{l}</p>
                  </div>
                ))}
              </div>

              {rekap.menganggur > 0 && (
                <div className="flex items-start gap-2 rounded-lg border border-amber-500/50 bg-amber-500/10 p-2"
                     data-testid="sbsk-ruang-menganggur">
                  <DoorOpen className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <p className="text-[11px] min-w-0">
                    <span className="font-semibold">
                      {rekap.menganggur} ruangan ({angka(rekap.luas_menganggur_m2)} m²)
                    </span>{" "}
                    sudah tergambar tetapi belum ditetapkan peruntukannya DAN
                    tidak berisi aset apa pun. Pertimbangkan ini sebelum
                    menyetujui usulan pengadaan ruang baru.
                  </p>
                </div>
              )}

              <div className="rounded-lg border border-border max-h-[46vh] overflow-y-auto">
                {items.length === 0 ? (
                  <p className="text-[11px] text-muted-foreground px-3 py-6 text-center">
                    Belum ada ruangan bergeometri di lingkup ini.
                  </p>
                ) : (
                  <ul className="divide-y divide-border/60" data-testid="sbsk-ruang-daftar">
                    {items.map((b) => (
                      <li key={b.node_id} className="px-3 py-2 flex items-start gap-2">
                        <span className="min-w-0 flex-1">
                          <span className="text-xs font-semibold block truncate">
                            {b.nama}
                            <span className="font-normal text-muted-foreground">
                              {" "}· {angka(b.luas_m2)} m²
                            </span>
                          </span>
                          <span className="text-[11px] text-muted-foreground block truncate">
                            {[b.peruntukan || "belum ditetapkan peruntukannya",
                              b.standar_m2 != null
                                && `standar ${angka(b.standar_m2)} m² (${b.standar_peruntukan})`,
                              b.selisih_m2 != null
                                && `${b.selisih_m2 > 0 ? "+" : ""}${angka(b.selisih_m2)} m²`,
                              b.jumlah_aset > 0 && `${b.jumlah_aset} aset`,
                              b.menganggur && "MENGANGGUR"]
                              .filter(Boolean).join(" · ")}
                          </span>
                        </span>
                        <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded shrink-0 ${
                          WARNA_STATUS[b.status] || WARNA_STATUS.tanpa_standar}`}>
                          {LABEL_STATUS[b.status] || b.status}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {(data.sebaran || []).length > 1 && (
                <div className="rounded-lg border border-border overflow-hidden"
                     data-testid="sbsk-ruang-sebaran">
                  <p className="px-3 py-1.5 text-[11px] font-semibold bg-muted/40">
                    Sebaran per lokasi
                  </p>
                  <ul className="divide-y divide-border/40">
                    {data.sebaran.map((e) => (
                      <li key={e.induk} className="px-3 py-1.5 flex items-center gap-2 text-[11px]">
                        <span className="min-w-0 flex-1 truncate">{e.induk}</span>
                        <span className="text-muted-foreground shrink-0 tabular-nums">
                          {e.jumlah_ruangan} ruangan · {angka(e.luas_m2)} m²
                          {e.menganggur > 0 && ` · ${e.menganggur} menganggur`}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <p className="text-[10px] text-muted-foreground">
                Toleransi kesesuaian ±{data.toleransi_persen}% — denah dijiplak
                dari gambar kerja, ketelitiannya bukan sentimeter.
                {data.terpotong && " Daftar dipotong pada plafon tampilan."}
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
