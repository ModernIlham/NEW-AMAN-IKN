/**
 * Client-side PDF compression helper.
 *
 * Calls the backend `/api/compress-pdf` endpoint (which fans out to
 * iLoveAPI → WhipDoc → original) and returns the compressed PDF as a
 * `data:application/pdf;base64,...` string ready to store/upload.
 *
 * Why server-side?
 *  - PDFs are binary-encoded and don't benefit from canvas re-encoding the way
 *    images do. A multi-page text PDF can shrink 30-70% via dedicated tools.
 *  - Keeps API keys (iLoveAPI/WhipDoc) on the server.
 *  - Falls back gracefully: if the server can't shrink it, the original bytes
 *    are returned verbatim — never blocks the user.
 *
 * The helper itself is resilient: on network/timeout error it returns the
 * original file as base64 so the upload still succeeds (just larger).
 */
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Read a File as a base64 data URL (no compression, just encoding).
 */
function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onloadend = () => resolve(r.result);
    r.onerror = () => reject(new Error("Gagal membaca file"));
    r.readAsDataURL(file);
  });
}

/**
 * Compress a PDF File via backend /api/compress-pdf endpoint.
 *
 * @param {File} file - Raw PDF file from <input type="file">.
 * @param {Object} [opts]
 * @param {number} [opts.timeoutMs=120000] - Request timeout (compression
 *   can take 30-90s for large PDFs).
 * @returns {Promise<{dataUrl: string, originalBytes: number, compressedBytes: number, method: string, savingsPercent: number}>}
 */
export async function compressPdfFile(file, opts = {}) {
  const { timeoutMs = 120000 } = opts;

  if (!file || file.type !== "application/pdf") {
    throw new Error("File bukan PDF");
  }

  const originalBytes = file.size;

  // Build multipart form
  const form = new FormData();
  form.append("file", file, file.name);

  try {
    const res = await axios.post(`${API}/compress-pdf`, form, {
      responseType: "blob",
      timeout: timeoutMs,
      headers: { "Content-Type": "multipart/form-data" },
    });

    // Backend may return the compressed PDF, or a JSON error object on failure
    if (
      res.data &&
      res.data.type &&
      res.data.type.startsWith("application/pdf")
    ) {
      const compressedBytes = res.data.size || 0;
      const method = res.headers["x-compression-method"] || "unknown";
      const savings = parseInt(res.headers["x-savings-percent"] || "0", 10);

      // Convert blob to data URL
      const dataUrl = await new Promise((resolve, reject) => {
        const r = new FileReader();
        r.onloadend = () => resolve(r.result);
        r.onerror = () => reject(new Error("Gagal mengonversi PDF"));
        r.readAsDataURL(res.data);
      });

      return {
        dataUrl,
        originalBytes,
        compressedBytes,
        method,
        savingsPercent: savings,
      };
    }

    // Unexpected non-PDF response → fall through to local read
    throw new Error("Server tidak mengembalikan PDF terkompresi");
  } catch (err) {
    // Graceful degradation: read the original file as data URL so the user
    // can still save. The caller may show a warning toast based on this.
    const dataUrl = await fileToDataUrl(file);
    return {
      dataUrl,
      originalBytes,
      compressedBytes: originalBytes,
      method: "fallback-original",
      savingsPercent: 0,
      error: err?.message || "Kompresi PDF gagal, file asli digunakan",
    };
  }
}
