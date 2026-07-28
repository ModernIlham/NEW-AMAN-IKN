import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Plus, Trash2, Loader2, RadioTower, ShieldAlert, Fence,
  KeyRound, Copy, Check, BellRing, MapPin, BatteryLow, Clock, Pencil,
  ShieldCheck, ArrowUpRight, Info, RefreshCw, Unlock, X, AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";
import { TENGGAT_BAKA, muatAndal, pesanGalat } from "@/lib/muatAndal";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function getApiError(err, fallback) {
  return err?.response?.data?.detail || fallback;
}

/**
 * Blok "bagian ini gagal dimuat" — dipakai menggantikan kalimat kosong tiap tab.
 * Kalimat kosong ("Belum ada …", "Tidak ada peringatan. Itu kabar baik.")
 * menyatakan sebuah FAKTA tentang data. Bila datanya tak pernah sampai, kalimat
 * itu berubah jadi jaminan palsu — paling berbahaya di tab Peringatan, yang
 * seluruh gunanya adalah memberi tahu ada aset keluar dari batas wilayahnya.
 */
function BagianGagal({ pesan, catatan, onUlang, sibuk, testid }) {
  return (
    <div className="text-center py-8 px-4" data-testid={testid}>
      <AlertTriangle className="w-7 h-7 mx-auto mb-2 text-amber-500" />
      <p className="text-xs text-foreground break-words">{pesan}</p>
      {catatan && <p className="text-[11px] text-muted-foreground mt-1">{catatan}</p>}
      {/* DIREDAM SELAGI MEMUAT. Kartu galat baru diganti di AKHIR muat(), jadi
          selama percobaan ulang berjalan layar ini tak berubah sedikit pun —
          operator menyimpulkan tombolnya tak bekerja lalu menekannya lagi dan
          lagi, menumpuk jalankan yang saling mendahului. Spinner di sini
          membuat kerja yang sedang berlangsung terlihat. */}
      <Button variant="outline" size="sm" className="mt-3 h-7 text-[11px]"
              onClick={onUlang} disabled={sibuk} data-testid={`${testid}-coba-lagi`}>
        {sibuk ? <Loader2 className="w-3 h-3 mr-1 animate-spin" />
               : <RefreshCw className="w-3 h-3 mr-1" />}
        {sibuk ? "Mencoba lagi…" : "Coba lagi"}
      </Button>
    </div>
  );
}

const TABS = [
  ["perangkat", "Perangkat", RadioTower],
  ["pagar", "Pagar Area", Fence],
  ["peringatan", "Peringatan", BellRing],
  ["izin", "Izin Darurat", Unlock],
];

const JENIS_LABEL = {
  masuk: "Masuk area",
  keluar: "Keluar area",
  dwell_terlampaui: "Tak kunjung kembali",
};

/** Menit → "5 mnt" / "3 jam" / "2 hari"; null = belum pernah terdengar. */
function lamaDiam(menit) {
  if (menit === null || menit === undefined) return "—";
  if (menit < 60) return `${menit} mnt`;
  if (menit < 1440) return `${Math.floor(menit / 60)} jam`;
  return `${Math.floor(menit / 1440)} hari`;
}

function waktuSingkat(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("id-ID", { day: "2-digit", month: "short",
    hour: "2-digit", minute: "2-digit" });
}

/**
 * PELACAKAN ASET — muka untuk pipeline IoT (Fase 11) + geofence (Fase 12).
 *
 * Kedua fase itu sebelumnya hidup sepenuhnya di API dan tak terlihat operator;
 * halaman ini yang membuatnya bisa dipakai orang, bukan hanya oleh mesin.
 *
 * KEBIJAKAN PRIVASI DITAMPILKAN DI ATAS, bukan disembunyikan di dokumen. Ia
 * dibaca dari endpoint yang membacanya dari KODE PENEGAKNYA (`privasi_utils`),
 * jadi angka yang dilihat pengguna dijamin sama dengan yang dijalankan mesin —
 * kebijakan yang tak terlihat tak bisa diperiksa siapa pun.
 */
