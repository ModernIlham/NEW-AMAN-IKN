import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { Search, Settings2 } from "lucide-react";
import { labelLingkup } from "@/lib/ranahPegawai";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Saringan jenis di tataran Daerah: provinsi · kabupaten/kota · desa (3.10).
const JENIS_DAERAH = [
  { kode: "pemerintah_provinsi", uraian: "Provinsi" },
  { kode: "pemerintah_kabkota", uraian: "Kabupaten/Kota" },
  { kode: "pemerintah_desa", uraian: "Desa" },
];

const KELAS_PILIH = "h-11 lg:h-9 rounded-md border border-input bg-background px-2 text-sm lg:text-xs w-full min-w-0 disabled:opacity-60";

/** "Kabupaten Y, Provinsi Z" — kab/kota & desa selalu bersama provinsinya. */
export function namaInstansi(i) {
  return labelLingkup({ instansi: i });
}

/**
 * Bilah lingkup tab luar (3.10 butir 4): instansi → satker, dicari di
 * server. Di tataran Daerah: provinsi dulu, lalu pemprov itu atau
 * kab/kotanya (lalu desanya). Mengganti tingkat atas MENGOSONGKAN pilihan di
 * bawahnya — daftar orang tidak boleh tersaring oleh satker dari instansi
 * yang sudah tidak dipilih.
 */
