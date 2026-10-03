import { openDB } from "idb";

// Jalur publik ini sengaja TIDAK memakai axios/interceptor/token staf AMAN.
export const PORTAL_API = `${process.env.REACT_APP_BACKEND_URL || ""}/api/portal-pemegang`;
export const PORTAL_TTL = 8 * 60 * 60 * 1000;
export const BATAS_BUKTI = 3 * 1024 * 1024;
export const STATUS_PENUGASAN = {
  menunggu_konfirmasi: "Menunggu konfirmasi", diterima: "Diterima",
  disanggah: "Disanggah", dicabut: "Akses dicabut",
};
export const LABEL_LAPORAN = {
  berkala: "Pemeriksaan berkala", kerusakan: "Kerusakan", kehilangan: "Kehilangan",
  perbaikan: "Perbaikan", pengembalian: "Permohonan pengembalian",
};
export const LABEL_STATUS = {
  diajukan: "Menunggu pemeriksaan", menunggu_verifikasi: "Menunggu pemeriksaan",
  terverifikasi: "Laporan terverifikasi", perlu_perbaikan: "Perlu perbaikan", ditolak: "Ditolak",
};

export function kunciPortal() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  const bytes = new Uint8Array(24);
  globalThis.crypto.getRandomValues(bytes);
  return Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");
}

export function pemilikPortal(sesi) {
  const p = sesi?.pegawai;
  return p?.id && p?.kode_satker && sesi?.session_id ? `${p.id}::${p.kode_satker}::${sesi.session_id}` : "";
}

export function tenggatPortal(sesi, now = Date.now()) {
  const end = Date.parse(sesi?.expires_at || "");
  const idle = Date.parse(sesi?.idle_expires_at || "");
  return Number.isFinite(end) && Number.isFinite(idle) ? Math.min(end, idle, now + PORTAL_TTL) : 0;
}

