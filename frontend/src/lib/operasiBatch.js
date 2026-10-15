import axios from "axios";
const API = `${process.env.REACT_APP_BACKEND_URL}/api/assets/batch-v2`;
const MAX_TARGET = 200;
const TERMINAL = new Set(["applied", "unchanged", "conflict", "missing", "failed"]);

function uuid() {
  const c = globalThis.crypto;
  if (typeof c?.randomUUID === "function") return c.randomUUID();
  if (!c?.getRandomValues) throw new Error("Peramban tidak menyediakan pembuat identitas aman. Gunakan peramban terbaru melalui HTTPS.");
  const bytes = c.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
  return [...bytes].map((b, i) => `${[4, 6, 8, 10].includes(i) ? "-" : ""}${b.toString(16).padStart(2, "0")}`).join("");
}
export const kunciCheckpointBatch = (owner, satker) => `aman_batch_v2:${JSON.stringify([owner, satker || ""])}`;
export function bacaCheckpointBatch(storage, key) {
  try { const value = JSON.parse(storage.getItem(key) || "null"); return value?.schema === 1 ? value : null; }
  catch { return null; }
}
export function ringkasBatch(group) {
  const out = { total: group?.total || 0, applied: 0, unchanged: 0, conflicts: 0, missing: 0, failed: 0, pending: 0, results: [] };
  for (const child of group?.children || []) {
    const r = child.response;
    out.applied += r?.applied || 0; out.unchanged += r?.unchanged || 0;
    out.conflicts += r?.conflicts || 0; out.missing += r?.missing || 0; out.failed += r?.failed || 0;
    out.pending += r ? (r.pending || 0) : child.asset_ids.length;
    out.results.push(...(r?.results || []));
  }
  out.success = out.applied + out.unchanged;
  out.attention = out.conflicts + out.missing + out.failed;
  out.done = !!group && group.children.every(c => c.prepared && !c.error && c.response && c.response.pending === 0);
  return out;
}
function apiError(message, code) { return Object.assign(new Error(message), { code }); }
export function pesanGalatBatch(error) {
  const detail = error?.response?.data?.detail;
  return (typeof detail === "string" ? detail : detail?.message) || error?.message || "Hasil operasi belum dapat dipastikan. Periksa status sebelum melanjutkan.";
}

/** Browser hanya menyimpan ID, target, status dan hitungan. Draf/media immutable
 * tersimpan di server sebelum satu target pun diubah. */
