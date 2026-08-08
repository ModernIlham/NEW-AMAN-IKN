/**
 * Unduhan file seragam dengan toast progres (sonner).
 *
 * Semua tombol download/export memakai helper ini agar UX-nya konsisten:
 *  - toast.loading dengan id stabil → di-update dengan ukuran terunduh
 *    (dan persen bila server mengirim content-length; gzip bisa menghapusnya)
 *  - sukses → trigger download browser + toast.success "{label} berhasil diunduh"
 *  - gagal  → toast.error dengan detail dari respons backend, lalu re-throw
 *    supaya pemanggil tetap bisa mengelola state loading/finally-nya sendiri.
 *
 * Auth tidak perlu diurus di sini — interceptor axios global (App.js) sudah
 * melampirkan bearer token ke setiap request.
 */
import axios from "axios";
import { toast } from "sonner";

import { mulaiUnduhanPusat, pathDariUrl } from "./pusatUnduhan";

// Interval minimal antar update toast (~4x per detik)
const PROGRESS_THROTTLE_MS = 250;

// Timeout BAKU unduhan (dulu ikut lantai axios global 20 dtk — laporan besar
// putus "Waktu unduh habis"). Lewat 2 menit, unduhan GET otomatis dialihkan
// ke Pusat Unduhan (job latar server) alih-alih dibuang.
const TIMEOUT_UNDUH_BAKU = 120000;

let downloadSeq = 0;

/**
 * Format ukuran gaya Indonesia: < 1 MB → "xxx KB", selainnya "x,y MB"
 * (koma desimal).
 */
function formatSize(bytes) {
  const kb = (bytes || 0) / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;
  return `${(kb / 1024).toFixed(1).replace(".", ",")} MB`;
}

/**
 * Isi Blob sebagai teks, dengan jalur mundur `FileReader`.
 *
 * `Blob.prototype.text()` baru ada sejak Chrome 76 / Safari 14 / Firefox 69.
 * WebView Android bawaan pada perangkat lapangan lama bisa lebih tua dari itu
 * — di sana `d.text()` melempar TypeError, tertangkap oleh `catch` pemanggil,
 * dan pesan servernya senyap berubah menjadi "Terjadi kesalahan": tepat
 * kegagalan yang hendak ditutup fungsi ini. `FileReader` ada di mana pun
 * `Blob` ada, jadi ia jalur mundur yang benar-benar mundur.
 */
function bacaBlobSebagaiTeks(blob) {
  if (typeof blob.text === "function") return blob.text();
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(String(fr.result || ""));
    fr.onerror = () => reject(fr.error || new Error("gagal membaca blob"));
    fr.readAsText(blob);
  });
}

/**
 * Ambil pesan error berguna dari respons axios — TERMASUK respons blob.
 *
 * Diekspor karena bukan hanya berkas ini yang meminta `responseType: 'blob'`.
 * Pada permintaan blob, axios membungkus BADAN GALAT sebagai Blob juga, jadi
 * `err.response.data.detail` bernilai undefined dan `getApiError` jatuh ke
 * pesan cadangan. Akibatnya server bisa menolak dengan alasan yang jelas
 * ("maks 300 kartu — persempit seleksi") sementara layar hanya berkata "Gagal
 * cetak kartu massal": penggunanya lalu mencoba lagi, dan lagi.
 */
