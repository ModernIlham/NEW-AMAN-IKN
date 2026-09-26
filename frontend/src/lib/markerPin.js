import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  Building2, Warehouse, House, Landmark, Monitor, Laptop, Printer, Camera,
  Router, Smartphone, Car, Truck, Bus, Bike, Armchair, Sofa, Archive,
  Package, Boxes, Wrench, Hammer, Plug, Zap, Lightbulb, Trees, Signpost,
  TrafficCone, Droplets,
  Hospital, School, University, Hotel, Store, Church, Factory, Tent,
  DoorOpen, Fence, Tablet, Keyboard, Mouse, Cpu, HardDrive, Server,
  Database, Wifi, Network, Usb, Cable, Battery, BatteryCharging, CircuitBoard,
  MemoryStick, Scan, Barcode, QrCode, Ship, Sailboat, Plane, TrainFront,
  TramFront, Ambulance, Forklift, Tractor, Construction, Container, BedDouble, Table2,
  LampDesk, LampFloor, LampCeiling, RockingChair, Blinds, BriefcaseBusiness, Drill, Nut,
  Bolt, Cog, Gauge, Weight, Power, Paintbrush, PaintRoller, Axe,
  Pickaxe, Ruler, Fuel, SquareParking, Milestone, Route, Map, MapPinned,
  Compass, Navigation, Dam, Waves, Mountain, Trash2, Recycle, Bath,
  ShowerHead, Refrigerator, WashingMachine, Microwave, CookingPot, Utensils, Coffee, CupSoda,
  AirVent, Fan, Heater, Tv, Radio, Speaker, Headphones, Mic,
  Video, Webcam, Projector, Music, Piano, Guitar, Film, Satellite,
  RadioTower, Antenna, KeyRound, Lock, Shield, Siren, FireExtinguisher, Cctv,
  ScanFace, Fingerprint, Bell, Flashlight, CircleAlert, LifeBuoy, Stethoscope, HeartPulse,
  Cross, Pill, Syringe, Microscope, TestTube, FlaskConical, Dna, Thermometer,
  Accessibility, FileText, Files, FolderOpen, ClipboardList, BookOpen, LibraryBig, NotebookPen,
  PenTool, Pencil, Calculator, CalendarDays, Mail, Inbox, Stamp, Scale,
  Gavel, Presentation, Sprout, Flower2, Leaf, TreePine, Shovel, Wheat,
  Fish, Bird, Rabbit, Dumbbell, Volleyball, Goal, Medal, Trophy,
  Timer, Binoculars, Backpack, Umbrella, Telescope,
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
  ["hospital", "Rumah sakit klinik", "Bangunan", Hospital],
  ["school", "Sekolah", "Bangunan", School],
  ["university", "Universitas kampus", "Bangunan", University],
  ["hotel", "Hotel penginapan", "Bangunan", Hotel],
  ["store", "Toko kios", "Bangunan", Store],
  ["church", "Tempat ibadah", "Bangunan", Church],
  ["factory", "Pabrik industri", "Bangunan", Factory],
  ["tent", "Tenda pos", "Bangunan", Tent],
  ["door", "Pintu masuk", "Bangunan", DoorOpen],
  ["fence", "Pagar pembatas", "Bangunan", Fence],
  ["tablet", "Tablet", "Elektronik", Tablet],
  ["keyboard", "Papan ketik keyboard", "Elektronik", Keyboard],
  ["mouse", "Mouse komputer", "Elektronik", Mouse],
  ["cpu", "Prosesor CPU", "Elektronik", Cpu],
  ["harddrive", "Penyimpanan hard disk", "Elektronik", HardDrive],
  ["server", "Server", "Elektronik", Server],
  ["database", "Basis data", "Elektronik", Database],
  ["wifi", "WiFi nirkabel", "Elektronik", Wifi],
  ["network", "Jaringan komputer", "Elektronik", Network],
  ["usb", "USB flashdisk", "Elektronik", Usb],
  ["cable", "Kabel data", "Elektronik", Cable],
  ["battery", "Baterai", "Elektronik", Battery],
  ["charging", "Pengisi daya baterai", "Elektronik", BatteryCharging],
  ["circuit", "Papan sirkuit", "Elektronik", CircuitBoard],
  ["memory", "Memori RAM", "Elektronik", MemoryStick],
  ["scanner", "Pemindai scanner", "Elektronik", Scan],
  ["barcode", "Barcode", "Elektronik", Barcode],
  ["qrcode", "Kode QR", "Elektronik", QrCode],
  ["ship", "Kapal", "Kendaraan", Ship],
  ["sailboat", "Perahu layar", "Kendaraan", Sailboat],
  ["plane", "Pesawat", "Kendaraan", Plane],
  ["train", "Kereta api", "Kendaraan", TrainFront],
  ["tram", "Trem", "Kendaraan", TramFront],
  ["ambulance", "Ambulans", "Kendaraan", Ambulance],
  ["forklift", "Forklift", "Kendaraan", Forklift],
  ["tractor", "Traktor", "Kendaraan", Tractor],
  ["construction", "Alat konstruksi berat", "Kendaraan", Construction],
  ["container", "Kontainer", "Kendaraan", Container],
  ["bed", "Tempat tidur", "Perabot & barang", BedDouble],
  ["table", "Meja kerja", "Perabot & barang", Table2],
  ["desk", "Lampu meja", "Perabot & barang", LampDesk],
  ["floorlamp", "Lampu lantai", "Perabot & barang", LampFloor],
  ["ceilinglamp", "Lampu plafon", "Perabot & barang", LampCeiling],
  ["rockingchair", "Kursi goyang", "Perabot & barang", RockingChair],
  ["blinds", "Tirai jendela", "Perabot & barang", Blinds],
  ["briefcase", "Tas kantor koper", "Perabot & barang", BriefcaseBusiness],
  ["drill", "Bor listrik", "Peralatan & utilitas", Drill],
  ["nut", "Mur", "Peralatan & utilitas", Nut],
  ["bolt", "Baut", "Peralatan & utilitas", Bolt],
  ["cog", "Roda gigi mesin", "Peralatan & utilitas", Cog],
  ["gauge", "Alat ukur tekanan", "Peralatan & utilitas", Gauge],
  ["weight", "Timbangan beban", "Peralatan & utilitas", Weight],
  ["power", "Sakelar daya", "Peralatan & utilitas", Power],
  ["paintbrush", "Kuas cat", "Peralatan & utilitas", Paintbrush],
  ["paintroller", "Rol pengecatan", "Peralatan & utilitas", PaintRoller],
  ["axe", "Kapak", "Peralatan & utilitas", Axe],
  ["pickaxe", "Beliung", "Peralatan & utilitas", Pickaxe],
  ["ruler", "Penggaris meteran", "Peralatan & utilitas", Ruler],
  ["fuel", "Pompa bahan bakar", "Peralatan & utilitas", Fuel],
  ["parking", "Parkir kendaraan", "Kawasan & jalan", SquareParking],
  ["milestone", "Patok kilometer", "Kawasan & jalan", Milestone],
  ["route", "Jalur rute", "Kawasan & jalan", Route],
  ["map", "Peta kawasan", "Kawasan & jalan", Map],
  ["mappin", "Titik lokasi", "Kawasan & jalan", MapPinned],
  ["compass", "Kompas", "Kawasan & jalan", Compass],
  ["navigation", "Arah navigasi", "Kawasan & jalan", Navigation],
  ["dam", "Bendungan", "Kawasan & jalan", Dam],
  ["waves", "Sungai laut perairan", "Kawasan & jalan", Waves],
  ["mountain", "Gunung perbukitan", "Kawasan & jalan", Mountain],
  ["trash", "Tempat sampah", "Kawasan & jalan", Trash2],
  ["recycle", "Daur ulang", "Kawasan & jalan", Recycle],
  ["bath", "Bak mandi", "Rumah tangga", Bath],
  ["shower", "Pancuran kamar mandi", "Rumah tangga", ShowerHead],
  ["fridge", "Kulkas", "Rumah tangga", Refrigerator],
  ["washer", "Mesin cuci", "Rumah tangga", WashingMachine],
  ["microwave", "Microwave pemanas makanan", "Rumah tangga", Microwave],
  ["cookingpot", "Panci memasak", "Rumah tangga", CookingPot],
  ["utensils", "Alat makan", "Rumah tangga", Utensils],
  ["coffee", "Mesin kopi cangkir", "Rumah tangga", Coffee],
  ["cup", "Gelas minum", "Rumah tangga", CupSoda],
  ["ac", "AC pendingin udara", "Rumah tangga", AirVent],
  ["fan", "Kipas angin", "Rumah tangga", Fan],
  ["heater", "Pemanas ruangan", "Rumah tangga", Heater],
  ["tv", "Televisi TV", "Komunikasi & multimedia", Tv],
  ["radio", "Radio", "Komunikasi & multimedia", Radio],
  ["speaker", "Pengeras suara speaker", "Komunikasi & multimedia", Speaker],
  ["headphones", "Headphone headset", "Komunikasi & multimedia", Headphones],
  ["microphone", "Mikrofon", "Komunikasi & multimedia", Mic],
  ["video", "Kamera video", "Komunikasi & multimedia", Video],
  ["webcam", "Webcam", "Komunikasi & multimedia", Webcam],
  ["projector", "Proyektor", "Komunikasi & multimedia", Projector],
  ["music", "Audio musik", "Komunikasi & multimedia", Music],
  ["piano", "Piano", "Komunikasi & multimedia", Piano],
  ["guitar", "Gitar", "Komunikasi & multimedia", Guitar],
  ["film", "Film rekaman", "Komunikasi & multimedia", Film],
  ["satellite", "Satelit", "Komunikasi & multimedia", Satellite],
  ["radiotower", "Menara radio BTS", "Komunikasi & multimedia", RadioTower],
  ["antenna", "Antena", "Komunikasi & multimedia", Antenna],
  ["key", "Kunci", "Keamanan", KeyRound],
  ["lock", "Gembok", "Keamanan", Lock],
  ["shield", "Perisai keamanan", "Keamanan", Shield],
  ["siren", "Sirene alarm", "Keamanan", Siren],
  ["extinguisher", "APAR pemadam api", "Keamanan", FireExtinguisher],
  ["cctv", "Kamera pengawas CCTV", "Keamanan", Cctv],
  ["facescan", "Pemindai wajah", "Keamanan", ScanFace],
  ["fingerprint", "Pemindai sidik jari", "Keamanan", Fingerprint],
  ["bell", "Bel", "Keamanan", Bell],
  ["flashlight", "Senter", "Keamanan", Flashlight],
  ["alert", "Peringatan bahaya", "Keamanan", CircleAlert],
  ["lifebuoy", "Pelampung keselamatan", "Keamanan", LifeBuoy],
  ["stethoscope", "Stetoskop", "Kesehatan & laboratorium", Stethoscope],
  ["heart", "Monitor denyut jantung", "Kesehatan & laboratorium", HeartPulse],
  ["cross", "Perlengkapan medis P3K", "Kesehatan & laboratorium", Cross],
  ["pill", "Obat kapsul", "Kesehatan & laboratorium", Pill],
  ["syringe", "Alat suntik", "Kesehatan & laboratorium", Syringe],
  ["microscope", "Mikroskop", "Kesehatan & laboratorium", Microscope],
  ["testtube", "Tabung reaksi", "Kesehatan & laboratorium", TestTube],
  ["flask", "Labu laboratorium", "Kesehatan & laboratorium", FlaskConical],
  ["dna", "Analisis DNA", "Kesehatan & laboratorium", Dna],
  ["thermometer", "Termometer suhu", "Kesehatan & laboratorium", Thermometer],
  ["accessibility", "Akses disabilitas", "Kesehatan & laboratorium", Accessibility],
  ["document", "Dokumen surat", "Dokumen & administrasi", FileText],
  ["files", "Berkas dokumen", "Dokumen & administrasi", Files],
  ["folder", "Map folder", "Dokumen & administrasi", FolderOpen],
  ["clipboard", "Papan daftar periksa", "Dokumen & administrasi", ClipboardList],
  ["book", "Buku", "Dokumen & administrasi", BookOpen],
  ["library", "Perpustakaan", "Dokumen & administrasi", LibraryBig],
  ["notebook", "Buku catatan", "Dokumen & administrasi", NotebookPen],
  ["pen", "Pena", "Dokumen & administrasi", PenTool],
  ["pencil", "Pensil", "Dokumen & administrasi", Pencil],
  ["calculator", "Kalkulator", "Dokumen & administrasi", Calculator],
  ["calendar", "Kalender", "Dokumen & administrasi", CalendarDays],
  ["mail", "Surat pos", "Dokumen & administrasi", Mail],
  ["inbox", "Kotak surat", "Dokumen & administrasi", Inbox],
  ["stamp", "Stempel", "Dokumen & administrasi", Stamp],
  ["scale", "Neraca timbangan", "Dokumen & administrasi", Scale],
  ["gavel", "Palu sidang", "Dokumen & administrasi", Gavel],
  ["presentation", "Papan presentasi", "Dokumen & administrasi", Presentation],
  ["sprout", "Bibit tanaman", "Pertanian & alam", Sprout],
  ["flower", "Bunga", "Pertanian & alam", Flower2],
  ["leaf", "Daun vegetasi", "Pertanian & alam", Leaf],
  ["pine", "Pohon pinus", "Pertanian & alam", TreePine],
  ["shovel", "Sekop", "Pertanian & alam", Shovel],
  ["wheat", "Padi gandum", "Pertanian & alam", Wheat],
  ["fish", "Ikan", "Pertanian & alam", Fish],
  ["bird", "Burung", "Pertanian & alam", Bird],
  ["rabbit", "Kelinci", "Pertanian & alam", Rabbit],
  ["dumbbell", "Alat olahraga beban", "Olahraga & lapangan", Dumbbell],
  ["volleyball", "Bola voli", "Olahraga & lapangan", Volleyball],
  ["goal", "Gawang", "Olahraga & lapangan", Goal],
  ["medal", "Medali", "Olahraga & lapangan", Medal],
  ["trophy", "Piala", "Olahraga & lapangan", Trophy],
  ["timer", "Stopwatch pengukur waktu", "Olahraga & lapangan", Timer],
  ["binoculars", "Teropong", "Olahraga & lapangan", Binoculars],
  ["backpack", "Ransel", "Olahraga & lapangan", Backpack],
  ["umbrella", "Payung", "Olahraga & lapangan", Umbrella],
  ["telescope", "Teleskop", "Olahraga & lapangan", Telescope],
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
      ${hasPhoto ? `<span data-marker-badge="photo" style="position:absolute;z-index:2;top:-4px;right:-4px;width:14px;height:14px;box-sizing:border-box;border-radius:50%;background:#0f172a;border:1.5px solid #fff;display:flex;align-items:center;justify-content:center">
        <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" aria-hidden="true"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
      </span>` : ""}
      ${count ? `<span data-marker-badge="comment" style="position:absolute;z-index:2;${hasPhoto ? "left:-6px" : "right:-5px"};top:-5px;border-radius:8px;background:#2563eb;color:#fff;border:1.5px solid #fff;padding:1px 3px;font:700 9px/12px system-ui;display:flex;align-items:center;gap:1px">
        <svg width="7" height="7" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>${count > 9 ? "9+" : count}</span>` : ""}
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