export function buatKlienOperasiBatch({ owner, satker = "", activityId, sessionId, storage = localStorage, onChange = () => {} }) {
  const key = kunciCheckpointBatch(owner, satker);
  const config = { timeout: 300000, headers: { "X-Session-Id": sessionId || "unknown-session" } };
  let busy = false;
  const save = group => {
    group.updatedAt = Date.now();
    try { storage.setItem(key, JSON.stringify(group)); }
    catch { throw apiError("Metadata pemulihan tidak dapat disimpan di perangkat. Kosongkan ruang penyimpanan atau kurangi jumlah target, lalu periksa status sebelum mencoba lagi.", "checkpoint_storage"); }
    onChange({ ...group, children: [...group.children] });
    return group;
  };
  const refresh = async group => {
    const next = { ...group, children: group.children.map(c => ({ ...c })), error: null };
    const readChild = async child => {
      try {
        const { data } = await axios.get(`${API}/${child.operation_id}`, config);
        child.prepared = true; child.response = data; child.error = null; delete child.errorCode;
      } catch (error) {
        child.error = pesanGalatBatch(error);
        child.errorCode = error?.response?.data?.detail?.code || error?.response?.status;
        if (error?.response?.status === 404) child.prepared = false;
      }
    };
    for (let i = 0; i < next.children.length; i += 3) {
      await Promise.all(next.children.slice(i, i + 3).map(readChild));
    }
    const summary = ringkasBatch(next);
    next.phase = next.children.some(c => c.error) ? "attention" : summary.done ? "completed" : "paused";
    return save(next);
  };
  const resume = async group => {
    let current = await refresh(group);
    if (current.children.some(c => !c.prepared || c.error)) {
      throw apiError("Sebagian persiapan/status belum tersedia. Periksa rincian operasi; perubahan belum dilanjutkan.", "incomplete_admission");
    }
    current.phase = "running"; save(current);
    for (const child of current.children) {
      if (child.response?.pending === 0) continue;
      try {
        const { data } = await axios.post(`${API}/${child.operation_id}/resume`, {}, config);
        child.response = data; child.error = null; save(current);
        if (data.pending > 0) {
          current.phase = "paused"; save(current);
          return current;
        }
      } catch (error) {
        // Timeout bisa terjadi setelah commit; GET adalah sumber hasil sebelum
        // percobaan ulang. Jangan membuat ID operasi pengganti.
        current = await refresh(current);
        if (ringkasBatch(current).done) return current;
        current.phase = "attention"; current.error = pesanGalatBatch(error); save(current);
        return current;
      }
    }
    current.phase = ringkasBatch(current).done ? "completed" : "paused";
    return save(current);
  };
  const exclusive = async fn => {
    if (busy) throw apiError("Operasi masih berjalan. Tunggu hasil atau periksa statusnya.", "operation_busy");
    busy = true;
    try { return await fn(); } finally { busy = false; }
  };
  return {
    key,
    read: () => bacaCheckpointBatch(storage, key),
    async plan(assetIds, updates, knownVersions = {}, activityOverride = activityId) {
      const ids = [...new Set(assetIds)].filter(Boolean);
      if (!owner || !ids.length) throw apiError("Pilih aset dan masuk kembali sebelum menerapkan perubahan.", "invalid_targets");
      const snapshot = JSON.parse(JSON.stringify(updates));
      const payloads = [];
      let generation;
      for (let i = 0; i < ids.length; i += MAX_TARGET) {
        const target = ids.slice(i, i + MAX_TARGET);
        const { data } = await axios.post(`${API}/preflight`, { asset_ids: target }, config);
        if (data.protocol !== "batch_v2" || data.max_targets !== MAX_TARGET) throw apiError("Server belum mendukung ubah massal yang dapat dilanjutkan. Muat ulang setelah pembaruan server.", "protocol_unavailable");
        if (generation && generation !== data.dataset_generation) throw apiError("Dataset berubah saat persiapan. Periksa data lalu ulangi persiapan.", "dataset_changed");
        generation = data.dataset_generation;
        const versions = Object.fromEntries(target.map(id => [id, knownVersions[id] || data.targets.find(t => t.id === id)?.version || 1]));
        payloads.push({ operation_id: `b2_${Date.now()}_${uuid()}`, asset_ids: target,
          dataset_generation: generation, expected_versions: versions, updates: snapshot });
      }
      return { payloads, metadata: { schema: 1, owner, satker, activityId: activityOverride, total: ids.length, createdAt: Date.now(), phase: "preparing",
        children: payloads.map(p => ({ operation_id: p.operation_id, asset_ids: p.asset_ids, prepared: false, response: null })) } };
    },
    start(plan) { return exclusive(async () => {
      if (plan.metadata.owner !== owner || plan.metadata.satker !== satker) throw apiError("Akun atau satker berubah. Siapkan ulang target pada akun yang sesuai.", "owner_changed");
      const existing = bacaCheckpointBatch(storage, key);
      if (existing && !ringkasBatch(existing).done) throw apiError("Selesaikan atau tinjau operasi sebelumnya sebelum memulai draf baru.", "operation_pending");
      const current = save(plan.metadata); // Persistence wajib berhasil SEBELUM admission/write.
      for (let i = 0; i < plan.payloads.length; i++) {
        try {
          const { data } = await axios.post(`${API}/prepare`, plan.payloads[i], config);
          current.children[i].prepared = true; current.children[i].response = data; save(current);
        } catch (error) {
          current.phase = "attention"; current.error = pesanGalatBatch(error); save(current);
          return current; // Tidak ada resume sebelum seluruh potongan diadmit.
        }
      }
      return resume(current);
    }); },
    refresh: group => exclusive(() => refresh(group)),
    resume: group => exclusive(() => resume(group)),
    abandonPreparation(group) { return exclusive(async () => {
      const current = await refresh(group);
      const untouched = current.children.every(c => c.errorCode === 404 || (!c.error && c.response &&
        c.response.pending === c.asset_ids.length && (c.response.results || []).every(r => r.status === "pending")));
      if (!untouched) throw apiError("Hasil sebagian aset sudah tercatat atau belum dapat diperiksa. Tinjau status sebelum membuat draf baru.", "operation_pending");
      storage.removeItem(key); onChange(null);
      return null;
    }); },
    clear(group) {
      const s = ringkasBatch(group);
      if (!s.done) throw apiError("Operasi belum selesai; periksa hasil server terlebih dahulu.", "operation_pending");
      storage.removeItem(key); onChange(null);
    },
  };
}
export { TERMINAL as STATUS_BATCH_SELESAI };

/** Efek UI hanya untuk konteks yang masih memiliki tiket. Status operasi tetap
 * bisa dibaca pada konteks baru; hasil lama tidak menutup draf atau menggulir. */
export async function terapkanHasilBatchKeTampilan({ operation, penjaga, ticket, activityId,
  resetDraft, hidePanel, refresh }) {
  if (!penjaga.berlaku(ticket) || operation.activityId !== activityId) return "stale";
  const summary = ringkasBatch(operation);
  if (summary.done && summary.attention === 0) {
    resetDraft(); hidePanel();
    await refresh?.(undefined, { refreshWindow: true });
    return "completed";
  }
  if (summary.success > 0) await refresh?.(undefined, { refreshWindow: true });
  return summary.attention ? "partial" : "pending";
}
