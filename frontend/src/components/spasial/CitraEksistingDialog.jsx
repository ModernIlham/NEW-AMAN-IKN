// Registri CITRA EKSISTING — dialog admin di halaman Hierarki Spasial.
//
// Admin mendaftarkan citra (drone/ortofoto) yang sudah dipotong jadi ubin XYZ
// dan diunggah ke server. Panduan memotong & menaruh ubin:
// docs/LAPISAN-CITRA-EKSISTING.md. Dialog ini hanya mengurus REGISTRI-nya.
import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { CheckCircle2, Loader2, Pencil, Plus, Satellite, Trash2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { formatTanggalCitra, lupakanDaftarCitra, periksaUbinCitra } from "@/lib/lapisanCitra";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const KOSONG = {
  nama: "", sumber: "", tanggal_rekam: "", url_template: "/uploads/ubin/<nama-citra-tahun-bulan>/{z}/{x}/{y}.jpg",
  barat: "", selatan: "", timur: "", utara: "", zoom_min: "14", zoom_maks: "20",
  opasitas: "85", aktif: true, keterangan: "",
};

function keForm(l) {
  return {
    nama: l.nama || "", sumber: l.sumber || "", tanggal_rekam: l.tanggal_rekam || "",
    url_template: l.url_template || "",
    barat: String(l.batas?.barat ?? ""), selatan: String(l.batas?.selatan ?? ""),
    timur: String(l.batas?.timur ?? ""), utara: String(l.batas?.utara ?? ""),
    zoom_min: String(l.zoom_min ?? ""), zoom_maks: String(l.zoom_maks ?? ""),
    opasitas: String(Math.round((l.opasitas ?? 0.85) * 100)), aktif: l.aktif !== false,
    keterangan: l.keterangan || "",
  };
}

const angka = (v) => (String(v).trim() === "" ? null : Number(String(v).replace(",", ".")));

function kePayload(f) {
  return {
    nama: f.nama, sumber: f.sumber, tanggal_rekam: f.tanggal_rekam, url_template: f.url_template.trim(),
    batas: { barat: angka(f.barat), selatan: angka(f.selatan), timur: angka(f.timur), utara: angka(f.utara) },
    zoom_min: angka(f.zoom_min), zoom_maks: angka(f.zoom_maks),
    opasitas: (angka(f.opasitas) ?? 85) / 100, aktif: !!f.aktif, keterangan: f.keterangan,
  };
}

function Bidang({ label, children, bantu }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium">{label}</span>
      {children}
      {bantu && <span className="block text-[11px] text-muted-foreground leading-snug">{bantu}</span>}
    </label>
  );
}

