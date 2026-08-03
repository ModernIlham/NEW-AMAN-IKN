// Penanda LOKASI temuan wasdal di denah (Spasial Fase 8).
//
// Alur: operator mengklik peta → titik tertancap → deteksi Fase 3
// (POST /spasial/lokasi-di-titik) menampilkan rantai wilayah (Kawasan → … →
// Gedung) + pilihan lantai bila titik jatuh di gedung → Simpan mengirim
// {lat, lon, node_id} ke endpoint tiket; SERVER yang men-snapshot nama/jalur
// dari DB (string klien tak dipercaya). Titik di luar kawasan terpetakan
// tetap boleh disimpan sebagai penanda koordinat murni.
import React, { useCallback, useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, MapPin, Save, Trash2, X } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
// Pusat KIPP IKN — pandangan awal saat tiket belum punya penanda.
const PUSAT_IKN = [-1.4025, 116.711];

export default function LokasiTemuanDialog({ judul, submitUrl, lokasiAwal, onClose, onSaved }) {
  const petaRef = useRef(null);
  const wadahRef = useRef(null);
  const markerRef = useRef(null);
  const [titik, setTitik] = useState(() => {
    // Number() + isFinite: titik tersimpan yang korup (string/NaN dari data
    // lama) tak boleh meledakkan .toFixed di render — jatuh ke "belum ada".
    const t = lokasiAwal?.titik;
    const lat = Number(t?.[1]);
    const lon = Number(t?.[0]);
    return Number.isFinite(lat) && Number.isFinite(lon) ? { lat, lon } : null;
  });
  const [deteksi, setDeteksi] = useState(null);   // hasil lokasi-di-titik terakhir
  const [nodeId, setNodeId] = useState(lokasiAwal?.node_id || "");
  const [sibuk, setSibuk] = useState(false);
  const [mendeteksi, setMendeteksi] = useState(false);
  const seqRef = useRef(0);

  const deteksiTitik = useCallback(async (lat, lon) => {
    const seq = ++seqRef.current;
    setMendeteksi(true);
    try {
      const r = await axios.post(`${API}/spasial/lokasi-di-titik`, { lat, lon });
      if (seq !== seqRef.current) return;          // klik lebih baru sudah terjadi
      setDeteksi(r.data);
      // Prapilih node TERDALAM; operator bisa mengganti ke lantai di bawahnya.
      const rantai = r.data?.rantai || [];
      setNodeId(rantai.length ? rantai[rantai.length - 1].id : "");
    } catch {
      if (seq === seqRef.current) {
        setDeteksi(null);
        setNodeId("");
        toast.error("Deteksi lokasi gagal — penanda tetap bisa disimpan");
      }
    } finally {
      if (seq === seqRef.current) setMendeteksi(false);
    }
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
    const latAwal = Number(lokasiAwal?.titik?.[1]);
    const lonAwal = Number(lokasiAwal?.titik?.[0]);
    const adaAwal = Number.isFinite(latAwal) && Number.isFinite(lonAwal);
    map.setView(adaAwal ? [latAwal, lonAwal] : PUSAT_IKN, adaAwal ? 18 : 15);
    if (adaAwal) {
      markerRef.current = L.marker([latAwal, lonAwal]).addTo(map);
    }
    map.on("click", (e) => {
      const { lat, lng } = e.latlng;
      if (markerRef.current) markerRef.current.setLatLng(e.latlng);
      else markerRef.current = L.marker(e.latlng).addTo(map);
      setTitik({ lat, lon: lng });
      deteksiTitik(lat, lng);
    });
    petaRef.current = map;
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
      if (ro) ro.disconnect();
      map.remove(); petaRef.current = null; markerRef.current = null;
    };
    // lokasiAwal hanya dibaca saat init — dialog di-mount ulang per tiket.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deteksiTitik]);

  const simpan = useCallback(async () => {
    if (!titik) return;
    setSibuk(true);
    try {
      const r = await axios.put(submitUrl, { lat: titik.lat, lon: titik.lon, node_id: nodeId });
      toast.success("Lokasi temuan tersimpan");
      onSaved?.(r.data?.lokasi_spasial || null);
      onClose?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan lokasi");
    } finally {
      setSibuk(false);
    }
  }, [titik, nodeId, submitUrl, onSaved, onClose]);

  const hapus = useCallback(async () => {
    setSibuk(true);
    try {
      await axios.put(submitUrl, { hapus: true });
      toast.success("Penanda lokasi dihapus");
      onSaved?.(null);
      onClose?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus penanda");
    } finally {
      setSibuk(false);
    }
  }, [submitUrl, onSaved, onClose]);

  const rantai = deteksi?.rantai || [];
  const lantai = deteksi?.lantai || [];

  return (
    <Dialog open onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent className="max-w-2xl p-0 gap-0 overflow-hidden" data-testid="lokasi-temuan-dialog">
        <DialogHeader className="px-4 pt-3 pb-2 border-b border-border">
          <DialogTitle className="text-sm flex items-center gap-1.5">
            <MapPin className="w-4 h-4 text-teal-600" />Lokasi Temuan
          </DialogTitle>
          <DialogDescription className="text-xs truncate">
            {judul} — klik peta untuk menancapkan titik; wilayah/gedung terdeteksi otomatis.
          </DialogDescription>
        </DialogHeader>

        <div ref={wadahRef} className="h-[42vh] min-h-[260px] w-full" data-testid="lokasi-temuan-peta" />

        <div className="px-4 py-2.5 border-t border-border space-y-1.5 text-xs">
          {!titik && <p className="text-muted-foreground">Belum ada titik — klik lokasi temuan di peta.</p>}
          {titik && (
            <p className="font-mono text-[11px] text-muted-foreground">
              {titik.lat.toFixed(6)}, {titik.lon.toFixed(6)}
              {mendeteksi && <Loader2 className="inline w-3 h-3 ml-1.5 animate-spin" />}
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
          {lantai.length > 0 && (
            <label className="flex items-center gap-2">
              <span className="text-muted-foreground shrink-0">Persempit ke lantai</span>
              <select value={nodeId} onChange={(e) => setNodeId(e.target.value)}
                      className="h-8 flex-1 rounded-md border border-border bg-background px-2"
                      data-testid="lokasi-temuan-lantai">
                <option value={rantai.length ? rantai[rantai.length - 1].id : ""}>
                  (cukup gedung)
                </option>
                {lantai.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.nama}{l.status !== "aktif" ? ` (${l.status})` : ""}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>

        <div className="px-4 py-3 border-t border-border flex flex-wrap items-center gap-2">
          {lokasiAwal && (
            <Button variant="outline" size="sm" className="text-red-600" disabled={sibuk}
                    onClick={hapus} data-testid="lokasi-temuan-hapus">
              <Trash2 className="w-3.5 h-3.5 mr-1" />Hapus Penanda
            </Button>
          )}
          <div className="flex-1" />
          <Button variant="outline" size="sm" onClick={() => onClose?.()} disabled={sibuk}
                  data-testid="lokasi-temuan-batal">
            <X className="w-3.5 h-3.5 mr-1" />Batal
          </Button>
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
