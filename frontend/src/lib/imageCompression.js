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
export function compressImageFile(file, opts = {}) {
  const { maxDim = 1920, quality = 0.85, maxBytes = 900 * 1024 } = opts;

  return new Promise((resolve, reject) => {
    if (!file || !file.type || !file.type.startsWith("image/")) {
      reject(new Error("Not an image file"));
      return;
    }

    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Gagal membaca file"));
    reader.onload = () => {
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
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
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
