// Penanda LOKASI di denah — dipakai temuan wasdal (Spasial Fase 8) DAN
// penempatan aset pada node denah (`PUT /assets/{id}/lokasi-spasial`).
//
// Alur: operator mengklik peta → titik tertancap → deteksi Fase 3
// (POST /spasial/lokasi-di-titik) menampilkan rantai wilayah (Kawasan → … →
// Gedung) + pilihan lantai bila titik jatuh di gedung + persempit ke RUANGAN
// (GET /spasial/ruangan-di-titik) → Simpan mengirim {lat, lon, node_id} ke
// `submitUrl`; SERVER yang men-snapshot nama/jalur dari DB (string klien tak
// dipercaya). Titik di luar kawasan terpetakan tetap boleh disimpan sebagai
// penanda koordinat murni.
//
// Titik yang SUDAH ada (penempatan tersimpan, atau umpan `titikAwal` dari
// koordinat GPS aset) dideteksi OTOMATIS saat dialog terbuka. Tanpa ini
// dialog terbuka bisu: marker tampak tapi panel info kosong total — tak ada
// rantai, tak ada pesan — dan operator menyimpulkan deteksinya rusak padahal
// deteksi belum pernah dijalankan (laporan pemilik: "belum terdeteksi
// informasi sama sekali"). Deteksi otomatis TIDAK menimpa node tersimpan:
// menimpanya membuat "buka lalu Simpan" diam-diam menurunkan penempatan
// lantai/ruangan menjadi gedung hasil deteksi.
//
// Penempatan TERSIMPAN ditampilkan langsung dari snapshot server
// (`lokasiAwal.jalur_nama`) tanpa menunggu deteksi — deteksi bisa gagal di
// jaringan lapangan yang buruk, dan "sudah saya simpan tapi tak ada
// informasinya" adalah keluhan yang benar bila satu-satunya sumber tampilan
// adalah panggilan jaringan yang barusan gagal.
//
// Poligon denah aktif ikut digambar di peta (GET /spasial/geojson per
// viewport) supaya operator MELIHAT denahnya, bukan menebak — ubin OSM yang
// lambat/mati di lapangan tak lagi menyisakan peta hitam kosong.
//
// Kontrak PUT-nya identik untuk kedua pemakai — itulah sebabnya dialog ini
// hanya perlu di-parameterkan KATA-KATANYA, bukan disalin. Default-nya tetap
// bunyi wasdal supaya pemanggil lama tak berubah perilaku.
import React, { useCallback, useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, MapPin, RotateCcw, Save, Trash2 } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
// Pusat KIPP IKN — pandangan awal saat tiket belum punya penanda.
const PUSAT_IKN = [-1.4025, 116.711];

// [lon, lat] GeoJSON → {lat, lon}, atau null bila korup (string/NaN dari data
// lama tak boleh meledakkan .toFixed di render — jatuh ke "belum ada").
function titikSah(t) {
  const lat = Number(t?.[1]);
  const lon = Number(t?.[0]);
  return Number.isFinite(lat) && Number.isFinite(lon) ? { lat, lon } : null;
}

