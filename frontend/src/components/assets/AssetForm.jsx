import React, { memo, useState, useCallback, useRef, useEffect, useMemo, startTransition } from "react";
import { createPortal } from "react-dom";
import {
  Plus, Edit3, X, Camera, Trash2, Check, ChevronDown, Search,
  Package, Briefcase, ShieldCheck, Settings, Tag, Save, Loader2, ClipboardList,
  Info, ChevronRight, BookOpen, Wrench, ArrowRight, HelpCircle, MapPin, LocateFixed,
  ChevronLeft, CloudOff, Upload, Eye, UserRound, AlertTriangle, History, IdCard,
} from "lucide-react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { ScrollArea } from "../ui/scroll-area";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../ui/select";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { DocumentChecklist, DEFAULT_DOC_ITEMS } from "./DocumentChecklist";
import InventoryFieldSheet, { PENGGUNA_MELEKAT_OPTIONS, PENGGUNA_NAME_LABELS, OPERASIONAL_JENIS_OPTIONS, CONDITION_OPTIONS } from "./InventoryFieldSheet";
import FullCameraSheet from "./FullCameraSheet";
import KartuTapDialog from "../pegawai/KartuTapDialog";
import { useBackGuard } from "../../hooks/useBackGuard";
import { toast } from "sonner";
import axios from "axios";
import { getApiError } from "../../lib/utils";
import { authMediaUrl } from "../../lib/mediaUrl";
import { acquireAccuratePosition } from "../../lib/geolocation";
import { lebihAkurat } from "../../lib/gpsAkurasi";
import { bolehSalinKoordinat } from "../../lib/salinKonteks";
import { compressImageFile, compressDataUrl, generateThumbnailFromDataUrl, dataUrlBytes } from "../../lib/imageCompression";
import { reserveDummyNup as reserveDummyNupLib } from "../../lib/dummyNup";
import { statusInventarisasiOtomatis, autoInventarisasiEnabled } from "../../lib/inventoryStatus";

// ============================================================================
// INVENTORY CLASSIFICATION INFO DATA (SE 17/SE/M/2024)
// ============================================================================
const KLASIFIKASI_INFO = {
  "Kesalahan Pencatatan": {
    icon: "📝",
    maksud: "BMN yang tidak ditemukan karena adanya kesalahan dalam proses pencatatan/administrasi, BUKAN karena BMN tersebut hilang secara fisik.",
    penanganan: "Lakukan koreksi data pada aplikasi SIMAK-BMN sesuai jenis kesalahan yang ditemukan. Buat Surat Pernyataan Koreksi Pencatatan.",
  },
  "Tidak Ditemukan Lainnya": {
    icon: "🔍",
    maksud: "BMN yang secara fisik memang tidak dapat ditemukan atau tidak dapat diidentifikasi keberadaannya, bukan karena kesalahan pencatatan.",
    penanganan: "Lakukan penelusuran mendalam. Jika tetap tidak ditemukan, siapkan Berita Acara dan SPTJM untuk proses penghapusan BMN.",
  }
};

const BERLEBIH_SENGKETA_INFO = {
  "Berlebih": {
    icon: "📦",
    color: "purple",
    maksud: "BMN yang ditemukan secara fisik saat inventarisasi tetapi tidak tercatat dalam Daftar BMN/SIMAK-BMN, atau tercatat tidak sesuai golongan/kodefikasi, atau melebihi Standar Barang dan Standar Kebutuhan (SBSK).",
    contoh: [
      "BMN tidak tercatat dalam SIMAK-BMN (ditemukan di gudang tanpa catatan)",
      "BMN dari satker lain yang dipindahkan tanpa proses administrasi formal",
      "Barang dari hibah/sumbangan yang belum dicatatkan",
      "Jumlah barang fisik lebih banyak dari catatan pembukuan"
    ],
    penanganan: "Catat dalam Kertas Kerja Inventarisasi dengan nilai wajar. Input ke SIMAK-BMN sebagai temuan berlebih. Verifikasi asal-usul perolehan BMN.",
    tindak_lanjut: [
      "Jika sah: Daftarkan ke dalam Daftar BMN",
      "Jika dari satker lain: Proses serah terima resmi",
      "Jika melebihi SBSK: Pemindahtanganan (jual/hibah/tukar menukar)",
      "Laporkan ke KPKNL/DJKN untuk penertiban"
    ]
  },
  "Sengketa": {
    icon: "⚖️",
    color: "rose",
    maksud: "BMN yang sedang dalam perselisihan hukum mengenai status kepemilikan, penguasaan, atau keberadaannya, biasanya melibatkan pihak ketiga atau putusan pengadilan.",
    contoh: [
      "Tanah/bangunan milik negara yang digugat oleh pihak lain di pengadilan",
      "BMN yang diklaim oleh lebih dari satu instansi",
      "Sertifikat tanah BMN tumpang tindih dengan sertifikat pihak swasta",
      "BMN yang disita/diblokir terkait perkara hukum"
    ],
    penanganan: "Teliti berkas perkara pengadilan terkait BMN. Catat status sengketa beserta nomor perkara dan pihak bersengketa. Pisahkan dari kategori barang lainnya.",
    tindak_lanjut: [
      "Koordinasi dengan bagian hukum instansi",
      "Pantau perkembangan putusan pengadilan",
      "Jika putusan inkracht: Tindak lanjut sesuai putusan",
      "Laporkan ke DJKN untuk penanganan lebih lanjut"
    ]
  }
};

const SUB_KLASIFIKASI_INFO = {
  "Kesalahan Kodefikasi": {
    maksud: "BMN tercatat dengan kode barang yang tidak sesuai dengan jenis/spesifikasi barang sebenarnya. Misalnya kode untuk Laptop tapi sebenarnya adalah Printer.",
    contoh: "Kode barang 3.05.01.05.007 (Meja Kerja) seharusnya 3.05.01.05.003 (Meja Rapat), karena salah input saat pencatatan awal.",
    penanganan: "Lakukan koreksi kode barang pada SIMAK-BMN. Ubah kode barang ke kode yang benar sesuai klasifikasi BMN.",
    alur: "1. Identifikasi kode yang salah → 2. Tentukan kode yang benar → 3. Buat Surat Koreksi Pencatatan → 4. Input perubahan di SIMAK-BMN → 5. Verifikasi hasil koreksi"
  },
  "Pencatatan Ganda": {
    maksud: "BMN yang sama tercatat lebih dari satu kali dalam SIMAK-BMN, sehingga muncul NUP ganda untuk satu barang fisik yang sama.",
    contoh: "1 unit AC tercatat 2 kali dengan NUP berbeda karena diinput ulang saat mutasi antar ruangan.",
    penanganan: "Hapus/koreksi NUP yang duplikat dan pertahankan satu NUP yang valid. Pastikan jumlah fisik sesuai dengan jumlah pencatatan.",
    alur: "1. Identifikasi NUP ganda → 2. Tentukan NUP yang valid → 3. Buat Surat Koreksi → 4. Hapus NUP duplikat di SIMAK-BMN → 5. Rekonsiliasi data"
  },
  "BMN Tercatat di Satker Lain": {
    maksud: "BMN secara fisik ada di satker ini, namun pencatatannya berada di satker lain, atau sebaliknya — tercatat di satker ini tapi fisiknya ada di satker lain.",
    contoh: "Kendaraan dinas tercatat di Satker A namun sudah dipinjampakaikan ke Satker B sejak 3 tahun lalu tanpa proses transfer.",
    penanganan: "Koordinasi dengan satker terkait untuk proses transfer BMN atau pengembalian BMN ke satker yang tercatat.",
    alur: "1. Identifikasi satker pemegang fisik → 2. Koordinasi antar satker → 3. Proses transfer/hibah/mutasi → 4. Update pencatatan di kedua satker → 5. Verifikasi"
  },
  "Kegiatan Perencanaan/Pengembangan Dicatat Sebagai BMN Tersendiri": {
    maksud: "Biaya perencanaan, konsultansi, atau pengembangan yang seharusnya menjadi bagian dari nilai perolehan aset utama (dikapitalisasi), namun tercatat sebagai BMN tersendiri.",
    contoh: "Biaya konsultan perencanaan gedung Rp 500 juta tercatat sebagai BMN tersendiri, padahal seharusnya menambah nilai gedung yang dibangun.",
    penanganan: "Lakukan penggabungan nilai ke aset utama (kapitalisasi). Hapus pencatatan BMN tersendiri dan tambahkan nilainya ke BMN induk.",
    alur: "1. Identifikasi BMN perencanaan/pengembangan → 2. Tentukan aset induk yang sesuai → 3. Kapitalisasi nilai → 4. Hapus NUP tersendiri → 5. Update nilai aset induk di SIMAK-BMN"
  },
  "BMN Objek Alih Status/Pemindahtanganan/Penghapusan": {
    maksud: "BMN yang sudah melalui proses alih status, pemindahtanganan (hibah/jual), atau penghapusan, tetapi masih tercatat aktif dalam SIMAK-BMN.",
    contoh: "Kendaraan yang sudah dihibahkan ke Pemda tahun lalu tapi belum dihapus dari pencatatan SIMAK-BMN Kementerian.",
    penanganan: "Proses penghapusan pencatatan sesuai dokumen pendukung (SK Penghapusan, Berita Acara Hibah, dll) yang sudah ada.",
    alur: "1. Kumpulkan dokumen pendukung → 2. Verifikasi kelengkapan dokumen → 3. Proses penghapusan di SIMAK-BMN → 4. Arsipkan dokumen → 5. Laporan penghapusan"
  },
  "Penggabungan BMN Satu Kesatuan Fungsi": {
    maksud: "Beberapa BMN yang seharusnya dicatat sebagai satu kesatuan fungsi (satu unit), namun tercatat terpisah-pisah sebagai BMN individu.",
    contoh: "Komputer, monitor, keyboard, dan mouse yang merupakan 1 unit PC workstation tercatat sebagai 4 NUP terpisah.",
    penanganan: "Gabungkan BMN-BMN tersebut menjadi satu NUP sebagai satu kesatuan fungsi. Hapus NUP terpisah yang tidak diperlukan.",
    alur: "1. Identifikasi BMN yang satu kesatuan → 2. Tentukan NUP utama → 3. Gabungkan nilai → 4. Buat Surat Koreksi → 5. Hapus NUP komponen di SIMAK-BMN"
  },
  "Kesalahan Pencatatan Pihak Ketiga": {
    maksud: "Kesalahan pencatatan yang dilakukan oleh pihak ketiga (kontraktor, vendor, konsultan) saat proses input data BMN awal.",
    contoh: "Kontraktor salah menginput spesifikasi dan kuantitas barang pada saat serah terima pekerjaan pengadaan.",
    penanganan: "Koordinasi dengan pihak ketiga untuk klarifikasi data. Lakukan koreksi berdasarkan dokumen kontrak dan BAST yang benar.",
    alur: "1. Identifikasi kesalahan → 2. Klarifikasi dengan pihak ketiga → 3. Kumpulkan dokumen pendukung → 4. Buat Surat Koreksi → 5. Perbaiki data di SIMAK-BMN"
  },
  "Tidak Ditemukan Fisiknya": {
    maksud: "BMN yang secara fisik benar-benar tidak ada/hilang di lokasi yang tercatat maupun di lokasi lain dalam lingkup satker.",
    contoh: "Laptop inventaris yang tidak ditemukan di ruangan manapun, dan tidak ada catatan peminjaman atau pemindahan.",
    penanganan: "Buat kronologis hilangnya BMN, laporkan ke atasan, dan siapkan dokumen untuk proses Tuntutan Ganti Rugi (TGR) jika diperlukan.",
    alur: "1. Penelusuran menyeluruh di semua lokasi → 2. Buat kronologis → 3. Lapor ke pimpinan → 4. Proses SPTJM → 5. Proses TGR/Penghapusan sesuai ketentuan"
  },
  "Tidak Dapat Ditelusuri": {
    maksud: "BMN yang tidak dapat dilacak keberadaan maupun informasinya karena keterbatasan data, pergantian pejabat, atau catatan yang tidak lengkap.",
    contoh: "BMN dari pengadaan tahun 2005 yang tidak ada lagi pejabat/pegawai yang mengetahui keberadaannya dan dokumen pendukungnya hilang.",
    penanganan: "Lakukan upaya penelusuran maksimal. Jika tetap tidak ditemukan, siapkan Berita Acara penelusuran dan dokumen pendukung untuk penghapusan.",
    alur: "1. Upaya penelusuran mendalam → 2. Wawancara pegawai/mantan pejabat → 3. Buat Berita Acara → 4. Proses SPTJM → 5. Ajukan penghapusan BMN"
  },
  "Tertimpa Bangunan Lain/Beralih Fungsi": {
    maksud: "BMN (biasanya tanah/bangunan) yang tertimpa oleh pembangunan baru atau telah beralih fungsi sehingga tidak dapat diidentifikasi sebagai BMN awal.",
    contoh: "Bangunan gudang lama yang sudah dibongkar dan di atasnya dibangun gedung baru, namun pencatatan gudang lama belum dihapus.",
    penanganan: "Dokumentasikan kondisi saat ini, kumpulkan bukti perubahan fisik, dan proses sesuai ketentuan penghapusan BMN.",
    alur: "1. Dokumentasi kondisi saat ini (foto, koordinat) → 2. Kumpulkan bukti perubahan → 3. Buat Berita Acara → 4. Proses SPTJM → 5. Ajukan penghapusan dan pencatatan aset baru"
  }
};

