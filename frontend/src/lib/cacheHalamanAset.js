import { gabungVersiBaris } from "./rekonsiliasiBaris";

const rowBytes = row => JSON.stringify(row).length * 2 + 64;
/** Jendela halaman absolut. Seleksi tetap ID; draf edit dan antrean tersimpan
 * pada pemiliknya sehingga eviction tidak menghapus perubahan pengguna. */
export function buatCacheHalamanAset({ scope = null, maxPages = 6, maxBytes = 8 * 1024 * 1024, margin = 1 } = {}) {
  const pages = new Map();
  let visibleIds = new Set(), focusPage = 1;
  const orderedPages = () => [...pages.keys()].sort((a, b) => a - b);
  const visiblePages = () => orderedPages().filter(p => pages.get(p).rows.some(r => visibleIds.has(r.id)));
  const bytes = () => [...pages.values()].reduce((sum, p) => sum + p.bytes, 0);
  const evict = requested => {
    const protectedPages = new Set([...visiblePages(), requested]);
    while (pages.size > maxPages || bytes() > maxBytes) {
      const keys = orderedPages();
      const edges = [keys[0], keys.at(-1)].filter(p => !protectedPages.has(p));
      if (!edges.length) break; // Visible data itself can exceed any byte budget.
      edges.sort((a, b) => Math.abs(b - focusPage) - Math.abs(a - focusPage));
      pages.delete(edges[0]);
    }
  };
  const put = (page, rows) => {
    const keys = orderedPages();
    if (keys.length && !pages.has(page) && (page < keys[0] - 1 || page > keys.at(-1) + 1)) pages.clear();
    pages.set(page, { rows, bytes: rows.reduce((sum, row) => sum + rowBytes(row), 0) });
    focusPage = page; evict(page);
  };
  return {
    scope,
    put,
    replace(page, rows) { pages.clear(); visibleIds.clear(); put(page, rows); },
    replaceWindow(entries) { pages.clear(); for (const [page, rows] of entries) pages.set(page, { rows, bytes: rows.reduce((sum, row) => sum + rowBytes(row), 0) }); const keys = orderedPages(); if (keys.length) focusPage = Math.max(keys[0], Math.min(focusPage, keys.at(-1))); evict(focusPage); },
    setVisible(ids) { visibleIds = new Set(ids); },
    updateRow(row) {
      for (const entry of pages.values()) {
        entry.rows = entry.rows.map(old => old.id === row.id ? gabungVersiBaris(old, row) : old);
        entry.bytes = entry.rows.reduce((sum, item) => sum + rowBytes(item), 0);
      }
      evict(focusPage);
    },
    removeRow(id) {
      for (const entry of pages.values()) {
        entry.rows = entry.rows.filter(row => row.id !== id);
        entry.bytes = entry.rows.reduce((sum, row) => sum + rowBytes(row), 0);
      }
    },
    rows() {
      const unique = new Map();
      for (const page of orderedPages()) for (const row of pages.get(page).rows) unique.set(row.id, gabungVersiBaris(unique.get(row.id), row));
      return [...unique.values()];
    },
    range() { const keys = orderedPages(); return { first: keys[0] || focusPage, last: keys.at(-1) || focusPage }; },
    refreshRange(totalPages) {
      const current = visiblePages();
      const anchor = current.length ? current : [focusPage];
      const first = Math.max(1, Math.min(Math.min(...anchor) - margin, totalPages));
      const last = Math.max(first, Math.min(Math.max(...anchor) + margin, totalPages));
      return { first, last };
    },
    metrics: () => ({ pages: pages.size, bytes: bytes(), maxPages, maxBytes, overBudget: pages.size > maxPages || bytes() > maxBytes }),
  };
}