export default function LokasiTemuanDialog({
  judul, submitUrl, lokasiAwal, titikAwal, onClose, onSaved,
  judulDialog = "Lokasi Temuan",
  petunjuk = "klik peta untuk menancapkan titik; wilayah/gedung terdeteksi otomatis.",
  labelHapus = "Hapus Penanda",
  pesanSimpan = "Lokasi temuan tersimpan",
  pesanHapus = "Penanda lokasi dihapus",
}) {
  const petaRef = useRef(null);
  const wadahRef = useRef(null);
  const markerRef = useRef(null);
  const lapisanDenahRef = useRef(null);
  const jamDenahRef = useRef(null);
  // Penempatan tersimpan menang; tanpa itu (atau bila korup) pakai umpan
  // `titikAwal` — koordinat GPS aset — supaya peta terbuka TEPAT di posisinya,
  // bukan kosong di pusat kawasan. Keduanya format GeoJSON [lon, lat].
  const seed = titikSah(lokasiAwal?.titik) || titikSah(titikAwal);
  const [titik, setTitik] = useState(seed);
  const [deteksi, setDeteksi] = useState(null);   // hasil lokasi-di-titik terakhir
  const [nodeId, setNodeId] = useState(lokasiAwal?.node_id || "");
  // Lantai yang sedang "dibuka" untuk persempit ruangan. Node tersimpan
  // bertipe LANTAI langsung membukanya; bertipe RUANGAN tak bisa (id lantainya
  // tak ada di snapshot) — jalur tersimpan toh sudah tampil apa adanya.
  const [lantaiAktif, setLantaiAktif] = useState(
    lokasiAwal?.node_tipe === "LANTAI" ? (lokasiAwal?.node_id || "") : "");
  const [ruangan, setRuangan] = useState(null);   // hasil ruangan-di-titik
  const [sibuk, setSibuk] = useState(false);
  const [mendeteksi, setMendeteksi] = useState(false);
  const seqRef = useRef(0);
  // Cermin nodeId untuk dibaca callback ber-deps kosong tanpa closure basi.
  const nodeIdRef = useRef(nodeId);
  useEffect(() => { nodeIdRef.current = nodeId; }, [nodeId]);

  const deteksiTitik = useCallback(async (lat, lon, pertahankanNode = false) => {
    const seq = ++seqRef.current;
    setMendeteksi(true);
    try {
      const r = await axios.post(`${API}/spasial/lokasi-di-titik`, { lat, lon });
      if (seq !== seqRef.current) return;          // klik lebih baru sudah terjadi
      setDeteksi(r.data);
      const rantai = r.data?.rantai || [];
      // `pertahankanNode` (deteksi otomatis saat dialog terbuka): node yang
      // SUDAH tersimpan tidak ditimpa — deteksi berhenti di gedung, jadi
      // menimpanya membuat "buka lalu Simpan" menurunkan penempatan
      // lantai/ruangan menjadi gedung tanpa ada yang memintanya.
      const adaTersimpan = pertahankanNode && nodeIdRef.current;
      if (!adaTersimpan) {
        // Gedung berlantai tunggal aktif → lantainya langsung terpilih;
        // selain itu prapilih node TERDALAM rantai.
        const lt = r.data?.lantai_terpilih || "";
        setLantaiAktif(lt);
        setRuangan(null);
        setNodeId(lt || (rantai.length ? rantai[rantai.length - 1].id : ""));
      }
    } catch {
      if (seq === seqRef.current) {
        setDeteksi(null);
        if (!pertahankanNode) setNodeId("");
        toast.error("Deteksi lokasi gagal — penanda tetap bisa disimpan");
      }
    } finally {
      if (seq === seqRef.current) setMendeteksi(false);
    }
  }, []);

  // Lapisan poligon denah aktif per-viewport. `interactive: false` WAJIB:
  // poligon yang menangkap klik menelan event sebelum sampai ke peta, dan
  // menancapkan titik DI DALAM denah — kegunaan inti dialog ini — jadi mustahil.
  const muatDenah = useCallback(async () => {
    const map = petaRef.current;
    if (!map) return;
    try {
      const b = map.getBounds();
      const bbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]
        .map((v) => v.toFixed(6)).join(",");
      const r = await axios.get(`${API}/spasial/geojson`,
        { params: { bbox, level_maks: 100 } });
      if (!petaRef.current) return;
      if (lapisanDenahRef.current) lapisanDenahRef.current.remove();
      lapisanDenahRef.current = L.geoJSON(r.data, {
        interactive: false,
        style: () => ({ color: "#14b8a6", weight: 1.2,
                        opacity: 0.9, fillOpacity: 0.08 }),
      }).addTo(map);
    } catch { /* peta dasar tetap berfungsi tanpa lapisan denah */ }
  }, []);

  // ── Peta ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!wadahRef.current || petaRef.current) return undefined;
    const map = L.map(wadahRef.current, { zoomControl: true, attributionControl: true, maxZoom: 22 });
    map.attributionControl.setPrefix(false); // prefiks "Leaflet" opsional; © OpenStreetMap tetap (wajib lisensi)
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 22, maxNativeZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    map.setView(seed ? [seed.lat, seed.lon] : PUSAT_IKN, seed ? 18 : 15);
    petaRef.current = map;
    if (seed) {
      markerRef.current = L.marker([seed.lat, seed.lon]).addTo(map);
      // Titik yang sudah ada langsung dideteksi — dialog tak boleh terbuka
      // bisu (marker tampak, panel info kosong). `true` = jangan timpa node
      // tersimpan.
      deteksiTitik(seed.lat, seed.lon, true);
    }
    muatDenah();
    map.on("moveend", () => {
      clearTimeout(jamDenahRef.current);
      jamDenahRef.current = setTimeout(muatDenah, 300);
    });
    map.on("click", (e) => {
      const { lat, lng } = e.latlng;
      if (markerRef.current) markerRef.current.setLatLng(e.latlng);
      else markerRef.current = L.marker(e.latlng).addTo(map);
      setTitik({ lat, lon: lng });
      deteksiTitik(lat, lng);
    });
    // "Leaflet blank di dalam modal": peta dibuat saat dialog masih beranimasi
    // → kontainer 0 px → peta putih polos. ResizeObserver + beberapa invalidate
    // terjadwal menjamin peta tampil setelah dialog terbuka (lihat DenahEditor).
    const invalidasi = () => { try { map.invalidateSize(false); } catch { /* dibuang */ } };
    const jamInval = [80, 250, 500, 900].map((ms) => setTimeout(invalidasi, ms));
    let ro = null;
    if (typeof ResizeObserver !== "undefined" && wadahRef.current) {
      ro = new ResizeObserver(invalidasi);
      ro.observe(wadahRef.current);
    }
    return () => {
      jamInval.forEach(clearTimeout);
      clearTimeout(jamDenahRef.current);
      if (ro) ro.disconnect();
      map.remove(); petaRef.current = null; markerRef.current = null;
      lapisanDenahRef.current = null;
    };
    // `seed` (lokasiAwal/titikAwal) hanya dibaca saat init — dialog di-mount
    // ulang per tiket/aset.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deteksiTitik, muatDenah]);

  // ── Persempit ke ruangan ─────────────────────────────────────────────────
  // Lantai terpilih + titik ada → tanyakan ruangan mana yang memuat titiknya.
  // Nol hasil BUKAN galat (titik di koridor): server mengirim daftar ruangan
  // lantai itu agar operator memilih sendiri.
  useEffect(() => {
    if (!lantaiAktif || !titik) { setRuangan(null); return undefined; }
    let batal = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/spasial/ruangan-di-titik`, {
          params: { lon: titik.lon, lat: titik.lat, lantai_id: lantaiAktif },
        });
        if (batal) return;
        setRuangan(r.data);
        // Prapilih ruangan hasil deteksi HANYA bila pilihan masih di lantainya
        // — node tersimpan/lebih dalam tak boleh tergeser diam-diam.
        if (r.data?.ditemukan && r.data?.ruangan?.id) {
          setNodeId((kini) => (kini === lantaiAktif ? r.data.ruangan.id : kini));
        }
      } catch { if (!batal) setRuangan(null); }
    })();
    return () => { batal = true; };
  }, [lantaiAktif, titik]);

  const simpan = useCallback(async () => {
    if (!titik) return;
    setSibuk(true);
    try {
      const r = await axios.put(submitUrl, { lat: titik.lat, lon: titik.lon, node_id: nodeId });
      toast.success(pesanSimpan);
      onSaved?.(r.data?.lokasi_spasial || null);
      onClose?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan lokasi");
    } finally {
      setSibuk(false);
    }
  }, [titik, nodeId, submitUrl, onSaved, onClose, pesanSimpan]);

  const hapus = useCallback(async () => {
    setSibuk(true);
    try {
      await axios.put(submitUrl, { hapus: true });
      toast.success(pesanHapus);
      onSaved?.(null);
      onClose?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus penanda");
    } finally {
      setSibuk(false);
    }
  }, [submitUrl, onSaved, onClose, pesanHapus]);

  const rantai = deteksi?.rantai || [];
  const lantai = deteksi?.lantai || [];
  // Opsi ruangan: hasil deteksi (+alternatif) atau daftar lantai bila titik
  // di koridor. Keduanya bentuk {id, nama}.
  const opsiRuangan = ruangan?.ditemukan
    ? [ruangan.ruangan, ...(ruangan.alternatif || [])].filter(Boolean)
    : (ruangan?.daftar_ruangan || []);
  const nilaiRuangan = opsiRuangan.some((r) => r.id === nodeId) ? nodeId : "";

  return (
    <Dialog open onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent className="max-w-2xl p-0 gap-0" data-testid="lokasi-temuan-dialog">
        {/* pr-10 memberi ruang tombol tutup bawaan dialog — tanpa ini judul/
            deskripsi menabrak ikon × (laporan pemilik: "rapikan judul dan
            tombol close"). */}
        <DialogHeader className="px-4 pt-3 pb-2 pr-10 border-b border-border text-left">
          <DialogTitle className="text-sm flex items-center gap-1.5 min-w-0">
            <MapPin className="w-4 h-4 shrink-0 text-teal-600" />
            <span className="truncate">{judulDialog}</span>
          </DialogTitle>
          <DialogDescription className="text-xs truncate">
            {judul} — {petunjuk}
          </DialogDescription>
        </DialogHeader>

        <div ref={wadahRef} className="h-[42vh] min-h-[260px] w-full" data-testid="lokasi-temuan-peta" />

        <div className="px-4 py-2.5 border-t border-border space-y-1.5 text-xs">
          {!titik && <p className="text-muted-foreground">Belum ada titik — klik lokasinya di peta.</p>}
          {titik && (
            <p className="font-mono text-[11px] text-muted-foreground">
              {titik.lat.toFixed(6)}, {titik.lon.toFixed(6)}
              {mendeteksi && <Loader2 className="inline w-3 h-3 ml-1.5 animate-spin" />}
            </p>
          )}
          {lokasiAwal && (
            <p className="text-muted-foreground" data-testid="lokasi-temuan-tersimpan">
              💾 Tersimpan: {lokasiAwal.jalur_nama
                || "koordinat saja (belum menempel ke denah)"}
            </p>
          )}
          {titik && deteksi && rantai.length > 0 && (
            <p data-testid="lokasi-temuan-rantai">
              📍 {rantai.map((r) => r.nama).filter(Boolean).join(" / ")}
            </p>
          )}
          {titik && deteksi && rantai.length === 0 && (
            <p className="text-amber-700 dark:text-amber-300">{deteksi.pesan || "Di luar kawasan terpetakan."}</p>
          )}
          {titik && !deteksi && !mendeteksi && (
            // Deteksi gagal (jaringan lapangan) — beri pintu coba lagi, jangan
            // biarkan operator menutup-buka dialog hanya untuk mengulang.
            <button type="button" className="text-teal-700 dark:text-teal-300 underline underline-offset-2 min-h-0 min-w-0 inline-flex items-center gap-1"
                    onClick={() => deteksiTitik(titik.lat, titik.lon, true)}
                    data-testid="lokasi-temuan-deteksi-ulang">
              <RotateCcw className="w-3 h-3" />Deteksi ulang
            </button>
          )}
          {lantai.length > 0 && (
            <label className="flex items-center gap-2">
              <span className="text-muted-foreground shrink-0">Persempit ke lantai</span>
              <select value={lantaiAktif}
                      onChange={(e) => {
                        const id = e.target.value;
                        setLantaiAktif(id);
                        setRuangan(null);
                        setNodeId(id || (rantai.length ? rantai[rantai.length - 1].id : ""));
                      }}
                      className="h-8 flex-1 min-w-0 rounded-md border border-border bg-background px-2"
                      data-testid="lokasi-temuan-lantai">
                <option value="">(cukup gedung)</option>
                {lantai.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.nama}{l.status !== "aktif" ? ` (${l.status})` : ""}
                  </option>
                ))}
              </select>
            </label>
          )}
          {lantaiAktif && opsiRuangan.length > 0 && (
            <label className="flex items-center gap-2">
              <span className="text-muted-foreground shrink-0">Persempit ke ruangan</span>
              <select value={nilaiRuangan}
                      onChange={(e) => setNodeId(e.target.value || lantaiAktif)}
                      className="h-8 flex-1 min-w-0 rounded-md border border-border bg-background px-2"
                      data-testid="lokasi-temuan-ruangan">
                <option value="">(cukup lantai)</option>
                {opsiRuangan.map((r) => (
                  <option key={r.id} value={r.id}>{r.nama}</option>
                ))}
              </select>
            </label>
          )}
          {lantaiAktif && ruangan && !ruangan.ditemukan && (
            <p className="text-muted-foreground">{ruangan.pesan}</p>
          )}
        </div>

        <div className="px-4 py-3 border-t border-border flex items-center gap-2">
          {lokasiAwal && (
            <Button variant="outline" size="sm" className="text-red-600" disabled={sibuk}
                    onClick={hapus} data-testid="lokasi-temuan-hapus">
              <Trash2 className="w-3.5 h-3.5 mr-1" />{labelHapus}
            </Button>
          )}
          <div className="flex-1" />
          <Button size="sm" onClick={simpan} disabled={!titik || sibuk || mendeteksi}
                  data-testid="lokasi-temuan-simpan">
            {sibuk ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
                   : <Save className="w-3.5 h-3.5 mr-1" />}
            Simpan Lokasi
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
