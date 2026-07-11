/**
 * Client-side image compression utility.
 * Resizes images to a max dimension and re-encodes as JPEG to drastically
 * reduce upload payload (typical: 5MB → 300-800KB, >10x reduction).
 *
 * Why client-side?
 *  - Reduces network transfer time dramatically (main cause of slow saves).
 *  - Reduces server CPU for Tinify/thumbnail generation.
 *  - Frees up mobile data for users.
 *
 * Browser support: all modern browsers (Canvas + File APIs).
 */

/**
 * Compress an image File into a data URL (base64 JPEG).
 * @param {File} file - Raw image file from <input type="file">.
 * @param {Object} opts
 * @param {number} opts.maxDim - Maximum width or height in pixels (default 1920).
 * @param {number} opts.quality - JPEG quality 0-1 (default 0.85).
 * @param {number} opts.maxBytes - Target max output size in bytes (default 900KB). If exceeded, quality is progressively lowered.
 * @returns {Promise<string>} base64 data URL (image/jpeg).
 */
// createImageBitmap dengan { imageOrientation: 'from-image' } menghasilkan
// bitmap yang SUDAH tegak sesuai EXIF (mengatasi foto miring dari galeri /
// kamera-OS di banyak Android WebView). Kita gambar bitmap itu apa adanya —
// tanpa transform manual — sehingga TIDAK ada risiko putar-ganda di browser
// modern yang sudah menegakkan sendiri. Fallback ke jalur <img> lama bila
// createImageBitmap tak ada.
const supportsImageBitmap = typeof createImageBitmap === "function";

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Gagal membaca file"));
    reader.onload = () => resolve(reader.result);
    reader.readAsDataURL(file);
  });
}

// Skala + encode JPEG progresif dari sebuah sumber gambar (ImageBitmap / <img>).
function encodeScaled(source, srcW, srcH, { maxDim, quality, maxBytes }) {
  try {
    let width = srcW, height = srcH;
    if (width > maxDim || height > maxDim) {
      if (width >= height) { height = Math.round(height * (maxDim / width)); width = maxDim; }
      else { width = Math.round(width * (maxDim / height)); height = maxDim; }
    }
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(source, 0, 0, width, height);
    let q = quality;
    let dataUrl = canvas.toDataURL("image/jpeg", q);
    const approxBytes = (s) => (s.length - (s.indexOf(",") + 1)) * 0.75;
    while (approxBytes(dataUrl) > maxBytes && q > 0.4) {
      q = Math.max(0.4, q - 0.1);
      dataUrl = canvas.toDataURL("image/jpeg", q);
    }
    return dataUrl;
  } finally {
    // Bebaskan ImageBitmap walau drawImage/toDataURL sempat melempar (OOM di HP
    // low-end) — mencegah kebocoran memori.
    if (source && typeof source.close === "function") { try { source.close(); } catch { /* ignore */ } }
  }
}

export async function compressImageFile(file, opts = {}) {
  if (!file || !file.type || !file.type.startsWith("image/")) throw new Error("Not an image file");
  const o = { maxDim: 1920, quality: 0.85, maxBytes: 900 * 1024, ...opts };
  if (supportsImageBitmap) {
    try {
      const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
      return encodeScaled(bmp, bmp.width, bmp.height, o);
    } catch { /* fallback ke jalur <img> */ }
  }
  const dataUrl = await readFileAsDataUrl(file);
  return compressDataUrl(dataUrl, opts);
}

/**
 * Compress an existing base64 data URL (resize + re-encode as JPEG via canvas).
 * Used as the offline fallback when the server-side /compress-image endpoint
 * is unreachable — the canvas pipeline is identical to compressImageFile().
 * @param {string} srcDataUrl - Source image as a data URL.
 * @param {Object} opts - Same options as compressImageFile (maxDim, quality, maxBytes).
 * @returns {Promise<string>} base64 data URL (image/jpeg).
 */
export async function compressDataUrl(srcDataUrl, opts = {}) {
  const o = { maxDim: 1920, quality: 0.85, maxBytes: 900 * 1024, ...opts };
  const { maxDim, quality, maxBytes } = o;
  if (!srcDataUrl || typeof srcDataUrl !== "string" || !srcDataUrl.startsWith("data:image/")) {
    throw new Error("Bukan data URL gambar");
  }

  // Jalur utama: bitmap ber-orientasi EXIF (menegakkan foto miring).
  if (supportsImageBitmap) {
    try {
      const blob = await (await fetch(srcDataUrl)).blob();
      const bmp = await createImageBitmap(blob, { imageOrientation: "from-image" });
      return encodeScaled(bmp, bmp.width, bmp.height, o);
    } catch { /* fallback ke <img> di bawah */ }
  }

  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onerror = () => reject(new Error("Gagal memuat gambar"));
    img.onload = () => {
      try {
        // Calculate target dimensions preserving aspect ratio
        let { width, height } = img;
        if (width > maxDim || height > maxDim) {
          if (width >= height) {
            height = Math.round(height * (maxDim / width));
            width = maxDim;
          } else {
            width = Math.round(width * (maxDim / height));
            height = maxDim;
          }
        }

        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        // High-quality image smoothing
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = "high";
        ctx.drawImage(img, 0, 0, width, height);

        // Encode as JPEG and progressively lower quality until under maxBytes
        let q = quality;
        let dataUrl = canvas.toDataURL("image/jpeg", q);
        // Rough size estimate: base64 string length * 0.75
        const approxBytes = (s) => (s.length - (s.indexOf(",") + 1)) * 0.75;
        while (approxBytes(dataUrl) > maxBytes && q > 0.4) {
          q = Math.max(0.4, q - 0.1);
          dataUrl = canvas.toDataURL("image/jpeg", q);
        }
        resolve(dataUrl);
      } catch (e) {
        reject(e);
      }
    };
    img.src = srcDataUrl;
  });
}

/**
 * Generate a small square thumbnail (center-cropped) data URL from a source data URL.
 * Used for local preview without hitting the server.
 */
export function generateThumbnailFromDataUrl(dataUrl, size = 100, quality = 0.7) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onerror = () => reject(new Error("Gagal memuat gambar"));
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext("2d");
      const scale = Math.max(size / img.width, size / img.height);
      const sw = size / scale;
      const sh = size / scale;
      const sx = (img.width - sw) / 2;
      const sy = (img.height - sh) / 2;
      ctx.drawImage(img, sx, sy, sw, sh, 0, 0, size, size);
      resolve(canvas.toDataURL("image/jpeg", quality));
    };
    img.src = dataUrl;
  });
}

/**
 * Utility: approximate size in bytes from a base64 data URL.
 */
export function dataUrlBytes(dataUrl) {
  if (!dataUrl || typeof dataUrl !== "string") return 0;
  const comma = dataUrl.indexOf(",");
  const payload = comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
  return Math.floor(payload.length * 0.75);
}
