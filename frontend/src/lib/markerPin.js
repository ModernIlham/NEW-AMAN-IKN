import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  Building2, Warehouse, House, Landmark, Monitor, Laptop, Printer, Camera,
  Router, Smartphone, Car, Truck, Bus, Bike, Armchair, Sofa, Archive,
  Package, Boxes, Wrench, Hammer, Plug, Zap, Lightbulb, Trees, Signpost,
  TrafficCone, Droplets,
} from "lucide-react";

// Katalog terkurasi; hanya komponen statis aplikasi, bukan SVG unggahan.
export const IKON_PIN = [
  ["building", "Gedung kantor", "Bangunan", Building2], ["warehouse", "Gudang", "Bangunan", Warehouse],
  ["house", "Rumah", "Bangunan", House], ["landmark", "Bangunan bersejarah", "Bangunan", Landmark],
  ["monitor", "Komputer monitor", "Elektronik", Monitor], ["laptop", "Laptop", "Elektronik", Laptop],
  ["printer", "Printer mesin cetak", "Elektronik", Printer], ["camera", "Kamera CCTV", "Elektronik", Camera],
  ["router", "Router jaringan WiFi", "Elektronik", Router], ["phone", "Telepon ponsel", "Elektronik", Smartphone],
  ["car", "Mobil", "Kendaraan", Car], ["truck", "Truk", "Kendaraan", Truck],
  ["bus", "Bus", "Kendaraan", Bus], ["bike", "Sepeda", "Kendaraan", Bike],
  ["armchair", "Kursi", "Perabot & barang", Armchair], ["sofa", "Sofa", "Perabot & barang", Sofa],
  ["archive", "Lemari arsip", "Perabot & barang", Archive], ["package", "Barang paket", "Perabot & barang", Package],
  ["boxes", "Persediaan kotak", "Perabot & barang", Boxes], ["wrench", "Perkakas servis", "Peralatan & utilitas", Wrench],
  ["hammer", "Palu", "Peralatan & utilitas", Hammer], ["plug", "Stopkontak listrik", "Peralatan & utilitas", Plug],
  ["zap", "Energi genset", "Peralatan & utilitas", Zap], ["lightbulb", "Lampu penerangan", "Peralatan & utilitas", Lightbulb],
  ["trees", "Pohon taman", "Kawasan & jalan", Trees], ["signpost", "Rambu penunjuk jalan", "Kawasan & jalan", Signpost],
  ["cone", "Kerucut lalu lintas", "Kawasan & jalan", TrafficCone], ["droplets", "Air saluran", "Kawasan & jalan", Droplets],
].map(([id, nama, kategori, Icon]) => ({ id, nama, kategori, Icon }));
export const KATEGORI_PIN = [...new Set(IKON_PIN.map((i) => i.kategori))];
const SVG_IKON = Object.fromEntries(IKON_PIN.map(({ id, Icon }) => [id,
  renderToStaticMarkup(React.createElement(Icon, { width: 18, height: 18, strokeWidth: 2, "aria-hidden": true })),
]));
export const PIN_BAWAAN = { v: 1, mode: "icon", icon: "package", text: "A", image: "",
  circle: true, circleColor: "#ffffff", strokeColor: "#334155", strokeWidth: 1, iconColor: "#0f172a" };
const warna = (v, fallback) => /^#[0-9a-f]{6}$/i.test(v || "") ? v : fallback;
const gambarAman = (v) => typeof v === "string" && v.length <= 13358 && /^data:image\/png;base64,[A-Za-z0-9+/]+={0,2}$/.test(v);

export function bacaMarkerPin(value) {
  try {
    if (!value || typeof value !== "string" || value.length > 14000) return null;
    const r = JSON.parse(value);
    if (!r || r.v !== 1 || !["icon", "text", "custom"].includes(r.mode)) return null;
    if (r.mode === "custom" && !gambarAman(r.image)) return null;
    return { ...PIN_BAWAAN, mode: r.mode, icon: Object.prototype.hasOwnProperty.call(SVG_IKON, r.icon) ? r.icon : "package",
      text: /^[A-Za-z0-9]{1,3}$/.test(r.text || "") ? r.text : "A", image: r.mode === "custom" ? r.image : "",
      circle: r.circle !== false, circleColor: warna(r.circleColor, PIN_BAWAAN.circleColor),
      strokeColor: warna(r.strokeColor, PIN_BAWAAN.strokeColor), iconColor: warna(r.iconColor, PIN_BAWAAN.iconColor),
      strokeWidth: [0, 1, 2, 3].includes(r.strokeWidth) ? r.strokeWidth : 1 };
  } catch { return null; }
}

