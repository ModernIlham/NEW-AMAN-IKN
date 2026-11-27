// Editor GAMBAR kondisi eksisting: titik, garis, area + gaya & label.
// Dimuat LAZY dari dialog Lapisan Eksisting (Leaflet + geoman berat).
//
// Citra eksisting yang aktif selalu tampil di bawah sebagai alas jiplak, jadi
// jalan atau bangunan baru bisa digambar persis di atas fotonya.
import React, { useCallback, useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "@geoman-io/leaflet-geoman-free";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Save, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { pasangPetaDasar } from "@/lib/petaDasar";
import { ambilDaftarCitra, buatPengelolaCitra, lupakanDaftarCitra } from "@/lib/lapisanCitra";
import {
  GAYA_BAWAAN, LABEL_BAWAAN, POSISI_LABEL, batasFitur, buatLabelPeta, buatLayerFitur,
  geometriDariLayer, lengkapiFitur, opsiGaya, tipeDariGeometri,
} from "@/lib/gambarPeta";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const PUSAT_IKN = [-0.966, 116.705];

const TERJEMAHAN = {
  tooltips: {
    placeCircleMarker: "Ketuk untuk menaruh titik",
    firstVertex: "Ketuk untuk titik pertama",
    continueLine: "Ketuk untuk titik berikutnya",
    finishLine: "Ketuk titik terakhir lagi untuk selesai",
    finishPoly: "Ketuk titik pertama untuk menutup area",
  },
  buttonTitles: {
    drawCircleMarkerButton: "Gambar titik",
    drawLineButton: "Gambar garis",
    drawPolyButton: "Gambar area",
    editButton: "Ubah titik sudut",
    dragButton: "Geser objek",
    deleteButton: "Hapus objek",
  },
  actions: { finish: "Selesai", cancel: "Batal", removeLastVertex: "Hapus titik terakhir" },
};

const NAMA_TIPE = { titik: "Titik", garis: "Garis", area: "Area" };
const NAMA_POSISI = { atas: "Atas", kanan: "Kanan", bawah: "Bawah", kiri: "Kiri", ikut: "Ikut garis", tengah: "Di tengah" };

function idBaru() { return Math.random().toString(36).slice(2, 12); }

function Baris({ label, children }) {
  return (
    <label className="flex items-center gap-2 text-xs">
      <span className="w-20 shrink-0 text-muted-foreground">{label}</span>
      <div className="flex-1 min-w-0 flex items-center gap-2">{children}</div>
    </label>
  );
}

function Geser({ nilai, min, max, langkah = 1, onUbah, satuan = "", testid }) {
  return (
    <>
      <input type="range" min={min} max={max} step={langkah} value={nilai}
        onChange={(e) => onUbah(Number(e.target.value))}
        className="flex-1 min-w-0 min-h-0 h-4 accent-teal-600" data-testid={testid} />
      <span className="w-10 text-right tabular-nums">{nilai}{satuan}</span>
    </>
  );
}

function Warna({ nilai, onUbah, testid }) {
  return (
    <input type="color" value={nilai} onChange={(e) => onUbah(e.target.value)}
      className="min-w-0 min-h-0 w-9 h-7 rounded border border-border bg-transparent p-0.5 cursor-pointer"
      data-testid={testid} />
  );
}

/** Panel gaya & label objek terpilih. */
function PanelObjek({ fitur, onUbah, onHapus }) {
  const g = fitur.gaya; const lb = fitur.label;
  const gaya = (k, v) => onUbah({ ...fitur, gaya: { ...g, [k]: v } });
  const label = (k, v) => onUbah({ ...fitur, label: { ...lb, [k]: v } });
  return (
    <div className="space-y-3" data-testid="editor-panel-objek">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">{NAMA_TIPE[fitur.tipe]}</span>
        <Button variant="ghost" size="sm" onClick={onHapus} className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950"
          data-testid="editor-hapus-objek">
          <Trash2 className="w-4 h-4 mr-1" /> Hapus
        </Button>
      </div>
      <div className="space-y-2">
        <Baris label={fitur.tipe === "area" ? "Garis tepi" : "Warna"}>
          <Warna nilai={g.warna} onUbah={(v) => gaya("warna", v)} testid="editor-warna" />
        </Baris>
        {fitur.tipe === "titik"
          ? <Baris label="Ukuran"><Geser nilai={g.ukuran} min={2} max={30} onUbah={(v) => gaya("ukuran", v)} testid="editor-ukuran" /></Baris>
          : <Baris label="Tebal"><Geser nilai={g.tebal} min={0.5} max={20} langkah={0.5} onUbah={(v) => gaya("tebal", v)} testid="editor-tebal" /></Baris>}
        <Baris label="Opasitas">
          <Geser nilai={Math.round(g.opasitas * 100)} min={0} max={100} satuan="%" onUbah={(v) => gaya("opasitas", v / 100)} testid="editor-opasitas" />
        </Baris>
        {fitur.tipe !== "titik" && (
          <Baris label="Putus-putus">
            <input type="checkbox" checked={g.putus} onChange={(e) => gaya("putus", e.target.checked)}
              className="min-w-0 min-h-0 w-4 h-4" data-testid="editor-putus" />
          </Baris>
        )}
        {fitur.tipe === "area" && (
          <>
            <Baris label="Warna isi"><Warna nilai={g.isi_warna} onUbah={(v) => gaya("isi_warna", v)} testid="editor-isi-warna" /></Baris>
            <Baris label="Opasitas isi">
              <Geser nilai={Math.round(g.isi_opasitas * 100)} min={0} max={100} satuan="%" onUbah={(v) => gaya("isi_opasitas", v / 100)} testid="editor-isi-opasitas" />
            </Baris>
          </>
        )}
      </div>
      <div className="border-t border-border pt-3 space-y-2">
        <span className="text-sm font-semibold">Label</span>
        <Input value={lb.teks} onChange={(e) => label("teks", e.target.value.slice(0, 120))}
          placeholder="Mis. Jl. Sumbu Baru" data-testid="editor-label-teks" />
        <Baris label="Warna"><Warna nilai={lb.warna} onUbah={(v) => label("warna", v)} testid="editor-label-warna" /></Baris>
        <Baris label="Ukuran"><Geser nilai={lb.ukuran} min={8} max={40} satuan="px" onUbah={(v) => label("ukuran", v)} testid="editor-label-ukuran" /></Baris>
        <Baris label="Tebal">
          <input type="checkbox" checked={lb.tebal} onChange={(e) => label("tebal", e.target.checked)}
            className="min-w-0 min-h-0 w-4 h-4" data-testid="editor-label-tebal" />
        </Baris>
        <Baris label="Garis tepi">
          <input type="checkbox" checked={!!lb.halo} onChange={(e) => label("halo", e.target.checked ? "#ffffff" : "")}
            className="min-w-0 min-h-0 w-4 h-4" data-testid="editor-label-halo" />
          {lb.halo && <Warna nilai={lb.halo} onUbah={(v) => label("halo", v)} testid="editor-label-halo-warna" />}
        </Baris>
        {POSISI_LABEL[fitur.tipe].length > 1 && (
          <Baris label="Posisi">
            <select value={lb.posisi} onChange={(e) => label("posisi", e.target.value)}
              className="h-8 flex-1 rounded-md border border-input bg-background px-2 text-xs" data-testid="editor-label-posisi">
              {POSISI_LABEL[fitur.tipe].map((p) => <option key={p} value={p}>{NAMA_POSISI[p]}</option>)}
            </select>
          </Baris>
        )}
      </div>
    </div>
  );
}

export default function EditorGambarPeta({ lapisan, onClose, onSaved }) {
  const [wadahEl, setWadahEl] = useState(null);
  const mapRef = useRef(null);
  const grupRef = useRef(null);
  const labelRef = useRef(null);
  const gayaTerakhirRef = useRef({ ...GAYA_BAWAAN });
  const [nama, setNama] = useState(lapisan.nama || "");
  const [zoomLabel, setZoomLabel] = useState(lapisan.label_zoom_min ?? 15);
  const [pilihId, setPilihId] = useState(null);
  const [pilihFitur, setPilihFitur] = useState(null);
  const [jumlah, setJumlah] = useState(lapisan.fitur?.length || 0);
  const [kotor, setKotor] = useState(false);
  const [menyimpan, setMenyimpan] = useState(false);
  const [galat, setGalat] = useState("");
  const { confirm, confirmDialog } = useConfirm();
  // Data awal hanya dipakai sekali saat peta dibuat.
  const awalRef = useRef(lapisan);

  const layerById = useCallback((id) => {
    let hasil = null;
    grupRef.current?.eachLayer((ly) => { if (ly._fitur?.id === id) hasil = ly; });
    return hasil;
  }, []);

  const kumpulkan = useCallback(() => {
    const out = [];
    grupRef.current?.eachLayer((ly) => {
      const geometri = geometriDariLayer(ly);
      if (ly._fitur && geometri) out.push({ ...ly._fitur, geometri });
    });
    return out;
  }, []);

  const segarkanLabel = useCallback(() => {
    labelRef.current?.atur(kumpulkan());
    setJumlah(grupRef.current ? grupRef.current.getLayers().length : 0);
  }, [kumpulkan]);

  const pilih = useCallback((id) => {
    grupRef.current?.eachLayer((ly) => ly.getElement?.()?.classList.toggle("aman-terpilih", ly._fitur?.id === id));
    setPilihId(id);
    const ly = id ? layerById(id) : null;
    setPilihFitur(ly ? { ...ly._fitur } : null);
  }, [layerById]);
  const pilihRef = useRef(pilih);
  pilihRef.current = pilih;

  // ── Init peta + geoman ────────────────────────────────────────────────────
  useEffect(() => {
    if (!wadahEl || mapRef.current) return undefined;
    let map;
    try {
      map = L.map(wadahEl, { zoomControl: true, attributionControl: true, maxZoom: 22 });
      map.attributionControl.setPrefix(false);
      pasangPetaDasar(map);
    } catch (e) {
      setGalat(String(e?.message || e || "Peta gagal dimuat"));
      return undefined;
    }
    // Citra eksisting selalu tampil sebagai alas jiplak.
    const latar = buatPengelolaCitra(map);
    let hidup = true;
    const adaFitur = (awalRef.current.fitur || []).length > 0;
    ambilDaftarCitra({ paksa: true })
      .then((d) => {
        if (!hidup) return;
        const citra = d.filter((l) => l.jenis === "citra");
        latar.atur(citra);
        // Gambar baru: langsung bidik citra teratas agar bisa langsung menjiplak.
        if (!adaFitur && citra.length) {
          const b = citra.reduce((a, l) => ((l.urutan || 0) > (a.urutan || 0) ? l : a)).batas;
          map.fitBounds([[b.selatan, b.barat], [b.utara, b.timur]], { maxZoom: 19 });
        }
      })
      .catch(() => { /* tanpa citra pun editor tetap jalan */ });

    const grup = L.featureGroup().addTo(map);
    grupRef.current = grup;
    const pasangKlik = (ly) => {
      ly.on("click", (e) => { L.DomEvent.stopPropagation(e); pilihRef.current(ly._fitur.id); });
    };
    const awal = awalRef.current;
    for (const f of awal.fitur || []) {
      const ly = buatLayerFitur(f, { interaktif: true });
      pasangKlik(ly);
      grup.addLayer(ly);
    }
    const pane = map.createPane("labelEditor");
    pane.style.zIndex = "650"; pane.style.pointerEvents = "none";
    const rendererLabel = L.svg({ pane: "labelEditor", padding: 0.3 });
    labelRef.current = buatLabelPeta(map, { renderer: rendererLabel, paneLabel: "labelEditor", zoomMin: 0 });
    labelRef.current.atur(awal.fitur || []);

    const bb = batasFitur(awal.fitur);
    if (bb) map.fitBounds(bb, { padding: [30, 30], maxZoom: 19 });
    else map.setView(PUSAT_IKN, 15);
    map.on("click", () => pilihRef.current(null));

    try {
      map.pm.setLang("id_gambar", TERJEMAHAN, "en");
      map.pm.setGlobalOptions({ layerGroup: grup, snappable: true });
      map.pm.addControls({
        position: "topleft",
        drawCircleMarker: true, drawPolyline: true, drawPolygon: true,
        editMode: true, dragMode: true, removalMode: true,
        drawMarker: false, drawRectangle: false, drawCircle: false, drawText: false,
        cutPolygon: false, rotateMode: false,
      });
      map.on("pm:create", (e) => {
        const ly = e.layer;
        const geometri = geometriDariLayer(ly);
        const tipe = tipeDariGeometri(geometri);
        if (!tipe) { grup.removeLayer(ly); return; }
        const f = lengkapiFitur({ id: idBaru(), tipe, geometri, gaya: { ...gayaTerakhirRef.current }, label: { ...LABEL_BAWAAN } });
        ly._fitur = f;
        ly.setStyle?.(opsiGaya(f));
        if (tipe === "titik") ly.setRadius?.(f.gaya.ukuran);
        pasangKlik(ly);
        setKotor(true);
        segarkanLabel();
        pilihRef.current(f.id);
      });
      map.on("pm:remove", (e) => {
        try { grup.removeLayer(e.layer); } catch { /* sudah lepas */ }
        setKotor(true);
        segarkanLabel();
        pilihRef.current(null);
      });
      grup.on("pm:edit pm:dragend", () => { setKotor(true); segarkanLabel(); });
    } catch (e) {
      setGalat(`Alat gambar gagal dimuat: ${String(e?.message || e)}`);
    }

    mapRef.current = map;
    const invalidasi = () => { try { map.invalidateSize(false); } catch { /* dibuang */ } };
    const jam = [80, 300].map((ms) => setTimeout(invalidasi, ms));
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(invalidasi) : null;
    ro?.observe(wadahEl);
    return () => {
      hidup = false;
      jam.forEach(clearTimeout);
      ro?.disconnect();
      try { labelRef.current?.lepas(); } catch { /* abaikan */ }
      map.remove();
      mapRef.current = null; grupRef.current = null; labelRef.current = null;
    };
  }, [wadahEl, segarkanLabel]);

  const ubahPilihan = useCallback((baru) => {
    const ly = layerById(baru.id);
    if (!ly) return;
    const f = lengkapiFitur(baru);
    ly._fitur = f;
    ly.setStyle?.(opsiGaya(f));
    if (f.tipe === "titik") ly.setRadius?.(f.gaya.ukuran);
    gayaTerakhirRef.current = { ...f.gaya };
    setPilihFitur({ ...f });
    setKotor(true);
    segarkanLabel();
  }, [layerById, segarkanLabel]);

  const hapusPilihan = useCallback(() => {
    const ly = pilihId ? layerById(pilihId) : null;
    if (!ly) return;
    grupRef.current.removeLayer(ly);
    setKotor(true);
    segarkanLabel();
    pilih(null);
  }, [pilihId, layerById, segarkanLabel, pilih]);

  const tutup = useCallback(async () => {
    if (kotor) {
      const ok = await confirm({ title: "Tutup tanpa menyimpan?", description: "Perubahan gambar akan hilang.", confirmText: "Tutup", danger: true });
      if (!ok) return;
    }
    onClose?.();
  }, [kotor, confirm, onClose]);

  const simpan = async () => {
    if (!nama.trim()) { toast.error("Nama lapisan wajib diisi"); return; }
    setMenyimpan(true);
    try {
      const r = await axios.put(`${API}/peta-lapisan/${lapisan.id}`, {
        jenis: "gambar", nama: nama.trim(), aktif: lapisan.aktif !== false,
        label_zoom_min: zoomLabel, fitur: kumpulkan(), version: lapisan.version,
      });
      lupakanDaftarCitra();
      toast.success("Gambar disimpan");
      setKotor(false);
      onSaved?.(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan gambar");
    } finally {
      setMenyimpan(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] bg-background flex flex-col" data-testid="editor-gambar">
      {confirmDialog}
      <style>{".aman-terpilih{filter:drop-shadow(0 0 2px #f59e0b) drop-shadow(0 0 4px #f59e0b)}"}</style>
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border">
        <Button variant="ghost" size="icon" onClick={tutup} aria-label="Tutup editor" data-testid="editor-tutup">
          <X className="w-5 h-5" />
        </Button>
        <Input value={nama} onChange={(e) => { setNama(e.target.value); setKotor(true); }}
          className="h-9 max-w-xs font-semibold" aria-label="Nama lapisan" data-testid="editor-nama" />
        <span className="hidden sm:inline text-xs text-muted-foreground tabular-nums">{jumlah} objek</span>
        <label className="hidden md:flex items-center gap-1.5 text-xs text-muted-foreground ml-2">
          Label tampil mulai zoom
          <input type="number" min={0} max={22} value={zoomLabel}
            onChange={(e) => { setZoomLabel(Math.max(0, Math.min(22, Number(e.target.value) || 0))); setKotor(true); }}
            className="w-14 h-8 rounded-md border border-input bg-background px-2 text-xs" data-testid="editor-zoom-label" />
        </label>
        <Button onClick={simpan} disabled={menyimpan || !kotor} className="ml-auto" data-testid="editor-simpan">
          {menyimpan ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Save className="w-4 h-4 mr-1" />} Simpan
        </Button>
      </div>
      {galat && <div className="px-3 py-1.5 text-xs text-red-600 border-b border-border">{galat}</div>}
      <div className="flex-1 min-h-0 flex flex-col md:flex-row">
        <div ref={setWadahEl} className="flex-1 min-h-[45vh] md:min-h-0" data-testid="editor-peta" />
        <aside className="md:w-72 border-t md:border-t-0 md:border-l border-border p-3 overflow-y-auto max-h-[45vh] md:max-h-none">
          {pilihFitur
            ? <PanelObjek fitur={pilihFitur} onUbah={ubahPilihan} onHapus={hapusPilihan} />
            : <p className="text-xs text-muted-foreground leading-relaxed" data-testid="editor-petunjuk">
                Pakai tombol di kiri peta untuk menggambar <b>titik</b>, <b>garis</b>, atau <b>area</b>.
                Ketuk objek untuk mengatur warna, tebal, dan labelnya.
              </p>}
        </aside>
      </div>
    </div>
  );
}