export default function BilahLingkupLuar({ kelompok, tataran, lingkup, onUbah,
  sebutan, jenisInstansi = {}, cacahInstansi = {}, cacahSatker = {}, onKelola,
  versi = 0, bolehKelola = false }) {
  const daerah = kelompok === "eksternal" && tataran === "daerah";
  const [provinsi, setProvinsi] = useState([]);
  const [instansi, setInstansi] = useState([]);
  const [satker, setSatker] = useState([]);
  const [jenis, setJenis] = useState("");
  const [cari, setCari] = useState("");
  const [q, setQ] = useState("");

  // Ganti kelompok/tataran → saringan lokal ikut kosong.
  useEffect(() => { setJenis(""); setCari(""); setQ(""); }, [kelompok, tataran]);
  useEffect(() => {
    const t = setTimeout(() => setQ(cari.trim()), 300);
    return () => clearTimeout(t);
  }, [cari]);

  useEffect(() => {
    if (!daerah) { setProvinsi([]); return; }
    axios.get(`${API}/luar/instansi`, { params: { kelompok: "eksternal",
      tataran: "daerah", jenis: "pemerintah_provinsi", page_size: 100 } })
      .then((r) => setProvinsi(r.data?.items || []))
      .catch(() => setProvinsi([]));
  }, [daerah, versi]);

  const provinsiId = lingkup.provinsi?.id || "";
  useEffect(() => {
    if (daerah && !provinsiId) { setInstansi([]); return; }
    const params = { kelompok, page_size: 100 };
    if (kelompok === "eksternal") params.tataran = tataran;
    if (daerah) params.provinsi_id = provinsiId;
    if (jenis) params.jenis = jenis;
    if (q) params.q = q;
    axios.get(`${API}/luar/instansi`, { params })
      .then((r) => setInstansi(r.data?.items || []))
      .catch(() => setInstansi([]));
  }, [kelompok, tataran, daerah, provinsiId, jenis, q, versi]);

  const instansiId = lingkup.instansi?.id || "";
  useEffect(() => {
    if (!instansiId) { setSatker([]); return; }
    axios.get(`${API}/luar/satker`, { params: { instansi_id: instansiId, page_size: 100 } })
      .then((r) => setSatker(r.data?.items || []))
      .catch(() => setSatker([]));
  }, [instansiId, versi]);

  // Pilihan aktif tetap tampil walau tersaring keluar oleh pencarian.
  const opsiInstansi = useMemo(() => {
    const ada = lingkup.instansi && !instansi.some((i) => i.id === lingkup.instansi.id);
    return ada ? [lingkup.instansi, ...instansi] : instansi;
  }, [instansi, lingkup.instansi]);

  const opsiJenis = daerah ? JENIS_DAERAH
    : kelompok === "pihak_ketiga"
      ? Object.entries(jenisInstansi.pihak_ketiga || {}).map(([kode, uraian]) => ({ kode, uraian }))
      : [];

  const pilihProvinsi = (id) => onUbah({
    provinsi: provinsi.find((p) => p.id === id) || null, instansi: null, satker: null });
  const pilihInstansi = (id) => onUbah({ ...lingkup,
    instansi: opsiInstansi.find((i) => i.id === id) || null, satker: null });
  const pilihSatker = (id) => onUbah({ ...lingkup,
    satker: satker.find((s) => s.id === id) || null });

  const label = labelLingkup(lingkup);
  return (
    <div className="bg-card rounded-xl border border-border shadow-sm p-2 sm:p-3 space-y-2"
      data-testid="pegawai-bilah-lingkup">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-1.5">
        {daerah && (
          <select value={provinsiId} onChange={(e) => pilihProvinsi(e.target.value)}
            aria-label="Provinsi" className={KELAS_PILIH} data-testid="lingkup-provinsi">
            <option value="">— Provinsi —</option>
            {provinsi.map((p) => <option key={p.id} value={p.id}>{p.nama}</option>)}
          </select>
        )}
        {opsiJenis.length > 0 && (
          <select value={jenis} onChange={(e) => setJenis(e.target.value)}
            aria-label={`Jenis ${sebutan.instansi}`} className={KELAS_PILIH}
            data-testid="lingkup-jenis">
            <option value="">Semua jenis</option>
            {opsiJenis.map((o) => <option key={o.kode} value={o.kode}>{o.uraian}</option>)}
          </select>
        )}
        <div className="relative min-w-0">
          <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" aria-hidden="true" />
          <input value={cari} onChange={(e) => setCari(e.target.value)}
            placeholder={`Cari ${sebutan.instansi}…`} aria-label={`Cari ${sebutan.instansi}`}
            disabled={daerah && !provinsiId}
            className={`${KELAS_PILIH} pl-8`} data-testid="lingkup-cari-instansi" />
        </div>
        <select value={instansiId} onChange={(e) => pilihInstansi(e.target.value)}
          aria-label={sebutan.instansi} disabled={daerah && !provinsiId}
          className={KELAS_PILIH} data-testid="lingkup-instansi">
          <option value="">{daerah && !provinsiId ? "Pilih provinsi dulu" : `— ${sebutan.instansi} —`}</option>
          {opsiInstansi.map((i) => (
            <option key={i.id} value={i.id}>
              {namaInstansi(i)}{cacahInstansi[i.id] != null ? ` (${cacahInstansi[i.id]})` : ""}
            </option>
          ))}
        </select>
        <select value={lingkup.satker?.id || ""} onChange={(e) => pilihSatker(e.target.value)}
          aria-label={sebutan.satker} disabled={!instansiId}
          className={KELAS_PILIH} data-testid="lingkup-satker">
          <option value="">{instansiId ? `— ${sebutan.satker} —` : `Pilih ${sebutan.instansi} dulu`}</option>
          {satker.map((s) => (
            <option key={s.id} value={s.id}>
              {s.nama_satker}{s.aktif === false ? " (nonaktif)" : ""}
              {cacahSatker[s.id] != null ? ` (${cacahSatker[s.id]})` : ""}
            </option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <p className="text-xs font-semibold text-foreground min-w-0 flex-1 break-words"
          data-testid="pegawai-lingkup-label">
          {label || (daerah && lingkup.provinsi ? lingkup.provinsi.nama
            : `Semua ${sebutan.instansi}`)}
        </p>
        {bolehKelola && (
          <button type="button" onClick={onKelola}
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 text-xs font-semibold min-h-[44px] lg:min-h-0 lg:h-8 hover:bg-muted"
            data-testid="lingkup-kelola">
            <Settings2 className="w-3.5 h-3.5" aria-hidden="true" />Kelola
          </button>
        )}
      </div>
      <p className="text-[11px] text-muted-foreground" data-testid="pegawai-direktori-bersama">
        Direktori ini dipakai bersama seluruh satker.
      </p>
    </div>
  );
}
