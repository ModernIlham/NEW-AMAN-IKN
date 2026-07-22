// Ekspor sebagai JOB LATAR: submit → poll progres → unduh otomatis saat selesai.
//
// Untuk ekspor berat (mis. Excel berfoto) yang bisa melewati batas timeout ~120s
// pada unduhan sinkron. Backend: POST <submitUrl> → {job_id}; poll GET
// /api/jobs/{id}; unduh GET /api/jobs/{id}/download (native anchor + ?token agar
// file besar andal lewat ingress). Auth submit/poll via interceptor axios global
// (App.js). Catatan: polling inline — bila pengguna meninggalkan halaman, job
// TETAP jalan di server tetapi unduh-otomatis tak terpicu (bisa diekspor ulang).
import axios from "axios";
import { toast } from "sonner";
import { authMediaUrl } from "./mediaUrl";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function nativeDownload(url) {
  const a = document.createElement("a");
  a.href = url;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * Jalankan ekspor via job latar.
 * @param {string} submitUrl endpoint POST yang mengembalikan { job_id }
 * @param {object} opts { label, intervalMs, maxMs }
 * @returns {Promise<boolean>} true bila berhasil diunduh
 */
export async function exportViaJob(submitUrl, { label = "Ekspor", intervalMs = 1500, maxMs = 600000 } = {}) {
  const tId = toast.loading(`${label}: memulai…`);
  let jobId;
  try {
    const r = await axios.post(submitUrl);
    jobId = r.data?.job_id;
    if (!jobId) throw new Error("job_id tidak diterima");
  } catch (e) {
    toast.error(`${label} gagal dimulai: ${e.response?.data?.detail || e.message}`, { id: tId });
    return false;
  }

  const start = Date.now();
  let miss404 = 0;
  for (;;) {
    await sleep(intervalMs);
    if (Date.now() - start > maxMs) {
      toast.error(`${label}: melebihi batas waktu tunggu`, { id: tId });
      return false;
    }
    let job;
    try {
      job = (await axios.get(`${API}/jobs/${jobId}`)).data;
      miss404 = 0;
    } catch (e) {
      if (e.response?.status === 404) {
        // Job belum sempat tersimpan / kedaluwarsa — toleransi beberapa kali.
        if (++miss404 >= 3) { toast.error(`${label}: job tak ditemukan`, { id: tId }); return false; }
      }
      continue; // gangguan jaringan sesaat → coba lagi
    }
    if (job.status === "done" || job.done === true) {
      if (job.status === "error") {
        toast.error(`${label} gagal: ${job.error_message || "kesalahan server"}`, { id: tId });
        return false;
      }
      toast.success(`${label}: selesai, mengunduh…`, { id: tId });
      nativeDownload(authMediaUrl(`${API}/jobs/${jobId}/download`));
      return true;
    }
    if (job.status === "error") {
      toast.error(`${label} gagal: ${job.error_message || "kesalahan server"}`, { id: tId });
      return false;
    }
    const pct = job.progress || 0;
    toast.loading(`${label}: ${job.message || "memproses"}… ${pct}%`, { id: tId });
  }
}
