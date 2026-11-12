import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Pencil, Plus, Power, Trash2, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import InputTanggalRoda from "@/components/ui/input-tanggal-roda";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { isSuperAdminPusat } from "@/lib/satkerAktif";
import { namaInstansi } from "@/components/pegawai/BilahLingkupLuar";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Sebutan `nomor_induk` mengikuti jenis badan (3.7a). Hanya label layar;
// nilainya diketik dari dokumen resmi badan itu, tidak ditebak.
export const LABEL_NOMOR_INDUK = {
  bumn: "NIB", bumd: "NIB", bumdes: "NIB / nomor badan hukum BUM Desa",
  badan_usaha_swasta: "NIB", satuan_pendidikan_swasta: "NPSN",
  koperasi: "Nomor Induk Koperasi", yayasan: "Nomor SK pengesahan badan hukum",
  badan_hukum_lain: "Nomor registrasi/badan hukum",
  kelompok_masyarakat: "Nomor SKT/badan hukum (bila ada)",
  lembaga_internasional: "Nomor registrasi", lainnya: "Nomor induk/registrasi",
};

const FIELD_INSTANSI = ["kelompok", "jenis", "nama", "singkatan", "alamat", "kota",
  "telepon", "email", "kode_referensi", "induk_id", "nomor_induk", "npwp",
  "dasar_pendirian_nomor", "dasar_pendirian_tanggal", "badan_penyelenggara", "aktif"];
const FIELD_SATKER = ["nama_satker", "kode_luar", "nama_unit_organisasi", "nama_sub_unit",
  "alamat", "telepon", "email", "aktif", "kode_satker_lengkap", "eselon_satker"];
const PEMDA = ["pemerintah_provinsi", "pemerintah_kabkota", "pemerintah_desa"];

function galat(err, cadangan) {
  const d = err?.response?.data?.detail;
  if (typeof d === "string") return d;
  return d?.message || cadangan;
}

const ambil = (doc, fields) => Object.fromEntries(fields.map((f) => [f, doc?.[f] ?? ""]));

const Kolom = ({ label, children, span2 }) => (
  <div className={span2 ? "sm:col-span-2" : ""}>
    <label className="text-xs font-medium text-foreground block mb-1">{label}</label>
    {children}
  </div>
);

/** Yang mirip di direktori, SEBELUM simpan — kembaran cepat menumpuk di
 *  direktori bersama (3.10 praktik 3). */
const DaftarMirip = ({ items, onPakai, label }) => (items.length === 0 ? null : (
  <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-2 space-y-1"
    data-testid="kelola-mirip">
    <p className="text-[11px] font-semibold text-amber-800 dark:text-amber-300">
      Sudah ada yang mirip — pakai yang ini bila sama:
    </p>
    {items.map((m) => (
      <button key={m.id} type="button" onClick={() => onPakai(m)}
        className="w-full text-left text-xs rounded-md px-2 min-h-[44px] lg:min-h-0 lg:py-1.5 hover:bg-muted"
        data-testid={`kelola-mirip-${m.id}`}>
        <span className="font-semibold">{label(m)}</span>
        <span className="text-muted-foreground"> — sudah ada, pakai yang ini</span>
      </button>
    ))}
  </div>
));

function useMirip(url, params, aktif) {
  const [mirip, setMirip] = useState([]);
  const kunci = JSON.stringify(params);
  useEffect(() => {
    const p = JSON.parse(kunci);
    if (!aktif || String(p.q || "").trim().length < 3) { setMirip([]); return undefined; }
    const t = setTimeout(() => {
      axios.get(url, { params: { ...p, page_size: 5 } })
        .then((r) => setMirip(r.data?.items || []))
        .catch(() => setMirip([]));
    }, 350);
    return () => clearTimeout(t);
  }, [url, kunci, aktif]);
  return mirip;
}