export async function pesanGalatRespons(err, timeoutMessage) {
  try {
    const d = err?.response?.data;
    let detail;
    if (d instanceof Blob) {
      const text = await bacaBlobSebagaiTeks(d);
      try {
        const obj = JSON.parse(text);
        // `detail` (FastAPI) ?? `error` (slowapi). Handler 429 bawaan slowapi
        // — terdaftar di server.py — membalas {"error": "Rate limit exceeded:
        // 3 per 1 minute"}, BUKAN {"detail": ...}. Tanpa cabang kedua ini,
        // JSON.parse berhasil, ?.detail = undefined, dan fungsi jatuh ke
        // "HTTP 429" — pengguna tak pernah diberi tahu bahwa ia hanya perlu
        // MENUNGGU semenit. Itu tajam justru karena pesan plafon kartu
        // menyuruhnya "cetak bertahap per kelompok": yang menurut aturan
        // malah yang paling cepat menabrak limitnya.
        detail = obj?.detail ?? obj?.error;
      } catch {
        detail = text;
      }
    } else if (d && typeof d === "object") {
      detail = d.detail ?? d.error;
    } else if (typeof d === "string") {
      detail = d;
    }
    if (typeof detail === "string" && detail.trim()) return detail.trim().slice(0, 300);
    if (Array.isArray(detail)) return detail.map((e) => e.msg || String(e)).join(", ");
  } catch { /* jatuh ke fallback di bawah */ }
  if (err?.code === "ECONNABORTED" || err?.message?.includes("timeout")) {
    return timeoutMessage || "Waktu unduh habis — coba lagi atau periksa koneksi";
  }
  if (err?.response?.status) return `HTTP ${err.response.status}`;
  return err?.message || "Terjadi kesalahan";
}

/**
 * Buat pelapor progres unduhan mandiri (toast sonner dengan id stabil).
 *
 * Dipakai oleh pemanggil yang butuh menampilkan progres tetapi ingin
 * mengelola sendiri hasil unduhannya (mis. buka pratinjau PDF di tab baru,
 * bukan langsung men-download). `onDownloadProgress` bisa langsung dipasang
 * ke config axios; `success`/`error` menutup toast yang sama.
 *
 * @param {string} label - Nama tampilan pada toast (mis. "kartu inventaris").
 * @returns {{onDownloadProgress: Function, success: Function, error: Function, toastId: string}}
 */
export function makeDownloadProgress(label) {
  const toastId = `download-${++downloadSeq}`;
  let lastUpdate = 0;

  const onDownloadProgress = (e) => {
    const now = Date.now();
    if (now - lastUpdate < PROGRESS_THROTTLE_MS) return;
    lastUpdate = now;
    const size = formatSize(e.loaded);
    // Catatan: e.total bisa undefined (gzip backend menghapus content-length)
    if (e.total) {
      const pct = Math.min(100, Math.round((e.loaded / e.total) * 100));
      toast.loading(`Mengunduh ${label}… ${size} (${pct}%)`, { id: toastId });
    } else {
      toast.loading(`Mengunduh ${label}… ${size}`, { id: toastId });
    }
  };

  toast.loading(`Mengunduh ${label}…`, { id: toastId });
  return {
    toastId,
    onDownloadProgress,
    success: (msg) => toast.success(msg || `${label} berhasil diunduh`, { id: toastId }),
    error: (msg) => toast.error(msg || `Gagal mengunduh ${label}`, { id: toastId }),
  };
}

/**
 * Unduh file dari `url` sebagai blob dengan toast progres, lalu picu
 * download browser dengan nama `filename`.
 *
 * @param {string} url - URL endpoint (boleh sudah berisi query string).
 * @param {string} filename - Nama file yang disimpan browser.
 * @param {Object} [opts]
 * @param {string} [opts.label=filename] - Nama tampilan pada toast.
 * @param {Object} [opts.params] - Query params tambahan (axios `params`).
 * @param {"get"|"post"} [opts.method="get"] - POST untuk endpoint ber-body (mis. batch ZIP).
 * @param {*} [opts.data] - Body request saat method "post".
 * @param {number} [opts.timeout] - Timeout axios (ms); baku 120 dtk.
 * @param {string} [opts.timeoutMessage] - Pesan khusus saat timeout.
 * @param {boolean|"langsung"} [opts.viaPusat] - `"langsung"`: langsung
 *   daftarkan ke Pusat Unduhan tanpa mencoba unduh sinkron (untuk laporan yang
 *   SUDAH diketahui berat) — HANYA berlaku untuk method GET dengan URL API
 *   internal (`.../api/...`); di luar itu tetap unduh sinkron. `false`:
 *   matikan fallback otomatis. Default: coba sinkron dulu, saat timeout
 *   dialihkan otomatis (hanya method GET, URL API internal).
 * @returns {Promise<import("axios").AxiosResponse|{viaPusat: true}>} respons
 *   axios (blob), atau {viaPusat:true} bila dialihkan ke Pusat Unduhan.
 * @throws error axios asli (setelah toast.error) agar caller bisa finally/cleanup.
 */