export function cariIkonPin(query, kategori = "Semua") {
  const terms = String(query || "").trim().toLocaleLowerCase("id-ID").split(/\s+/).filter(Boolean);
  return IKON_PIN.filter((i) => (kategori === "Semua" || i.kategori === kategori)
    && terms.every((t) => `${i.nama} ${i.kategori} ${i.id}`.toLocaleLowerCase("id-ID").includes(t)));
}

// Mengembalikan opsi divIcon, dipakai peta internal, publik, dan pratinjau.
// Seluruh interpolasi berasal dari allowlist di atas, bukan HTML/URL pengguna.
export function opsiPinDesain(value, { color = "#64748b", selected = false, complete = false, hasPhoto = false, badge = 0 } = {}) {
  const d = bacaMarkerPin(value);
  if (!d) return null;
  const isi = d.mode === "custom" ? `<img src="${d.image}" alt="" style="width:18px;height:18px;object-fit:contain"/>`
    : d.mode === "text" ? `<span style="font:800 ${d.text.length > 2 ? 10 : 13}px/1 system-ui,sans-serif">${d.text}</span>` : SVG_IKON[d.icon];
  const ring = selected ? "#f59e0b" : complete ? "#16a34a" : "#ffffff";
  const count = Number.isFinite(Number(badge)) ? Math.max(0, Math.min(99, Math.floor(Number(badge)))) : 0;
  // Leaflet memberi SEMUA svg di map-pane z-index:200. Lapisan lokal harus
  // eksplisit; bila tidak, badan pin menutupi huruf, lingkaran, dan gambar.
  return { className: "aman-pin-desain", iconSize: [36, 44], iconAnchor: [18, 44], popupAnchor: [0, -40],
    html: `<div style="position:relative;width:36px;height:44px;filter:drop-shadow(0 1px 2px #0006)">
      <svg width="36" height="44" viewBox="0 0 36 44" style="position:absolute;inset:0;overflow:visible;z-index:0"><path d="M18 1C8.6 1 1 8.6 1 18c0 11 17 25 17 25s17-14 17-25C35 8.6 27.4 1 18 1Z" fill="${warna(color, "#64748b")}" stroke="${ring}" stroke-width="${selected ? 3 : 2}"/></svg>
      <div style="position:absolute;z-index:1;left:6px;top:6px;width:24px;height:24px;box-sizing:border-box;border-radius:50%;display:flex;align-items:center;justify-content:center;color:${d.iconColor};background:${d.circle ? d.circleColor : "transparent"};border:${d.strokeWidth}px solid ${d.strokeColor}">${isi}</div>
      ${selected ? '<span style="position:absolute;z-index:2;left:-5px;bottom:1px;border-radius:50%;background:#f59e0b;color:#fff;border:1px solid #fff;font:700 12px/16px system-ui;width:16px;text-align:center">✓</span>' : ""}
      ${count || hasPhoto ? `<span style="position:absolute;z-index:2;right:-5px;top:-5px;border-radius:8px;background:#0f172a;color:#fff;border:1px solid #fff;padding:1px 3px;font:700 9px/12px system-ui">${count ? (count > 9 ? "9+" : count) : "▣"}</span>` : ""}
    </div>` };
}

export async function siapkanIkonPin(file) {
  if (!file || !["image/png", "image/jpeg", "image/webp"].includes(file.type)) throw new Error("Pilih gambar PNG, JPEG, atau WebP (bukan SVG/GIF).");
  if (file.size > 2 * 1024 * 1024) throw new Error("Ukuran ikon maksimal 2 MB.");
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise((resolve, reject) => {
      const el = new Image(); el.onload = () => resolve(el); el.onerror = () => reject(new Error("Gambar ikon tidak dapat dibaca.")); el.src = url;
    });
    if (!img.naturalWidth || !img.naturalHeight || img.naturalWidth > 4096 || img.naturalHeight > 4096) throw new Error("Dimensi ikon maksimal 4096×4096 piksel.");
    const canvas = document.createElement("canvas"); canvas.width = 64; canvas.height = 64;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Peramban tidak dapat menyiapkan ikon.");
    const skala = 56 / Math.max(img.naturalWidth, img.naturalHeight);
    const w = img.naturalWidth * skala, h = img.naturalHeight * skala;
    ctx.drawImage(img, (64 - w) / 2, (64 - h) / 2, w, h);
    const data = canvas.toDataURL("image/png");
    if (!gambarAman(data)) throw new Error("Ikon terlalu rinci. Pilih gambar/logo sederhana (hasil maksimal 10 KB).");
    return data;
  } finally { URL.revokeObjectURL(url); }
}