const FormInstansi = ({ awal, kelompok, tataran, lingkup, refLuar, sebutan, onSimpan, onBatal,
  onPakai, sibuk }) => {
  const baru = !awal.id;
  const [f, setF] = useState(awal);
  const [satkerPertama, setSatkerPertama] = useState({ nama_satker: "", kode_luar: "" });
  const [opsiInduk, setOpsiInduk] = useState([]);
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));
  const jenisBoleh = Object.entries(refLuar.jenis_instansi?.[kelompok] || {}).filter(([k]) => (
    kelompok === "eksternal" ? (refLuar.tataran_dari_jenis || {})[k] === tataran
      : k !== "perorangan"));
  const indukJenis = (refLuar.induk_daerah || {})[f.jenis];
  const mirip = useMirip(`${API}/luar/instansi`, { kelompok, q: f.nama }, baru);

  useEffect(() => {
    if (!indukJenis) { setOpsiInduk([]); return; }
    const params = { kelompok: "eksternal", tataran: "daerah", jenis: indukJenis, page_size: 100 };
    if (indukJenis === "pemerintah_kabkota" && lingkup.provinsi?.id) {
      params.provinsi_id = lingkup.provinsi.id;
    }
    axios.get(`${API}/luar/instansi`, { params })
      .then((r) => setOpsiInduk(r.data?.items || []))
      .catch(() => setOpsiInduk([]));
  }, [indukJenis, lingkup.provinsi]);

  const butuhSatker = baru && !PEMDA.includes(f.jenis);
  const kirim = () => {
    const body = { ...ambil(f, FIELD_INSTANSI), kelompok };
    if (!PEMDA.includes(f.jenis)) body.induk_id = "";
    if (butuhSatker) body.satker_pertama = satkerPertama;
    onSimpan(body);
  };
  return (
    <div className="space-y-3 rounded-lg border border-border p-3" data-testid="kelola-form-instansi">
      {kelompok === "eksternal" && (
        <p className="text-[11px] leading-snug rounded-md px-2 py-1.5 bg-sky-500/10 text-sky-800 dark:text-sky-300"
          data-testid="kelola-keterangan-batas">
          Pusat atau daerah ditentukan oleh <b>milik siapa</b> instansinya, bukan letak
          kantornya. Kantor wilayah, kantor pelayanan, Polres, Kodim, kejaksaan negeri, dan
          kantor Kemenag adalah <b>satker kementerian/lembaganya</b> (Pusat). Dinas, badan,
          sekretariat daerah, RSUD, kecamatan, dan kelurahan adalah <b>perangkat daerah
          pemdanya</b> (Daerah).
        </p>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Kolom label="Jenis *">
          <select value={f.jenis} onChange={set("jenis")} disabled={!baru}
            className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
            data-testid="kelola-instansi-jenis">
            <option value="">— pilih —</option>
            {jenisBoleh.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </Kolom>
        <Kolom label={`Nama ${sebutan.instansi} *`}>
          <Input value={f.nama} onChange={set("nama")} data-testid="kelola-instansi-nama" />
        </Kolom>
        {indukJenis && (
          <Kolom label={indukJenis === "pemerintah_provinsi" ? "Provinsi *" : "Kabupaten/Kota *"} span2>
            <select value={f.induk_id} onChange={set("induk_id")}
              className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
              data-testid="kelola-instansi-induk">
              <option value="">— pilih —</option>
              {opsiInduk.map((i) => <option key={i.id} value={i.id}>{namaInstansi(i)}</option>)}
            </select>
            {indukJenis === "pemerintah_provinsi" && (
              <button type="button"
                onClick={() => setF({ ...awal, jenis: "pemerintah_provinsi", nama: "" })}
                className="mt-1 text-[11px] font-semibold text-sky-700 dark:text-sky-400 underline underline-offset-2 min-h-[44px] lg:min-h-0"
                data-testid="kelola-catat-provinsi">
                Provinsinya belum ada? Catat provinsinya dulu
              </button>
            )}
          </Kolom>
        )}
        <Kolom label="Singkatan"><Input value={f.singkatan} onChange={set("singkatan")} /></Kolom>
        <Kolom label="Kode resmi (bagian anggaran / wilayah)">
          <Input value={f.kode_referensi} onChange={set("kode_referensi")} className="font-mono"
            placeholder="diketik dari dokumen resmi" />
        </Kolom>
        <Kolom label="Alamat" span2><Input value={f.alamat} onChange={set("alamat")} /></Kolom>
        <Kolom label="Kota"><Input value={f.kota} onChange={set("kota")} /></Kolom>
        <Kolom label="Telepon"><Input value={f.telepon} onChange={set("telepon")} inputMode="tel" /></Kolom>
        <Kolom label="Email" span2><Input type="email" value={f.email} onChange={set("email")} /></Kolom>
        {kelompok === "pihak_ketiga" && (
          <>
            <Kolom label={LABEL_NOMOR_INDUK[f.jenis] || "Nomor induk/registrasi"}>
              <Input value={f.nomor_induk} onChange={set("nomor_induk")} className="font-mono"
                data-testid="kelola-instansi-nomor-induk" />
            </Kolom>
            <Kolom label="NPWP badan"><Input value={f.npwp} onChange={set("npwp")} className="font-mono" /></Kolom>
            <Kolom label="Nomor akta/SK pendirian">
              <Input value={f.dasar_pendirian_nomor} onChange={set("dasar_pendirian_nomor")} />
            </Kolom>
            <Kolom label="Tanggal akta/SK pendirian">
              <InputTanggalRoda name="dasar_pendirian_tanggal" value={f.dasar_pendirian_tanggal}
                onChange={set("dasar_pendirian_tanggal")} minYear={1900} maxYear={new Date().getFullYear()} />
            </Kolom>
            {f.jenis === "satuan_pendidikan_swasta" && (
              <Kolom label="Badan penyelenggara (yayasan)" span2>
                <Input value={f.badan_penyelenggara} onChange={set("badan_penyelenggara")} />
              </Kolom>
            )}
          </>
        )}
        {butuhSatker && (
          <>
            <Kolom label={`${sebutan.satker} pertama *`}>
              <Input value={satkerPertama.nama_satker} data-testid="kelola-satker-pertama"
                onChange={(e) => setSatkerPertama((s) => ({ ...s, nama_satker: e.target.value }))} />
            </Kolom>
            <Kolom label={`Kode ${sebutan.satker} (bila ada)`}>
              <Input value={satkerPertama.kode_luar} className="font-mono"
                onChange={(e) => setSatkerPertama((s) => ({ ...s, kode_luar: e.target.value }))} />
            </Kolom>
          </>
        )}
      </div>
      <DaftarMirip items={mirip} onPakai={onPakai} label={namaInstansi} />
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onBatal}>Batal</Button>
        <Button onClick={kirim} disabled={sibuk} className="bg-sky-600 hover:bg-sky-700 text-white"
          data-testid="kelola-instansi-simpan">
          {sibuk && <Loader2 className="w-4 h-4 animate-spin mr-1.5" />}Simpan
        </Button>
      </div>
    </div>
  );
};

const FormSatker = ({ awal, kelompok, instansi, sebutan, onSimpan, onBatal, onPakai, sibuk }) => {
  const baru = !awal.id;
  const [f, setF] = useState(awal);
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));
  const mirip = useMirip(`${API}/luar/satker`, { instansi_id: instansi.id, q: f.nama_satker }, baru);
  return (
    <div className="space-y-3 rounded-lg border border-border p-3" data-testid="kelola-form-satker">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Kolom label={`Nama ${sebutan.satker} *`} span2>
          <Input value={f.nama_satker} onChange={set("nama_satker")} data-testid="kelola-satker-nama" />
        </Kolom>
        <Kolom label="Kode (bila ada)"><Input value={f.kode_luar} onChange={set("kode_luar")} className="font-mono" /></Kolom>
        {kelompok === "eksternal" && (
          <>
            <Kolom label="Tingkat eselon puncak">
              <select value={f.eselon_satker} onChange={set("eselon_satker")}
                className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm">
                <option value="">— tidak dinyatakan —</option>
                {[1, 2, 3, 4, 5].map((n) => <option key={n} value={String(n)}>Eselon {n}</option>)}
              </select>
            </Kolom>
            <Kolom label="Kode Satker Lengkap (20 karakter)" span2>
              <Input value={f.kode_satker_lengkap} maxLength={20} className="font-mono uppercase"
                onChange={(e) => setF((x) => ({ ...x, kode_satker_lengkap: e.target.value
                  .toUpperCase().replace(/[^0-9A-Z]/g, "").slice(0, 20) }))} />
            </Kolom>
          </>
        )}
        <Kolom label="Unit organisasi"><Input value={f.nama_unit_organisasi} onChange={set("nama_unit_organisasi")} /></Kolom>
        <Kolom label="Telepon"><Input value={f.telepon} onChange={set("telepon")} inputMode="tel" /></Kolom>
        <Kolom label="Alamat" span2><Input value={f.alamat} onChange={set("alamat")} /></Kolom>
        <Kolom label="Email" span2><Input type="email" value={f.email} onChange={set("email")} /></Kolom>
      </div>
      <DaftarMirip items={mirip} onPakai={onPakai} label={(s) => s.nama_satker} />
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onBatal}>Batal</Button>
        <Button onClick={() => onSimpan(ambil(f, FIELD_SATKER))} disabled={sibuk}
          className="bg-sky-600 hover:bg-sky-700 text-white" data-testid="kelola-satker-simpan">
          {sibuk && <Loader2 className="w-4 h-4 animate-spin mr-1.5" />}Simpan
        </Button>
      </div>
    </div>
  );
};