export async function portalRequest(path, { method = "GET", body, csrf, version, key, signal, blob = false } = {}) {
  const headers = { Accept: blob ? "image/*" : "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") {
    headers["Idempotency-Key"] = key || kunciPortal();
    if (csrf) headers["X-Portal-CSRF"] = csrf;
    if (version !== undefined) headers["If-Match"] = String(version);
  }
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener("abort", abort, { once: true });
  if (signal?.aborted) controller.abort();
  const timer = setTimeout(abort, 30000);
  try {
    const response = await fetch(`${PORTAL_API}${path}`, {
      method, headers, credentials: "include", cache: "no-store", redirect: "error",
      referrerPolicy: "no-referrer", signal: controller.signal,
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      const error = new Error(typeof payload.detail === "string" ? payload.detail
        : typeof payload.pesan === "string" ? payload.pesan : "Permintaan tidak dapat diproses. Muat ulang dan coba kembali.");
      error.status = response.status;
      throw error;
    }
    return await (blob ? response.blob() : response.status === 204 ? Promise.resolve({}) : response.json());
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Koneksi melewati batas waktu. Coba kirim ulang; kunci pengiriman laporan tetap sama untuk mencegah duplikasi.");
    throw error;
  } finally { clearTimeout(timer); signal?.removeEventListener("abort", abort); }
}

const bukaDB = () => openDB("aman_portal_pemegang_privat", 1, {
  upgrade(db) { db.createObjectStore("data"); },
});

export async function hapusLuringPortal() {
  const db = await bukaDB();
  await db.clear("data");
}

// Satu transaksi mencakup cek pemilik dan tulis. Tab dari pemegang lama
// tidak boleh membaca/menimpa antrean pemegang baru setelah pergantian sesi.
async function transaksiPortal(sesi, kerjakan) {
  const owner = pemilikPortal(sesi);
  const db = await bukaDB();
  const tx = db.transaction("data", "readwrite");
  const meta = await tx.store.get("meta");
  if (!owner || !meta || meta.owner !== owner || meta.expires <= Date.now() || tenggatPortal(sesi) <= Date.now()) {
    if (meta?.expires <= Date.now()) await tx.store.clear();
    await tx.done;
    throw new Error("Penyimpanan luring tidak aktif atau kedaluwarsa. Sambungkan internet dan aktifkan kembali pada perangkat pribadi.");
  }
  const result = await kerjakan(tx.store);
  await tx.done;
  return result;
}

export async function aktifkanLuringPortal(sesi) {
  const owner = pemilikPortal(sesi);
  const expires = tenggatPortal(sesi);
  if (!owner || expires <= Date.now()) throw new Error("Sesi harus valid sebelum menyimpan data luring.");
  const db = await bukaDB();
  const tx = db.transaction("data", "readwrite");
  const meta = await tx.store.get("meta");
  if (meta?.owner !== owner || meta?.expires <= Date.now()) await tx.store.clear();
  await tx.store.put({ owner, expires }, "meta");
  await tx.done;
}

// Panggil setelah sesi daring diverifikasi. Identitas berbeda/TTL lewat:
// kosongkan data, jangan memulihkan foto/draf milik pengguna sebelumnya.
export async function bacaLuringPortal(sesi) {
  const db = await bukaDB();
  const tx = db.transaction("data", "readwrite");
  const meta = await tx.store.get("meta");
  if (!pemilikPortal(sesi) || meta?.owner !== pemilikPortal(sesi) || meta?.expires <= Date.now() || tenggatPortal(sesi) <= Date.now()) {
    await tx.store.clear();
    await tx.done;
    return { aktif: false, aset: [], antrean: [] };
  }
  const aset = await tx.store.get("aset") || [];
  // Pemanggil telah memeriksa /sesi daring: idle server yang sah boleh
  // memperpanjang cache/draf sesi SAMA, tidak pernah melewati batas absolut.
  const expires = tenggatPortal(sesi);
  const antrean = (await tx.store.get("antrean") || []).filter(d => d.expires > Date.now()).map(d => ({ ...d, expires }));
  await tx.store.put({ ...meta, expires }, "meta");
  await tx.store.put(antrean, "antrean");
  await tx.done;
  return { aktif: Boolean(meta), aset, antrean };
}

export async function simpanSnapshotPortal(sesi, aset) {
  const fields = ["id", "version", "status", "asset_id", "asset_name", "asset_code", "NUP", "kode_register", "location", "condition", "dasar_penugasan", "sumber_bast", "penerimaan_otomatis"];
  return transaksiPortal(sesi, store => store.put(aset.map(a => Object.fromEntries(fields.map(k => [k, a[k]]))), "aset"));
}

export async function simpanDrafPortal(sesi, payload, { id, key, siap = false } = {}) {
  return transaksiPortal(sesi, async store => {
    const antrean = (await store.get("antrean") || []).filter(d => d.expires > Date.now());
    const draftId = id || kunciPortal();
    const existing = antrean.find(d => d.id === draftId);
    if (existing?.siap) throw new Error("Laporan yang sudah masuk antrean tidak boleh diubah; hapus antrean sebelum membuat laporan baru.");
    if (!existing && antrean.length >= 10) throw new Error("Maksimal 10 draf/antrean pada perangkat. Kirim atau hapus yang tidak diperlukan.");
    const draft = { id: draftId, key: key || kunciPortal(), owner: pemilikPortal(sesi),
      expires: tenggatPortal(sesi), payload, siap, dibuat_pada: new Date().toISOString() };
    const next = [...antrean.filter(d => d.id !== draftId), draft];
    await store.put(next, "antrean");
    return next;
  });
}

export async function hapusDrafPortal(sesi, id) {
  return transaksiPortal(sesi, async store => {
    const next = (await store.get("antrean") || []).filter(d => d.id !== id && d.expires > Date.now());
    await store.put(next, "antrean");
    return next;
  });
}

export function periksaAntreanPortal(draft, sesi, assignments) {
  if (draft.owner !== pemilikPortal(sesi)) return "Identitas pemegang berubah; antrean tidak boleh dikirim.";
  if (draft.expires <= Date.now() || tenggatPortal(sesi) <= Date.now()) return "Draf/sesi telah kedaluwarsa.";
  const assignment = assignments.find(a => a.id === draft.payload.penugasan_id);
  if (!assignment || assignment.status !== "diterima") return "Penugasan belum diterima atau tidak lagi tersedia. Hubungi operator.";
  if (assignment.version !== draft.payload.penugasan_version) return "Penugasan berubah. Periksa data terbaru dan buat laporan baru; isi lama tidak ditimpa otomatis.";
  return "";
}

export async function bacaBuktiPortal(files, existing = []) {
  const selected = Array.from(files || []);
  if (existing.length + selected.length > 3) throw new Error("Maksimal tiga foto per laporan.");
  const existingBytes = existing.reduce((n, b) => n + Math.floor(b.data_base64.length * 3 / 4), 0);
  if (existingBytes + selected.reduce((n, f) => n + f.size, 0) > BATAS_BUKTI) {
    throw new Error("Total foto maksimal 3 MB. Pilih foto berukuran lebih kecil; bukti tidak dikompresi ulang oleh portal.");
  }
  if (selected.some(f => !["image/jpeg", "image/png", "image/webp"].includes(f.type))) throw new Error("Gunakan foto JPEG, PNG, atau WebP.");
  const photos = await Promise.all(selected.map(file => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve({ nama: file.name.slice(0, 150), mime: file.type, data_base64: String(reader.result).split(",")[1] });
    reader.onerror = () => reject(new Error("Foto tidak dapat dibaca. Pilih kembali berkasnya."));
    reader.readAsDataURL(file);
  })));
  return [...existing, ...photos];
}
