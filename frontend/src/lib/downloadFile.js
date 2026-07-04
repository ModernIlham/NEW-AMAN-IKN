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

// Interval minimal antar update toast (~4x per detik)
const PROGRESS_THROTTLE_MS = 250;

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

/** Ambil pesan error berguna dari respons axios (termasuk respons blob). */
async function extractErrorMessage(err, timeoutMessage) {
  try {
    const d = err?.response?.data;
    let detail;
    if (d instanceof Blob) {
      const text = await d.text();
      try {
        detail = JSON.parse(text)?.detail;
      } catch {
        detail = text;
      }
    } else if (d && typeof d === "object") {
      detail = d.detail;
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
 * @param {number} [opts.timeout] - Timeout axios (ms).
 * @param {string} [opts.timeoutMessage] - Pesan khusus saat timeout.
 * @returns {Promise<import("axios").AxiosResponse>} respons axios (blob).
 * @throws error axios asli (setelah toast.error) agar caller bisa finally/cleanup.
 */
export async function downloadFileWithProgress(url, filename, opts = {}) {
  const { label = filename, params, method = "get", data, timeout, timeoutMessage } = opts;
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
  try {
    const config = { responseType: "blob", onDownloadProgress };
    if (params) config.params = params;
    if (timeout) config.timeout = timeout;
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
    const msg = await extractErrorMessage(err, timeoutMessage);
    toast.error(`Gagal mengunduh ${label}: ${msg}`, { id: toastId });
    throw err;
  }
}