const ClassificationInfoCard = ({ subKlasifikasi, klasifikasi }) => {
  const [expanded, setExpanded] = React.useState(false);
  const info = subKlasifikasi ? SUB_KLASIFIKASI_INFO[subKlasifikasi] : null;
  const klasInfo = klasifikasi ? KLASIFIKASI_INFO[klasifikasi] : null;

  if (!info && klasInfo) {
    return (
      <div className={`mt-1.5 rounded-md border text-[10px] overflow-hidden ${
        klasifikasi === "Kesalahan Pencatatan" ? "bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-700" : "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-700"
      }`}>
        <div className="px-2.5 py-1.5 flex items-start gap-1.5">
          <Info className="w-3 h-3 mt-0.5 flex-shrink-0 text-amber-600 dark:text-amber-400" />
          <div>
            <span className="font-semibold">{klasInfo.icon} {klasifikasi}:</span>{" "}
            <span className="text-muted-foreground">{klasInfo.maksud}</span>
            <p className="mt-1 text-muted-foreground italic">{klasInfo.penanganan}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!info) return null;

  return (
    <div className="mt-1.5 rounded-md border border-blue-200 dark:border-blue-700 bg-gradient-to-b from-blue-50 to-slate-50 dark:from-blue-900/20 dark:to-slate-800/20 overflow-hidden text-[10px]">
      <button
        type="button"
        onClick={() => setExpanded(p => !p)}
        className="w-full px-2.5 py-1.5 flex items-center gap-1.5 hover:bg-blue-100/50 dark:hover:bg-blue-900/30 transition-colors text-left"
      >
        <HelpCircle className="w-3 h-3 text-blue-500 dark:text-blue-400 flex-shrink-0" />
        <span className="font-semibold text-blue-800 dark:text-blue-300 flex-1 truncate">Panduan: {subKlasifikasi}</span>
        <ChevronRight className={`w-3 h-3 text-blue-400 transition-transform ${expanded ? 'rotate-90' : ''}`} />
      </button>

      {expanded && (
        <div className="px-2.5 pb-2.5 space-y-2 border-t border-blue-100 dark:border-blue-800">
          <div className="pt-2">
            <div className="flex items-center gap-1 mb-0.5">
              <BookOpen className="w-2.5 h-2.5 text-blue-600 dark:text-blue-400" />
              <span className="font-bold text-blue-700 dark:text-blue-300">Maksud & Pengertian</span>
            </div>
            <p className="text-muted-foreground leading-relaxed pl-3.5">{info.maksud}</p>
          </div>
          <div className="bg-card rounded p-2 border border-blue-200 dark:border-blue-800">
            <div className="flex items-center gap-1 mb-0.5">
              <span className="text-[9px]">💡</span>
              <span className="font-bold text-emerald-700 dark:text-emerald-400">Contoh Kasus</span>
            </div>
            <p className="text-muted-foreground leading-relaxed pl-3.5 italic">"{info.contoh}"</p>
          </div>
          <div>
            <div className="flex items-center gap-1 mb-0.5">
              <Wrench className="w-2.5 h-2.5 text-amber-600 dark:text-amber-400" />
              <span className="font-bold text-amber-700 dark:text-amber-400">Cara Penanganan</span>
            </div>
            <p className="text-muted-foreground leading-relaxed pl-3.5">{info.penanganan}</p>
          </div>
          <div className="bg-card rounded p-2 border border-amber-200 dark:border-amber-800">
            <div className="flex items-center gap-1 mb-1">
              <ArrowRight className="w-2.5 h-2.5 text-violet-600 dark:text-violet-400" />
              <span className="font-bold text-violet-700 dark:text-violet-400">Alur Tindak Lanjut</span>
            </div>
            <div className="pl-3.5 space-y-0.5">
              {info.alur.split(' → ').map((step, i) => (
                <div key={i} className="flex items-start gap-1">
                  <span className="bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300 rounded-full w-3.5 h-3.5 flex items-center justify-center font-bold flex-shrink-0 mt-0.5 text-[8px]">
                    {step.match(/^(\d+)\./)?.[1] || i+1}
                  </span>
                  <span className="text-muted-foreground">{step.replace(/^\d+\.\s*/, '')}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const StatusInfoCard = ({ status }) => {
  const [expanded, setExpanded] = React.useState(false);
  const info = BERLEBIH_SENGKETA_INFO[status];
  if (!info) return null;
  const colorMap = { purple: { bg: "bg-purple-50 dark:bg-purple-900/20", border: "border-purple-200 dark:border-purple-700", text: "text-purple-700 dark:text-purple-400", accent: "text-purple-800 dark:text-purple-300", badge: "bg-purple-100 dark:bg-purple-800/50" }, rose: { bg: "bg-rose-50 dark:bg-rose-900/20", border: "border-rose-200 dark:border-rose-700", text: "text-rose-700 dark:text-rose-400", accent: "text-rose-800 dark:text-rose-300", badge: "bg-rose-100 dark:bg-rose-800/50" } };
  const c = colorMap[info.color] || colorMap.purple;
  return (
    <div className={`mt-1.5 rounded-md border ${c.border} ${c.bg} overflow-hidden text-[10px]`}>
      <button type="button" onClick={() => setExpanded(p => !p)} className={`w-full px-2.5 py-1.5 flex items-center gap-1.5 hover:opacity-80 transition-colors text-left`}>
        <Info className={`w-3 h-3 ${c.text} flex-shrink-0`} />
        <span className={`font-semibold ${c.accent} flex-1`}>{info.icon} {status}: {info.maksud.slice(0, 80)}...</span>
        <ChevronRight className={`w-3 h-3 ${c.text} transition-transform ${expanded ? 'rotate-90' : ''}`} />
      </button>
      {expanded && (
        <div className="px-2.5 pb-2.5 space-y-2 border-t border-border/50">
          <div className="pt-2">
            <div className="flex items-center gap-1 mb-0.5"><BookOpen className="w-2.5 h-2.5 text-blue-600 dark:text-blue-400" /><span className="font-bold text-blue-700 dark:text-blue-300">Pengertian</span></div>
            <p className="text-muted-foreground leading-relaxed pl-3.5">{info.maksud}</p>
          </div>
          <div className="bg-card rounded p-2 border border-border">
            <div className="flex items-center gap-1 mb-1"><span className="text-[9px]">💡</span><span className="font-bold text-emerald-700">Contoh Kasus</span></div>
            <ul className="pl-3.5 space-y-0.5">{info.contoh.map((c, i) => <li key={i} className="text-muted-foreground flex items-start gap-1"><span className="text-emerald-500 mt-0.5">•</span>{c}</li>)}</ul>
          </div>
          <div>
            <div className="flex items-center gap-1 mb-0.5"><Wrench className="w-2.5 h-2.5 text-amber-600 dark:text-amber-400" /><span className="font-bold text-amber-700 dark:text-amber-400">Cara Penanganan</span></div>
            <p className="text-muted-foreground leading-relaxed pl-3.5">{info.penanganan}</p>
          </div>
          <div className="bg-card rounded p-2 border border-amber-200 dark:border-amber-800">
            <div className="flex items-center gap-1 mb-1"><ArrowRight className="w-2.5 h-2.5 text-violet-600 dark:text-violet-400" /><span className="font-bold text-violet-700 dark:text-violet-400">Tindak Lanjut</span></div>
            <ul className="pl-3.5 space-y-0.5">{info.tindak_lanjut.map((t, i) => (
              <li key={i} className="flex items-start gap-1"><span className="bg-violet-100 text-violet-700 rounded-full w-3.5 h-3.5 flex items-center justify-center font-bold flex-shrink-0 mt-0.5 text-[8px]">{i+1}</span><span className="text-muted-foreground">{t}</span></li>
            ))}</ul>
          </div>
        </div>
      )}
    </div>
  );
};


const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const axiosLargeUpload = axios.create({
  timeout: 120000,
  maxContentLength: Infinity,
  maxBodyLength: Infinity
});

// Separate instance → does NOT run App.js's global request interceptor, so it
// must attach the JWT bearer token itself. Without this a direct save (the
// path not routed through the optimistic queue) reaches the backend with no
// Authorization header and 401s. Token is read at request time to stay fresh.
axiosLargeUpload.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token && !config.headers?.Authorization) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * Pull the current user from localStorage so every asset save carries the
 * audit identity in request headers. This axios instance is separate from
 * `axios.defaults` and therefore does NOT inherit the global interceptor
 * registered in DashboardPage — without this, the backend audit log + WS
 * notifications recorded "Unknown" for changes made through this form.
 */
function getAuditHeaders() {
  try {
    const raw = localStorage.getItem("user");
    if (!raw) return {};
    const u = JSON.parse(raw);
    const name = u?.name || u?.username || "";
    const id = u?.id || "";
    const headers = {};
    if (name) headers["X-Audit-User"] = name;
    if (id) headers["X-Audit-User-Id"] = id;
    return headers;
  } catch {
    return {};
  }
}

// Photos are already client-compressed via compressImageFile() at capture time.
// Only photos that are still large (>500KB) go through server-side Tinify —
// saves bandwidth + Tinify quota for the common case.
const SKIP_THRESHOLD = 500 * 1024; // bytes

const compressOnePhoto = async (photo, { localOnly = false } = {}) => {
  const bytes = dataUrlBytes(photo);
  if (bytes > 0 && bytes <= SKIP_THRESHOLD) return photo;

  // 1) Server-side Tinify — best ratio, but needs connectivity.
  //    Dilewati pada alur kamera beruntun (localOnly): surveyor tidak boleh
  //    menunggu round-trip per foto hanya untuk lanjut ke aset berikutnya.
  if (navigator.onLine && !localOnly) {
    try {
      const r = await axios.post(`${API}/compress-image`, { image_data: photo });
      if (r.data.success && r.data.compressed_data) return r.data.compressed_data;
    } catch { /* jatuh ke kompresi lokal di bawah */ }
  }

  // 2) Offline / server gagal: kompresi lokal via canvas (resize 1920px, JPEG
  //    q0.85) — mencegah base64 mentah menembus batas payload 14MB saat offline
  try {
    const local = await compressDataUrl(photo, { maxDim: 1920, quality: 0.85 });
    // Jangan pernah hasilkan output lebih besar dari aslinya
    if (dataUrlBytes(local) < bytes) return local;
    return photo;
  } catch {
    // 3) Canvas juga gagal (format tak didukung) — terpaksa kirim apa adanya
    return photo;
  }
};

const compressPhotos = async (photos, opts) => {
  const compressed = [];
  for (const photo of photos) {
    compressed.push(await compressOnePhoto(photo, opts));
  }
  return compressed;
};

/**
 * Map a server asset row (GET /assets/{id}?exclude_media=true) OR a cached
 * list-projection row (offline snapshot / list state) to the edit form shape.
 * Both carry the same text fields; media (photos, full checklist) is loaded
 * separately. Missing fields default exactly like the empty-form branches.
 */
function buildEditFormData(a, activityId) {
  const existingCL = Array.isArray(a.document_checklist) ? a.document_checklist : [];
  const mergedChecklist = [
    ...DEFAULT_DOC_ITEMS.map(name => existingCL.find(i => i.name === name) || { name, checked: false, notes: "", photos: [], documents: [] }),
    ...existingCL.filter(i => !DEFAULT_DOC_ITEMS.includes(i.name))
  ];
  return {
    asset_code: a.asset_code || "", NUP: a.NUP || "", asset_name: a.asset_name || "", category: a.category || "",
    brand: a.brand || "", model: a.model || "", kode_register: a.kode_register || "",
    serial_number: a.serial_number || "", purchase_date: a.purchase_date || "", purchase_price: a.purchase_price || "",
    location: a.location || "", eselon1: a.eselon1 || "", eselon2: a.eselon2 || "", user: a.user || "",
    pengguna_melekat_ke: a.pengguna_melekat_ke || "", pengguna_jabatan: a.pengguna_jabatan || "",
    pengguna_nip: a.pengguna_nip || "",
    operasional_jenis: a.operasional_jenis || "",
    nomor_bast: a.nomor_bast || "",
    condition: a.condition || "Baik", status: a.status || "Aktif",
    nomor_spm: a.nomor_spm || "", perolehan_dari_nama: a.perolehan_dari_nama || "",
    nomor_kontrak: a.nomor_kontrak || "", nomor_bukti_perolehan: a.nomor_bukti_perolehan || "",
    supplier: a.supplier || "", notes: a.notes || "", photos: [],
    thumbnail_index: a.thumbnail_index || 0,
    stiker_status: a.stiker_status || "Belum Terpasang",
    stiker_ukuran: a.stiker_ukuran || "",
    stiker_photo_index: a.stiker_photo_index != null ? a.stiker_photo_index : null,
    inventory_status: a.inventory_status || "Belum Diinventarisasi",
    klasifikasi_tidak_ditemukan: a.klasifikasi_tidak_ditemukan || "",
    sub_klasifikasi: a.sub_klasifikasi || "",
    uraian_tidak_ditemukan: a.uraian_tidak_ditemukan || "",
    tindak_lanjut: a.tindak_lanjut || "",
    koordinat_latitude: a.koordinat_latitude || "",
    koordinat_longitude: a.koordinat_longitude || "",
    kronologis: a.kronologis || "",
    keterangan_berlebih: a.keterangan_berlebih || "",
    asal_usul_berlebih: a.asal_usul_berlebih || "",
    nomor_perkara: a.nomor_perkara || "",
    pihak_bersengketa: a.pihak_bersengketa || "",
    keterangan_sengketa: a.keterangan_sengketa || "",
    garansi_hingga: a.garansi_hingga || "",
    garansi_jenis: a.garansi_jenis || "",
    document_checklist: mergedChecklist,
    activity_id: activityId || null
  };
}

// ============================================================================
// INLINE FIELD VALIDATION
// ============================================================================
// Which form section (tab) each errorable field lives in — lets us switch to
// the tab containing the first error before scrolling/focusing it.
const FIELD_SECTION = {
  asset_code: "basic", asset_name: "basic", NUP: "basic", category: "basic",
  koordinat_latitude: "basic", koordinat_longitude: "basic",
  pengguna_jabatan: "basic", condition: "basic", status: "basic",
  kode_register: "basic", inventory_status: "basic",
  stiker_status: "basic", stiker_ukuran: "basic",
  nomor_spm: "procurement", perolehan_dari_nama: "procurement",
  nomor_kontrak: "procurement", nomor_bukti_perolehan: "procurement",
  supplier: "procurement",
};

// Best-effort mapping of a server /validate error STRING to the offending field
// so it can be shown inline. Order matters (most specific first). Anything that
// matches nothing here stays in the summary block. See routes/validation.py +
// routes/imports.py:validate_import_row for the source strings.
const SERVER_ERROR_FIELD_PATTERNS = [
  [/kode register/i, "kode_register"],
  [/kombinasi kode barang|\bNUP\b/i, "NUP"],
  [/kode aset|kode barang|asset_code/i, "asset_code"],
  [/nomor spm|\bspm\b/i, "nomor_spm"],
  [/kategori|category/i, "category"],
  [/kondisi|condition/i, "condition"],
  [/stiker_ukuran|ukuran stiker/i, "stiker_ukuran"],
  [/stiker_status|status stiker/i, "stiker_status"],
  [/inventory_status|status inventaris/i, "inventory_status"],
  [/\bstatus\b/i, "status"],
];
function mapServerErrorToField(msg) {
  if (typeof msg !== "string") return null;
  for (const [re, field] of SERVER_ERROR_FIELD_PATTERNS) {
    if (re.test(msg)) return field;
  }
  return null;
}

const AssetForm = memo(({
  isOpen,
  onClose,
  activity,
  categories,
  editAsset,
  onSubmitSuccess,
  onOptimisticSubmit,
  onSaveAndNavigate,
  onCameraReviewSaved,
  onExitToNewAsset,
  assetIndex = -1,
  totalAssetsInView = 0,
  hasMoreToLoad = false,
  saveQueueLength = 0,
  inventoryMode = false,
  onShowCategoryManager,
  onOpenKartu,
  onOpenTimeline,
  alwaysExpanded = false
}) => {
  const [formSection, setFormSection] = useState("basic");
  const [formErrors, setFormErrors] = useState([]);
  // Inline per-field validation: { [fieldName]: message }. Rendered as a red
  // border + helper text beneath the offending input, cleared on change.
  const [fieldErrors, setFieldErrors] = useState({});
  // Bumped on a failed submit to trigger the scroll-to-first-error effect even
  // when the target tab didn't change (setFormSection would be a no-op then).
  const [errorScrollNonce, setErrorScrollNonce] = useState(0);
  const pendingScrollFieldRef = useRef(null);
  const formScrollRef = useRef(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [categoryDropdownOpen, setCategoryDropdownOpen] = useState(false);
  const [categorySearch, setCategorySearch] = useState("");
  const [showGuide, setShowGuide] = useState(false);
  // Mode inventarisasi lapangan: false = tampilan cepat (InventoryFieldSheet),
  // true = form lengkap. Direset ke false setiap kali pindah aset.
  const [showFullForm, setShowFullForm] = useState(false);
  const navigationIntentRef = useRef(null); // 'next' | 'prev' | null
  
  const fileInputRef = useRef(null);
  const cameraInputRef = useRef(null);
  const bastInputRef = useRef(null);
  // One-shot penanda agar dialog pilihan Mode Kamera Penuh hanya ditawarkan
  // SEKALI per sesi form aset baru (tidak muncul lagi setiap render).
  const autoCameraFiredRef = useRef(false);

  // Dokumen BAST tersimpan di server (GridFS): {file_id, filename} — hanya
  // bermakna pada mode edit (unggah butuh asset id).
  const [bastInfo, setBastInfo] = useState(null);
  const [bastUploading, setBastUploading] = useState(false);

  const emptyForm = useMemo(() => ({
    asset_code: "", NUP: "", asset_name: "", category: "", brand: "", model: "",
    kode_register: "", serial_number: "", purchase_date: "", purchase_price: "",
    location: "", eselon1: "", eselon2: "", user: "",
    pengguna_melekat_ke: "", pengguna_jabatan: "", pengguna_nip: "", operasional_jenis: "", nomor_bast: "",
    condition: "Baik", status: "Aktif",
    nomor_spm: "", perolehan_dari_nama: "", nomor_kontrak: "",
    nomor_bukti_perolehan: "", supplier: "", notes: "", photos: [],
    thumbnail_index: 0,
    stiker_status: "Belum Terpasang", stiker_ukuran: "", stiker_photo_index: null,
    inventory_status: "Belum Diinventarisasi", klasifikasi_tidak_ditemukan: "", sub_klasifikasi: "", uraian_tidak_ditemukan: "", tindak_lanjut: "",
    koordinat_latitude: "", koordinat_longitude: "", kronologis: "",
    keterangan_berlebih: "", asal_usul_berlebih: "", nomor_perkara: "", pihak_bersengketa: "", keterangan_sengketa: "",
    garansi_hingga: "", garansi_jenis: "",
    document_checklist: DEFAULT_DOC_ITEMS.map(name => ({ name, checked: false, notes: "", photos: [], documents: [] })),
    activity_id: activity?.id || null
  }), [activity?.id]);

  const [formData, setFormData] = useState(emptyForm);
  const [editId, setEditId] = useState(null);
  // Auto-isi GARANSI dari inventarisasi sebelumnya: saat kode barang + NUP
  // dan/atau kode register sama dengan aset yang pernah tercatat DAN kolom
  // garansi masih kosong, tanggal berakhir garansi terbawa otomatis
  // (offline-tolerant: gagal fetch = diam; tetap bisa isi manual).
  const [garansiOtomatis, setGaransiOtomatis] = useState(false);
  useEffect(() => {
    const kode = String(formData.asset_code || "").trim();
    const nup = String(formData.NUP || "").trim();
    const reg = String(formData.kode_register || "").trim();
    if (formData.garansi_hingga || (!reg && !(kode && nup))) return undefined;
    const t = setTimeout(async () => {
      try {
        const r = await axios.get(`${API}/assets/garansi-sebelumnya`, {
          params: { kode_register: reg, asset_code: kode, NUP: nup,
                    exclude_id: editId || "" },
        });
        if (r.data?.garansi_hingga) {
          setFormData((p) => (p.garansi_hingga ? p
            : { ...p, garansi_hingga: r.data.garansi_hingga }));
          setGaransiOtomatis(true);
        }
      } catch { /* offline / tak ada riwayat — biarkan manual */ }
    }, 600);
    return () => clearTimeout(t);
  }, [formData.asset_code, formData.NUP, formData.kode_register,
      formData.garansi_hingga, editId]);
  // Peringatan kodefikasi LIVE (§5A Prinsip 2, non-blocking): hasil cek
  // GET /integritas/cek-kode untuk asset_code saat ini — hanya info, tak
  // pernah memblokir simpan (data lama boleh punya kode tak terdaftar).
  const [kodefikasiWarn, setKodefikasiWarn] = useState(null);
  // Nama resmi barang dari referensi (bila kode terdaftar penuh) → tanda "terhubung".
  const [kodeRefNama, setKodeRefNama] = useState("");
  // Pemilih kode barang dari referensi kodefikasi (#K, offline-tolerant).
  // kodeResults: array = hasil, null = referensi tak tersedia (offline), [] = kosong.
  const [kodePickerOpen, setKodePickerOpen] = useState(false);
  const [kodeQuery, setKodeQuery] = useState("");
  const [kodeResults, setKodeResults] = useState([]);
  const [kodeLoading, setKodeLoading] = useState(false);
  // Pemilih pengguna dari Master Pegawai (#R3, offline-tolerant). pegawaiAll:
  // undefined = belum dimuat, null = tak tersedia (offline), array = daftar.
  const [pegawaiAll, setPegawaiAll] = useState(undefined);
  const [pegawaiPickerOpen, setPegawaiPickerOpen] = useState(false);
  const [kartuTapOpen, setKartuTapOpen] = useState(false); // tap kartu e-KTP → isi pengguna
  const [pegawaiQuery, setPegawaiQuery] = useState("");
  // Asset version (OCC): appended as ?v= cache-buster to all media streaming
  // URLs (photo strip, checklist photos/PDFs) so the browser cache is busted
  // whenever the asset changes.
  const [assetVersion, setAssetVersion] = useState(1);
  const [isFormLoading, setIsFormLoading] = useState(false);
  // Offline edit: form initialized from the cached list row (offline snapshot)
  // because GET /assets/{id} was unreachable — shows a notice, media unavailable.
  const [offlineNotice, setOfflineNotice] = useState(false);
  // Saran nama ruangan (master #294) untuk datalist field Lokasi — agar penamaan
  // ruangan KONSISTEN (dasar DBR/KIR yang rapi). Best-effort, tetap boleh teks bebas.
  const [ruanganNames, setRuanganNames] = useState([]);

  // Muat saran ruangan sekali saat form dibuka (best-effort; offline diabaikan).
  useEffect(() => {
    if (!isOpen || ruanganNames.length) return undefined;
    let cancelled = false;
    axios.get(`${API}/ruangan`).then((r) => {
      if (cancelled) return;
      setRuanganNames((r.data?.items || [])
        .map((x) => [x.kode_ruangan, x.nama_ruangan].filter(Boolean).join(" — "))
        .filter(Boolean));
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [isOpen, ruanganNames.length]);

  // Muat Master Pegawai sekali saat form dibuka (best-effort; untuk pemilih
  // pengguna & peringatan "NIP belum terdaftar"). Offline diabaikan (null).
  useEffect(() => {
    if (!isOpen || pegawaiAll !== undefined) return undefined;
    let cancelled = false;
    axios.get(`${API}/pegawai`).then((r) => {
      if (!cancelled) setPegawaiAll(r.data?.items || []);
    }).catch(() => { if (!cancelled) setPegawaiAll(null); });
    return () => { cancelled = true; };
  }, [isOpen, pegawaiAll]);

  // Cek kodefikasi LIVE (debounce) saat Kode Aset berubah: peringatan lunak bila
  // prefix kode tak terdaftar di referensi. Non-blocking, best-effort — gagal /
  // offline diabaikan diam-diam (tak mengganggu input). §5A Prinsip 2 (#271).
  useEffect(() => {
    const kode = (formData.asset_code || "").trim();
    if (!isOpen || !kode) { setKodefikasiWarn(null); setKodeRefNama(""); return undefined; }
    let cancelled = false;
    const t = setTimeout(async () => {
      // Peringatan (cek-kode) + nama resmi (lookup) sekaligus; keduanya
      // best-effort — offline/gagal diabaikan diam-diam (tak mengganggu input).
      const [cek, lk] = await Promise.allSettled([
        axios.get(`${API}/integritas/cek-kode?asset_code=${encodeURIComponent(kode)}`),
        axios.get(`${API}/kodefikasi/lookup/${encodeURIComponent(kode)}`),
      ]);
      if (cancelled) return;
      const cekData = cek.status === "fulfilled" ? cek.value.data : null;
      setKodefikasiWarn(cekData && cekData.peringatan ? cekData : null);
      const lkData = lk.status === "fulfilled" ? lk.value.data : null;
      setKodeRefNama(lkData?.uraian_terdalam || "");
    }, 500);
    return () => { cancelled = true; clearTimeout(t); };
  }, [formData.asset_code, isOpen]);

  // Cari kode barang di referensi saat pemilih terbuka (debounce, offline-tolerant).
  useEffect(() => {
    if (!kodePickerOpen) return undefined;
    let cancelled = false;
    setKodeLoading(true);
    const t = setTimeout(async () => {
      try {
        const r = await axios.get(`${API}/kodefikasi`, {
          params: { search: kodeQuery.trim(), page_size: 30 } });
        if (!cancelled) setKodeResults(r.data?.items || []);
      } catch {
        if (!cancelled) setKodeResults(null); // referensi tak tersedia (offline)
      } finally {
        if (!cancelled) setKodeLoading(false);
      }
    }, 300);
    return () => { cancelled = true; clearTimeout(t); };
  }, [kodePickerOpen, kodeQuery]);

  // Dirty tracking: store original data + modification flags
  const originalDataRef = useRef(null);
  const photosModifiedRef = useRef(false);
  const checklistModifiedRef = useRef(false);
  // True once the photo strip for the CURRENT edit target was built from the
  // light fetch (photo_count → streaming thumbnail URLs).
  // While false, photoItems does NOT reflect the photos stored server-side —
  // photo_ops must then keep every existing photo by index or a save that
  // merely ADDS a photo would silently delete all the old ones.
  const mediaLoadedRef = useRef(false);

  // Lazy load: full checklist data (with photo data URLs and PDF data URLs) is
  // only fetched once the user opens the "Dokumen" tab — keeps initial form
  // load fast for the common case where the user only edits text fields.
  const [checklistFullLoaded, setChecklistFullLoaded] = useState(false);
  const [checklistFullLoading, setChecklistFullLoading] = useState(false);
  // Ref guard: prevents the lazy-load effect from re-triggering when its own
  // setState calls bump `checklistFullLoading` and re-run the effect, whose
  // cleanup would then cancel the in-flight request and leave the loader
  // spinning forever.
  const checklistFetchStartedRef = useRef(false);

  // Derive isEditing from prop immediately — no flash of "Tambah Baru"
  const isEditing = !!editAsset;

  // Photo items: tracks each photo as {type: 'existing'|'new', thumbnail, originalIndex?, newData?}
  const [photoItems, setPhotoItems] = useState([]);

  // Load edit data when editAsset changes — two-phase: light data first, then media separately.
  // Keyed by editAsset?.id (not object identity) + an initialized-id guard, so
  // list refreshes or re-clicks that merely re-point the same row can never
  // re-run init and wipe in-progress typing.
  const initializedIdRef = useRef(null);
  useEffect(() => {
    if (editAsset) {
      if (initializedIdRef.current === editAsset.id) return; // same row already loaded — keep user's typing
      initializedIdRef.current = editAsset.id;
      setIsFormLoading(true);
      setEditId(editAsset.id);
      setFormSection("basic");
      setShowFullForm(false);
      setFormErrors([]);
      setFieldErrors({});
      setIsSubmitting(false);
      setOfflineNotice(false);
      originalDataRef.current = null;
      photosModifiedRef.current = false;
      checklistModifiedRef.current = false;
      mediaLoadedRef.current = false;
      setChecklistFullLoaded(false);
      setChecklistFullLoading(false);
      checklistFetchStartedRef.current = false;
      setPhotoItems([]);
      setBastInfo(null);
      setBastUploading(false);
      let cancelled = false;
      // OFFLINE FALLBACK: initialize the form from the cached list row (the
      // offline snapshot / list projection carries every text field incl.
      // version). Media (photos, full checklist) stays unloaded — the guards
      // in handleSubmit keep the save non-destructive for those. Saving flows
      // through the optimistic queue with baseVersion from this same row.
      const initFromCacheRow = () => {
        const lightData = buildEditFormData(editAsset, activity?.id);
        setAssetVersion(Number(editAsset.version) || 1);
        setBastInfo(editAsset.bast_file_id ? { file_id: editAsset.bast_file_id, filename: editAsset.bast_filename || "" } : null);
        setFormData(lightData);
        // Diff baseline = same cached row, so submit PATCHes only what the
        // user actually changed while offline.
        originalDataRef.current = { ...lightData, _photoCount: Number(editAsset.photo_count) || 0 };
        setOfflineNotice(true);
        setIsFormLoading(false);
      };
      (async () => {
        // Known-offline: the GET below cannot succeed — open from cache
        // immediately (no error toast, no unusable form).
        if (!navigator.onLine) { initFromCacheRow(); return; }
        try {
          // Phase 1: Fetch lightweight data (no base64 photos/documents)
          const r = await axios.get(`${API}/assets/${editAsset.id}?exclude_media=true`);
          if (cancelled) return;
          const a = r.data;
          const lightData = buildEditFormData(a, activity?.id);
          setBastInfo(a.bast_file_id ? { file_id: a.bast_file_id, filename: a.bast_filename || "" } : null);
          setFormData(lightData);
          setIsFormLoading(false);

          // Phase 2: Build the photo strip from streaming URLs — no /media
          // roundtrip anymore. Each thumbnail is a plain <img> hitting
          // GET /assets/{id}/photos/{i}?thumb=1, so images load independently
          // (progressive) and are cached by the browser (the endpoint sends
          // Cache-Control/ETag; ?v={version} busts the cache after every edit).
          // These are public GET endpoints — same posture as the checklist
          // photo/PDF streaming URLs — because <img> cannot send auth headers.
          // Checklist metadata (checked/notes/counts) already came with the
          // light fetch; thumbnails + sentinels load via /checklist-full when
          // the "Dokumen" tab opens.
          const photoCount = Number(a.photo_count) || 0;
          const version = Number(a.version) || 1;
          setAssetVersion(version);
          const items = Array.from({ length: photoCount }, (_, i) => ({
            type: 'existing',
            thumbnail: authMediaUrl(`${API}/assets/${editAsset.id}/photos/${i}?thumb=1&v=${version}`),
            originalIndex: i,
          }));
          setPhotoItems(items);
          // photoItems now mirrors the server-side photo list (indices from the
          // authoritative photo_count of the light fetch), so photo_ops can
          // safely derive keep[] from it — same contract the /media load had.
          mediaLoadedRef.current = true;

          // Keep photos array length correct for validation / count display.
          const placeholderPhotos = Array(photoCount).fill("__existing__");
          originalDataRef.current = { ...lightData, photos: placeholderPhotos, _photoCount: photoCount };
          startTransition(() => {
            setFormData(prev => ({ ...prev, photos: placeholderPhotos }));
          });
        } catch (err) {
          if (cancelled) return;
          if (!err?.response) {
            // Network-level failure (offline / server unreachable) → cache row
            initFromCacheRow();
          } else {
            // Server answered with an error (404 asset deleted, 401, …) —
            // cached data would be misleading here; keep the explicit error.
            toast.error("Gagal memuat data aset");
            setIsFormLoading(false);
            setIsSubmitting(false);
          }
        }
      })();
      return () => { cancelled = true; };
    } else {
      initializedIdRef.current = null;
      setFormData({...emptyForm});
      setEditId(null);
      setAssetVersion(1);
      setFormSection("basic");
      setShowFullForm(false);
      setFormErrors([]);
      setFieldErrors({});
      setCategorySearch("");
      setIsSubmitting(false);
      setIsFormLoading(false);
      setOfflineNotice(false);
      originalDataRef.current = null;
      photosModifiedRef.current = false;
      checklistModifiedRef.current = false;
      mediaLoadedRef.current = false;
      setChecklistFullLoaded(false);
      setChecklistFullLoading(false);
      checklistFetchStartedRef.current = false;
      setPhotoItems([]);
      setBastInfo(null);
      setBastUploading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editAsset?.id, activity?.id]);

  const resetForm = useCallback(() => {
    setFormData({...emptyForm});
    setEditId(null);
    setAssetVersion(1);
    setFormSection("basic");
    setFormErrors([]);
    setFieldErrors({});
    setCategorySearch("");
    setOfflineNotice(false);
    originalDataRef.current = null;
    photosModifiedRef.current = false;
    checklistModifiedRef.current = false;
    mediaLoadedRef.current = false;
    setChecklistFullLoaded(false);
    setChecklistFullLoading(false);
    checklistFetchStartedRef.current = false;
    setPhotoItems([]);
    setBastInfo(null);
    setBastUploading(false);
  }, [emptyForm]);

  // Auto-fill GPS coordinates from device location
  const [gpsLoading, setGpsLoading] = useState(false);
  const fetchGPS = useCallback(() => {
    if (!navigator.geolocation) { toast.error("GPS tidak didukung di browser ini"); return; }
    setGpsLoading(true);
    // Realtime: koordinat diperbarui tiap fix yang lebih akurat, lalu diambil
    // yang paling tepat. maximumAge:0 memastikan bukan koordinat lama (ter-cache).
    acquireAccuratePosition({
      onUpdate: ({ lat, lng }) => setFormData(p => ({ ...p, koordinat_latitude: lat, koordinat_longitude: lng })),
    }).then(({ lat, lng, accuracy }) => {
      try { localStorage.setItem("aman_last_gps", JSON.stringify({ lat, lng, ts: Date.now() })); } catch {}
      setFormData(p => ({ ...p, koordinat_latitude: lat, koordinat_longitude: lng }));
      setGpsLoading(false);
      toast.success(`Koordinat GPS diperbarui${Number.isFinite(accuracy) ? ` (±${Math.round(accuracy)} m)` : ""}`);
    }).catch(err => {
      setGpsLoading(false);
      if (err?.code === 1) toast.error("Akses lokasi ditolak. Izinkan di pengaturan browser.");
      else toast.error("Gagal mendapatkan lokasi GPS");
    });
  }, []);

  // Lazy-load full checklist (with photo data URLs and PDF data URLs) when the
  // user opens the "Dokumen" tab for the first time on an existing asset. This
  // keeps the initial form open instant while still ensuring the data needed
  // to render thumbnails / open PDFs / safely save modifications is present
  // before the user can interact.
  //
  // Implementation note: the loading flags are intentionally NOT in the deps
  // array. If they were, our own setState calls would re-run the effect, the
  // cleanup would flip `cancelled = true` on the in-flight request, and the
  // loader would spin forever (no setState ever flips loaded=true). We use a
  // ref guard instead so we still only fire once per asset.
  useEffect(() => {
    if (!isEditing) return;
    if (formSection !== "documents") return;
    if (!editId) return;
    if (checklistFetchStartedRef.current) return;
    checklistFetchStartedRef.current = true;
    setChecklistFullLoading(true);
    let cancelled = false;
    (async () => {
      try {
        // 60s timeout so a stalled request shows a clear error instead of an
        // infinite spinner. /checklist-full now returns metadata only (photos
        // streamed individually) so the response is small.
        const r = await axios.get(`${API}/assets/${editId}/checklist-full`, { timeout: 60000 });
        if (cancelled) return;
        const fullChecklist = r.data?.document_checklist || [];
        setFormData(prev => {
          const fullByName = new Map(fullChecklist.map(it => [it.name, it]));
          const merged = (prev.document_checklist || []).map(item => {
            const f = fullByName.get(item.name);
            if (!f) return item;
            // Build sentinel arrays for existing media. The backend resolves
            // "__existing__:<idx>" back to the original photo/document on save
            // — this lets us avoid re-shipping multi-MB base64 blobs.
            const photoCount = f.photo_count || 0;
            const sentinelPhotos = Array.from({ length: photoCount }, (_, i) => `__existing__:${i}`);
            const docCount = f.document_count || (f.documents || []).length;
            const sentinelDocs = (f.documents || []).map((d, i) => ({
              name: d.name || "document.pdf",
              data: `__existing__:${typeof d.idx === "number" ? d.idx : i}`,
            }));
            return {
              ...item,
              checked: f.checked != null ? f.checked : item.checked,
              notes: f.notes != null ? f.notes : item.notes,
              photos: sentinelPhotos,
              photo_thumbnails: f.photo_thumbnails || item.photo_thumbnails || [],
              documents: sentinelDocs.length === docCount ? sentinelDocs : sentinelDocs,
            };
          });
          if (originalDataRef.current) {
            originalDataRef.current = {
              ...originalDataRef.current,
              document_checklist: merged.map(i => ({ ...i })),
            };
          }
          return { ...prev, document_checklist: merged };
        });
        setChecklistFullLoaded(true);
      } catch (err) {
        if (!cancelled) {
          // Reset guard so user can retry by switching tabs
          checklistFetchStartedRef.current = false;
          const msg = err?.code === "ECONNABORTED"
            ? "Waktu muat habis (60s). Cek koneksi atau hubungi admin."
            : !err?.response
              ? "Checklist dokumen butuh koneksi — buka kembali tab ini saat online."
              : `Gagal memuat data dokumen aset (HTTP ${err.response.status})`;
          toast.error(msg);
        }
      } finally {
        if (!cancelled) setChecklistFullLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [formSection, editId, isEditing]);

  // Auto-get GPS only for EDIT mode when asset has no coords AND inventory mode is active.
  // Cache GPS: bila fix terakhir masih segar (< 5 menit) pakai langsung agar form
  // instan terisi, lalu tetap minta fix baru di background (hanya menimpa bila
  // pengguna belum mengetik koordinat lain sejak nilai cache diterapkan).
  useEffect(() => {
    if (isOpen && isEditing && inventoryMode && !formData.koordinat_latitude && !formData.koordinat_longitude) {
      let cached = null;
      try { cached = JSON.parse(localStorage.getItem("aman_last_gps") || "null"); } catch {}
      if (cached?.lat && cached?.lng && Date.now() - (cached.ts || 0) < 5 * 60 * 1000) {
        const { lat, lng } = cached;
        setFormData(p => (!p.koordinat_latitude && !p.koordinat_longitude) ? { ...p, koordinat_latitude: lat, koordinat_longitude: lng } : p);
        if (navigator.geolocation) {
          navigator.geolocation.getCurrentPosition(
            pos => {
              const freshLat = pos.coords.latitude.toFixed(6);
              const freshLng = pos.coords.longitude.toFixed(6);
              try { localStorage.setItem("aman_last_gps", JSON.stringify({ lat: freshLat, lng: freshLng, ts: Date.now() })); } catch {}
              setFormData(p => (p.koordinat_latitude === lat && p.koordinat_longitude === lng) ? { ...p, koordinat_latitude: freshLat, koordinat_longitude: freshLng } : p);
            },
            () => {}, // fix baru gagal — nilai cache tetap dipakai
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
          );
        }
      } else {
        fetchGPS();
      }
    }
  }, [isOpen, isEditing, inventoryMode]); // eslint-disable-line react-hooks/exhaustive-deps

  // Aset BARU di mode inventarisasi: tawarkan PILIHAN (sekali per sesi form
  // aset baru) untuk masuk Mode Kamera Penuh ala Timemark — halaman kamera
  // fullscreen dengan jam berjalan, GPS live, info aset, edit info, dan hapus
  // foto — atau tetap mengisi form biasa. Tidak lagi membuka kamera otomatis.
  const [cameraPromptOpen, setCameraPromptOpen] = useState(false);
  const [fullCameraOpen, setFullCameraOpen] = useState(false);
  const [cameraAutoScan, setCameraAutoScan] = useState(false);
  useEffect(() => {
    // Tawarkan dialog pilihan SEKALI saat membuka form aset baru — tapi tidak
    // saat kita sudah berada di dalam Mode Kamera Penuh (mis. transisi tinjau→baru).
    if (isOpen && !isEditing && inventoryMode && !fullCameraOpen) {
      if (autoCameraFiredRef.current) return;
      autoCameraFiredRef.current = true;
      setCameraPromptOpen(true);
      return;
    }
    // Reset one-shot HANYA saat form benar-benar tertutup, bukan tiap pindah aset.
    if (!isOpen) { autoCameraFiredRef.current = false; setCameraPromptOpen(false); setFullCameraOpen(false); }
  }, [isOpen, isEditing, inventoryMode, fullCameraOpen]);

  // Back HP saat dialog pilihan kamera terbuka → tutup dialognya saja
  useBackGuard(useCallback(() => setCameraPromptOpen(false), []), cameraPromptOpen);

  // Foto dari Mode Kamera Penuh: dataURL sudah ≤1920px q0.85 (setara pipeline
  // kompresi form) + sudah distempel waktu/GPS — langsung masuk daftar foto.
  const addCameraPhoto = useCallback(async (dataUrl) => {
    photosModifiedRef.current = true;
    if (isEditing) {
      // Saat edit OFFLINE, foto server yang sudah ada belum dimuat ke photoItems
      // (mediaLoadedRef false) — hitung dari _photoCount agar batas 6 tetap benar.
      const existingUnloaded = mediaLoadedRef.current ? 0 : (originalDataRef.current?._photoCount || 0);
      if (photoItems.length + existingUnloaded >= 6) { toast.error("Maks 6 foto"); return; }
      const thumb = await generateThumbnailFromDataUrl(dataUrl, 100, 0.7).catch(() => dataUrl);
      setPhotoItems(prev => (prev.length + existingUnloaded >= 6 ? prev : [...prev, { type: "new", thumbnail: thumb, newData: dataUrl }]));
      return;
    }
    setFormData(p => {
      if (p.photos.length >= 6) { toast.error("Maks 6 foto"); return p; }
      return {
        ...p,
        photos: [...p.photos, dataUrl],
        ...(p.inventory_status === "Belum Diinventarisasi" && p.photos.length === 0 ? { inventory_status: "Ditemukan" } : {}),
      };
    });
  }, [isEditing, photoItems.length]);

  // GPS PINTAR (#4): selama sesi kamera SATU aset, watchPosition mengalirkan fix
  // {lat,lng,accuracy} terus-menerus. Alih-alih memakai fix TERAKHIR (yang bisa
  // ber-jitter / kurang akurat), koordinat dikunci ke jepretan PALING AKURAT —
  // hanya di-commit bila fix ini lebih akurat (accuracy lebih kecil) daripada
  // yang terbaik sejauh ini; fix pertama selalu dipakai. Commit jadi jarang
  // (akurasi membaik lalu berhenti), sekaligus ringan untuk HP low-end. Reset
  // "fix terbaik" per aset via efek [editAsset?.id, cameraSavedCount] di bawah.
  const bestGpsAccuracyRef = useRef(null);
  const handleCameraGpsFix = useCallback((fix) => {
    const lat = fix?.lat, lng = fix?.lng;
    if (lat == null || lng == null) return;
    try { localStorage.setItem("aman_last_gps", JSON.stringify({ lat, lng, ts: Date.now() })); } catch {}
    const best = bestGpsAccuracyRef.current;
    if (best && !lebihAkurat(fix, best)) return; // sudah punya yang lebih akurat
    bestGpsAccuracyRef.current = fix;
    setFormData(p => (p.koordinat_latitude === lat && p.koordinat_longitude === lng ? p : { ...p, koordinat_latitude: lat, koordinat_longitude: lng }));
  }, []);

  // Clear a single field's inline error (used on change so the red state
  // disappears as soon as the user starts correcting the field).
  const clearFieldError = useCallback((name) => {
    setFieldErrors(prev => {
      if (!prev[name]) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
  }, []);

  const handleInputChange = useCallback(e => {
    const { name, value } = e.target;
    setFormData(p => ({ ...p, [name]: value }));
    clearFieldError(name);
  }, [clearFieldError]);

  // Pilih kode dari referensi kodefikasi → isi asset_code + nama (bila kosong).
  const onPickKode = useCallback((item) => {
    setFormData(p => ({
      ...p,
      asset_code: item.kode,
      asset_name: (p.asset_name || "").trim() ? p.asset_name : (item.uraian || ""),
    }));
    clearFieldError("asset_code");
    clearFieldError("asset_name");
    setKodePickerOpen(false);
    setKodeQuery("");
  }, [clearFieldError]);

  // Hasil pemilih pegawai (filter client-side by nama/NIP). null = offline.
  const pegawaiResults = useMemo(() => {
    if (!Array.isArray(pegawaiAll)) return pegawaiAll;   // undefined/null diteruskan
    const q = pegawaiQuery.trim().toLowerCase();
    const list = !q ? pegawaiAll : pegawaiAll.filter((p) =>
      [p.nama, p.nip].some((v) => String(v || "").toLowerCase().includes(q)));
    return list.slice(0, 40);
  }, [pegawaiAll, pegawaiQuery]);

  // Peringatan lunak: NIP pengguna diisi tapi tak ada di Master Pegawai.
  const penggunaNipWarn = useMemo(() => {
    const nip = (formData.pengguna_nip || "").trim();
    if (!nip || !Array.isArray(pegawaiAll)) return false;
    return !pegawaiAll.some((p) => String(p.nip || "").trim() === nip);
  }, [formData.pengguna_nip, pegawaiAll]);

  // Pilih pegawai dari master → isi user (nama) + pengguna_nip + jabatan (bila kosong).
  const onPickPegawai = useCallback((p) => {
    setFormData(prev => ({
      ...prev,
      user: p.nama || prev.user,
      pengguna_nip: p.nip || prev.pengguna_nip,
      pengguna_jabatan: (prev.pengguna_jabatan || "").trim() ? prev.pengguna_jabatan : (p.jabatan || ""),
    }));
    clearFieldError("user");
    clearFieldError("pengguna_nip");
    setPegawaiPickerOpen(false);
    setPegawaiQuery("");
  }, [clearFieldError]);

  // Urutan NUP dummy: logika bersama di lib/dummyNup.js (satu sumber urutan
  // dengan tambah-cepat di peta aset — localStorage key & cache modul sama).
  const reserveDummyNup = useCallback(
    (assetCode, categoryLabel) => reserveDummyNupLib(activity?.id, assetCode, categoryLabel),
    [activity?.id]);

  // Kategori "dummy" + NUP otomatis untuk Mode Kamera Penuh: surveyor tidak
  // perlu memilih kategori — Kode Aset di-set ke kategori dummy dan NUP dinomori
  // otomatis, unik & berurutan per perangkat (lihat reserveDummyNup).
  const applyDummyCategory = useCallback(async () => {
    const dummy = (categories || []).find(c => /dummy/i.test(c.label || ""));
    if (!dummy) return;
    setFormData(p => ({ ...p, category: dummy.label, ...(dummy.kode_aset ? { asset_code: dummy.kode_aset } : {}) }));
    clearFieldError("asset_code");
    const nup = await reserveDummyNup(dummy.kode_aset, dummy.label);
    setFormData(p => ({ ...p, NUP: nup }));
  }, [categories, reserveDummyNup, clearFieldError]);

  // Jumlah aset tersimpan selama sesi Kamera Penuh (indikator alur beruntun).
  const [cameraSavedCount, setCameraSavedCount] = useState(0);

  // GPS PINTAR: reset "fix terbaik" tiap ganti aset (edit) atau simpan-lalu-baru
  // (cameraSavedCount naik) → tiap aset memilih koordinat GPS terakuratnya sendiri.
  useEffect(() => { bestGpsAccuracyRef.current = null; }, [editAsset?.id, cameraSavedCount]);

  // Mode Kamera Penuh untuk aset BARU: standby-kan kategori dummy + NUP otomatis.
  useEffect(() => {
    if (fullCameraOpen && !isEditing && !formData.category) applyDummyCategory();
  }, [fullCameraOpen, isEditing, formData.category, applyDummyCategory]);

  const handleSelectChange = useCallback((f, v) => {
    setFormData(p => ({ ...p, [f]: v }));
    clearFieldError(f);
  }, [clearFieldError]);

  // Switch to the tab holding `fieldName`, then queue a scroll+focus to it.
  const focusFieldError = useCallback((fieldName) => {
    if (!fieldName) return;
    const section = FIELD_SECTION[fieldName] || "basic";
    // The jabatan input only exists in the full form — open it from the quick
    // inventory sheet (parity with the previous setShowFullForm behavior).
    if (fieldName === "pengguna_jabatan") setShowFullForm(true);
    setFormSection(section);
    pendingScrollFieldRef.current = fieldName;
    setErrorScrollNonce(n => n + 1);
  }, []);

  // Scroll the first errored field into view + focus it after the tab switch
  // has rendered. Keyed on the nonce so it re-fires even for same-tab errors.
  useEffect(() => {
    const name = pendingScrollFieldRef.current;
    if (!name) return;
    const t = setTimeout(() => {
      pendingScrollFieldRef.current = null;
      const root = formScrollRef.current || document;
      const el = root.querySelector(`[name="${name}"]`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        try { el.focus({ preventScroll: true }); } catch { /* not focusable */ }
      }
    }, 60);
    return () => clearTimeout(t);
  }, [errorScrollNonce]);

  // Ganti status inventarisasi + bersihkan field turunan yang tidak relevan.
  // Dipakai oleh Select "Status Inventarisasi" DAN tombol segmented di
  // InventoryFieldSheet (mode inventarisasi lapangan).
  const handleInventoryStatusChange = useCallback(v => {
    setFormData(p => ({
      ...p, inventory_status: v,
      ...(v !== "Tidak Ditemukan" ? { klasifikasi_tidak_ditemukan: "", sub_klasifikasi: "", uraian_tidak_ditemukan: "", tindak_lanjut: "" } : {}),
      ...(v !== "Berlebih" ? { keterangan_berlebih: "", asal_usul_berlebih: "" } : {}),
      ...(v !== "Sengketa" ? { nomor_perkara: "", pihak_bersengketa: "", keterangan_sengketa: "" } : {}),
      ...(v === "Ditemukan" || v === "Belum Diinventarisasi" ? { kronologis: "" } : {})
    }));
  }, []);

  // Ganti klasifikasi "Tidak Ditemukan" + reset sub-klasifikasi turunannya.
  // Dipakai oleh form penuh DAN InventoryFieldSheet.
  const handleKlasifikasiChange = useCallback(v => {
    setFormData(p => ({ ...p, klasifikasi_tidak_ditemukan: v, sub_klasifikasi: "" }));
  }, []);

  // Ganti status stiker + bersihkan foto stiker bila stiker belum terpasang.
  // Dipakai oleh form penuh DAN InventoryFieldSheet.
  const handleStikerStatusChange = useCallback(v => {
    setFormData(p => ({
      ...p, stiker_status: v,
      ...(v !== "Sudah Terpasang" ? { stiker_photo_index: null } : {}),
    }));
  }, []);

  // Pengguna "melekat ke": klik ulang pilihan yang sama = batal pilih;
  // nama jabatan hanya relevan bila melekat ke Jabatan, jenis operasional
  // hanya relevan bila melekat ke Operasional.
  // Dipakai oleh form penuh DAN InventoryFieldSheet.
  const handlePenggunaMelekatChange = useCallback(v => {
    setFormData(p => {
      const next = p.pengguna_melekat_ke === v ? "" : v;
      return {
        ...p,
        pengguna_melekat_ke: next,
        ...(next !== "Jabatan" ? { pengguna_jabatan: "" } : {}),
        ...(next !== "Operasional" ? { operasional_jenis: "" } : {}),
      };
    });
  }, []);

  // Sub-opsi Operasional: klik ulang pilihan yang sama = batal pilih.
  // Dipakai oleh form penuh DAN InventoryFieldSheet.
  const handleOperasionalJenisChange = useCallback(v => {
    setFormData(p => ({ ...p, operasional_jenis: p.operasional_jenis === v ? "" : v }));
  }, []);

  // Unggah dokumen BAST (PDF/gambar, maks 10MB) — hanya mode edit (butuh id).
  // Posture sama dengan unggah dokumen pengesahan (PengesahanDialog).
  const handleBastUpload = useCallback(async e => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !editId) return;
    const name = (file.name || "").toLowerCase();
    if (!name.endsWith(".pdf") && !/\.(jpe?g|png|webp)$/.test(name)) {
      toast.error("Dokumen BAST harus PDF atau gambar (JPG/PNG/WEBP)");
      return;
    }
    if (file.size > 10 * 1024 * 1024) { toast.error("Ukuran dokumen BAST maksimal 10MB"); return; }
    setBastUploading(true);
    try {
      const uploadData = new FormData();
      uploadData.append("file", file);
      const token = localStorage.getItem("token");
      const r = await axios.post(`${API}/assets/${editId}/bast`, uploadData, {
        headers: {
          "Content-Type": "multipart/form-data",
          Authorization: `Bearer ${token}`,
          ...getAuditHeaders(),
        },
        timeout: 120000,
      });
      setBastInfo({ file_id: r.data?.bast_file_id || "", filename: r.data?.bast_filename || file.name });
      toast.success(`Dokumen BAST "${file.name}" berhasil diunggah`);
    } catch (err) {
      toast.error(getApiError(err, "Gagal mengunggah dokumen BAST"));
    } finally {
      setBastUploading(false);
    }
  }, [editId]);

  const handleBastPreview = useCallback(() => {
    if (!editId) return;
    // bast_file_id unik per unggahan → cache-buster alami untuk GET publik
    window.open(authMediaUrl(`${API}/assets/${editId}/bast${bastInfo?.file_id ? `?v=${bastInfo.file_id}` : ""}`), "_blank");
  }, [editId, bastInfo?.file_id]);

  const openCamera = useCallback(() => cameraInputRef.current?.click(), []);
  const openGallery = useCallback(() => fileInputRef.current?.click(), []);

  // Mode Kamera Penuh butuh getUserMedia (konteks aman/HTTPS). Bila tak
  // didukung (WebView pemerintah tanpa izin kamera / non-HTTPS), fallback ke
  // kamera OS via input file — jangan buntu.
  const cameraSupported = typeof navigator !== "undefined" && !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  const openFullCamera = useCallback(() => {
    if (cameraSupported) setFullCameraOpen(true);
    else { toast.info("Mode kamera langsung tidak didukung — memakai kamera biasa."); cameraInputRef.current?.click(); }
  }, [cameraSupported]);
  // Callback stabil untuk FullCameraSheet (jaga memo + hindari render berlebih).
  const closeFullCamera = useCallback(() => { setFullCameraOpen(false); setCameraAutoScan(false); }, []);
  // Buka Mode Kamera langsung dalam keadaan memindai QR (edit inventarisasi).
  const openFullCameraScan = useCallback(() => { setCameraAutoScan(true); openFullCamera(); }, [openFullCamera]);
  const cameraSetField = useCallback((name, value) => { setFormData(p => ({ ...p, [name]: value })); clearFieldError(name); }, [clearFieldError]);

  // "Samakan dengan sebelumnya": konteks lokasi/pengguna dari aset terakhir
  // yang disimpan (localStorage 'aman_last_asset_ctx', ditulis saat submit).
  const [lastCtx, setLastCtx] = useState(null);
  useEffect(() => {
    if (!(inventoryMode && isEditing)) return;
    try { setLastCtx(JSON.parse(localStorage.getItem("aman_last_asset_ctx") || "null")); } catch { setLastCtx(null); }
  }, [inventoryMode, isEditing, editAsset?.id]);

  const applyLastCtx = useCallback(() => {
    let ctx = null;
    try { ctx = JSON.parse(localStorage.getItem("aman_last_asset_ctx") || "null"); } catch {}
    if (!ctx) return;
    // Koordinat GPS ikut disalin SECARA CERDAS: hanya bila koordinat form masih
    // kosong (jangan timpa GPS segar/manual) DAN konteks masih baru (aset lama
    // kemungkinan pindah lokasi). Koordinat salinan bersifat sementara — GPS
    // kamera yang akurat akan menggantikannya (bestGpsAccuracyRef=null per aset).
    const salinKoord = bolehSalinKoordinat(ctx, formData.koordinat_latitude, formData.koordinat_longitude, Date.now());
    // Hanya isi field yang masih kosong — jangan pernah menimpa isian pengguna
    setFormData(p => ({
      ...p,
      ...(!p.location && ctx.location ? { location: ctx.location } : {}),
      ...(!p.eselon1 && ctx.eselon1 ? { eselon1: ctx.eselon1 } : {}),
      ...(!p.eselon2 && ctx.eselon2 ? { eselon2: ctx.eselon2 } : {}),
      ...(!p.user && ctx.user ? { user: ctx.user } : {}),
      ...(salinKoord ? { koordinat_latitude: ctx.koordinat_latitude, koordinat_longitude: ctx.koordinat_longitude } : {}),
    }));
    toast.success(salinKoord ? "Disalin dari aset sebelumnya (termasuk koordinat GPS)" : "Disalin dari aset sebelumnya");
  }, [formData.koordinat_latitude, formData.koordinat_longitude]);

  const handleChecklistChange = useCallback(u => { checklistModifiedRef.current = true; setFormData(p => ({...p, document_checklist: u})); }, []);

  // In edit mode, photo count comes from photoItems. In create mode, from formData.photos
  const currentPhotoCount = isEditing ? photoItems.length : formData.photos.length;

  const handleImageChange = useCallback(async e => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    photosModifiedRef.current = true;
    const max = 6;

    // Filter invalid files upfront
    const validFiles = files.filter(file => {
      if (file.size > 15 * 1024 * 1024) { toast.error(`${file.name} > 15MB`); return false; }
      if (!file.type.startsWith('image/')) { toast.error(`${file.name} bukan gambar`); return false; }
      return true;
    });

    if (isEditing) {
      // Edit offline: tambahkan _photoCount server yang belum dimuat ke hitungan.
      const existingUnloaded = mediaLoadedRef.current ? 0 : (originalDataRef.current?._photoCount || 0);
      const cur = photoItems.length + existingUnloaded;
      const allowed = validFiles.slice(0, max - cur);
      if (validFiles.length > allowed.length) toast.error(`Maks ${max} foto`);
      if (!allowed.length) return;

      // Compress + thumbnail in parallel — 10x faster perceived saving
      const toastId = toast.loading(`Mengompresi ${allowed.length} foto...`, { duration: 8000 });
      try {
        const processed = await Promise.all(allowed.map(async (file) => {
          const originalBytes = file.size;
          const compressed = await compressImageFile(file);
          const thumb = await generateThumbnailFromDataUrl(compressed, 100, 0.7);
          const compressedBytes = dataUrlBytes(compressed);
          return { compressed, thumb, originalBytes, compressedBytes };
        }));
        toast.dismiss(toastId);
        const totalOrig = processed.reduce((s, p) => s + p.originalBytes, 0);
        const totalComp = processed.reduce((s, p) => s + p.compressedBytes, 0);
        const savedPct = totalOrig > 0 ? Math.round(((totalOrig - totalComp) / totalOrig) * 100) : 0;
        if (savedPct > 5) toast.success(`Foto dikompresi: hemat ${savedPct}% bandwidth`, { duration: 2500 });

        setPhotoItems(prev => [...prev, ...processed.map(p => ({ type: 'new', thumbnail: p.thumb, newData: p.compressed }))]);
        setFormData(p => ({
          ...p,
          photos: [...p.photos, ...processed.map(x => x.compressed)],
          ...(p.inventory_status === "Belum Diinventarisasi" && p.photos.length === 0 ? { inventory_status: "Ditemukan" } : {})
        }));
      } catch (err) {
        toast.dismiss(toastId);
        toast.error(`Gagal memproses foto: ${err.message || err}`);
      }
    } else {
      // Create mode
      const cur = formData.photos.length;
      const allowed = validFiles.slice(0, max - cur);
      if (validFiles.length > allowed.length) toast.error(`Maks ${max} foto`);
      if (!allowed.length) return;

      const toastId = toast.loading(`Mengompresi ${allowed.length} foto...`, { duration: 8000 });
      try {
        const compressedList = await Promise.all(allowed.map((file) => compressImageFile(file)));
        toast.dismiss(toastId);
        setFormData(p => ({
          ...p,
          photos: [...p.photos, ...compressedList],
          ...(p.inventory_status === "Belum Diinventarisasi" && p.photos.length === 0 ? { inventory_status: "Ditemukan" } : {})
        }));
      } catch (err) {
        toast.dismiss(toastId);
        toast.error(`Gagal memproses foto: ${err.message || err}`);
      }
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (cameraInputRef.current) cameraInputRef.current.value = "";
  }, [isEditing, photoItems.length, formData.photos.length]);

  const removePhoto = useCallback(index => {
    photosModifiedRef.current = true;
    if (isEditing) {
      // Edit mode: remove from photoItems
      setPhotoItems(prev => prev.filter((_, i) => i !== index));
      setFormData(p => {
        const newPhotos = p.photos.filter((_, i) => i !== index);
        let newThumbIdx = p.thumbnail_index;
        let newStikerIdx = p.stiker_photo_index;
        if (index === p.thumbnail_index) newThumbIdx = 0;
        else if (index < p.thumbnail_index) newThumbIdx = Math.max(0, p.thumbnail_index - 1);
        if (p.stiker_photo_index !== null) {
          if (index === p.stiker_photo_index) newStikerIdx = null;
          else if (index < p.stiker_photo_index) newStikerIdx = p.stiker_photo_index - 1;
        }
        return { ...p, photos: newPhotos, thumbnail_index: newThumbIdx, stiker_photo_index: newStikerIdx };
      });
    } else {
      // Create mode: keep existing behavior
      setFormData(p => {
        const newPhotos = p.photos.filter((_, i) => i !== index);
        let newThumbIdx = p.thumbnail_index;
        let newStikerIdx = p.stiker_photo_index;
        if (index === p.thumbnail_index) newThumbIdx = 0;
        else if (index < p.thumbnail_index) newThumbIdx = Math.max(0, p.thumbnail_index - 1);
        if (p.stiker_photo_index !== null) {
          if (index === p.stiker_photo_index) newStikerIdx = null;
          else if (index < p.stiker_photo_index) newStikerIdx = p.stiker_photo_index - 1;
        }
        return { ...p, photos: newPhotos, thumbnail_index: newThumbIdx, stiker_photo_index: newStikerIdx };
      });
    }
  }, [isEditing]);

  const handleSubmit = useCallback(async e => {
    e.preventDefault();
    // Tangkap & bersihkan intent navigasi di awal agar tidak tersisa "basi"
    // saat submit gagal validasi (mis. tombol Kamera Penuh ditekan tanpa nama).
    const navIntent = navigationIntentRef.current;
    navigationIntentRef.current = null;

    // Jangan submit saat aset yang sedang ditinjau BELUM selesai dimuat — kalau
    // dipaksa, jalur EDIT (butuh originalDataRef) belum siap dan bisa jatuh ke
    // CREATE lalu MENIMPA aset lama dengan data aset baru sebelumnya.
    if (isFormLoading) { toast.info("Menunggu data aset dimuat…"); return; }

    // === Inline client-side validation ===
    const errs = {};
    if (!formData.asset_code) errs.asset_code = "Kode Aset wajib diisi";
    if (!formData.asset_name) errs.asset_name = "Nama Aset wajib diisi";

    // Validate lat/long: required ONLY once the asset is inventoried
    // (status != "Belum Diinventarisasi"). Uploading a photo alone never
    // forces GPS, so a "Belum Diinventarisasi" asset saves without coordinates.
    const isInventoried = formData.inventory_status && formData.inventory_status !== "Belum Diinventarisasi";
    if (isInventoried && !formData.koordinat_latitude) errs.koordinat_latitude = "Koordinat wajib diisi setelah inventarisasi";
    if (isInventoried && !formData.koordinat_longitude) errs.koordinat_longitude = "Koordinat wajib diisi setelah inventarisasi";

    // Pengguna terstruktur: bila melekat ke Jabatan, nama jabatan wajib diisi.
    if (formData.pengguna_melekat_ke === "Jabatan" && !(formData.pengguna_jabatan || "").trim()) {
      errs.pengguna_jabatan = "Nama jabatan wajib diisi bila pengguna melekat ke Jabatan";
    }

    // Kode register (opsional) harus 32 karakter hex — sama dengan aturan
    // server (/assets/validate). Dicek di klien juga karena alur kamera
    // beruntun melewati round-trip validasi server.
    const kodeReg = String(formData.kode_register || "").trim();
    if (kodeReg && !/^[A-Fa-f0-9]{32}$/.test(kodeReg)) {
      errs.kode_register = `Kode Register harus tepat 32 karakter hex (saat ini ${kodeReg.length} karakter)`;
    }

    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      setFormErrors([]);
      // Prioritas gulir ke error pertama (urutan wajar dari atas form).
      const order = ["asset_code", "asset_name", "kode_register", "koordinat_latitude", "koordinat_longitude", "pengguna_jabatan"];
      focusFieldError(order.find(f => errs[f]) || Object.keys(errs)[0]);
      toast.error(`Periksa ${Object.keys(errs).length} field yang belum benar`);
      return;
    }

    // Validate (server round-trip) — skip saat offline: simpan langsung masuk
    // antrean dan backend tetap memvalidasi ulang saat tersinkron. Alur kamera
    // beruntun (camera:*) juga melewatinya supaya "Simpan & Baru" instan —
    // create tetap divalidasi server saat antrean tersinkron, dan bentrok NUP
    // dummy sudah ditangani auto-renumber.
    if (navigator.onLine && !(navIntent || "").startsWith("camera:")) {
      try {
        const url = isEditing && editId ? `${API}/assets/validate?exclude_id=${editId}` : `${API}/assets/validate`;
        const r = await axios.post(url, formData);
        if (!r.data.valid) {
          const serverErrors = Array.isArray(r.data.errors) ? r.data.errors : [];
          // Map errors that identify a field → inline; keep the rest as a summary.
          const mapped = {};
          const unmapped = [];
          for (const msg of serverErrors) {
            const field = mapServerErrorToField(msg);
            if (field && !mapped[field]) mapped[field] = msg;
            else unmapped.push(msg);
          }
          setFieldErrors(mapped);
          setFormErrors(unmapped);
          const firstField = serverErrors.map(mapServerErrorToField).find(Boolean);
          if (firstField) {
            focusFieldError(firstField);
          } else {
            // Server hanya mengirim string generik → pertahankan blok ringkasan,
            // tetap gulir ke atas form agar terlihat.
            setFormSection("basic");
            if (formScrollRef.current) formScrollRef.current.scrollTo({ top: 0, behavior: "smooth" });
          }
          const total = Object.keys(mapped).length + unmapped.length;
          toast.error(Object.keys(mapped).length > 0 ? `Periksa ${total} field yang belum benar` : "Data tidak valid");
          return;
        }
      } catch { /* allow submission if validation endpoint fails */ }
    }

    setIsSubmitting(true);
    
    try {
      let payload;
      let usePatch = false;

      // Alur kamera beruntun: kompresi lokal saja (tanpa round-trip Tinify per
      // foto) supaya scan/navigasi aset berikutnya tidak menunggu jaringan.
      const cameraFlow = (navIntent || "").startsWith("camera:");

      // Status inventarisasi OTOMATIS (default AKTIF): saat foto + koordinat sudah
      // ada dan status masih default "Belum Diinventarisasi", simpan sebagai
      // "Sudah Diinventarisasi". Dihitung SEKALI di sini lalu hanya diterapkan ke
      // PAYLOAD (bukan ke formData) agar validasi di atas tak berubah timing-nya.
      // Karena hanya naik saat koordinat ADA, aturan "inventarisasi wajib
      // koordinat" tetap terpenuhi.
      const hasPhoto = ((photoItems?.length || 0) > 0) || (formData.photos || []).some(Boolean);
      const autoStatus = statusInventarisasiOtomatis({
        inventory_status: formData.inventory_status,
        hasPhoto,
        lat: formData.koordinat_latitude,
        lng: formData.koordinat_longitude,
        enabled: autoInventarisasiEnabled(),
      });

      if (isEditing && editId && originalDataRef.current) {
        // === EDIT MODE: Build diff payload — only send changed fields ===
        const orig = originalDataRef.current;
        const patch = {};

        // Compare text/select fields
        const TEXT_FIELDS = [
          "asset_code", "NUP", "asset_name", "category", "brand", "model",
          "kode_register", "serial_number", "purchase_date", "purchase_price",
          "location", "eselon1", "eselon2", "user", "condition", "status",
          "pengguna_melekat_ke", "pengguna_jabatan", "pengguna_nip", "operasional_jenis", "nomor_bast",
          "nomor_spm", "perolehan_dari_nama", "nomor_kontrak",
          "nomor_bukti_perolehan", "supplier", "notes",
          "stiker_status", "stiker_ukuran",
          "inventory_status", "klasifikasi_tidak_ditemukan", "sub_klasifikasi",
          "uraian_tidak_ditemukan", "tindak_lanjut",
          "koordinat_latitude", "koordinat_longitude", "kronologis",
          "keterangan_berlebih", "asal_usul_berlebih",
          "nomor_perkara", "pihak_bersengketa", "keterangan_sengketa",
          "garansi_hingga", "garansi_jenis",
          "activity_id",
        ];
        for (const key of TEXT_FIELDS) {
          if (String(formData[key] ?? "") !== String(orig[key] ?? "")) {
            patch[key] = formData[key];
          }
        }

        // Terapkan status inventarisasi otomatis ke patch (override hasil loop
        // bila perlu). Hanya dikirim bila berbeda dari nilai asli server.
        if (autoStatus !== (orig.inventory_status ?? "")) patch.inventory_status = autoStatus;
        else delete patch.inventory_status;

        // Compare simple numeric/nullable fields
        if (formData.thumbnail_index !== orig.thumbnail_index) patch.thumbnail_index = formData.thumbnail_index;
        if (formData.stiker_photo_index !== orig.stiker_photo_index) patch.stiker_photo_index = formData.stiker_photo_index;

        // Photos: use photo_ops (server-side manipulation, no full photos sent)
        if (photosModifiedRef.current) {
          const keepIndices = [];
          const newPhotosToAdd = [];
          // Photo strip never built (offline edit from cache — the light
          // fetch never succeeded): photoItems only holds NEW photos, so an
          // empty keep[] would wipe every existing server photo. Preserve
          // them all by index — offline edits can only ADD photos, never remove.
          if (!mediaLoadedRef.current) {
            const known = Number(originalDataRef.current?._photoCount) || 0;
            for (let i = 0; i < known; i++) keepIndices.push(i);
          }
          for (const item of photoItems) {
            if (item.type === 'existing') {
              keepIndices.push(item.originalIndex);
            } else if (item.type === 'new' && item.newData) {
              // Compress new photos before sending (server-side Tinify, dengan
              // fallback kompresi lokal via canvas saat offline/gagal; alur
              // kamera memakai kompresi lokal saja agar tidak menunggu)
              newPhotosToAdd.push(await compressOnePhoto(item.newData, { localOnly: cameraFlow }));
            }
          }
          if (newPhotosToAdd.length > 0) toast.info("Mengompres foto baru...", { duration: 2000 });
          patch.photo_ops = {
            keep: keepIndices,
            add: newPhotosToAdd,
            thumbnail_index: formData.thumbnail_index || 0,
          };
        }

        // Document checklist: only send if modified
        if (checklistModifiedRef.current) {
          const cleanedChecklist = await Promise.all((formData.document_checklist || []).map(async item => {
            // Photos: pass through "__existing__:<idx>" sentinels untouched —
            // the backend will resolve them to the original photo bytes. Only
            // newly added photos (raw data URLs) are compressed.
            const compressedItemPhotos = [];
            for (const photo of (item.photos || [])) {
              if (typeof photo === "string" && photo.startsWith("__existing__:")) {
                compressedItemPhotos.push(photo);
              } else {
                compressedItemPhotos.push(await compressOnePhoto(photo, { localOnly: cameraFlow }));
              }
            }
            // Documents: pass through sentinels untouched. New uploads ship
            // their data URL as before.
            const cleanedDocs = Array.isArray(item.documents) ? item.documents.map(doc => ({
              name: doc.name || "document.pdf",
              data: doc.data || "",
            })) : [];
            return {
              name: item.name || "", checked: Boolean(item.checked), notes: item.notes || "",
              photos: compressedItemPhotos,
              documents: cleanedDocs,
            };
          }));
          patch.document_checklist = cleanedChecklist;
        }

        // Tanpa perubahan: berhenti — KECUALI ini aksi navigasi Kamera Penuh,
        // supaya surveyor tetap bisa berpindah antar aset tersimpan meski tak
        // ada yang diedit (PATCH kosong = no-op di backend).
        if (Object.keys(patch).length === 0 && !navIntent) {
          toast.info("Tidak ada perubahan");
          setIsSubmitting(false);
          return;
        }

        payload = patch;
        usePatch = true;

      } else {
        // === CREATE MODE: Full payload as before ===
        if (!cameraFlow) toast.info("Mengompres foto...", { duration: 2000 });
        const compressedPhotos = await compressPhotos(formData.photos, { localOnly: cameraFlow });
        const coverIdx = formData.thumbnail_index || 0;
        const coverPhoto = compressedPhotos[coverIdx] || compressedPhotos[0] || null;

        const cleanedChecklist = await Promise.all((formData.document_checklist || []).map(async item => ({
          name: item.name || '', checked: Boolean(item.checked), notes: item.notes || '',
          photos: await compressPhotos(item.photos || []),
          documents: Array.isArray(item.documents) ? item.documents.map(doc => ({ name: doc.name || 'document.pdf', data: doc.data || '' })) : []
        })));

        payload = {
          ...formData, inventory_status: autoStatus, photo: coverPhoto, photos: compressedPhotos, document_checklist: cleanedChecklist,
        };
      }
      
      // Check payload size
      const payloadSizeMB = JSON.stringify(payload).length / 1024 / 1024;
      if (payloadSizeMB > 14) {
        toast.error(`Ukuran data terlalu besar (${payloadSizeMB.toFixed(1)}MB). Kurangi jumlah foto.`);
        setIsSubmitting(false);
        return;
      }
      
      // Simpan konteks untuk "Salin dari aset sebelumnya": lokasi/pengguna +
      // KOORDINAT GPS + timestamp (ts). Koordinat dipakai sebagai titik awal
      // cerdas untuk aset berikutnya yang berdekatan; ts menjaga agar salinan
      // koordinat hanya dipakai saat konteks masih baru (lihat salinKonteks).
      try {
        const ctx = {};
        for (const k of ["location", "eselon1", "eselon2", "user"]) {
          if (formData[k]) ctx[k] = formData[k];
        }
        if (formData.koordinat_latitude && formData.koordinat_longitude) {
          ctx.koordinat_latitude = formData.koordinat_latitude;
          ctx.koordinat_longitude = formData.koordinat_longitude;
        }
        if (Object.keys(ctx).length > 0) {
          ctx.ts = Date.now();
          localStorage.setItem("aman_last_asset_ctx", JSON.stringify(ctx));
        }
      } catch {}

      // Optimistic mode: pass payload to parent, close immediately
      if (onOptimisticSubmit || onSaveAndNavigate) {
        const navDirection = navIntent;

        // Kamera Penuh — simpan lalu SIAPKAN ASET BARU (tetap di kamera):
        // form direset ke aset baru (kategori dummy + NUP baru via effect).
        if (navDirection === "camera:new") {
          if (onOptimisticSubmit) onOptimisticSubmit(payload, isEditing, editId, usePatch);
          setCameraSavedCount(c => c + 1);
          if (isEditing) {
            // Sedang meninjau aset lama: minta induk melepas editAsset agar form
            // benar-benar kembali ke mode "aset baru" (hindari editId/isEditing
            // desync). Effect dummy akan mengisi kategori & NUP.
            onExitToNewAsset?.();
          } else {
            resetForm(); // effect dummy mengisi kategori & NUP untuk aset berikutnya
          }
          toast.success("Aset tersimpan — siap foto aset baru");
          setIsSubmitting(false);
          return;
        }
        // Kamera Penuh — simpan lalu TINJAU aset tersimpan sebelumnya (edit).
        if (navDirection === "camera:review") {
          if (onCameraReviewSaved) { onCameraReviewSaved(payload, isEditing, editId, usePatch); setCameraSavedCount(c => c + 1); }
          else if (onOptimisticSubmit) { onOptimisticSubmit(payload, isEditing, editId, usePatch); resetForm(); onClose?.(); }
          setIsSubmitting(false);
          return;
        }

        if (navDirection && onSaveAndNavigate) {
          onSaveAndNavigate(payload, isEditing, editId, navDirection, usePatch);
          // Don't call resetForm() here — onSaveAndNavigate is async (awaits lockAsset),
          // so resetForm would clear the form BEFORE the next asset is set.
          // The useEffect will handle reset when editAsset changes to the next row.
          setIsSubmitting(false);
          return;
        }

        if (onOptimisticSubmit) {
          onOptimisticSubmit(payload, isEditing, editId, usePatch);
          resetForm();
          onClose?.();
          setIsSubmitting(false);
          return;
        }
      }
      
      if (isEditing && editId) {
        const auditHeaders = getAuditHeaders();
        if (usePatch) {
          await axiosLargeUpload.patch(`${API}/assets/${editId}`, payload, { headers: auditHeaders });
        } else {
          await axiosLargeUpload.put(`${API}/assets/${editId}`, payload, { headers: auditHeaders });
        }
        toast.success("Aset diupdate");
      } else {
        await axiosLargeUpload.post(`${API}/assets`, payload, { headers: getAuditHeaders() });
        toast.success("Aset ditambahkan");
      }
      resetForm();
      onSubmitSuccess?.();
      onClose?.();
    } catch (err) {
      let errorMsg = "Gagal menyimpan";
      if (err.response?.data?.detail) {
        errorMsg = getApiError(err, errorMsg);
      }
      else if (err.code === 'ECONNABORTED') errorMsg = "Koneksi timeout. Coba kurangi ukuran file.";
      toast.error(errorMsg);
    } finally { setIsSubmitting(false); }
  }, [formData, isEditing, editId, isFormLoading, resetForm, onSubmitSuccess, onOptimisticSubmit, onSaveAndNavigate, onCameraReviewSaved, onExitToNewAsset, onClose, focusFieldError]);

  // — Aksi alur beruntun Mode Kamera Penuh (semua lewat handleSubmit agar
  //   validasi + kompresi + payload tetap konsisten) —
  // Guard sinkron: cegah ketuk ganda cepat yang bisa meng-enqueue 2 aset kembar
  // (isSubmitting berbasis state tidak cukup cepat untuk balapan tap).
  const cameraSubmitBusyRef = useRef(false);
  const submitWithIntent = useCallback((intent) => {
    if (cameraSubmitBusyRef.current) return;
    cameraSubmitBusyRef.current = true;
    navigationIntentRef.current = intent;
    Promise.resolve(handleSubmit({ preventDefault: () => {} }))
      .finally(() => { cameraSubmitBusyRef.current = false; });
  }, [handleSubmit]);
  const cameraSaveAndNew = useCallback(() => submitWithIntent("camera:new"), [submitWithIntent]);
  // ◀ Sebelumnya di Mode Kamera Penuh (aset baru): kalau SUDAH ada foto, nama
  // pasti terisi (rana terkunci sampai nama diisi) → simpan lalu tinjau. Kalau
  // BELUM ada foto, langsung tinjau aset sebelumnya TANPA validasi/simpan
  // (mencegah error "wajib isi" yang membuat tombol tak bisa berpindah).
  const cameraReviewSaved = useCallback(() => {
    if (!isEditing && (formData.photos?.length || 0) === 0) {
      onCameraReviewSaved?.(null, isEditing, editId, false, true); // navigateOnly
    } else {
      submitWithIntent("camera:review");
    }
  }, [submitWithIntent, onCameraReviewSaved, isEditing, editId, formData.photos]);
  const cameraNavigate = useCallback((dir) => submitWithIntent(dir), [submitWithIntent]); // 'prev' | 'next'
  // Scan QR dari Mode Kamera: simpan perubahan aset saat ini dulu (jalur sama
  // dengan navigasi), lalu induk mencari & membuka aset hasil scan.
  const cameraScanAsset = useCallback((code) => submitWithIntent(`camera:scan:${code}`), [submitWithIntent]);
  // Simpan aset saat ini TANPA berpindah (form & kamera tetap di aset ini) —
  // dipakai tombol "Simpan & Scan" sebelum scanner dibuka lagi.
  const cameraSaveStay = useCallback(() => submitWithIntent("camera:stay"), [submitWithIntent]);

  // Tampilan eksklusif inventarisasi lapangan menggantikan seluruh body form.
  const sheetMode = inventoryMode && isEditing && !showFullForm;

  // "Simpan & Lanjut" bermakna bila masih ada aset berikutnya DI daftar, ATAU
  // masih ada halaman berikutnya yang bisa dimuat (hasMoreToLoad) — sehingga
  // menyimpan baris terakhir yang dimuat tetap melanjutkan ritme ke halaman
  // berikutnya (pemanggil memuatnya lalu membuka aset pertamanya).
  // Guard ini identik dengan onClick tombol submit form penuh di bawah.
  const canSaveNext = isEditing && !!onSaveAndNavigate && assetIndex >= 0
    && (assetIndex < totalAssetsInView - 1 || hasMoreToLoad);
  const queueNextIntent = useCallback(() => {
    if (isEditing && onSaveAndNavigate && assetIndex >= 0
        && (assetIndex < totalAssetsInView - 1 || hasMoreToLoad)) {
      navigationIntentRef.current = 'next';
    }
  }, [isEditing, onSaveAndNavigate, assetIndex, totalAssetsInView, hasMoreToLoad]);

  const filteredCategories = useMemo(() => {
    const cats = Array.isArray(categories) ? categories : [];
    if (!categorySearch) return cats.slice(0, 200);
    const s = categorySearch.toLowerCase();
    return cats.filter(c => (c.label||'').toLowerCase().includes(s) || (c.kode_aset||'').toLowerCase().includes(s)).slice(0, 200);
  }, [categories, categorySearch]);

  // Inline error helpers: red border on the input + a small helper line under it.
  const fieldErrCls = (name) => fieldErrors[name] ? " border-red-500 dark:border-red-500 focus-visible:ring-red-500" : "";
  const renderFieldError = (name) => fieldErrors[name] ? (
    <p className="text-[11px] text-red-600 dark:text-red-400 mt-0.5" data-testid={`field-error-${name}`}>{fieldErrors[name]}</p>
  ) : null;

  return (
    <>
      {isOpen && !alwaysExpanded && <div className="fixed inset-0 bg-black/40 z-30 lg:hidden" onClick={onClose} />}

      {/* Dialog pilihan saat Tambah Aset Baru di mode inventarisasi */}
      {cameraPromptOpen && createPortal(
        <div className="fixed inset-0 z-[115] bg-black/60 flex items-center justify-center p-6" data-testid="camera-choice-dialog">
          <div className="bg-card rounded-2xl p-5 w-full max-w-sm space-y-3 shadow-2xl">
            <div className="flex items-center gap-2.5">
              <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center flex-shrink-0">
                <Camera className="w-5 h-5 text-white" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-foreground">Masuk Mode Kamera Penuh?</h3>
                <p className="text-[11px] text-muted-foreground">Kamera fullscreen dengan jam & GPS live, info aset, edit info, dan hapus foto — tanpa keluar dari kamera.</p>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-2">
              <button type="button" data-testid="camera-choice-full"
                onClick={() => { setCameraPromptOpen(false); openFullCamera(); }}
                className="h-11 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold flex items-center justify-center gap-1.5 transition-colors">
                <Camera className="w-4 h-4" />Mode Kamera Penuh
              </button>
              <button type="button" data-testid="camera-choice-form"
                onClick={() => setCameraPromptOpen(false)}
                className="h-11 rounded-lg border border-border bg-background text-foreground/80 hover:bg-accent text-sm font-medium transition-colors">
                Isi Form Biasa
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* Mode Kamera Penuh ala Timemark */}
      {fullCameraOpen && (
        <FullCameraSheet
          formData={formData}
          photos={isEditing ? photoItems.map(it => it.thumbnail) : formData.photos}
          isEditing={isEditing}
          assetIndex={assetIndex}
          totalAssetsInView={totalAssetsInView}
          hasMoreToLoad={hasMoreToLoad}
          savedCount={cameraSavedCount}
          busy={isSubmitting || isFormLoading}
          preparing={isFormLoading || isSubmitting || (!isEditing && !!formData.category && !formData.NUP)}
          onClose={closeFullCamera}
          onCapture={addCameraPhoto}
          onRemovePhoto={removePhoto}
          onSetField={cameraSetField}
          onGpsFix={handleCameraGpsFix}
          onSaveAndNew={cameraSaveAndNew}
          onReviewSaved={onCameraReviewSaved ? cameraReviewSaved : undefined}
          onNavigate={cameraNavigate}
          onScanAsset={isEditing && inventoryMode && onSaveAndNavigate ? cameraScanAsset : undefined}
          onSaveAndScanNext={isEditing && inventoryMode && onSaveAndNavigate ? cameraSaveStay : undefined}
          autoScan={cameraAutoScan}
        />
      )}
      <aside
        className={`${alwaysExpanded ? 'translate-x-0' : (isOpen ? "translate-x-0" : "-translate-x-full")} ${alwaysExpanded ? 'relative w-full' : 'fixed lg:relative inset-y-0 left-0 z-40 lg:z-auto w-[85vw] sm:w-80 xl:w-96'} bg-card border-r border-border transition-transform duration-300 print:hidden shadow-2xl lg:shadow-none flex flex-col overflow-hidden h-full`}
      >
        {/* Header */}
        <div className={`p-3 border-b-2 flex justify-between items-center flex-shrink-0 ${isEditing ? "bg-amber-50 dark:bg-amber-900/20 border-amber-300 dark:border-amber-700" : "bg-blue-50 dark:bg-blue-900/20 border-blue-300 dark:border-blue-700"}`}>
          <div className="flex items-center gap-2">
            <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${isEditing ? "bg-amber-500" : "bg-blue-600"}`}>
              {isEditing ? <Edit3 className="w-3.5 h-3.5 text-white" /> : <Plus className="w-3.5 h-3.5 text-white" />}
            </div>
            <div>
              <h2 className={`font-bold text-sm ${isEditing ? "text-amber-900 dark:text-amber-300" : "text-blue-900 dark:text-blue-300"}`}>
                {isEditing ? "Edit Aset" : "Tambah Aset Baru"}
              </h2>
              {isEditing && <p className="text-[10px] text-amber-600 dark:text-amber-400 truncate max-w-[160px]">{formData.asset_code}</p>}
            </div>
          </div>
          <div className="flex items-center gap-1">
            {isEditing && onOpenKartu && (
              <Button
                type="button" variant="ghost" size="sm"
                className="h-7 gap-1 px-2 text-[10px] text-emerald-700 dark:text-emerald-400 hover:bg-emerald-100 hover:text-emerald-800 dark:hover:bg-emerald-900/40 dark:hover:text-emerald-300"
                onClick={() => onOpenKartu({
                  kode_register: formData.kode_register,
                  asset_code: formData.asset_code,
                  NUP: formData.NUP,
                  asset_name: formData.asset_name,
                })}
                title="Riwayat pengesahan aset ini lintas kegiatan"
                data-testid="asset-form-kartu-btn"
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Kartu</span>
              </Button>
            )}
            {isEditing && onOpenTimeline && editAsset?.id && (
              <Button
                type="button" variant="ghost" size="sm"
                className="h-7 gap-1 px-2 text-[10px] text-violet-700 dark:text-violet-400 hover:bg-violet-100 hover:text-violet-800 dark:hover:bg-violet-900/40 dark:hover:text-violet-300"
                onClick={() => onOpenTimeline(editAsset.id)}
                title="Timeline perlakuan aset ini lintas modul"
                data-testid="asset-form-timeline-btn"
              >
                <History className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Timeline</span>
              </Button>
            )}
            {!alwaysExpanded && <Button variant="ghost" size="sm" className="lg:hidden h-7 w-7 p-0" onClick={onClose}><X className="w-4 h-4" /></Button>}
          </div>
        </div>

        {/* Tabs — disembunyikan pada mode inventarisasi lapangan (sheet) */}
        {!sheetMode && <div className="flex border-b border-border bg-muted flex-shrink-0">
          {[
            { key: "basic", label: "Info Dasar", icon: Package },
            { key: "procurement", label: "Pengadaan", icon: Briefcase },
            { key: "documents", label: "Dokumen", icon: ShieldCheck }
          ].map(t => (
            <button key={t.key} type="button" onClick={() => setFormSection(t.key)}
              className={`flex-1 flex items-center justify-center gap-1 py-2 text-xs font-medium border-b-2 ${
                formSection === t.key ? 'border-blue-600 text-blue-700 bg-card' : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <t.icon className="w-3.5 h-3.5" /><span className="hidden sm:inline">{t.label}</span>
            </button>
          ))}
        </div>}

        {/* Loading Skeleton */}
        {isFormLoading && (
          <div className="flex-1 overflow-y-auto p-3 space-y-3 animate-pulse" data-testid="form-loading-skeleton">
            <div className="space-y-1.5">
              <div className="h-3 w-20 bg-muted rounded" />
              <div className="h-8 bg-muted rounded" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5"><div className="h-3 w-12 bg-muted rounded" /><div className="h-8 bg-muted rounded" /></div>
              <div className="space-y-1.5"><div className="h-3 w-24 bg-muted rounded" /><div className="h-8 bg-muted rounded" /></div>
            </div>
            <div className="space-y-1.5"><div className="h-3 w-20 bg-muted rounded" /><div className="h-8 bg-muted rounded" /></div>
            <div className="space-y-1.5"><div className="h-3 w-16 bg-muted rounded" /><div className="h-8 bg-muted rounded" /></div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5"><div className="h-3 w-10 bg-muted rounded" /><div className="h-8 bg-muted rounded" /></div>
              <div className="space-y-1.5"><div className="h-3 w-10 bg-muted rounded" /><div className="h-8 bg-muted rounded" /></div>
            </div>
            <div className="space-y-1.5"><div className="h-3 w-24 bg-muted rounded" /><div className="h-8 bg-muted rounded" /></div>
            <div className="space-y-1.5"><div className="h-3 w-12 bg-muted rounded" /><div className="h-8 bg-muted rounded" /></div>
            <div className="flex gap-1.5 pt-2">
              <div className="w-14 h-14 bg-muted rounded" />
              <div className="w-14 h-14 bg-muted rounded" />
              <div className="w-14 h-14 bg-muted rounded border-2 border-dashed border-muted-foreground/20" />
            </div>
            <div className="flex items-center justify-center gap-2 pt-4 text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="text-xs">Memuat data aset...</span>
            </div>
          </div>
        )}

        {/* Errors */}
        {!isFormLoading && formErrors.length > 0 && (
          <div className="mx-3 mt-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg p-2 flex-shrink-0">
            <p className="text-xs font-medium text-red-700 dark:text-red-400 mb-1">Validasi gagal:</p>
            {formErrors.map((e, i) => <p key={i} className="text-[11px] text-red-600 dark:text-red-400">{e}</p>)}
          </div>
        )}

        {/* Offline: form initialized from the cached list row */}
        {!isFormLoading && isEditing && offlineNotice && (
          <div className="mx-3 mt-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg px-2.5 py-1.5 flex items-start gap-1.5 flex-shrink-0" data-testid="offline-form-notice">
            <CloudOff className="w-3.5 h-3.5 mt-0.5 text-amber-600 dark:text-amber-400 flex-shrink-0" />
            <p className="text-[11px] leading-snug text-amber-700 dark:text-amber-300">
              Data dimuat dari cache offline — foto &amp; checklist penuh tidak tersedia sampai online. Perubahan tetap bisa disimpan dan akan disinkronkan otomatis.
            </p>
          </div>
        )}

        {/* Sinkronisasi SIMAN V2: aset ini berbeda dengan data SIMAN (valid).
            Rincian + arah sinkron; tindakan "terapkan" ada di Pelaporan ›
            Sinkronisasi SIMAN agar tidak bentrok dengan draft form ini. */}
        {!isFormLoading && isEditing && editAsset?.siman?.status === "selisih" && (
          <div className="mx-3 mt-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg px-2.5 py-1.5 flex-shrink-0" data-testid="siman-form-banner">
            <p className="text-[11px] font-semibold text-amber-700 dark:text-amber-300">
              ≠ SIMAN — {(editAsset.siman.selisih || []).length} field berbeda dengan data SIMAN V2
            </p>
            <ul className="mt-0.5 space-y-0.5">
              {(editAsset.siman.selisih || []).slice(0, 6).map((s) => (
                <li key={s.field} className="text-[10px] leading-snug text-amber-700/90 dark:text-amber-300/90">
                  {s.label}: <span className="line-through opacity-70">{s.aman || "(kosong)"}</span> → <b>{s.siman || "(kosong)"}</b>
                </li>
              ))}
              {(editAsset.siman.selisih || []).length > 6 && (
                <li className="text-[10px] text-amber-700/70 dark:text-amber-300/70">… dan {(editAsset.siman.selisih || []).length - 6} field lain</li>
              )}
            </ul>
            <p className="text-[10px] mt-1 text-amber-700/80 dark:text-amber-300/80">
              Sinkronkan lewat menu <b>Pelaporan › Sinkronisasi SIMAN V2</b> (nilai SIMAN = data valid), atau perbaiki manual di form ini.
            </p>
          </div>
        )}
        {!isFormLoading && isEditing && editAsset?.siman?.status === "tidak_di_siman" && (
          <div className="mx-3 mt-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg px-2.5 py-1.5 flex-shrink-0" data-testid="siman-form-banner-hilang">
            <p className="text-[11px] font-semibold text-red-700 dark:text-red-300">
              Tidak ditemukan di SIMAN V2 (impor {String(editAsset.siman.diperiksa_pada || "").slice(0, 10)})
            </p>
            <p className="text-[10px] mt-0.5 text-red-700/80 dark:text-red-300/80">
              Periksa: aset belum tercatat di SIMAN, sudah dihapuskan, atau kode barang/NUP-nya berubah (reklasifikasi).
            </p>
          </div>
        )}

        {/* Mode inventarisasi lapangan — sheet eksklusif menggantikan body form.
            Dirender di dalam <form onSubmit={handleSubmit}> agar tombol submit
            sheet memakai jalur simpan/validasi yang sama persis. */}
        {!isFormLoading && sheetMode && (
          <form onSubmit={handleSubmit} className="flex-1 flex flex-col overflow-hidden min-h-0">
            <InventoryFieldSheet
              formData={formData}
              photoItems={photoItems}
              photoCount={currentPhotoCount}
              isSubmitting={isSubmitting}
              gpsLoading={gpsLoading}
              lastCtx={lastCtx}
              assetIndex={assetIndex}
              totalAssetsInView={totalAssetsInView}
              canSaveNext={canSaveNext}
              onInputChange={handleInputChange}
              onInventoryStatusChange={handleInventoryStatusChange}
              onConditionChange={v => handleSelectChange("condition", v)}
              onKlasifikasiChange={handleKlasifikasiChange}
              onSubKlasifikasiChange={v => handleSelectChange("sub_klasifikasi", v)}
              onStikerStatusChange={handleStikerStatusChange}
              onStikerUkuranChange={v => handleSelectChange("stiker_ukuran", v)}
              onPenggunaMelekatChange={handlePenggunaMelekatChange}
              onOperasionalJenisChange={handleOperasionalJenisChange}
              onOpenCamera={openCamera}
              onOpenFullCamera={openFullCamera}
              onOpenFullCameraScan={openFullCameraScan}
              onOpenGallery={openGallery}
              onFetchGPS={fetchGPS}
              onApplyLastCtx={applyLastCtx}
              onQueueNextIntent={queueNextIntent}
              onShowFullForm={() => setShowFullForm(true)}
            />
            <input ref={fileInputRef} type="file" accept="image/*" multiple onChange={handleImageChange} className="hidden" />
            <input ref={cameraInputRef} type="file" accept="image/*" capture="environment" onChange={handleImageChange} className="hidden" />
          </form>
        )}

        {/* Form */}
        {!isFormLoading && !sheetMode && <div ref={formScrollRef} className="flex-1 overflow-y-auto">
          <form onSubmit={handleSubmit} className="p-3 space-y-2.5">
            {/* Mode inventarisasi: kembali ke tampilan cepat dari form lengkap */}
            {inventoryMode && isEditing && showFullForm && (
              <button
                type="button"
                onClick={() => setShowFullForm(false)}
                data-testid="back-to-quick-mode"
                className="w-full h-9 flex items-center justify-center gap-1.5 rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 text-xs font-semibold hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />Kembali ke Mode Cepat
              </button>
            )}
            {formSection === "basic" && (<>
              <div className="space-y-1">
                <Label className="text-xs">Kode Aset *</Label>
                {(() => {
                  const kodeLocked = !!categories.find(c => c.kode_aset && c.label === formData.category);
                  return (
                    <div className="flex gap-1.5">
                      <Input name="asset_code" value={formData.asset_code} onChange={handleInputChange} placeholder="Cari di referensi atau ketik kode" required className={`h-8 bg-muted flex-1 min-w-0${fieldErrCls("asset_code")}`} readOnly={kodeLocked} aria-invalid={!!fieldErrors.asset_code} />
                      {!kodeLocked && (
                        <DropdownMenu open={kodePickerOpen} onOpenChange={setKodePickerOpen}>
                          <DropdownMenuTrigger asChild>
                            <button type="button" title="Cari kode barang di referensi kodefikasi" className="h-8 px-2.5 rounded-md border border-input bg-card hover:bg-accent flex items-center gap-1 text-xs shrink-0" data-testid="asset-code-picker">
                              <Search className="w-3.5 h-3.5" /><span className="hidden sm:inline">Referensi</span>
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent className="w-[calc(100vw-3rem)] max-w-sm">
                            <div className="p-2">
                              <Input placeholder="Cari kode / nama barang…" value={kodeQuery} onChange={e => setKodeQuery(e.target.value)} className="h-8 mb-2" data-testid="asset-code-picker-search" />
                              <ScrollArea className="h-56">
                                {kodeResults === null ? (
                                  <div className="text-xs text-center text-muted-foreground py-3">Referensi tak tersedia (offline). Ketik kode manual.</div>
                                ) : kodeLoading ? (
                                  <div className="text-xs text-center text-muted-foreground py-3">Memuat…</div>
                                ) : kodeResults.length === 0 ? (
                                  <div className="text-xs text-center text-muted-foreground py-3">{kodeQuery.trim() ? "Tidak ditemukan" : "Ketik untuk mencari kode barang"}</div>
                                ) : kodeResults.map(it => (
                                  <button type="button" key={it.kode} onClick={() => onPickKode(it)} className="w-full text-left px-2 py-1.5 rounded hover:bg-accent flex items-start gap-2 min-w-0" data-testid={`asset-code-opt-${it.kode}`}>
                                    <span className="font-mono text-xs text-foreground shrink-0">{it.kode}</span>
                                    <span className="flex-1 min-w-0">
                                      <span className="block text-xs text-foreground/90 break-words">{it.uraian}</span>
                                      <span className="block text-[10px] text-muted-foreground">{it.level} {it.label_level}{it.meta?.satuan ? ` · ${it.meta.satuan}` : ""}{it.is_persediaan ? " · persediaan" : ""}</span>
                                    </span>
                                    {formData.asset_code === it.kode && <Check className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />}
                                  </button>
                                ))}
                              </ScrollArea>
                            </div>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </div>
                  );
                })()}
                {renderFieldError("asset_code")}
                {/* Peringatan kodefikasi LIVE (non-blocking, §5A Prinsip 2) —
                    tak menghalangi simpan; hanya mengingatkan agar referensi
                    kodefikasi dilengkapi. Sembunyi bila field error sudah ada. */}
                {kodefikasiWarn && !fieldErrors.asset_code && (
                  <p className="text-[10px] text-amber-600 dark:text-amber-400 flex items-start gap-1" data-testid="kodefikasi-warning">
                    <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                    <span>{kodefikasiWarn.pesan}</span>
                  </p>
                )}
                {/* Konfirmasi positif: kode terdaftar penuh → nama resmi referensi. */}
                {!kodefikasiWarn && !fieldErrors.asset_code && kodeRefNama && (
                  <p className="text-[10px] text-emerald-600 dark:text-emerald-400 flex items-start gap-1" data-testid="kodefikasi-ok">
                    <Check className="w-3 h-3 mt-0.5 flex-shrink-0" />
                    <span>Terhubung ke referensi: {kodeRefNama}</span>
                  </p>
                )}
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1 min-w-0"><Label className="text-xs">NUP</Label><Input name="NUP" value={formData.NUP} onChange={handleInputChange} placeholder="1" className="h-8" /></div>
                <div className="space-y-1 min-w-0"><Label className="text-xs">Serial Number</Label><Input name="serial_number" value={formData.serial_number} onChange={handleInputChange} className="h-8" /></div>
              </div>
              <div className="space-y-1"><Label className="text-xs">Nama Aset *</Label><Input name="asset_name" value={formData.asset_name} onChange={handleInputChange} required className={`h-8${fieldErrCls("asset_name")}`} aria-invalid={!!fieldErrors.asset_name} />{renderFieldError("asset_name")}</div>
              
              {/* Category */}
              <div className="space-y-1">
                <div className="flex justify-between items-center">
                  <Label className="text-xs">Kategori *</Label>
                  <Button type="button" variant="ghost" size="sm" onClick={onShowCategoryManager} className="h-5 w-5 p-0"><Settings className="w-3 h-3" /></Button>
                </div>
                <DropdownMenu open={categoryDropdownOpen} onOpenChange={setCategoryDropdownOpen}>
                  <DropdownMenuTrigger asChild>
                    <button type="button" className="flex items-start px-3 py-2 text-sm bg-card hover:bg-accent w-full min-h-[32px] border rounded-md">
                      <div className="flex-1 overflow-x-auto min-w-0 pb-0.5">
                        <span className="whitespace-nowrap text-left block text-xs">
                          {formData.category ? `${categories.find(c => c.label === formData.category)?.kode_aset || ''} ${formData.category}`.trim() : 'Pilih kategori'}
                        </span>
                      </div>
                      <ChevronDown className="w-3.5 h-3.5 flex-shrink-0 ml-2 mt-0.5" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent className="w-[calc(100vw-3rem)] max-w-sm">
                    <div className="p-2">
                      <Input placeholder="Cari kode/deskripsi..." value={categorySearch} onChange={e => setCategorySearch(e.target.value)} className="h-8 mb-2" />
                      <ScrollArea className="h-48">
                        {filteredCategories.map(c => (
                          <DropdownMenuItem key={c.id} onClick={() => {
                            handleSelectChange("category", c.label);
                            if (c.kode_aset) { setFormData(p => ({ ...p, asset_code: c.kode_aset })); clearFieldError("asset_code"); }
                            // Kategori "dummy": NUP dinomori otomatis (max+1 dalam
                            // lingkup kode aset + kegiatan, sesuai kunci unik backend).
                            if (/dummy/i.test(c.label || "")) {
                              const params = new URLSearchParams({ activity_id: activity?.id || "" });
                              if (c.kode_aset) params.set("asset_code", c.kode_aset);
                              else params.set("category", c.label);
                              axios.get(`${API}/assets/next-nup?${params}`)
                                .then(res => {
                                  const next = res?.data?.next_nup;
                                  if (next) setFormData(p => p.NUP ? p : { ...p, NUP: next });
                                })
                                .catch(() => {});
                            }
                            setCategoryDropdownOpen(false); setCategorySearch("");
                          }} className="flex items-start">
                            <span className="break-words text-xs leading-snug flex-1">{c.kode_aset ? `${c.kode_aset} - ${c.label}` : c.label}</span>
                            {formData.category === c.label && <Check className="w-3.5 h-3.5 text-blue-600 ml-2 flex-shrink-0 mt-0.5" />}
                          </DropdownMenuItem>
                        ))}
                        {filteredCategories.length === 0 && <div className="text-xs text-center text-muted-foreground py-2">Tidak ditemukan</div>}
                      </ScrollArea>
                    </div>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
              
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1 min-w-0"><Label className="text-xs">Brand</Label><Input name="brand" value={formData.brand} onChange={handleInputChange} className="h-8" /></div>
                <div className="space-y-1 min-w-0"><Label className="text-xs">Model</Label><Input name="model" value={formData.model} onChange={handleInputChange} className="h-8" /></div>
              </div>
              <div className="space-y-1"><Label className="text-xs">Kode Register</Label><Input name="kode_register" value={formData.kode_register} onChange={handleInputChange} placeholder="32 karakter hex" maxLength={32} className="h-8" /></div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1"><Label className="text-xs">Tanggal Beli</Label><Input type="date" name="purchase_date" value={formData.purchase_date} onChange={handleInputChange} className="h-8" /></div>
                <div className="space-y-1"><Label className="text-xs">Harga (Rp)</Label><Input type="number" name="purchase_price" value={formData.purchase_price} onChange={handleInputChange} className="h-8" /></div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label className="text-xs">Garansi hingga{garansiOtomatis ? <span className="ml-1 text-[10px] text-sky-600 dark:text-sky-400 font-normal">otomatis</span> : null}</Label>
                  <Input type="date" name="garansi_hingga" value={formData.garansi_hingga || ""} onChange={handleInputChange} className="h-8" data-testid="asset-garansi" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Jenis garansi</Label>
                  <Input name="garansi_jenis" value={formData.garansi_jenis || ""} onChange={handleInputChange} list="garansi-jenis-opsi" placeholder="mis. Pabrikan" className="h-8" data-testid="asset-garansi-jenis" />
                  <datalist id="garansi-jenis-opsi">
                    {["Pabrikan", "Distributor", "Toko", "Purna Jual", "Lainnya"].map((j) => <option key={j} value={j} />)}
                  </datalist>
                </div>
                <p className="text-[10px] text-muted-foreground col-span-2 -mt-1">Tanggal berakhir garansi (rentang lazim sejak tanggal perolehan) + jenis/tipenya. Kosongkan bila tidak ada.</p>
              </div>
              <div className="space-y-1"><Label className="text-xs">Lokasi</Label><Input name="location" value={formData.location} onChange={handleInputChange} className="h-8" list="daftar-ruangan-master" placeholder="pilih ruangan / ketik bebas" /><datalist id="daftar-ruangan-master">{ruanganNames.map((n) => <option key={n} value={n} />)}</datalist></div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1"><Label className="text-xs">Eselon I</Label>
                  <select name="eselon1" value={formData.eselon1} onChange={e => { handleInputChange(e); setFormData(p => ({...p, eselon2: ''})); }} className="w-full h-8 px-2 rounded-md border border-input bg-background text-sm" data-testid="asset-eselon1-select">
                    <option value="">-- Pilih Eselon I --</option>
                    {(activity?.eselon1 || []).map((es, i) => {
                      const nama = typeof es === 'object' ? es.nama : es;
                      return <option key={i} value={nama}>{nama}</option>;
                    })}
                  </select>
                </div>
                <div className="space-y-1"><Label className="text-xs">Eselon II</Label>
                  <select name="eselon2" value={formData.eselon2} onChange={handleInputChange} className="w-full h-8 px-2 rounded-md border border-input bg-background text-sm" data-testid="asset-eselon2-select">
                    <option value="">-- Pilih Eselon II --</option>
                    {(() => {
                      const sel = (activity?.eselon1 || []).find(es => (typeof es === 'object' ? es.nama : es) === formData.eselon1);
                      return (sel && typeof sel === 'object' ? sel.eselon2 || [] : []).map((e2, i) => <option key={i} value={e2}>{e2}</option>);
                    })()}
                  </select>
                </div>
              </div>
              {/* Pengguna — melekat ke Individual/Jabatan/Operasional + BAST */}
              <div className="p-2 bg-muted rounded-lg space-y-2" data-testid="pengguna-section">
                <div className="flex items-center gap-1.5"><UserRound className="w-3.5 h-3.5 text-muted-foreground" /><Label className="text-xs font-medium">Pengguna</Label></div>
                <div className="space-y-1">
                  <Label className="text-[10px] text-muted-foreground">Melekat ke</Label>
                  <div className="grid grid-cols-3 gap-1.5">
                    {PENGGUNA_MELEKAT_OPTIONS.map(o => (
                      <button
                        key={o} type="button"
                        aria-pressed={formData.pengguna_melekat_ke === o}
                        onClick={() => handlePenggunaMelekatChange(o)}
                        data-testid={`pengguna-melekat-${o}`}
                        className={`h-7 rounded-md border text-[10px] font-semibold leading-tight px-1 transition-colors ${
                          formData.pengguna_melekat_ke === o
                            ? "bg-blue-600 border-blue-600 text-white"
                            : "bg-card border-border text-foreground/80 hover:bg-accent"
                        }`}
                      >
                        {o}
                      </button>
                    ))}
                  </div>
                </div>
                {formData.pengguna_melekat_ke === "Jabatan" && (
                  <div className="space-y-1">
                    <Label className="text-xs">Nama Jabatan *</Label>
                    <Input name="pengguna_jabatan" value={formData.pengguna_jabatan} onChange={handleInputChange} placeholder="Contoh: Kepala Subbagian Umum" className={`h-8${fieldErrCls("pengguna_jabatan")}`} aria-invalid={!!fieldErrors.pengguna_jabatan} data-testid="input-pengguna-jabatan" />
                    {renderFieldError("pengguna_jabatan")}
                  </div>
                )}
                {formData.pengguna_melekat_ke === "Operasional" && (
                  <div className="space-y-1">
                    <Label className="text-xs">Jenis Operasional</Label>
                    <div className="grid grid-cols-2 gap-1.5">
                      {OPERASIONAL_JENIS_OPTIONS.map(o => (
                        <button
                          key={o} type="button"
                          aria-pressed={formData.operasional_jenis === o}
                          onClick={() => handleOperasionalJenisChange(o)}
                          data-testid={`operasional-jenis-${o}`}
                          className={`h-7 rounded-md border text-[10px] font-semibold leading-tight px-1 transition-colors ${
                            formData.operasional_jenis === o
                              ? "bg-blue-600 border-blue-600 text-white"
                              : "bg-card border-border text-foreground/80 hover:bg-accent"
                          }`}
                        >
                          {o}
                        </button>
                      ))}
                    </div>
                    <p className="text-[9px] text-muted-foreground italic">Ruangan = barang harus tetap berada di ruang tersebut.</p>
                  </div>
                )}
                <div className="space-y-1">
                  <Label className="text-xs">{PENGGUNA_NAME_LABELS[formData.pengguna_melekat_ke] || "Pengguna"}</Label>
                  <div className="flex gap-1.5">
                    <Input name="user" value={formData.user} onChange={handleInputChange} className="h-8 flex-1 min-w-0" data-testid="input-pengguna-nama" />
                    {/* Tap kartu e-KTP → pegawai terisi otomatis (identifikasi cepat) */}
                    <button type="button" title="Tap kartu pegawai (e-KTP/NFC)"
                      onClick={() => setKartuTapOpen(true)}
                      className="h-8 px-2 rounded-md border border-input bg-card hover:bg-accent flex items-center shrink-0 min-w-0 min-h-0"
                      data-testid="pengguna-tap-kartu">
                      <IdCard className="w-3.5 h-3.5 text-blue-600" />
                    </button>
                    <DropdownMenu open={pegawaiPickerOpen} onOpenChange={setPegawaiPickerOpen}>
                      <DropdownMenuTrigger asChild>
                        <button type="button" title="Pilih dari Master Pegawai" className="h-8 px-2.5 rounded-md border border-input bg-card hover:bg-accent flex items-center gap-1 text-xs shrink-0" data-testid="pengguna-pegawai-picker">
                          <Search className="w-3.5 h-3.5" /><span className="hidden sm:inline">Pegawai</span>
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent className="w-[calc(100vw-3rem)] max-w-sm">
                        <div className="p-2">
                          <Input placeholder="Cari nama / NIP pegawai…" value={pegawaiQuery} onChange={e => setPegawaiQuery(e.target.value)} className="h-8 mb-2" data-testid="pengguna-pegawai-search" />
                          <ScrollArea className="h-56">
                            {pegawaiResults === null ? (
                              <div className="text-xs text-center text-muted-foreground py-3">Master Pegawai tak tersedia (offline). Ketik manual.</div>
                            ) : pegawaiResults === undefined ? (
                              <div className="text-xs text-center text-muted-foreground py-3">Memuat…</div>
                            ) : pegawaiResults.length === 0 ? (
                              <div className="text-xs text-center text-muted-foreground py-3">{pegawaiQuery.trim() ? "Tidak ditemukan" : "Belum ada pegawai di master"}</div>
                            ) : pegawaiResults.map(p => (
                              <button type="button" key={p.id || p.nip} onClick={() => onPickPegawai(p)} className="w-full text-left px-2 py-1.5 rounded hover:bg-accent flex items-start gap-2 min-w-0" data-testid={`pengguna-pegawai-opt-${p.nip || p.id}`}>
                                <span className="flex-1 min-w-0">
                                  <span className="block text-xs text-foreground/90 break-words">{p.nama}</span>
                                  <span className="block text-[10px] text-muted-foreground font-mono">{p.nip || "tanpa NIP"}{p.jabatan ? ` · ${p.jabatan}` : ""}{p.unit_kerja ? ` · ${p.unit_kerja}` : ""}</span>
                                </span>
                                {(formData.pengguna_nip && p.nip === formData.pengguna_nip) && <Check className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />}
                              </button>
                            ))}
                          </ScrollArea>
                        </div>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">NIP/NIK Pegawai</Label>
                  <Input name="pengguna_nip" value={formData.pengguna_nip} onChange={handleInputChange} placeholder="NIP/NIK pegawai pengguna" className="h-8" data-testid="input-pengguna-nip" />
                  {penggunaNipWarn && (
                    <p className="text-[10px] text-amber-600 dark:text-amber-400 flex items-start gap-1" data-testid="pengguna-nip-warning">
                      <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                      <span>NIP/NIK belum terdaftar di Master Pegawai — daftarkan agar pencatatan konsisten.</span>
                    </p>
                  )}
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Nomor BAST</Label>
                  <div className="flex gap-1.5">
                    <Input name="nomor_bast" value={formData.nomor_bast} onChange={handleInputChange} placeholder="Nomor BAST" className="h-8 flex-1 min-w-0" data-testid="input-nomor-bast" />
                    {isEditing && (
                      <Button
                        type="button" variant="outline" size="sm"
                        className="h-8 px-2 text-[10px] flex-shrink-0"
                        onClick={() => bastInputRef.current?.click()}
                        disabled={bastUploading}
                        title="Unggah dokumen BAST (PDF/gambar, maks 10MB)"
                        data-testid="bast-upload-btn"
                      >
                        {bastUploading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Upload className="w-3 h-3" />}
                        <span className="ml-1">{bastUploading ? "Unggah..." : "Upload BAST"}</span>
                      </Button>
                    )}
                  </div>
                  {isEditing && bastInfo?.file_id && (
                    <button
                      type="button"
                      onClick={handleBastPreview}
                      data-testid="bast-preview-btn"
                      title={`Lampiran BAST tersedia${bastInfo.filename ? `: ${bastInfo.filename}` : ""} — terhubung otomatis dengan bukti serah terima dari modul Penggunaan`}
                      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 text-[10px] font-semibold hover:bg-emerald-500/25 max-w-full min-w-0 min-h-0"
                    >
                      <Eye className="w-3 h-3 flex-shrink-0" />
                      <span className="truncate">Lampiran BAST tersedia — lihat foto/dokumen</span>
                    </button>
                  )}
                  {!isEditing && (
                    <p className="text-[9px] text-muted-foreground italic">Simpan aset terlebih dahulu untuk mengunggah file BAST.</p>
                  )}
                </div>
                <input ref={bastInputRef} type="file" accept=".pdf,image/jpeg,image/png,image/webp" className="hidden" onChange={handleBastUpload} data-testid="bast-file-input" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1"><Label className="text-xs">Kondisi</Label>
                  <Select value={formData.condition} onValueChange={v => handleSelectChange("condition", v)}><SelectTrigger className="h-8"><SelectValue /></SelectTrigger>
                    <SelectContent>{CONDITION_OPTIONS.map(o => <SelectItem key={o.value} value={o.value}>{o.value}</SelectItem>)}</SelectContent></Select></div>
                <div className="space-y-1"><Label className="text-xs">Status</Label>
                  <Select value={formData.status} onValueChange={v => handleSelectChange("status", v)}><SelectTrigger className="h-8"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Aktif">Aktif</SelectItem>
                      <SelectItem value="Idle">Idle</SelectItem>
                      <SelectItem value="Maintenance">Maintenance</SelectItem>
                      <SelectItem value="Nonaktif">Nonaktif</SelectItem>
                    </SelectContent></Select></div>
              </div>
              
              {/* Stiker */}
              <div className="p-2 bg-muted rounded-lg space-y-2">
                <div className="flex items-center gap-1.5"><Tag className="w-3.5 h-3.5 text-muted-foreground" /><Label className="text-xs font-medium">Informasi Stiker</Label></div>
                <div className="grid grid-cols-2 gap-2">
                  <Select value={formData.stiker_status} onValueChange={handleStikerStatusChange}><SelectTrigger className="h-7 text-xs"><SelectValue /></SelectTrigger>
                    <SelectContent><SelectItem value="Belum Terpasang">Belum Terpasang</SelectItem><SelectItem value="Sudah Terpasang">Sudah Terpasang</SelectItem></SelectContent></Select>
                  <Input name="stiker_ukuran" value={formData.stiker_ukuran} onChange={handleInputChange} placeholder="Ukuran (5x3cm)" className="h-7 text-xs hidden" />
                  <Select value={formData.stiker_ukuran || ""} onValueChange={v => setFormData(p => ({...p, stiker_ukuran: v}))}>
                    <SelectTrigger className="h-7 text-xs"><SelectValue placeholder="Pilih ukuran" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Kecil">Kecil (3x1.5cm)</SelectItem>
                      <SelectItem value="Sedang">Sedang (5x3cm)</SelectItem>
                      <SelectItem value="Besar">Besar (8x5cm)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {/* Stiker Photo Selection */}
                {formData.stiker_status === "Sudah Terpasang" && currentPhotoCount > 0 && (
                  <div className="space-y-1 pt-1 border-t border-border">
                    <Label className="text-[10px] text-emerald-700 dark:text-emerald-400 font-medium">
                      Pilih Foto Stiker {formData.stiker_photo_index !== null && formData.stiker_photo_index !== undefined ? `(Foto ${formData.stiker_photo_index + 1})` : '(Belum dipilih)'}
                    </Label>
                    <div className="flex gap-1.5 flex-wrap">
                      {(isEditing ? photoItems : formData.photos).map((item, i) => {
                        const src = isEditing ? item.thumbnail : item;
                        return (
                          <div key={i}
                            data-testid={`stiker-photo-option-${i}`}
                            onClick={() => setFormData(prev => ({ ...prev, stiker_photo_index: prev.stiker_photo_index === i ? null : i }))}
                            className={`relative w-12 h-12 rounded cursor-pointer border-2 transition-all ${
                              i === formData.stiker_photo_index
                                ? 'border-emerald-500 ring-1 ring-emerald-300 shadow-sm'
                                : 'border-border hover:border-emerald-300 opacity-60 hover:opacity-100'
                            }`}
                          >
                            <img src={src} alt="" loading="lazy" className="w-full h-full object-cover rounded bg-muted" />
                            {i === formData.stiker_photo_index && (
                              <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 bg-emerald-500 text-white text-[7px] px-1 rounded whitespace-nowrap">Stiker</div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                    {formData.stiker_photo_index === null && (
                      <p className="text-[9px] text-amber-600 italic">Klik foto di atas untuk memilih sebagai foto stiker</p>
                    )}
                  </div>
                )}
                {formData.stiker_status === "Sudah Terpasang" && currentPhotoCount === 0 && (
                  <p className="text-[9px] text-amber-600 italic pt-1 border-t border-border">Upload foto terlebih dahulu untuk memilih foto stiker</p>
                )}
              </div>
              
              {/* Status Inventarisasi (SE 17/SE/M/2024) */}
              <div className="p-2 bg-amber-50 dark:bg-amber-900/20 rounded-lg space-y-2 border border-amber-200 dark:border-amber-700">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5"><ClipboardList className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" /><Label className="text-xs font-medium text-amber-800 dark:text-amber-300">Status Inventarisasi</Label></div>
                  <button
                    type="button"
                    onClick={() => setShowGuide(p => !p)}
                    className={`flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9px] font-medium transition-all duration-200 border ${
                      showGuide 
                        ? 'bg-blue-500 text-white border-blue-500 shadow-sm shadow-blue-200' 
                        : 'bg-card text-muted-foreground border-border hover:border-blue-300 hover:text-blue-500'
                    }`}
                    title={showGuide ? "Sembunyikan panduan" : "Tampilkan panduan"}
                  >
                    <HelpCircle className="w-2.5 h-2.5" />
                    <span>{showGuide ? 'ON' : 'OFF'}</span>
                  </button>
                </div>
                <Select value={formData.inventory_status || "Belum Diinventarisasi"} onValueChange={handleInventoryStatusChange}>
                  <SelectTrigger className="h-7 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Belum Diinventarisasi">Belum Diinventarisasi</SelectItem>
                    <SelectItem value="Ditemukan">Ditemukan</SelectItem>
                    <SelectItem value="Tidak Ditemukan">Tidak Ditemukan</SelectItem>
                    <SelectItem value="Berlebih">Berlebih</SelectItem>
                    <SelectItem value="Sengketa">Sengketa</SelectItem>
                  </SelectContent>
                </Select>

                {/* === BERLEBIH SECTION === */}
                {formData.inventory_status === "Berlebih" && (
                  <div className="space-y-2 pt-1 border-t border-purple-200 dark:border-purple-700">
                    {showGuide && <StatusInfoCard status="Berlebih" />}
                    <div className="space-y-1">
                      <Label className="text-[10px] text-purple-700 dark:text-purple-400">Keterangan Berlebih</Label>
                      <textarea name="keterangan_berlebih" value={formData.keterangan_berlebih || ""} onChange={handleInputChange}
                        className="w-full border border-purple-200 dark:border-purple-700 rounded-md p-1.5 text-xs min-h-[40px] resize-none focus:ring-purple-300 focus:border-purple-400 bg-card text-foreground" placeholder="Jelaskan mengapa BMN dikategorikan berlebih..." />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-[10px] text-purple-700 dark:text-purple-400">Asal Usul BMN Berlebih</Label>
                      <textarea name="asal_usul_berlebih" value={formData.asal_usul_berlebih || ""} onChange={handleInputChange}
                        className="w-full border border-purple-200 dark:border-purple-700 rounded-md p-1.5 text-xs min-h-[40px] resize-none focus:ring-purple-300 focus:border-purple-400 bg-card text-foreground" placeholder="Asal usul perolehan BMN (hibah, transfer satker lain, dll)..." />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-[10px] text-purple-700 dark:text-purple-400">Tindak Lanjut</Label>
                      <textarea name="tindak_lanjut" value={formData.tindak_lanjut || ""} onChange={handleInputChange}
                        className="w-full border border-purple-200 dark:border-purple-700 rounded-md p-1.5 text-xs min-h-[40px] resize-none focus:ring-purple-300 focus:border-purple-400 bg-card text-foreground" placeholder="Tindak lanjut: pendaftaran, serah terima, pemindahtanganan..." />
                    </div>
                  </div>
                )}

                {/* === SENGKETA SECTION === */}
                {formData.inventory_status === "Sengketa" && (
                  <div className="space-y-2 pt-1 border-t border-rose-200 dark:border-rose-700">
                    {showGuide && <StatusInfoCard status="Sengketa" />}
                    <div className="space-y-1">
                      <Label className="text-[10px] text-rose-700 dark:text-rose-400">Nomor Perkara</Label>
                      <Input name="nomor_perkara" value={formData.nomor_perkara || ""} onChange={handleInputChange}
                        placeholder="Nomor perkara pengadilan..." className="h-7 text-xs border-rose-200 dark:border-rose-700 focus:ring-rose-300 focus:border-rose-400" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-[10px] text-rose-700 dark:text-rose-400">Pihak Bersengketa</Label>
                      <Input name="pihak_bersengketa" value={formData.pihak_bersengketa || ""} onChange={handleInputChange}
                        placeholder="Nama pihak yang bersengketa..." className="h-7 text-xs border-rose-200 dark:border-rose-700 focus:ring-rose-300 focus:border-rose-400" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-[10px] text-rose-700 dark:text-rose-400">Keterangan Sengketa</Label>
                      <textarea name="keterangan_sengketa" value={formData.keterangan_sengketa || ""} onChange={handleInputChange}
                        className="w-full border border-rose-200 dark:border-rose-700 rounded-md p-1.5 text-xs min-h-[40px] resize-none focus:ring-rose-300 focus:border-rose-400 bg-card text-foreground" placeholder="Jelaskan detail sengketa BMN..." />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-[10px] text-rose-700 dark:text-rose-400">Tindak Lanjut</Label>
                      <textarea name="tindak_lanjut" value={formData.tindak_lanjut || ""} onChange={handleInputChange}
                        className="w-full border border-rose-200 dark:border-rose-700 rounded-md p-1.5 text-xs min-h-[40px] resize-none focus:ring-rose-300 focus:border-rose-400 bg-card text-foreground" placeholder="Koordinasi hukum, pemantauan perkara..." />
                    </div>
                  </div>
                )}

                {formData.inventory_status === "Tidak Ditemukan" && (
                  <div className="space-y-2 pt-1 border-t border-amber-200 dark:border-amber-700">
                    <div className="space-y-1">
                      <Label className="text-[10px] text-amber-700 dark:text-amber-400">Klasifikasi</Label>
                      <Select value={formData.klasifikasi_tidak_ditemukan || ""} onValueChange={handleKlasifikasiChange}>
                        <SelectTrigger className="h-7 text-xs"><SelectValue placeholder="Pilih klasifikasi" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Kesalahan Pencatatan">Kesalahan Pencatatan</SelectItem>
                          <SelectItem value="Tidak Ditemukan Lainnya">Tidak Ditemukan Lainnya</SelectItem>
                        </SelectContent>
                      </Select>
                      {/* Info card for main klasifikasi - shows when klasifikasi selected but sub not yet */}
                      {showGuide && formData.klasifikasi_tidak_ditemukan && !formData.sub_klasifikasi && (
                        <ClassificationInfoCard klasifikasi={formData.klasifikasi_tidak_ditemukan} />
                      )}
                    </div>
                    {formData.klasifikasi_tidak_ditemukan && (
                      <div className="space-y-1">
                        <Label className="text-[10px] text-amber-700 dark:text-amber-400">Sub Klasifikasi</Label>
                        <Select value={formData.sub_klasifikasi || ""} onValueChange={v => setFormData(p => ({...p, sub_klasifikasi: v}))}>
                          <SelectTrigger className="h-7 text-xs"><SelectValue placeholder="Pilih sub-kategori" /></SelectTrigger>
                          <SelectContent>
                            {formData.klasifikasi_tidak_ditemukan === "Kesalahan Pencatatan" ? (<>
                              <SelectItem value="Kesalahan Kodefikasi">Kesalahan Kodefikasi</SelectItem>
                              <SelectItem value="Pencatatan Ganda">Pencatatan Ganda</SelectItem>
                              <SelectItem value="BMN Tercatat di Satker Lain">BMN Tercatat di Satker Lain</SelectItem>
                              <SelectItem value="Kegiatan Perencanaan/Pengembangan Dicatat Sebagai BMN Tersendiri">Perencanaan/Pengembangan Dicatat Sebagai BMN</SelectItem>
                              <SelectItem value="BMN Objek Alih Status/Pemindahtanganan/Penghapusan">Objek Alih Status/Pemindahtanganan/Penghapusan</SelectItem>
                              <SelectItem value="Penggabungan BMN Satu Kesatuan Fungsi">Penggabungan BMN Satu Kesatuan Fungsi</SelectItem>
                              <SelectItem value="Kesalahan Pencatatan Pihak Ketiga">Kesalahan Pencatatan Pihak Ketiga</SelectItem>
                            </>) : (<>
                              <SelectItem value="Tidak Ditemukan Fisiknya">Tidak Ditemukan Fisiknya</SelectItem>
                              <SelectItem value="Tidak Dapat Ditelusuri">Tidak Dapat Ditelusuri</SelectItem>
                              <SelectItem value="Tertimpa Bangunan Lain/Beralih Fungsi">Tertimpa Bangunan Lain/Beralih Fungsi</SelectItem>
                            </>)}
                          </SelectContent>
                        </Select>
                        {/* Info card for sub-klasifikasi - shows detailed guidance */}
                        {showGuide && formData.sub_klasifikasi && (
                          <ClassificationInfoCard subKlasifikasi={formData.sub_klasifikasi} klasifikasi={formData.klasifikasi_tidak_ditemukan} />
                        )}
                      </div>
                    )}
                    <div className="space-y-1">
                      <Label className="text-[10px] text-amber-700 dark:text-amber-400">Uraian Tidak Ditemukan</Label>
                      <textarea name="uraian_tidak_ditemukan" value={formData.uraian_tidak_ditemukan || ""} onChange={handleInputChange}
                        className="w-full border rounded-md p-1.5 text-xs min-h-[40px] resize-none bg-card text-foreground border-border" placeholder="Jelaskan detail mengapa BMN tidak ditemukan..." />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-[10px] text-amber-700 dark:text-amber-400">Tindak Lanjut</Label>
                      <textarea name="tindak_lanjut" value={formData.tindak_lanjut || ""} onChange={handleInputChange}
                        className="w-full border rounded-md p-1.5 text-xs min-h-[40px] resize-none bg-card text-foreground border-border" placeholder="Tindak lanjut yang sudah/akan dilakukan..." />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-[10px] text-amber-700 dark:text-amber-400">Kronologis</Label>
                      <textarea name="kronologis" value={formData.kronologis || ""} onChange={handleInputChange}
                        className="w-full border rounded-md p-1.5 text-xs min-h-[40px] resize-none bg-card text-foreground border-border" placeholder="Uraian kronologis ketidakberadaan BMN..." />
                    </div>
                  </div>
                )}

                {/* Koordinat Lokasi */}
                <div className="space-y-1 pt-1">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1">
                      <MapPin className="w-3 h-3 text-amber-600 dark:text-amber-400" />
                      <Label className="text-[10px] text-amber-700 dark:text-amber-400">
                        Koordinat Lokasi
                        {(currentPhotoCount > 0 || (formData.inventory_status && formData.inventory_status !== "Belum Diinventarisasi")) && (
                          <span className="text-red-500 ml-0.5">*</span>
                        )}
                      </Label>
                    </div>
                    <Button type="button" variant="ghost" size="sm" onClick={fetchGPS} disabled={gpsLoading}
                      className={`h-5 px-1.5 text-[10px] font-medium disabled:opacity-100 ${gpsLoading
                        ? "text-amber-600 dark:text-amber-400"
                        : "text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"}`}
                      data-testid="refresh-gps-btn">
                      {gpsLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <LocateFixed className="w-3 h-3" />}
                      <span className="ml-0.5">{gpsLoading ? 'Mencari...' : 'Ambil GPS'}</span>
                    </Button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-0.5">
                      <Label className="text-[10px] text-muted-foreground">Latitude</Label>
                      <Input name="koordinat_latitude" value={formData.koordinat_latitude || ""} onChange={handleInputChange}
                        placeholder="-6.175110" className={`h-7 text-xs${fieldErrCls("koordinat_latitude")}`} aria-invalid={!!fieldErrors.koordinat_latitude} />
                    </div>
                    <div className="space-y-0.5">
                      <Label className="text-[10px] text-muted-foreground">Longitude</Label>
                      <Input name="koordinat_longitude" value={formData.koordinat_longitude || ""} onChange={handleInputChange}
                        placeholder="106.865036" className={`h-7 text-xs${fieldErrCls("koordinat_longitude")}`} aria-invalid={!!fieldErrors.koordinat_longitude} />
                    </div>
                  </div>
                  {(fieldErrors.koordinat_latitude || fieldErrors.koordinat_longitude) && renderFieldError(fieldErrors.koordinat_latitude ? "koordinat_latitude" : "koordinat_longitude")}
                </div>
              </div>
              
              {/* Photos */}
              <div className="space-y-1.5">
                <Label className="text-xs">Foto Aset ({currentPhotoCount}/6)</Label>
                <div className="flex gap-1.5 flex-wrap">
                  {isEditing ? (
                    /* Edit mode: render from photoItems (thumbnails) */
                    photoItems.map((item, i) => (
                      <div key={i} className="relative group">
                        <img src={item.thumbnail} alt="" loading="lazy" className={`w-14 h-14 object-cover rounded cursor-pointer border-2 bg-muted ${i === formData.thumbnail_index ? 'border-blue-500' : i === formData.stiker_photo_index ? 'border-emerald-500' : 'border-border'}`} onClick={() => setFormData(prev => ({ ...prev, thumbnail_index: i }))} data-testid={`photo-thumb-${i}`} />
                        <button type="button" onClick={() => removePhoto(i)} className="absolute -top-1.5 -right-1.5 bg-red-500 text-white rounded-full w-5 h-5 min-w-0 min-h-0 flex items-center justify-center opacity-0 group-hover:opacity-100" title="Hapus foto" aria-label="Hapus foto"><X className="w-3 h-3" /></button>
                        {i === formData.thumbnail_index && <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 bg-blue-500 text-white text-[8px] px-1 rounded">Cover</div>}
                        {i === formData.stiker_photo_index && i !== formData.thumbnail_index && <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 bg-emerald-500 text-white text-[8px] px-1 rounded">Stiker</div>}
                      </div>
                    ))
                  ) : (
                    /* Create mode: render from formData.photos */
                    formData.photos.map((p, i) => (
                      <div key={i} className="relative group">
                        <img src={p} alt="" className={`w-14 h-14 object-cover rounded cursor-pointer border-2 ${i === formData.thumbnail_index ? 'border-blue-500' : i === formData.stiker_photo_index ? 'border-emerald-500' : 'border-border'}`} onClick={() => setFormData(prev => ({ ...prev, thumbnail_index: i }))} />
                        <button type="button" onClick={() => removePhoto(i)} className="absolute -top-1.5 -right-1.5 bg-red-500 text-white rounded-full w-5 h-5 min-w-0 min-h-0 flex items-center justify-center opacity-0 group-hover:opacity-100" title="Hapus foto" aria-label="Hapus foto"><X className="w-3 h-3" /></button>
                        {i === formData.thumbnail_index && <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 bg-blue-500 text-white text-[8px] px-1 rounded">Cover</div>}
                        {i === formData.stiker_photo_index && i !== formData.thumbnail_index && <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 bg-emerald-500 text-white text-[8px] px-1 rounded">Stiker</div>}
                      </div>
                    ))
                  )}
                  {currentPhotoCount < 6 && (<>
                    <button type="button" onClick={() => fileInputRef.current?.click()} className="w-14 h-14 border-2 border-dashed border-border rounded flex flex-col items-center justify-center hover:border-blue-400 gap-0.5" title="Pilih File">
                      <Plus className="w-4 h-4 text-muted-foreground" />
                      <span className="text-[7px] text-muted-foreground">File</span>
                    </button>
                    <button type="button" onClick={() => cameraInputRef.current?.click()} className="w-14 h-14 border-2 border-dashed border-blue-300 dark:border-blue-600 rounded flex flex-col items-center justify-center hover:border-blue-500 bg-blue-50/50 dark:bg-blue-900/30 gap-0.5" title="Ambil Foto" data-testid="camera-capture-btn">
                      <Camera className="w-4 h-4 text-blue-500 dark:text-blue-400" />
                      <span className="text-[7px] text-blue-500 dark:text-blue-400">Kamera</span>
                    </button>
                    <input ref={fileInputRef} type="file" accept="image/*" multiple onChange={handleImageChange} className="hidden" />
                    <input ref={cameraInputRef} type="file" accept="image/*" capture="environment" onChange={handleImageChange} className="hidden" />
                  </>)}
                </div>
              </div>
              <div className="space-y-1"><Label className="text-xs">Catatan</Label><Input name="notes" value={formData.notes} onChange={handleInputChange} className="h-8" /></div>
            </>)}
            
            {formSection === "procurement" && (<>
              <div className="space-y-1"><Label className="text-xs">Nomor SPM</Label><Input name="nomor_spm" value={formData.nomor_spm} onChange={handleInputChange} placeholder="02847T/621001/2024" className="h-8" /></div>
              <div className="space-y-1"><Label className="text-xs">Perolehan Dari</Label><Input name="perolehan_dari_nama" value={formData.perolehan_dari_nama} onChange={handleInputChange} className="h-8" /></div>
              <div className="space-y-1"><Label className="text-xs">Nomor Kontrak</Label><Input name="nomor_kontrak" value={formData.nomor_kontrak} onChange={handleInputChange} className="h-8" /></div>
              <div className="space-y-1"><Label className="text-xs">Bukti Perolehan (BAST)</Label><Input name="nomor_bukti_perolehan" value={formData.nomor_bukti_perolehan} onChange={handleInputChange} className="h-8" /></div>
              <div className="space-y-1"><Label className="text-xs">Supplier</Label><Input name="supplier" value={formData.supplier} onChange={handleInputChange} className="h-8" /></div>
            </>)}
            
            {formSection === "documents" && (
              isEditing && !checklistFullLoaded ? (
                <div className="py-8 flex flex-col items-center justify-center gap-2 text-muted-foreground" data-testid="checklist-loading">
                  <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
                  <span className="text-xs">Memuat dokumen & foto kelengkapan...</span>
                </div>
              ) : (
                <DocumentChecklist
                  checklist={formData.document_checklist}
                  onChange={handleChecklistChange}
                  assetId={editId}
                  assetVersion={assetVersion}
                />
              )
            )}
            
            {/* Submit Area */}
            <div className="pt-3 border-t sticky bottom-0 bg-card -mx-3 px-3 py-2">
              <div className="flex gap-2">
                <Button
                  id="asset-form-submit-btn" type="submit"
                  className={`flex-1 h-9 relative ${isEditing ? "bg-amber-600 hover:bg-amber-700" : ""}`}
                  disabled={isSubmitting}
                  onClick={() => {
                    if (isEditing && onSaveAndNavigate && assetIndex >= 0
                        && (assetIndex < totalAssetsInView - 1 || hasMoreToLoad)) {
                      navigationIntentRef.current = 'next';
                    }
                  }}
                  data-testid="asset-form-submit"
                >
                  {isSubmitting ? (
                    <><Loader2 className="w-4 h-4 mr-1 animate-spin" />Menyimpan...</>
                  ) : (
                    <><Save className="w-4 h-4 mr-1" />{isEditing ? "Update" : "Simpan"}</>
                  )}
                  {saveQueueLength > 0 && (
                    <span className="absolute -top-1.5 -right-1.5 bg-blue-500 text-white text-[9px] font-bold rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1 shadow-sm animate-pulse" data-testid="save-queue-badge">
                      {saveQueueLength}
                    </span>
                  )}
                </Button>
                {isEditing && <Button type="button" variant="outline" onClick={() => { resetForm(); onClose?.(); }} className="border-amber-300 text-amber-700" disabled={isSubmitting}><X className="w-4 h-4" /></Button>}
              </div>
            </div>
          </form>
        </div>}
      </aside>
      {/* Tap kartu e-KTP → pegawai dikenali → isi pengguna barang */}
      <KartuTapDialog open={kartuTapOpen} onOpenChange={setKartuTapOpen}
        onPegawai={onPickPegawai} />
    </>
  );
});

AssetForm.displayName = "AssetForm";
export default AssetForm;