export async function downloadFileWithProgress(url, filename, opts = {}) {
  const { label = filename, params, method = "get", data, timeout,
          timeoutMessage, viaPusat } = opts;

  // URL final (query params ikut) → path internal /api untuk Pusat Unduhan.
  // Pakai axios.getUri agar serialisasi query PERSIS sama dengan request
  // sinkron (array/undefined/null) — kalau tidak, file yang disusun di latar
  // bisa memakai filter berbeda dari yang diminta user.
  const urlFinal = params ? axios.getUri({ url, params }) : url;
  const kePusat = async (toastId) => {
    const path = pathDariUrl(urlFinal);
    if (!path) return false;
    await mulaiUnduhanPusat({ path, namaFile: filename, label });
    toast.info(
      `${label}: disusun di latar belakang — pantau di panel Pusat Unduhan `
      + "(kanan bawah); hasilnya tersimpan 30 hari",
      { id: toastId, duration: 6000 });
    return true;
  };

  const { toastId, onDownloadProgress } = makeDownloadProgress(label);
  if (viaPusat === "langsung") {
    // "langsung" hanya berlaku untuk GET ke URL API internal (.../api/...).
    // Di luar itu turun ke unduhan sinkron (dengan peringatan konsol) alih-alih
    // gagal senyap, agar caller keliru tetap mendapat file.
    if (method !== "get") {
      console.warn("[unduh] viaPusat 'langsung' hanya mendukung GET; "
        + "lanjut unduhan sinkron.");
    } else {
      try {
        if (await kePusat(toastId)) return { viaPusat: true };
        console.warn("[unduh] URL bukan /api internal; Pusat Unduhan "
          + "dilewati, lanjut unduhan sinkron.");
      } catch (err) {
        const msg = await pesanGalatRespons(err, timeoutMessage);
        toast.error(`Gagal mengunduh ${label}: ${msg}`, { id: toastId });
        throw err;
      }
    }
  }
  try {
    const config = { responseType: "blob", onDownloadProgress };
    if (params) config.params = params;
    config.timeout = timeout || TIMEOUT_UNDUH_BAKU;
    const r = method === "post"
      ? await axios.post(url, data, config)
      : await axios.get(url, config);

    const blobUrl = window.URL.createObjectURL(new Blob([r.data]));
    const link = document.createElement("a");
    link.href = blobUrl;
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(blobUrl);
    toast.success(`${label} berhasil diunduh`, { id: toastId });
    return r;
  } catch (err) {
    // Waktu habis pada GET = server kemungkinan MASIH menyusun file — jangan
    // dibuang: daftarkan ke Pusat Unduhan agar dilanjutkan di latar dan bisa
    // diunduh dari sana tanpa request ulang.
    const habisWaktu = err?.code === "ECONNABORTED"
      || (typeof err?.message === "string" && err.message.includes("timeout"));
    if (habisWaktu && method === "get" && viaPusat !== false) {
      try {
        if (await kePusat(toastId)) return { viaPusat: true };
      } catch (errPusat) {
        // Pendaftaran ke Pusat Unduhan ditolak (409 kuota / 429 limiter /
        // 400 path) — tampilkan ALASAN NYATA itu, bukan pesan timeout yang
        // menyesatkan; caller tetap menerima error timeout asli.
        const msgPusat = await pesanGalatRespons(errPusat, timeoutMessage);
        toast.error(`Gagal mengunduh ${label}: ${msgPusat}`, { id: toastId });
        throw err;
      }
    }
    const msg = await pesanGalatRespons(err, timeoutMessage);
    toast.error(`Gagal mengunduh ${label}: ${msg}`, { id: toastId });
    throw err;
  }
}
