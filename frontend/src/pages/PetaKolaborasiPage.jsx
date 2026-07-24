import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import axios from "axios";
import { toast } from "sonner";
import {
  MapPin, MessageSquarePlus, Plus, X, Loader2, Send, Users, Clock,
  AlertTriangle, RefreshCcw, WifiOff,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Pin sederhana via divIcon (hindari masalah aset ikon default leaflet).
function pin(color, sel) {
  return L.divIcon({
    className: "",
    html: `<div style="width:${sel ? 20 : 15}px;height:${sel ? 20 : 15}px;border-radius:50% 50% 50% 0;background:${color};transform:rotate(-45deg);border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)"></div>`,
    iconSize: [sel ? 20 : 15, sel ? 20 : 15],
    iconAnchor: [sel ? 10 : 8, sel ? 10 : 8],
  });
}

function fmtWaktu(iso) {
  try {
    return new Date(iso).toLocaleString("id-ID", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  } catch { return "-"; }
}

// Sisa masa tayang → teks singkat ("2 hari 3 jam" / "Berakhir").
function sisaTayang(iso) {
  if (!iso) return "";
  const ms = new Date(iso).getTime() - Date.now();
  if (isNaN(ms)) return "";
  if (ms <= 0) return "Masa tayang berakhir";
  const jam = Math.floor(ms / 3600000);
  const hari = Math.floor(jam / 24);
  if (hari >= 1) return `Sisa ${hari} hari ${jam % 24} jam`;
  if (jam >= 1) return `Sisa ${jam} jam`;
  return `Sisa ${Math.max(1, Math.floor(ms / 60000))} menit`;
}

export default function PetaKolaborasiPage() {
  const { id, token } = useMemo(() => {
    const m = window.location.pathname.match(/^\/peta\/kolaborasi\/([\w-]+)/);
    const t = new URLSearchParams(window.location.search).get("token") || "";
    return { id: m ? m[1] : "", token: t };
  }, []);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [galat, setGalat] = useState("");
  const [koneksi, setKoneksi] = useState(false);
  const [nama, setNama] = useState(() => { try { return localStorage.getItem("peta_nama") || ""; } catch { return ""; } });
  const [namaDialog, setNamaDialog] = useState(false);
  const [namaDraf, setNamaDraf] = useState("");
  const aksiSetelahNama = useRef(null); // aksi yang menunggu nama terisi

  const [dipilih, setDipilih] = useState(null); // {target_jenis, target_id, judul, ...}
  const [modeTambah, setModeTambah] = useState(false);
  const [formTitik, setFormTitik] = useState(null); // {lat,lng,nama_titik,keterangan}
  const [komentarTeks, setKomentarTeks] = useState("");
  const [kirim, setKirim] = useState(false);

  const mapElRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const fitOnceRef = useRef(false);

  const muat = useCallback(async () => {
    if (!id) { setGalat("Link peta tidak lengkap."); setLoading(false); return; }
    try {
      const r = await axios.get(`${API}/peta/kolaborasi/${id}`, { params: { token }, timeout: 20000 });
      setData(r.data); setGalat(""); setKoneksi(false);
    } catch (e) {
      if (!e?.response) setKoneksi(true);
      else setGalat(e.response?.data?.detail || "Link tidak valid atau masa tayang telah berakhir.");
    } finally { setLoading(false); }
  }, [id, token]);

  useEffect(() => { muat(); }, [muat]);

  // Inisialisasi peta (sekali) saat data pertama tersedia.
  useEffect(() => {
    if (!data || mapRef.current || !mapElRef.current) return;
    const map = L.map(mapElRef.current, { zoomControl: true, attributionControl: true, maxZoom: 22, tapHold: true });
    map.setView([-1.4, 116.7], 5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 22, maxNativeZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    setTimeout(() => map.invalidateSize(), 60);
    return () => { map.remove(); mapRef.current = null; };
  }, [data]);

  // Klik peta di mode "tambah titik" → buka form titik baru.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const onClick = (ev) => {
      if (!modeTambah) return;
      setFormTitik({ lat: ev.latlng.lat, lng: ev.latlng.lng, nama_titik: "", keterangan: "" });
      setModeTambah(false);
    };
    map.on("click", onClick);
    return () => map.off("click", onClick);
  }, [modeTambah]);

  // Gambar ulang marker saat data / seleksi berubah.
  useEffect(() => {
    const map = mapRef.current, layer = layerRef.current;
    if (!map || !layer || !data) return;
    layer.clearLayers();
    const pts = [];
    (data.titik_aset || []).forEach((a) => {
      const sel = dipilih?.target_jenis === "aset" && dipilih?.target_id === a.id;
      const m = L.marker([a.lat, a.lng], { icon: pin(sel ? "#1d4ed8" : "#2563eb", sel) });
      m.on("click", () => setDipilih({ target_jenis: "aset", target_id: a.id, judul: `${a.kode || ""}${a.nup ? ` · NUP ${a.nup}` : ""}`, sub: a.nama, status: a.status }));
      m.addTo(layer); pts.push([a.lat, a.lng]);
    });
    (data.titik_kolaborasi || []).forEach((t) => {
      const sel = dipilih?.target_jenis === "titik" && dipilih?.target_id === t.id;
      const m = L.marker([t.lat, t.lng], { icon: pin(sel ? "#047857" : "#10b981", sel) });
      m.on("click", () => setDipilih({ target_jenis: "titik", target_id: t.id, judul: t.nama_titik, sub: t.keterangan, oleh: t.oleh, waktu: t.created_at }));
      m.addTo(layer); pts.push([t.lat, t.lng]);
    });
    if (!fitOnceRef.current && pts.length) {
      try { map.fitBounds(L.latLngBounds(pts), { padding: [40, 40], maxZoom: 18 }); } catch { /* noop */ }
      fitOnceRef.current = true;
    }
  }, [data, dipilih]);

  const butuhNama = useCallback((aksi) => {
    if (data && !data.tamu) { aksi(); return; }   // user login pakai identitasnya
    if (nama.trim()) { aksi(); return; }
    aksiSetelahNama.current = aksi;
    setNamaDraf(nama);
    setNamaDialog(true);
  }, [data, nama]);

  const simpanNama = () => {
    const n = namaDraf.trim().slice(0, 60);
    if (!n) { toast.error("Isi nama Anda dulu"); return; }
    setNama(n); try { localStorage.setItem("peta_nama", n); } catch { /* noop */ }
    setNamaDialog(false);
    const aksi = aksiSetelahNama.current; aksiSetelahNama.current = null;
    if (aksi) aksi();
  };

  const komentarUntuk = useMemo(() => {
    if (!data || !dipilih) return [];
    return (data.komentar || []).filter((k) => k.target_jenis === dipilih.target_jenis && k.target_id === dipilih.target_id);
  }, [data, dipilih]);

  const kirimTitik = async () => {
    if (!formTitik) return;
    if (!formTitik.nama_titik.trim()) { toast.error("Nama titik wajib diisi"); return; }
    butuhNama(async () => {
      setKirim(true);
      try {
        const r = await axios.post(`${API}/peta/kolaborasi/${id}/titik`, {
          lat: formTitik.lat, lng: formTitik.lng,
          nama_titik: formTitik.nama_titik.trim(), keterangan: (formTitik.keterangan || "").trim(),
          oleh: nama,
        }, { params: { token }, timeout: 20000 });
        setData((d) => ({ ...d, titik_kolaborasi: [...(d.titik_kolaborasi || []), r.data] }));
        setFormTitik(null);
        toast.success("Titik ditambahkan");
      } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menambah titik"); }
      finally { setKirim(false); }
    });
  };

  const kirimKomentar = async () => {
    if (!dipilih || !komentarTeks.trim()) { toast.error("Tulis komentar dulu"); return; }
    butuhNama(async () => {
      setKirim(true);
      try {
        const r = await axios.post(`${API}/peta/kolaborasi/${id}/komentar`, {
          target_jenis: dipilih.target_jenis, target_id: dipilih.target_id,
          teks: komentarTeks.trim(), oleh: nama,
        }, { params: { token }, timeout: 20000 });
        setData((d) => ({ ...d, komentar: [...(d.komentar || []), r.data] }));
        setKomentarTeks("");
        toast.success("Komentar terkirim");
      } catch (e) { toast.error(e?.response?.data?.detail || "Gagal mengirim komentar"); }
      finally { setKirim(false); }
    });
  };

  // ── Status layar ──
  if (loading) return <div className="min-h-screen flex items-center justify-center bg-slate-50"><Loader2 className="w-7 h-7 animate-spin text-blue-600" /></div>;
  if (koneksi) return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
      <div className="text-center max-w-sm">
        <WifiOff className="w-10 h-10 text-amber-500 mx-auto mb-3" />
        <p className="font-semibold text-slate-800">Koneksi bermasalah</p>
        <p className="text-sm text-slate-500 mt-1">Link Anda mungkin masih berlaku — periksa internet lalu coba lagi.</p>
        <button onClick={() => { setLoading(true); muat(); }} className="mt-4 inline-flex items-center gap-1.5 px-4 h-10 rounded-lg bg-blue-600 text-white text-sm font-semibold">
          <RefreshCcw className="w-4 h-4" />Coba lagi
        </button>
      </div>
    </div>
  );
  if (galat) return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
      <div className="text-center max-w-sm">
        <AlertTriangle className="w-10 h-10 text-red-500 mx-auto mb-3" />
        <p className="font-semibold text-slate-800">Tidak dapat membuka peta</p>
        <p className="text-sm text-slate-600 mt-1">{galat}</p>
      </div>
    </div>
  );

  const bolehKontribusi = !!data?.boleh_kontribusi;
  const bolehTitik = bolehKontribusi && (data?.tamu ? data?.izinkan_titik_publik : true);
  const bolehKomentar = bolehKontribusi && (data?.tamu ? data?.izinkan_komentar_publik : true);

  return (
    <div className="fixed inset-0 flex flex-col bg-slate-100">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-3 py-2 flex items-center gap-2 z-[500] shadow-sm">
        <span className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
          <MapPin className="w-5 h-5 text-white" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-bold text-slate-800 truncate leading-tight">
            {data?.judul || "Peta Kolaboratif"}
          </p>
          <p className="text-[11px] text-slate-500 truncate flex items-center gap-1.5">
            {data?.nama_kegiatan ? <span className="truncate">{data.nama_kegiatan}</span> : null}
            <span className="inline-flex items-center gap-0.5 flex-shrink-0"><Clock className="w-3 h-3" />{sisaTayang(data?.berlaku_sampai)}</span>
          </p>
        </div>
        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-blue-700 bg-blue-100 px-2 py-1 rounded-full flex-shrink-0">
          <Users className="w-3 h-3" />Kolaboratif
        </span>
      </header>

      {/* Info kedaluwarsa (operator melihat arsip) */}
      {data?.kedaluwarsa && (
        <div className="bg-amber-50 border-b border-amber-200 px-3 py-1.5 text-[11px] text-amber-800 flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
          Masa tayang berakhir — mode arsip (hanya lihat). Perpanjang dari aplikasi untuk berkontribusi lagi.
        </div>
      )}

      {/* Peta */}
      <div className="relative flex-1 min-h-0">
        <div ref={mapElRef} className="absolute inset-0" data-testid="peta-kolaborasi-map" />

        {/* Legenda */}
        <div className="absolute top-2 left-2 z-[500] bg-white/95 rounded-lg shadow px-2.5 py-1.5 text-[10px] text-slate-600 space-y-0.5">
          <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-blue-600 inline-block" />Titik aset</div>
          <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />Titik kolaborasi</div>
        </div>

        {/* Tombol Tambah Titik */}
        {bolehTitik && (
          <button
            onClick={() => { setDipilih(null); setModeTambah((v) => !v); if (!modeTambah) toast.info("Ketuk peta untuk menaruh titik"); }}
            className={`absolute bottom-4 right-4 z-[500] h-12 px-4 rounded-full shadow-lg flex items-center gap-2 text-sm font-semibold ${modeTambah ? "bg-red-600 text-white" : "bg-emerald-600 text-white"}`}
            data-testid="peta-tambah-titik"
          >
            {modeTambah ? <><X className="w-5 h-5" />Batal</> : <><Plus className="w-5 h-5" />Tambah Titik</>}
          </button>
        )}
        {modeTambah && (
          <div className="absolute bottom-20 left-1/2 -translate-x-1/2 z-[500] bg-slate-800 text-white text-[11px] px-3 py-1.5 rounded-full shadow">Ketuk lokasi di peta</div>
        )}
      </div>

      {/* Panel detail titik + komentar (bottom sheet) */}
      {dipilih && (
        <div className="absolute inset-x-0 bottom-0 z-[600] bg-white rounded-t-2xl shadow-2xl max-h-[60vh] flex flex-col border-t border-slate-200" data-testid="peta-panel-titik">
          <div className="flex items-start gap-2 p-3 border-b border-slate-100">
            <span className={`w-2.5 h-2.5 rounded-full mt-1.5 flex-shrink-0 ${dipilih.target_jenis === "aset" ? "bg-blue-600" : "bg-emerald-500"}`} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold text-slate-800 truncate">{dipilih.judul || "Titik"}</p>
              {dipilih.sub && <p className="text-xs text-slate-500 truncate">{dipilih.sub}</p>}
              {dipilih.oleh && <p className="text-[10px] text-slate-400">oleh {dipilih.oleh}{dipilih.waktu ? ` · ${fmtWaktu(dipilih.waktu)}` : ""}</p>}
            </div>
            <button onClick={() => setDipilih(null)} className="p-1.5 rounded-md hover:bg-slate-100 text-slate-500"><X className="w-4 h-4" /></button>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {komentarUntuk.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-4">Belum ada komentar di titik ini.</p>
            ) : komentarUntuk.map((k) => (
              <div key={k.id} className="bg-slate-50 rounded-lg px-3 py-2">
                <p className="text-sm text-slate-700 whitespace-pre-wrap break-words">{k.teks}</p>
                <p className="text-[10px] text-slate-400 mt-1">{k.oleh} · {fmtWaktu(k.created_at)}</p>
              </div>
            ))}
          </div>
          {bolehKomentar ? (
            <div className="p-2 border-t border-slate-100 flex items-end gap-2">
              <textarea
                value={komentarTeks} onChange={(e) => setKomentarTeks(e.target.value)}
                rows={1} maxLength={1000} placeholder="Tulis komentar…"
                className="flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 max-h-24"
                data-testid="peta-komentar-input"
              />
              <button onClick={kirimKomentar} disabled={kirim} className="h-10 w-10 rounded-lg bg-blue-600 text-white flex items-center justify-center flex-shrink-0 disabled:opacity-50" data-testid="peta-komentar-kirim">
                {kirim ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </div>
          ) : (
            <div className="p-2 border-t border-slate-100 text-[11px] text-slate-400 text-center flex items-center justify-center gap-1">
              <MessageSquarePlus className="w-3.5 h-3.5" />{data?.kedaluwarsa ? "Mode arsip — komentar dinonaktifkan." : "Komentar publik dinonaktifkan pembagi."}
            </div>
          )}
        </div>
      )}

      {/* Form titik baru */}
      {formTitik && (
        <div className="fixed inset-0 z-[700] bg-black/40 flex items-end sm:items-center justify-center p-3" onClick={() => setFormTitik(null)}>
          <div className="bg-white rounded-2xl w-full max-w-sm p-4 space-y-3" onClick={(e) => e.stopPropagation()}>
            <p className="text-sm font-bold text-slate-800 flex items-center gap-1.5"><MapPin className="w-4 h-4 text-emerald-600" />Titik Kolaborasi Baru</p>
            <p className="text-[11px] text-slate-500">{formTitik.lat.toFixed(6)}, {formTitik.lng.toFixed(6)}</p>
            <input
              autoFocus value={formTitik.nama_titik} maxLength={120}
              onChange={(e) => setFormTitik((f) => ({ ...f, nama_titik: e.target.value }))}
              placeholder="Nama/label titik *"
              className="w-full rounded-lg border border-slate-300 px-3 h-10 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              data-testid="peta-titik-nama"
            />
            <textarea
              value={formTitik.keterangan} maxLength={1000} rows={3}
              onChange={(e) => setFormTitik((f) => ({ ...f, keterangan: e.target.value }))}
              placeholder="Keterangan (opsional)"
              className="w-full resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setFormTitik(null)} className="px-3 h-10 rounded-lg border border-slate-300 text-sm text-slate-600">Batal</button>
              <button onClick={kirimTitik} disabled={kirim} className="px-4 h-10 rounded-lg bg-emerald-600 text-white text-sm font-semibold flex items-center gap-1.5 disabled:opacity-50" data-testid="peta-titik-simpan">
                {kirim ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}Tambah
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Dialog nama tamu */}
      {namaDialog && (
        <div className="fixed inset-0 z-[800] bg-black/40 flex items-center justify-center p-3">
          <div className="bg-white rounded-2xl w-full max-w-xs p-4 space-y-3">
            <p className="text-sm font-bold text-slate-800">Siapa nama Anda?</p>
            <p className="text-[11px] text-slate-500">Nama ini ditampilkan pada titik & komentar yang Anda tambahkan.</p>
            <input
              autoFocus value={namaDraf} maxLength={60}
              onChange={(e) => setNamaDraf(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") simpanNama(); }}
              placeholder="Nama Anda"
              className="w-full rounded-lg border border-slate-300 px-3 h-10 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              data-testid="peta-nama-input"
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => { setNamaDialog(false); aksiSetelahNama.current = null; }} className="px-3 h-10 rounded-lg border border-slate-300 text-sm text-slate-600">Batal</button>
              <button onClick={simpanNama} className="px-4 h-10 rounded-lg bg-blue-600 text-white text-sm font-semibold" data-testid="peta-nama-simpan">Lanjut</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