export default function CitraEksistingDialog({ onClose }) {
  const [daftar, setDaftar] = useState([]);
  const [memuat, setMemuat] = useState(true);
  const [form, setForm] = useState(null);       // {id?, version?, ...field}
  const [menyimpan, setMenyimpan] = useState(false);
  const [periksa, setPeriksa] = useState({});   // id → hasil pemeriksaan
  const { confirm, confirmDialog } = useConfirm();

  const muat = useCallback(async () => {
    setMemuat(true);
    try {
      const r = await axios.get(`${API}/peta-lapisan`);
      setDaftar(Array.isArray(r.data?.items) ? r.data.items : []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Daftar citra gagal dimuat");
    } finally {
      setMemuat(false);
    }
  }, []);
  useEffect(() => { muat(); }, [muat]);

  const ubah = (k) => (e) => setForm((f) => ({ ...f, [k]: e?.target ? (e.target.type === "checkbox" ? e.target.checked : e.target.value) : e }));

  const simpan = async () => {
    setMenyimpan(true);
    try {
      const body = kePayload(form);
      if (form.id) await axios.put(`${API}/peta-lapisan/${form.id}`, { ...body, version: form.version });
      else await axios.post(`${API}/peta-lapisan`, body);
      lupakanDaftarCitra();
      toast.success(form.id ? "Citra diperbarui" : "Citra didaftarkan");
      setForm(null);
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan citra");
    } finally {
      setMenyimpan(false);
    }
  };

  const hapus = async (l) => {
    const ok = await confirm({
      title: "Hapus citra dari daftar?",
      description: `"${l.nama}" tidak akan tampil lagi di peta. Berkas ubin di server tidak ikut terhapus.`,
      confirmText: "Hapus", danger: true,
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/peta-lapisan/${l.id}`);
      lupakanDaftarCitra();
      toast.success("Citra dihapus dari daftar");
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus citra");
    }
  };

  const jalankanPeriksa = async (l) => {
    setPeriksa((p) => ({ ...p, [l.id]: { status: "memeriksa" } }));
    const hasil = await periksaUbinCitra(l);
    setPeriksa((p) => ({ ...p, [l.id]: hasil }));
  };

  return (
    <Dialog open onOpenChange={(v) => { if (!v) onClose?.(); }}>
      {confirmDialog}
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="citra-eksisting-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Satellite className="w-5 h-5 text-amber-600" /> Citra Eksisting
          </DialogTitle>
          <DialogDescription>
            Foto udara terbaru (drone/ortofoto) yang ditumpuk di atas peta dasar OSM. Citra tampil di peta
            semua pengguna saat tombol <b>Eksisting</b> dinyalakan, hanya di dalam batas wilayahnya.
          </DialogDescription>
        </DialogHeader>

        {!form && (
          <div className="space-y-2">
            {memuat && <div className="py-6 flex justify-center"><Loader2 className="w-5 h-5 animate-spin" /></div>}
            {!memuat && daftar.length === 0 && (
              <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground space-y-1" data-testid="citra-daftar-kosong">
                <p className="font-medium text-foreground">Belum ada citra terdaftar.</p>
                <p>
                  Siapkan citra sebagai ubin XYZ (mis. QGIS → Processing → <i>Generate XYZ tiles (Directory)</i>,
                  format JPG atau PNG), unggah foldernya ke server, lalu daftarkan di sini. Panduan lengkap:
                  <code className="mx-1 text-xs">docs/LAPISAN-CITRA-EKSISTING.md</code>.
                </p>
              </div>
            )}
            {daftar.map((l) => {
              const p = periksa[l.id];
              return (
                <div key={l.id} className="rounded-lg border p-3 space-y-1" data-testid={`citra-item-${l.id}`}>
                  <div className="flex items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="font-semibold text-sm truncate">{l.nama}</div>
                      <div className="text-xs text-muted-foreground">
                        Direkam {formatTanggalCitra(l.tanggal_rekam)}{l.sumber ? ` · ${l.sumber}` : ""} · zoom {l.zoom_min}–{l.zoom_maks}
                        {l.aktif ? "" : " · NONAKTIF"}
                      </div>
                      <div className="text-[11px] font-mono text-muted-foreground truncate">{l.url_template}</div>
                    </div>
                    <Button variant="outline" size="sm" onClick={() => jalankanPeriksa(l)}
                      disabled={p?.status === "memeriksa"} data-testid={`citra-periksa-${l.id}`}>
                      {p?.status === "memeriksa" ? <Loader2 className="w-4 h-4 animate-spin" /> : "Periksa"}
                    </Button>
                    {l.bisa_ubah && (
                      <>
                        <Button variant="ghost" size="icon" aria-label={`Ubah ${l.nama}`}
                          onClick={() => setForm({ id: l.id, version: l.version, ...keForm(l) })}
                          data-testid={`citra-ubah-${l.id}`}>
                          <Pencil className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="icon" aria-label={`Hapus ${l.nama}`}
                          onClick={() => hapus(l)} data-testid={`citra-hapus-${l.id}`}>
                          <Trash2 className="w-4 h-4 text-red-600" />
                        </Button>
                      </>
                    )}
                  </div>
                  {p && p.status !== "memeriksa" && (
                    <div className={`text-xs flex items-start gap-1.5 ${p.status === "ok" ? "text-emerald-700 dark:text-emerald-400" : "text-amber-700 dark:text-amber-400"}`}
                      data-testid={`citra-hasil-periksa-${l.id}`}>
                      {p.status === "ok" ? <CheckCircle2 className="w-3.5 h-3.5 mt-0.5 shrink-0" /> : <XCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />}
                      <span className="min-w-0">{p.pesan} <a href={p.url} target="_blank" rel="noreferrer" className="underline break-all">Contoh ubin</a></span>
                    </div>
                  )}
                  {!l.bisa_ubah && (
                    <div className="text-[11px] text-muted-foreground">Dikelola satker {l.kode_satker || "pusat"}.</div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {form && (
          <div className="space-y-3" data-testid="citra-form">
            <div className="grid sm:grid-cols-2 gap-3">
              <Bidang label="Nama citra *">
                <Input value={form.nama} onChange={ubah("nama")} placeholder="Citra drone kawasan inti" data-testid="citra-f-nama" />
              </Bidang>
              <Bidang label="Tanggal rekam *">
                <Input type="date" value={form.tanggal_rekam} onChange={ubah("tanggal_rekam")} data-testid="citra-f-tanggal" />
              </Bidang>
              <Bidang label="Sumber">
                <Input value={form.sumber} onChange={ubah("sumber")} placeholder="Tim satker (drone)" data-testid="citra-f-sumber" />
              </Bidang>
              <Bidang label="Opasitas bawaan (%)">
                <Input type="number" min="10" max="100" value={form.opasitas} onChange={ubah("opasitas")} data-testid="citra-f-opasitas" />
              </Bidang>
            </div>
            <Bidang label="Alamat ubin *" bantu={'Jalur di server ini (diawali "/") atau alamat https://, wajib memuat {z}, {x}, {y}.'}>
              <Input value={form.url_template} onChange={ubah("url_template")} className="font-mono text-xs" data-testid="citra-f-url" />
            </Bidang>
            <div>
              <span className="text-xs font-medium">Batas wilayah (derajat, WGS84) *</span>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-1">
                {[["barat", "Barat (bujur min)"], ["selatan", "Selatan (lintang min)"], ["timur", "Timur (bujur maks)"], ["utara", "Utara (lintang maks)"]].map(([k, lbl]) => (
                  <Bidang key={k} label={<span className="text-[11px] text-muted-foreground">{lbl}</span>}>
                    <Input inputMode="decimal" value={form[k]} onChange={ubah(k)} data-testid={`citra-f-${k}`} />
                  </Bidang>
                ))}
              </div>
              <p className="text-[11px] text-muted-foreground mt-1">Ubin hanya diminta di dalam kotak ini — tidak ada permintaan sia-sia di luar area.</p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Bidang label="Zoom minimum *">
                <Input type="number" min="0" max="22" value={form.zoom_min} onChange={ubah("zoom_min")} data-testid="citra-f-zmin" />
              </Bidang>
              <Bidang label="Zoom maksimum ubin *" bantu="Zoom tertinggi yang ubinnya ada; di atasnya ubin diperbesar.">
                <Input type="number" min="0" max="22" value={form.zoom_maks} onChange={ubah("zoom_maks")} data-testid="citra-f-zmaks" />
              </Bidang>
            </div>
            <Bidang label="Keterangan">
              <Input value={form.keterangan} onChange={ubah("keterangan")} data-testid="citra-f-keterangan" />
            </Bidang>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.aktif} onChange={ubah("aktif")} className="min-w-0 min-h-0 w-4 h-4" data-testid="citra-f-aktif" />
              Aktif (tampil di peta). Matikan untuk mengarsipkan tanpa menghapus.
            </label>
          </div>
        )}

        <DialogFooter className="gap-2">
          {form ? (
            <>
              <Button variant="outline" onClick={() => setForm(null)} disabled={menyimpan}>Batal</Button>
              <Button onClick={simpan} disabled={menyimpan} data-testid="citra-simpan">
                {menyimpan && <Loader2 className="w-4 h-4 mr-1 animate-spin" />} Simpan
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={onClose}>Tutup</Button>
              <Button onClick={() => setForm({ ...KOSONG })} data-testid="citra-tambah">
                <Plus className="w-4 h-4 mr-1" /> Daftarkan citra
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