const BarisCatatan = ({ judul, sub, aktif, dipilih, onPilih, onUbah, onAktif, onHapus, testId }) => (
  <li className={`flex items-center gap-1 py-1.5 px-1 rounded-md ${dipilih ? "bg-sky-500/10" : ""}`}
    data-testid={testId}>
    <button type="button" onClick={onPilih}
      className="flex-1 min-w-0 text-left rounded-md px-1.5 min-h-[44px] lg:min-h-0 lg:py-1 hover:bg-muted">
      <span className={`block text-sm font-medium break-words ${aktif ? "text-foreground" : "text-muted-foreground line-through"}`}>{judul}</span>
      {sub && <span className="block text-[11px] text-muted-foreground">{sub}</span>}
    </button>
    {onUbah && (
      <button type="button" onClick={onUbah} title="Ubah" aria-label={`Ubah ${judul}`}
        className="p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted">
        <Pencil className="w-3.5 h-3.5" />
      </button>
    )}
    {onAktif && (
      <button type="button" onClick={onAktif} title={aktif ? "Nonaktifkan" : "Aktifkan"}
        aria-label={`${aktif ? "Nonaktifkan" : "Aktifkan"} ${judul}`}
        className="p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted"
        data-testid={`${testId}-aktif`}>
        <Power className="w-3.5 h-3.5" />
      </button>
    )}
    {onHapus && (
      <button type="button" onClick={onHapus} title="Hapus permanen" aria-label={`Hapus permanen ${judul}`}
        className="p-2 rounded-md text-muted-foreground hover:text-red-600 hover:bg-red-500/10"
        data-testid={`${testId}-hapus`}>
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    )}
  </li>
);