export default function PelacakanPage({ user, onBack }) {
  const isAdmin = user?.role === "admin" || user?.role === "super_admin";
  const isWriter = user?.role !== "viewer";
  const [tab, setTab] = useState("perangkat");
  const [memuat, setMemuat] = useState(false);
  // Kegagalan PER BAGIAN — supaya bagian yang berhasil tetap tampil dan bagian
  // yang gagal tak menyamar sebagai "tidak ada data".
  const [gagalBagian, setGagalBagian] = useState({});
  const reqRef = useRef(0);            // penjaga urutan respons muat()
  const [perangkat, setPerangkat] = useState([]);
  const [profilTersedia, setProfilTersedia] = useState([]);
  const [aturan, setAturan] = useState([]);
  const [paramBawaan, setParamBawaan] = useState(null);
  const [jenisTersedia, setJenisTersedia] = useState([]);
  const [event, setEvent] = useState([]);
  const [belumDibaca, setBelumDibaca] = useState(0);
  const [hanyaBelum, setHanyaBelum] = useState(false);
  const [nodes, setNodes] = useState([]);
  const [izin, setIzin] = useState([]);
  const [izinMaksJam, setIzinMaksJam] = useState(72);
  const [izinMinAlasan, setIzinMinAlasan] = useState(10);
  const [formIzin, setFormIzin] = useState(null);
  const { confirm, confirmDialog } = useConfirm();

  // Dialog
  const [formPerangkat, setFormPerangkat] = useState(null);
  const [tokenBaru, setTokenBaru] = useState(null);   // {nama, token}
  const [formAturan, setFormAturan] = useState(null);
  const [posisi, setPosisi] = useState(null);          // {perangkat, items}
  const [eskalasi, setEskalasi] = useState(null);      // event yang dinaikkan
  const [menyimpan, setMenyimpan] = useState(false);

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  // EMPAT BAGIAN BERDIRI SENDIRI-SENDIRI.
  //
  // Dulu `Promise.all`: satu endpoint gagal → SELURUH `try` melompat ke `catch`,
  // keempat daftar tetap kosong, dan tab Peringatan lalu mencetak "Tidak ada
  // peringatan. Itu kabar baik." Layar MENJAMIN AMAN justru ketika ia tidak tahu
  // apa-apa — pada halaman yang seluruh gunanya adalah memberi tahu bahwa ada
  // aset keluar dari batas wilayahnya. Itu bukan sekadar tampilan keliru.
  //
  // `allSettled` membuat bagian yang berhasil tetap tampil, dan bagian yang
  // gagal mengatakannya sendiri.
  const muat = useCallback(async () => {
    // PENJAGA URUTAN — WAJIB SEJAK `allSettled`.
    //
    // Dengan `Promise.all` yang lama, jalankan yang gagal MELOMPAT ke catch dan
    // tidak menulis state sama sekali; balasan basi karena itu tak berbahaya.
    // `allSettled` menghapus korsleting itu: SETIAP jalankan kini selalu sampai
    // ke blok penulisan di bawah, termasuk yang gagal sebagian. `muat` dipanggil
    // dari sebelas tempat (useEffect, tombol Coba lagi keempat bagian, dan tujuh
    // handler mutasi), dan satu endpoint yang menggantung menahan jalankannya
    // sampai puluhan detik oleh coba-ulang.
    //
    // Akibat tanpa penjaga ini, terperagakan: t=0 halaman dibuka (jalankan A,
    // /geofence/event menggantung); t=2 dtk operator mendaftarkan perangkat →
    // jalankan B selesai cepat dan perangkat baru tampil; lalu A mendarat
    // terakhir dengan potret t=0 → `setPerangkat` MENGHAPUS perangkat yang baru
    // didaftarkan, tanpa toast, tanpa galat. Komit yang sama memasang penjaga
    // ini di SbskRuangPanel untuk kelas bug yang persis sama.
    const seq = ++reqRef.current;
    setMemuat(true);
    const ambil = (url, params) => muatAndal(
      () => axios.get(`${API}${url}`, { params, timeout: TENGGAT_BAKA }));
    const [rp, ra, re, rz] = await Promise.allSettled([
      ambil("/iot/perangkat"),
      ambil("/geofence/aturan"),
      ambil("/geofence/event", { batas: 100 }),
      ambil("/iot/izin-darurat"),
    ]);
    if (seq !== reqRef.current) return;   // jalankan yang lebih muda sudah menang
    const gagal = {};
    if (rp.status === "fulfilled") {
      setPerangkat(rp.value.data?.items || []);
      setProfilTersedia(rp.value.data?.profil_tersedia || []);
    } else gagal.perangkat = pesanGalat(rp.reason, "Daftar perangkat gagal dimuat");
    if (ra.status === "fulfilled") {
      setAturan(ra.value.data?.items || []);
      setParamBawaan(ra.value.data?.param_bawaan || null);
      setJenisTersedia(ra.value.data?.jenis_tersedia || []);
    } else gagal.aturan = pesanGalat(ra.reason, "Daftar aturan pagar gagal dimuat");
    if (re.status === "fulfilled") {
      setEvent(re.value.data?.items || []);
      setBelumDibaca(re.value.data?.belum_dibaca || 0);
    } else {
      gagal.event = pesanGalat(re.reason, "Daftar peringatan gagal dimuat");
      // TIDAK DIKETAHUI, bukan nol. Membiarkan angka lama (atau 0 bawaan)
      // membuat badge tetap menjanjikan sesuatu tentang daftar yang gagal
      // dibaca — dan ketiadaan badge terbaca operator sebagai "tak ada
      // peringatan baru". Itu jaminan aman palsu yang berpindah dari badan tab
      // ke lencananya, persis yang hendak dihabisi bagian ini.
      setBelumDibaca(null);
    }
    if (rz.status === "fulfilled") {
      setIzin(rz.value.data?.items || []);
      setIzinMaksJam(rz.value.data?.maks_jam || 72);
      setIzinMinAlasan(rz.value.data?.alasan_min_karakter || 10);
    } else gagal.izin = pesanGalat(rz.reason, "Daftar izin darurat gagal dimuat");
    setGagalBagian(gagal);
    setMemuat(false);
  }, []);

  useEffect(() => { muat(); }, [muat]);

  // Area pagar HANYA boleh POLIGON. Backend menolak titik/garis dengan pesan
  // jelas, tetapi menawarkannya di dropdown berarti pengguna baru tahu setelah
  // menabraknya — jadi disaring di sumber daftarnya.
  useEffect(() => {
    axios.get(`${API}/spasial/node`).then((r) => {
      setNodes((r.data?.items || []).filter(
        (n) => n.tipe_geometri === "Polygon" || n.tipe_geometri === "MultiPolygon"));
    }).catch(() => setNodes([]));
  }, []);

  const eventTampil = useMemo(
    () => (hanyaBelum ? event.filter((e) => !e.dibaca) : event), [event, hanyaBelum]);

  // ── Aksi perangkat ────────────────────────────────────────────────────────

  const simpanPerangkat = async () => {
    const f = formPerangkat;
    if (!f?.nama?.trim()) { toast.error("Nama perangkat wajib diisi"); return; }
    setMenyimpan(true);
    try {
      const r = await axios.post(`${API}/iot/perangkat`, {
        nama: f.nama.trim(), asset_id: f.asset_id || "",
        profil_privasi: f.profil_privasi, keterangan: f.keterangan || "",
      });
      setFormPerangkat(null);
      // Token ditampilkan SEKALI — server hanya menyimpan hash-nya.
      setTokenBaru({ nama: r.data?.nama, token: r.data?.token });
      muat();
    } catch (e) {
      toast.error(getApiError(e, "Gagal mendaftarkan perangkat"));
    } finally { setMenyimpan(false); }
  };

  const rotasiToken = async (dev) => {
    const ok = await confirm({
      title: "Rotasi token perangkat?",
      description: `Token lama "${dev.nama}" langsung TIDAK BERLAKU. Perangkat di `
        + "lapangan harus diisi token baru sebelum bisa mengirim posisi lagi.",
      confirmText: "Rotasi", variant: "destructive",
    });
    if (!ok) return;
    try {
      const r = await axios.post(`${API}/iot/perangkat/${dev.id}/rotasi-token`);
      setTokenBaru({ nama: dev.nama, token: r.data?.token });
    } catch (e) { toast.error(getApiError(e, "Gagal merotasi token")); }
  };

  const lihatPosisi = async (dev) => {
    try {
      const r = await axios.get(`${API}/iot/perangkat/${dev.id}/posisi`,
                                { params: { batas: 50 } });
      setPosisi({ perangkat: r.data?.perangkat || dev, items: r.data?.items || [] });
    } catch (e) { toast.error(getApiError(e, "Gagal memuat riwayat posisi")); }
  };

  // ── Aksi pagar ────────────────────────────────────────────────────────────

  const simpanAturan = async () => {
    const f = formAturan;
    if (!f?.nama?.trim()) { toast.error("Nama aturan wajib diisi"); return; }
    if (!f.device_id) { toast.error("Pilih perangkat yang dipantau"); return; }
    if (!f.area_node_id) { toast.error("Pilih area pagar"); return; }
    if (!(f.jenis || []).length) { toast.error("Pilih minimal satu jenis peringatan"); return; }
    setMenyimpan(true);
    const badan = {
      nama: f.nama.trim(), device_id: f.device_id, area_node_id: f.area_node_id,
      jenis: f.jenis, maks_di_luar_jam: Number(f.maks_di_luar_jam) || 0,
      param: f.param || {}, aktif: f.aktif !== false,
    };
    try {
      if (f.id) await axios.put(`${API}/geofence/aturan/${f.id}`, badan);
      else await axios.post(`${API}/geofence/aturan`, badan);
      toast.success(f.id ? "Pagar diperbarui" : "Pagar dipasang");
      setFormAturan(null);
      muat();
    } catch (e) {
      toast.error(getApiError(e, "Gagal menyimpan pagar"));
    } finally { setMenyimpan(false); }
  };

  const hapusAturan = async (a) => {
    const ok = await confirm({
      title: "Hapus pagar ini?",
      description: `"${a.nama}" berhenti dipantau. Peringatan yang SUDAH terbit `
        + "tetap tersimpan sebagai riwayat pengawasan.",
      confirmText: "Hapus", variant: "destructive",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/geofence/aturan/${a.id}`);
      toast.success("Pagar dihapus");
      muat();
    } catch (e) { toast.error(getApiError(e, "Gagal menghapus pagar")); }
  };

  // ── Aksi peringatan ───────────────────────────────────────────────────────

  const tandaiDibaca = async (ev) => {
    try {
      await axios.post(`${API}/geofence/event/${ev.id}/dibaca`);
      setEvent((xs) => xs.map((x) => (x.id === ev.id ? { ...x, dibaca: true } : x)));
      setBelumDibaca((n) => Math.max(0, n - 1));
    } catch (e) { toast.error(getApiError(e, "Gagal menandai")); }
  };

  const naikkanPenertiban = async () => {
    if (!eskalasi) return;
    setMenyimpan(true);
    try {
      await axios.post(`${API}/geofence/event/${eskalasi.ev.id}/penertiban`,
                       { uraian: eskalasi.uraian || "" });
      toast.success("Tiket penertiban dibuka di modul Wasdal");
      setEskalasi(null);
      muat();
    } catch (e) {
      toast.error(getApiError(e, "Gagal menaikkan jadi penertiban"));
    } finally { setMenyimpan(false); }
  };

  // ── Aksi izin darurat ─────────────────────────────────────────────────────

  const ajukanIzin = async () => {
    const f = formIzin;
    if (!f?.device_id) { toast.error("Pilih perangkat"); return; }
    if ((f.alasan || "").trim().length < izinMinAlasan) {
      toast.error(`Alasan wajib minimal ${izinMinAlasan} karakter`); return;
    }
    setMenyimpan(true);
    try {
      await axios.post(`${API}/iot/izin-darurat`, {
        device_id: f.device_id, alasan: f.alasan.trim(),
        berlaku_jam: Number(f.berlaku_jam) || 24,
      });
      toast.success("Pengajuan dikirim — menunggu persetujuan pejabat");
      setFormIzin(null);
      muat();
    } catch (e) {
      toast.error(getApiError(e, "Gagal mengajukan izin"));
    } finally { setMenyimpan(false); }
  };

  const setujuiIzin = async (z) => {
    const ok = await confirm({
      title: "Setujui pembukaan presisi penuh?",
      description: `Perangkat "${z.device_nama}" akan menyimpan koordinat penuh `
        + `selama ${z.berlaku_jam} jam, termasuk di luar jam kerja. Tindakan ini `
        + "tercatat atas nama Anda dan tak dapat dihapus dari register.",
      confirmText: "Setujui",
    });
    if (!ok) return;
    try {
      await axios.post(`${API}/iot/izin-darurat/${z.id}/setujui`);
      toast.success("Izin aktif — berlaku untuk observasi berikutnya");
      muat();
    } catch (e) { toast.error(getApiError(e, "Gagal menyetujui")); }
  };

  const cabutIzin = async (z) => {
    const ok = await confirm({
      title: "Cabut izin sekarang?",
      description: "Presisi kembali ke profil normal mulai observasi berikutnya.",
      confirmText: "Cabut", variant: "destructive",
    });
    if (!ok) return;
    try {
      await axios.post(`${API}/iot/izin-darurat/${z.id}/cabut`);
      toast.success("Izin dicabut");
      muat();
    } catch (e) { toast.error(getApiError(e, "Gagal mencabut izin")); }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-20 bg-card/95 backdrop-blur border-b border-border">
        <div className="max-w-6xl mx-auto px-3 sm:px-6 h-12 flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={onBack} className="min-w-0 min-h-0 px-2"
                  data-testid="pelacakan-back">
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <RadioTower className="w-4 h-4 text-emerald-500 flex-shrink-0" />
          <h1 className="text-sm font-bold truncate">Pelacakan Aset</h1>
          {belumDibaca === null ? (
            <span className="ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-amber-500 text-white"
                  title="Daftar peringatan gagal dimuat" data-testid="pelacakan-badge-tak-diketahui">
              ? peringatan
            </span>
          ) : belumDibaca > 0 && (
            <span className="ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-red-500 text-white"
                  data-testid="pelacakan-badge-belum">
              {belumDibaca} baru
            </span>
          )}
          <Button variant="ghost" size="sm" onClick={muat} disabled={memuat}
                  className={`min-w-0 min-h-0 px-2 ${belumDibaca === null || belumDibaca > 0 ? "" : "ml-auto"}`}
                  data-testid="pelacakan-refresh">
            {memuat ? <Loader2 className="w-4 h-4 animate-spin" />
                    : <RefreshCw className="w-4 h-4" />}
          </Button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {/* Kebijakan privasi tampil di ATAS, dibaca dari kode penegaknya. */}
        {profilTersedia.length > 0 && (
          <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2">
            <div className="flex items-start gap-2">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0 mt-0.5" />
              <div className="min-w-0">
                <p className="text-[11px] text-foreground font-semibold">
                  Sistem ini melacak BARANG NEGARA, bukan ORANG.
                </p>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  Perangkat pegangan perorangan hanya menyimpan level wilayah/gedung
                  dan hanya pada jam kerja. Angka di bawah dibaca langsung dari kode
                  yang menegakkannya.
                </p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {profilTersedia.map((p) => (
                    <span key={p.profil}
                          className="text-[10px] rounded-md border border-border bg-card px-1.5 py-0.5">
                      <b>{p.profil}</b> · {p.presisi} · {p.jam_aktif}
                      {p.hari_kerja_saja ? " (hari kerja)" : ""} · simpan {p.retensi_hari} hari
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="flex bg-muted rounded-lg p-0.5 gap-0.5">
          {TABS.map(([k, label, Icon]) => (
            <button key={k} type="button" onClick={() => setTab(k)}
              className={`flex-1 text-[11px] sm:text-xs font-semibold py-1.5 rounded-md transition-colors flex items-center justify-center gap-1.5 min-w-0 min-h-0 ${tab === k ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
              data-testid={`pelacakan-tab-${k}`}>
              <Icon className="w-3.5 h-3.5" />{label}
              {k === "peringatan" && belumDibaca === null && (
                <span className="text-[9px] font-bold px-1 rounded-full bg-amber-500 text-white">?</span>
              )}
              {k === "peringatan" && belumDibaca > 0 && (
                <span className="text-[9px] font-bold px-1 rounded-full bg-red-500 text-white">
                  {belumDibaca}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* ── PERANGKAT ─────────────────────────────────────────────────── */}
        {tab === "perangkat" && (
          <div className="space-y-2">
            {isAdmin && (
              <Button size="sm" className="w-full sm:w-auto min-h-0"
                      onClick={() => setFormPerangkat({ profil_privasi: "personal" })}
                      data-testid="pelacakan-daftar-perangkat">
                <Plus className="w-3.5 h-3.5 mr-1" />Daftarkan perangkat
              </Button>
            )}
            {gagalBagian.perangkat ? (
              <BagianGagal pesan={gagalBagian.perangkat} onUlang={muat} sibuk={memuat}
                           catatan="Daftar perangkat belum tentu kosong — ia belum sempat dibaca."
                           testid="pelacakan-perangkat-galat" />
            ) : !perangkat.length && !memuat && (
              <p className="text-xs text-muted-foreground text-center py-8">
                Belum ada perangkat pelacak terdaftar.
              </p>
            )}
            {perangkat.map((d) => (
              <div key={d.id} className="rounded-xl border border-border bg-card p-3"
                   data-testid={`pelacakan-perangkat-${d.id}`}>
                <div className="flex items-start gap-2 min-w-0">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold truncate">{d.nama}</p>
                    <p className="text-[10px] text-muted-foreground truncate">
                      {d.asset_name || "Belum ditautkan ke aset"} · {d.kebijakan}
                    </p>
                    <div className="mt-1 flex flex-wrap gap-1.5 text-[10px]">
                      <span className="inline-flex items-center gap-1 rounded-md bg-muted px-1.5 py-0.5">
                        <Clock className="w-3 h-3" />
                        {d.kesehatan?.diam_menit === null || d.kesehatan?.diam_menit === undefined
                          ? "Belum pernah mengirim"
                          : `Terakhir ${lamaDiam(d.kesehatan.diam_menit)} lalu`}
                      </span>
                      {typeof d.kesehatan?.baterai_persen === "number" && (
                        <span className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 ${d.kesehatan.baterai_persen < 20 ? "bg-red-500/10 text-red-600 dark:text-red-400" : "bg-muted"}`}>
                          <BatteryLow className="w-3 h-3" />{d.kesehatan.baterai_persen}%
                        </span>
                      )}
                      {d.kesehatan?.ts_ragu && (
                        <span className="inline-flex items-center gap-1 rounded-md bg-amber-500/10 text-amber-600 dark:text-amber-400 px-1.5 py-0.5">
                          <ShieldAlert className="w-3 h-3" />Jam perangkat meragukan
                        </span>
                      )}
                      {!d.aktif && (
                        <span className="rounded-md bg-muted px-1.5 py-0.5">Nonaktif</span>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-col sm:flex-row gap-1 flex-shrink-0">
                    <Button variant="outline" size="sm" className="min-w-0 min-h-0 px-2 h-7 text-[10px]"
                            onClick={() => lihatPosisi(d)}
                            data-testid={`pelacakan-posisi-${d.id}`}>
                      <MapPin className="w-3 h-3 sm:mr-1" />
                      <span className="hidden sm:inline">Posisi</span>
                    </Button>
                    {isAdmin && (
                      <Button variant="outline" size="sm" className="min-w-0 min-h-0 px-2 h-7 text-[10px]"
                              onClick={() => rotasiToken(d)}
                              data-testid={`pelacakan-rotasi-${d.id}`}>
                        <KeyRound className="w-3 h-3 sm:mr-1" />
                        <span className="hidden sm:inline">Token</span>
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── PAGAR ─────────────────────────────────────────────────────── */}
        {tab === "pagar" && (
          <div className="space-y-2">
            <div className="rounded-lg border border-blue-500/20 bg-blue-500/5 px-3 py-2 flex items-start gap-2">
              <Info className="w-3.5 h-3.5 text-blue-500 flex-shrink-0 mt-0.5" />
              <p className="text-[11px] text-muted-foreground">
                Pagar memakai <b>histeresis</b>: keluar baru diakui setelah perangkat
                lebih dari {paramBawaan?.buffer_keluar_m ?? 25} m di luar batas dan
                bertahan {Math.round((paramBawaan?.dwell_keluar_dtk ?? 180) / 60)} menit.
                Itu yang mencegah aset yang <i>diam di garis batas</i> membanjiri Anda
                dengan peringatan palsu.
              </p>
            </div>
            {isAdmin && (
              <Button size="sm" className="w-full sm:w-auto min-h-0"
                      disabled={!perangkat.length}
                      onClick={() => setFormAturan({ jenis: ["masuk", "keluar"],
                                                     maks_di_luar_jam: 0, aktif: true })}
                      data-testid="pelacakan-pasang-pagar">
                <Plus className="w-3.5 h-3.5 mr-1" />Pasang pagar
              </Button>
            )}
            {/* Hanya benar bila daftar perangkat MEMANG SUDAH terbaca, dan
                terbaca kosong — karena itu `!memuat` ikut jadi syarat, sama
                seperti gerbang tiga tab lainnya. */}
            {!perangkat.length && !memuat && !gagalBagian.perangkat && (
              <p className="text-[11px] text-muted-foreground px-1">
                Daftarkan perangkat lebih dulu — pagar memantau perangkat, bukan aset
                secara langsung.
              </p>
            )}
            {/* Tombol di atas MATI ketika daftar perangkat gagal dimuat. Tanpa
                baris ini tab Pagar hanya memperlihatkan tombol abu-abu tanpa
                sepatah kata — operator menyimpulkan haknya dicabut atau fiturnya
                rusak. Kartu galat perangkat sendiri hanya dirender di tab
                Perangkat, jadi keterangannya harus dibawa ke sini. */}
            {gagalBagian.perangkat && (
              <p className="text-[11px] text-amber-700 dark:text-amber-300 px-1"
                 data-testid="pelacakan-pagar-perangkat-galat">
                Daftar perangkat gagal dimuat, jadi tombol di atas dimatikan —
                bukan karena belum ada perangkat. Buka tab <b>Perangkat</b> untuk
                mencoba lagi.
              </p>
            )}
            {gagalBagian.aturan && (
              <BagianGagal pesan={gagalBagian.aturan} onUlang={muat} sibuk={memuat}
                           catatan="Pagar yang terpasang tidak sedang ditampilkan — jangan disimpulkan belum ada."
                           testid="pelacakan-aturan-galat" />
            )}
            {aturan.map((a) => (
              <div key={a.id} className="rounded-xl border border-border bg-card p-3 flex items-start gap-2"
                   data-testid={`pelacakan-aturan-${a.id}`}>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold truncate">{a.nama}</p>
                  <p className="text-[10px] text-muted-foreground truncate">
                    {a.device_nama} ↔ {a.area_nama}
                  </p>
                  <div className="mt-1 flex flex-wrap gap-1 text-[10px]">
                    {(a.jenis || []).map((j) => (
                      <span key={j} className="rounded-md bg-muted px-1.5 py-0.5">
                        {JENIS_LABEL[j] || j}
                      </span>
                    ))}
                    {a.maks_di_luar_jam > 0 && (
                      <span className="rounded-md bg-muted px-1.5 py-0.5">
                        lapor bila &gt; {a.maks_di_luar_jam} jam di luar
                      </span>
                    )}
                    {!a.aktif && <span className="rounded-md bg-muted px-1.5 py-0.5">Nonaktif</span>}
                  </div>
                </div>
                {isAdmin && (
                  <div className="flex gap-1 flex-shrink-0">
                    <Button variant="outline" size="sm" className="min-w-0 min-h-0 px-2 h-7"
                            onClick={() => setFormAturan({ ...a })}
                            data-testid={`pelacakan-ubah-aturan-${a.id}`}>
                      <Pencil className="w-3 h-3" />
                    </Button>
                    <Button variant="outline" size="sm" className="min-w-0 min-h-0 px-2 h-7 text-red-600"
                            onClick={() => hapusAturan(a)}
                            data-testid={`pelacakan-hapus-aturan-${a.id}`}>
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* ── PERINGATAN ────────────────────────────────────────────────── */}
        {tab === "peringatan" && (
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-[11px] text-muted-foreground px-1">
              <input type="checkbox" checked={hanyaBelum}
                     onChange={(e) => setHanyaBelum(e.target.checked)}
                     data-testid="pelacakan-filter-belum" />
              Hanya yang belum dibaca
            </label>
            {/* "Itu kabar baik" HANYA boleh diucapkan bila daftarnya memang
                berhasil dimuat. Saat gagal, layar wajib mengatakan bahwa ia
                TIDAK TAHU — bukan menjamin aman. */}
            {gagalBagian.event ? (
              <BagianGagal pesan={gagalBagian.event} onUlang={muat} sibuk={memuat}
                           catatan="Ada tidaknya peringatan tidak diketahui — jangan disimpulkan aman."
                           testid="pelacakan-event-galat" />
            ) : !eventTampil.length && !memuat && (
              <p className="text-xs text-muted-foreground text-center py-8">
                Tidak ada peringatan. Itu kabar baik.
              </p>
            )}
            {eventTampil.map((ev) => (
              <div key={ev.id}
                   className={`rounded-xl border p-3 ${ev.dibaca ? "border-border bg-card" : "border-amber-500/40 bg-amber-500/5"}`}
                   data-testid={`pelacakan-event-${ev.id}`}>
                <div className="flex items-start gap-2 min-w-0">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold truncate">
                      {JENIS_LABEL[ev.jenis] || ev.jenis} — {ev.area_nama}
                    </p>
                    <p className="text-[10px] text-muted-foreground truncate">
                      {ev.device_nama}{ev.asset_name ? ` · ${ev.asset_name}` : ""} · {waktuSingkat(ev.pada)}
                    </p>
                    <div className="mt-1 flex flex-wrap gap-1 text-[10px]">
                      {ev.retro && (
                        <span className="rounded-md bg-muted px-1.5 py-0.5"
                              title="Berasal dari antrean offline perangkat — bukan kejadian yang sedang berlangsung">
                          Data susulan
                        </span>
                      )}
                      {typeof ev.jarak_m === "number" && (
                        <span className="rounded-md bg-muted px-1.5 py-0.5">
                          {ev.jarak_m} m dari batas
                        </span>
                      )}
                      {ev.penertiban_id && (
                        <span className="rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 px-1.5 py-0.5">
                          Sudah jadi tiket penertiban
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-col gap-1 flex-shrink-0">
                    {!ev.dibaca && isWriter && (
                      <Button variant="outline" size="sm" className="min-w-0 min-h-0 px-2 h-7 text-[10px]"
                              onClick={() => tandaiDibaca(ev)}
                              data-testid={`pelacakan-dibaca-${ev.id}`}>
                        <Check className="w-3 h-3 sm:mr-1" />
                        <span className="hidden sm:inline">Sudah dilihat</span>
                      </Button>
                    )}
                    {!ev.penertiban_id && isWriter && (
                      <Button variant="outline" size="sm" className="min-w-0 min-h-0 px-2 h-7 text-[10px]"
                              onClick={() => setEskalasi({ ev, uraian: "" })}
                              data-testid={`pelacakan-eskalasi-${ev.id}`}>
                        <ArrowUpRight className="w-3 h-3 sm:mr-1" />
                        <span className="hidden sm:inline">Tindak lanjuti</span>
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── IZIN DARURAT ──────────────────────────────────────────────── */}
        {tab === "izin" && (
          <div className="space-y-2">
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 flex items-start gap-2">
              <ShieldAlert className="w-3.5 h-3.5 text-amber-500 flex-shrink-0 mt-0.5" />
              <div className="min-w-0">
                <p className="text-[11px] font-semibold text-foreground">
                  Izin ini berlaku MAJU saja.
                </p>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  Posisi perangkat perorangan yang sudah terlanjur masuk SUDAH
                  kehilangan koordinatnya di jalur tulis — sistem sengaja tak
                  menyimpannya, bukan menyimpan lalu menyembunyikan. Tak ada izin
                  yang bisa memulihkannya. Karena itu ajukan <b>segera</b> setelah
                  barang dilaporkan hilang; menunda berarti kehilangan jejak yang
                  tak bisa diambil kembali.
                </p>
                <p className="text-[10px] text-muted-foreground mt-1">
                  Syarat: alasan tertulis (min. {izinMinAlasan} karakter),
                  disetujui pejabat yang <b>bukan pemohon</b>, maksimal{" "}
                  {izinMaksJam} jam. Setiap langkah tercatat di log audit.
                </p>
              </div>
            </div>
            {isWriter && (
              <Button size="sm" className="w-full sm:w-auto min-h-0"
                      disabled={!perangkat.length}
                      onClick={() => setFormIzin({ berlaku_jam: 24, alasan: "" })}
                      data-testid="pelacakan-ajukan-izin">
                <Plus className="w-3.5 h-3.5 mr-1" />Ajukan pembukaan presisi
              </Button>
            )}
            {gagalBagian.perangkat && (
              <p className="text-[11px] text-amber-700 dark:text-amber-300 px-1"
                 data-testid="pelacakan-izin-perangkat-galat">
                Daftar perangkat gagal dimuat, jadi tombol di atas dimatikan —
                bukan karena belum ada perangkat. Buka tab <b>Perangkat</b> untuk
                mencoba lagi.
              </p>
            )}
            {gagalBagian.izin ? (
              <BagianGagal pesan={gagalBagian.izin} onUlang={muat} sibuk={memuat}
                           catatan="Izin yang sedang berlaku tidak sedang ditampilkan."
                           testid="pelacakan-izin-galat" />
            ) : !izin.length && !memuat && (
              <p className="text-xs text-muted-foreground text-center py-8">
                Belum pernah ada pembukaan presisi darurat.
              </p>
            )}
            {izin.map((z) => (
              <div key={z.id}
                   className={`rounded-xl border p-3 ${z.sedang_berlaku ? "border-amber-500/40 bg-amber-500/5" : "border-border bg-card"}`}
                   data-testid={`pelacakan-izin-${z.id}`}>
                <div className="flex items-start gap-2 min-w-0">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold truncate">
                      {z.device_nama}{z.asset_name ? ` · ${z.asset_name}` : ""}
                    </p>
                    <p className="text-[10px] text-muted-foreground break-words">
                      {z.alasan}
                    </p>
                    <div className="mt-1 flex flex-wrap gap-1 text-[10px]">
                      <span className="rounded-md bg-muted px-1.5 py-0.5">
                        {z.status === "diusulkan" ? "Menunggu persetujuan"
                          : z.status === "aktif"
                            ? (z.sedang_berlaku
                                ? `Aktif — sisa ${Math.floor((z.sisa_menit || 0) / 60)} jam ${(z.sisa_menit || 0) % 60} mnt`
                                : "Masa berlaku habis")
                            : z.status}
                      </span>
                      <span className="rounded-md bg-muted px-1.5 py-0.5">
                        diminta {z.diminta_oleh} · {waktuSingkat(z.diminta_pada)}
                      </span>
                      {z.disetujui_oleh && (
                        <span className="rounded-md bg-muted px-1.5 py-0.5">
                          disetujui {z.disetujui_oleh}
                        </span>
                      )}
                    </div>
                  </div>
                  {isAdmin && (
                    <div className="flex flex-col gap-1 flex-shrink-0">
                      {z.status === "diusulkan" && (
                        <Button variant="outline" size="sm"
                                className="min-w-0 min-h-0 px-2 h-7 text-[10px]"
                                onClick={() => setujuiIzin(z)}
                                data-testid={`pelacakan-setujui-izin-${z.id}`}>
                          <Check className="w-3 h-3 sm:mr-1" />
                          <span className="hidden sm:inline">Setujui</span>
                        </Button>
                      )}
                      {(z.status === "aktif" || z.status === "diusulkan") && (
                        <Button variant="outline" size="sm"
                                className="min-w-0 min-h-0 px-2 h-7 text-[10px] text-red-600"
                                onClick={() => cabutIzin(z)}
                                data-testid={`pelacakan-cabut-izin-${z.id}`}>
                          <X className="w-3 h-3 sm:mr-1" />
                          <span className="hidden sm:inline">Cabut</span>
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* ── Dialog: ajukan izin darurat ───────────────────────────────────── */}
      <Dialog open={!!formIzin} onOpenChange={(o) => !o && setFormIzin(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-sm">Ajukan pembukaan presisi</DialogTitle>
            <DialogDescription className="text-[11px]">
              Pengajuan <b>belum</b> membuka apa pun — presisi baru terbuka
              setelah disetujui pejabat yang bukan Anda sendiri.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <select className="w-full rounded-md border border-border bg-background px-2 py-2 text-xs"
                    value={formIzin?.device_id || ""}
                    onChange={(e) => setFormIzin((f) => ({ ...f, device_id: e.target.value }))}
                    data-testid="pelacakan-izin-perangkat">
              <option value="">— pilih perangkat —</option>
              {perangkat.map((d) => (
                <option key={d.id} value={d.id}>{d.nama} ({d.profil_privasi})</option>
              ))}
            </select>
            <textarea
              className="w-full rounded-md border border-border bg-background px-2 py-2 text-xs min-h-24"
              placeholder={`Alasan tertulis, minimal ${izinMinAlasan} karakter (mis. "Laptop dinas dilaporkan hilang di Blok A3 pada 27 Juli")`}
              value={formIzin?.alasan || ""}
              onChange={(e) => setFormIzin((f) => ({ ...f, alasan: e.target.value }))}
              data-testid="pelacakan-izin-alasan" />
            <div>
              <p className="text-[10px] text-muted-foreground mb-1">
                Masa berlaku (jam, maksimal {izinMaksJam}):
              </p>
              <Input type="number" min="0.5" max={izinMaksJam} step="0.5" className="text-xs"
                     value={formIzin?.berlaku_jam ?? 24}
                     onChange={(e) => setFormIzin((f) => ({ ...f, berlaku_jam: e.target.value }))}
                     data-testid="pelacakan-izin-jam" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setFormIzin(null)}>Batal</Button>
            <Button size="sm" onClick={ajukanIzin} disabled={menyimpan}
                    data-testid="pelacakan-izin-simpan">
              {menyimpan && <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />}Ajukan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog: daftar perangkat ──────────────────────────────────────── */}
      <Dialog open={!!formPerangkat} onOpenChange={(o) => !o && setFormPerangkat(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-sm">Daftarkan perangkat pelacak</DialogTitle>
            <DialogDescription className="text-[11px]">
              Profil privasi menentukan seberapa detail posisinya boleh disimpan.
              Pilih sesuai SIAPA yang terdampak bila posisinya terekam.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Input placeholder="Nama perangkat (mis. GPS Innova B 1234 XY)"
                   value={formPerangkat?.nama || ""} className="text-xs"
                   onChange={(e) => setFormPerangkat((f) => ({ ...f, nama: e.target.value }))}
                   data-testid="pelacakan-form-nama" />
            <select className="w-full rounded-md border border-border bg-background px-2 py-2 text-xs"
                    value={formPerangkat?.profil_privasi || "personal"}
                    onChange={(e) => setFormPerangkat((f) => ({ ...f, profil_privasi: e.target.value }))}
                    data-testid="pelacakan-form-profil">
              {profilTersedia.map((p) => (
                <option key={p.profil} value={p.profil}>
                  {p.label} — {p.presisi}, {p.jam_aktif}, simpan {p.retensi_hari} hari
                </option>
              ))}
            </select>
            <Input placeholder="ID aset yang dilekati (opsional)"
                   value={formPerangkat?.asset_id || ""} className="text-xs"
                   onChange={(e) => setFormPerangkat((f) => ({ ...f, asset_id: e.target.value }))}
                   data-testid="pelacakan-form-aset" />
            <Input placeholder="Keterangan (opsional)"
                   value={formPerangkat?.keterangan || ""} className="text-xs"
                   onChange={(e) => setFormPerangkat((f) => ({ ...f, keterangan: e.target.value }))} />
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setFormPerangkat(null)}>Batal</Button>
            <Button size="sm" onClick={simpanPerangkat} disabled={menyimpan}
                    data-testid="pelacakan-form-simpan">
              {menyimpan && <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />}Daftarkan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog: token tampil SEKALI ───────────────────────────────────── */}
      <Dialog open={!!tokenBaru} onOpenChange={(o) => !o && setTokenBaru(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-sm flex items-center gap-1.5">
              <KeyRound className="w-4 h-4 text-amber-500" />Token perangkat
            </DialogTitle>
            <DialogDescription className="text-[11px]">
              Salin sekarang. Server hanya menyimpan <b>sidik</b> token ini, bukan
              tokennya — menutup jendela ini berarti token tak bisa dilihat lagi dan
              satu-satunya jalan adalah merotasinya.
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-lg border border-border bg-muted/50 p-2">
            <p className="text-[10px] text-muted-foreground mb-1">{tokenBaru?.nama}</p>
            <code className="block text-[11px] break-all font-mono">{tokenBaru?.token}</code>
          </div>
          <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/5 p-2">
            <p className="text-[10px] text-muted-foreground">
              <b>Untuk HP/tablet:</b> kirim tautan ini ke pemegang barang. Ia
              membukanya di peramban, membaca pemberitahuan privasi, lalu menekan
              Mulai — tanpa perlu akun aplikasi ini.
            </p>
            <code className="block text-[10px] break-all font-mono mt-1">
              {`${window.location.origin}/lacak?token=${tokenBaru?.token || ""}`}
            </code>
          </div>
          <DialogFooter className="flex-col sm:flex-row gap-1">
            <Button size="sm" variant="outline" onClick={() => {
              navigator.clipboard?.writeText(tokenBaru?.token || "")
                .then(() => toast.success("Token disalin"))
                .catch(() => toast.error("Gagal menyalin — salin manual dari kotak di atas"));
            }} data-testid="pelacakan-salin-token">
              <Copy className="w-3.5 h-3.5 mr-1" />Salin token
            </Button>
            <Button size="sm" onClick={() => {
              const tautan = `${window.location.origin}/lacak?token=${tokenBaru?.token || ""}`;
              navigator.clipboard?.writeText(tautan)
                .then(() => toast.success("Tautan pendamping disalin"))
                .catch(() => toast.error("Gagal menyalin — salin manual dari kotak di atas"));
            }} data-testid="pelacakan-salin-tautan">
              <Copy className="w-3.5 h-3.5 mr-1" />Salin tautan HP
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setTokenBaru(null)}>
              Sudah disimpan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog: pasang/ubah pagar ─────────────────────────────────────── */}
      <Dialog open={!!formAturan} onOpenChange={(o) => !o && setFormAturan(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-sm">
              {formAturan?.id ? "Ubah pagar" : "Pasang pagar area"}
            </DialogTitle>
            <DialogDescription className="text-[11px]">
              Area pagar harus berupa <b>poligon</b> (kawasan/gedung yang sudah digambar
              batasnya di Hierarki Spasial) — titik tak punya sisi dalam dan luar.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Input placeholder="Nama aturan (mis. Innova wajib di pool)"
                   value={formAturan?.nama || ""} className="text-xs"
                   onChange={(e) => setFormAturan((f) => ({ ...f, nama: e.target.value }))}
                   data-testid="pelacakan-aturan-nama" />
            <select className="w-full rounded-md border border-border bg-background px-2 py-2 text-xs"
                    value={formAturan?.device_id || ""}
                    onChange={(e) => setFormAturan((f) => ({ ...f, device_id: e.target.value }))}
                    data-testid="pelacakan-aturan-perangkat">
              <option value="">— pilih perangkat —</option>
              {perangkat.map((d) => <option key={d.id} value={d.id}>{d.nama}</option>)}
            </select>
            <select className="w-full rounded-md border border-border bg-background px-2 py-2 text-xs"
                    value={formAturan?.area_node_id || ""}
                    onChange={(e) => setFormAturan((f) => ({ ...f, area_node_id: e.target.value }))}
                    data-testid="pelacakan-aturan-area">
              <option value="">— pilih area —</option>
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>{n.nama} ({n.tipe})</option>
              ))}
            </select>
            <div className="space-y-1">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">
                Beri tahu saya saat
              </p>
              {jenisTersedia.map((j) => (
                <label key={j} className="flex items-center gap-2 text-[11px]">
                  <input type="checkbox"
                         checked={(formAturan?.jenis || []).includes(j)}
                         onChange={(e) => setFormAturan((f) => ({
                           ...f,
                           jenis: e.target.checked
                             ? [...(f.jenis || []), j]
                             : (f.jenis || []).filter((x) => x !== j),
                         }))}
                         data-testid={`pelacakan-aturan-jenis-${j}`} />
                  {JENIS_LABEL[j] || j}
                </label>
              ))}
            </div>
            {(formAturan?.jenis || []).includes("dwell_terlampaui") && (
              <div>
                <p className="text-[10px] text-muted-foreground mb-1">
                  Lapor bila aset di luar area lebih dari (jam):
                </p>
                <Input type="number" min="0" step="0.5" className="text-xs"
                       value={formAturan?.maks_di_luar_jam ?? 0}
                       onChange={(e) => setFormAturan((f) => ({ ...f, maks_di_luar_jam: e.target.value }))}
                       data-testid="pelacakan-aturan-dwell" />
              </div>
            )}
            <label className="flex items-center gap-2 text-[11px]">
              <input type="checkbox" checked={formAturan?.aktif !== false}
                     onChange={(e) => setFormAturan((f) => ({ ...f, aktif: e.target.checked }))}
                     data-testid="pelacakan-aturan-aktif" />
              Pagar aktif
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setFormAturan(null)}>Batal</Button>
            <Button size="sm" onClick={simpanAturan} disabled={menyimpan}
                    data-testid="pelacakan-aturan-simpan">
              {menyimpan && <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />}Simpan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog: riwayat posisi ────────────────────────────────────────── */}
      <Dialog open={!!posisi} onOpenChange={(o) => !o && setPosisi(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-sm">Riwayat posisi — {posisi?.perangkat?.nama}</DialogTitle>
            <DialogDescription className="text-[11px]">
              {posisi?.perangkat?.kebijakan}. Data yang tampil sudah tersaring saat
              MASUK, bukan saat ditampilkan — yang tak boleh disimpan memang tak
              pernah tersimpan.
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-80 overflow-y-auto space-y-1">
            {!posisi?.items?.length && (
              <p className="text-[11px] text-muted-foreground py-4 text-center">
                Belum ada posisi tersimpan untuk perangkat ini.
              </p>
            )}
            {(posisi?.items || []).map((o, i) => (
              <div key={i} className="rounded-lg border border-border bg-card px-2 py-1.5 text-[10px]">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono">
                    {o.geo?.coordinates
                      ? `${o.geo.coordinates[1].toFixed(5)}, ${o.geo.coordinates[0].toFixed(5)}`
                      : (o.lokasi_spasial?.jalur_nama || o.lokasi_spasial?.node_nama
                         || "wilayah saja")}
                  </span>
                  <span className="text-muted-foreground flex-shrink-0">
                    {waktuSingkat(o.ts_device)}
                  </span>
                </div>
                <div className="mt-0.5 flex flex-wrap gap-1 text-muted-foreground">
                  {o.presisi_didegradasi && <span>presisi diturunkan (profil privasi)</span>}
                  {o.outlier && <span className="text-amber-600 dark:text-amber-400">lompatan mustahil</span>}
                  {o.ts_ragu && <span className="text-amber-600 dark:text-amber-400">jam perangkat ragu</span>}
                  {typeof o.akurasi_m === "number" && <span>±{o.akurasi_m} m</span>}
                </div>
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setPosisi(null)}>Tutup</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog: eskalasi ke penertiban ────────────────────────────────── */}
      <Dialog open={!!eskalasi} onOpenChange={(o) => !o && setEskalasi(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-sm">Naikkan jadi tiket penertiban</DialogTitle>
            <DialogDescription className="text-[11px]">
              Tiket masuk register Wasdal dengan tenggat <b>15 hari kerja</b> (PMK
              207/2021). Karena itu langkah ini sengaja MANUAL — pembacaan GPS saja
              tak boleh membuka perkara resmi.
            </DialogDescription>
          </DialogHeader>
          <textarea
            className="w-full rounded-md border border-border bg-background px-2 py-2 text-xs min-h-24"
            placeholder="Uraian (kosongkan untuk memakai ringkasan peringatan otomatis)"
            value={eskalasi?.uraian || ""}
            onChange={(e) => setEskalasi((s) => ({ ...s, uraian: e.target.value }))}
            data-testid="pelacakan-eskalasi-uraian" />
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setEskalasi(null)}>Batal</Button>
            <Button size="sm" onClick={naikkanPenertiban} disabled={menyimpan}
                    data-testid="pelacakan-eskalasi-simpan">
              {menyimpan && <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />}Buka tiket
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}