/**
 * Kelola direktori organisasi luar (PGW-07 butir 5): instansi → satker, dua
 * tingkat, dengan jenjang provinsi → kab/kota → desa di tataran Daerah.
 * Semua admin boleh menambah/mengubah/menonaktifkan; hapus permanen khusus
 * super-admin (server menegakkan hal yang sama — layar tidak menawarkannya).
 */
export default function KelolaOrganisasiLuar({ open, onClose, kelompok, tataran, lingkup,
  refLuar = {}, sebutan, user, onPilih, onBerubah }) {
  const superAdmin = isSuperAdminPusat(user);
  const daerah = kelompok === "eksternal" && tataran === "daerah";
  const [daftar, setDaftar] = useState([]);
  const [satker, setSatker] = useState([]);
  const [cari, setCari] = useState("");
  const [formI, setFormI] = useState(null);
  const [formS, setFormS] = useState(null);
  const [sibuk, setSibuk] = useState(false);
  const { confirm, confirmDialog } = useConfirm();
  const instansi = lingkup.instansi;

  const muat = useCallback(() => {
    const params = { kelompok, page_size: 100 };
    if (kelompok === "eksternal") params.tataran = tataran;
    if (daerah && lingkup.provinsi?.id) params.provinsi_id = lingkup.provinsi.id;
    if (cari.trim()) params.q = cari.trim();
    axios.get(`${API}/luar/instansi`, { params })
      .then((r) => setDaftar(r.data?.items || [])).catch(() => setDaftar([]));
    if (instansi?.id) {
      axios.get(`${API}/luar/satker`, { params: { instansi_id: instansi.id, page_size: 100 } })
        .then((r) => setSatker(r.data?.items || [])).catch(() => setSatker([]));
    } else setSatker([]);
  }, [kelompok, tataran, daerah, lingkup.provinsi, instansi, cari]);

  useEffect(() => { if (open) muat(); }, [open, muat]);
  useEffect(() => { if (!open) { setFormI(null); setFormS(null); } }, [open]);

  const sesudahUbah = () => { muat(); onBerubah?.(); };

  const lingkupDari = (i, s = null) => {
    let provinsi = lingkup.provinsi || null;
    if (i?.jenis === "pemerintah_provinsi") provinsi = i;
    else if (i?.provinsi_id && i.provinsi_id !== provinsi?.id) {
      provinsi = { id: i.provinsi_id, nama: i.provinsi_nama };
    }
    return { provinsi: daerah ? provinsi : null, instansi: i, satker: s };
  };

  const simpanInstansi = async (body) => {
    setSibuk(true);
    try {
      if (formI.id) {
        await axios.put(`${API}/luar/instansi/${formI.id}`, body,
          { headers: { "If-Match": String(formI.version || 1) } });
        toast.success(`${sebutan.instansi} diperbarui`);
      } else {
        const r = await axios.post(`${API}/luar/instansi`, body);
        toast.success(`${sebutan.instansi} ${body.nama} dicatat`);
        onPilih(lingkupDari(r.data?.instansi, r.data?.satker || null));
      }
      setFormI(null);
      sesudahUbah();
    } catch (err) { toast.error(galat(err, "Gagal menyimpan")); }
    finally { setSibuk(false); }
  };

  const simpanSatker = async (body) => {
    setSibuk(true);
    try {
      if (formS.id) {
        await axios.put(`${API}/luar/satker/${formS.id}`, body,
          { headers: { "If-Match": String(formS.version || 1) } });
        toast.success(`${sebutan.satker} diperbarui`);
      } else {
        const r = await axios.post(`${API}/luar/satker`, { ...body, instansi_id: instansi.id });
        toast.success(`${sebutan.satker} ${body.nama_satker} dicatat`);
        onPilih({ ...lingkup, satker: r.data });
      }
      setFormS(null);
      sesudahUbah();
    } catch (err) { toast.error(galat(err, "Gagal menyimpan")); }
    finally { setSibuk(false); }
  };

  const ubahAktif = async (jenis, doc) => {
    const url = jenis === "instansi" ? `${API}/luar/instansi/${doc.id}` : `${API}/luar/satker/${doc.id}`;
    const body = { ...ambil(doc, jenis === "instansi" ? FIELD_INSTANSI : FIELD_SATKER),
      aktif: doc.aktif === false };
    try {
      await axios.put(url, body, { headers: { "If-Match": String(doc.version || 1) } });
      toast.success(body.aktif ? "Diaktifkan kembali" : "Dinonaktifkan — tidak lagi ditawarkan untuk catatan baru");
      sesudahUbah();
    } catch (err) { toast.error(galat(err, "Gagal mengubah status")); }
  };

  const hapus = async (jenis, doc, judul) => {
    const ok = await confirm({
      title: `Hapus permanen ${judul}?`,
      description: "Ditolak bila masih dipakai. Penghapusan tidak dapat dibatalkan.",
      confirmLabel: "Hapus permanen", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(jenis === "instansi" ? `${API}/luar/instansi/${doc.id}` : `${API}/luar/satker/${doc.id}`);
      toast.success(`${judul} dihapus`);
      if (jenis === "instansi" && instansi?.id === doc.id) onPilih(lingkupDari(null));
      if (jenis === "satker" && lingkup.satker?.id === doc.id) onPilih({ ...lingkup, satker: null });
      sesudahUbah();
    } catch (err) { toast.error(galat(err, "Gagal menghapus")); }
  };

  const catatPerorangan = async () => {
    try {
      const r = await axios.post(`${API}/luar/wadah-perorangan`);
      onPilih({ provinsi: null, instansi: r.data?.instansi, satker: r.data?.satker });
      onClose();
    } catch (err) { toast.error(galat(err, "Gagal membuka wadah perorangan")); }
  };

  const pakai = (i, s = null) => { onPilih(lingkupDari(i, s)); onClose(); };
  const awalInstansi = () => ({ ...Object.fromEntries(FIELD_INSTANSI.map((k) => [k, ""])),
    aktif: true, jenis: kelompok === "eksternal" && !daerah ? "kementerian_lembaga" : "",
    induk_id: daerah && lingkup.provinsi?.id ? lingkup.provinsi.id : "" });

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-2xl" data-testid="kelola-organisasi-luar">
        <DialogHeader>
          <DialogTitle>Kelola {sebutan.instansi} &amp; {sebutan.satker}</DialogTitle>
          <DialogDescription className="text-xs">
            Direktori ini dipakai bersama seluruh satker — cari dulu sebelum menambah.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 max-h-[70vh] overflow-y-auto">
          <section className="space-y-2">
            <div className="flex items-center gap-2">
              <Input value={cari} onChange={(e) => setCari(e.target.value)}
                placeholder={`Cari ${sebutan.instansi}…`} className="h-10" data-testid="kelola-cari" />
              <Button variant="outline" className="gap-1.5 flex-shrink-0"
                onClick={() => { setFormS(null); setFormI(awalInstansi()); }} data-testid="kelola-tambah-instansi">
                <Plus className="w-4 h-4" />{sebutan.instansi}
              </Button>
            </div>
            {kelompok === "pihak_ketiga" && (
              <Button variant="outline" size="sm" className="gap-1.5" onClick={catatPerorangan}
                data-testid="kelola-perorangan">
                <UserRound className="w-4 h-4" />Perorangan (Masyarakat)
              </Button>
            )}
            {formI && (
              <FormInstansi key={formI.id || `baru-${formI.jenis}`} awal={formI} kelompok={kelompok}
                tataran={tataran} lingkup={lingkup} refLuar={refLuar} sebutan={sebutan}
                onSimpan={simpanInstansi} onBatal={() => setFormI(null)} onPakai={(i) => pakai(i)}
                sibuk={sibuk} />
            )}
            <ul className="divide-y divide-border/60" data-testid="kelola-daftar-instansi">
              {daftar.filter((i) => !i.wadah).map((i) => (
                <BarisCatatan key={i.id} testId={`kelola-instansi-${i.id}`} judul={namaInstansi(i)}
                  sub={`${i.jumlah_satker ?? 0} ${sebutan.satker.toLowerCase()} · ${i.jumlah_orang ?? 0} orang`}
                  aktif={i.aktif !== false} dipilih={instansi?.id === i.id}
                  onPilih={() => onPilih(lingkupDari(i))}
                  onUbah={() => { setFormS(null); setFormI({ ...awalInstansi(), ...ambil(i, FIELD_INSTANSI), id: i.id, version: i.version }); }}
                  onAktif={() => ubahAktif("instansi", i)}
                  onHapus={superAdmin ? () => hapus("instansi", i, i.nama) : null} />
              ))}
              {daftar.length === 0 && (
                <li className="py-3 text-xs text-muted-foreground text-center">Belum ada yang cocok.</li>
              )}
            </ul>
          </section>
          {instansi && !instansi.wadah && (
            <section className="space-y-2 border-t border-border pt-3">
              <div className="flex items-center gap-2">
                <p className="flex-1 min-w-0 text-sm font-semibold break-words">
                  {sebutan.satker} — {namaInstansi(instansi)}
                </p>
                <Button variant="outline" className="gap-1.5 flex-shrink-0"
                  onClick={() => { setFormI(null); setFormS({ ...Object.fromEntries(FIELD_SATKER.map((k) => [k, ""])), aktif: true }); }}
                  data-testid="kelola-tambah-satker">
                  <Plus className="w-4 h-4" />{sebutan.satker}
                </Button>
              </div>
              {formS && (
                <FormSatker key={formS.id || "baru"} awal={formS} kelompok={kelompok} instansi={instansi}
                  sebutan={sebutan} onSimpan={simpanSatker} onBatal={() => setFormS(null)}
                  onPakai={(s) => pakai(instansi, s)} sibuk={sibuk} />
              )}
              <ul className="divide-y divide-border/60" data-testid="kelola-daftar-satker">
                {satker.map((s) => (
                  <BarisCatatan key={s.id} testId={`kelola-satker-${s.id}`} judul={s.nama_satker}
                    sub={`${s.jumlah_orang ?? 0} orang`} aktif={s.aktif !== false}
                    dipilih={lingkup.satker?.id === s.id} onPilih={() => pakai(instansi, s)}
                    onUbah={() => { setFormI(null); setFormS({ ...ambil(s, FIELD_SATKER), id: s.id, version: s.version }); }}
                    onAktif={() => ubahAktif("satker", s)}
                    onHapus={superAdmin ? () => hapus("satker", s, s.nama_satker) : null} />
                ))}
              </ul>
            </section>
          )}
        </div>
        {confirmDialog}
      </DialogContent>
    </Dialog>
  );
}
