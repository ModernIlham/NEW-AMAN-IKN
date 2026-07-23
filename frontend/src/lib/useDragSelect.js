import { useRef, useCallback } from "react";

// Drag-to-select untuk daftar & galeri aset: tekan-tahan pada kotak select lalu
// geser melewati kotak select baris lain → seluruh baris yang dilewati ikut
// TERSELEKSI (atau ter-DESELEKSI bila memulai dari baris yang SUDAH terpilih —
// arahnya mengikuti kotak awal). Memudahkan pilih banyak baris berurutan.
//
// Implementasi via EVENT DELEGATION (elementFromPoint pada container), sehingga
// AMAN untuk daftar tervirtualisasi: tak perlu meneruskan handler ke tiap baris.
// Cukup:
//   1) beri atribut `data-select-box data-asset-id={id}` pada tiap kotak select,
//   2) sebar `containerProps` pada elemen pembungkus daftar/galeri.
//
// HANYA untuk pointer mouse — pada sentuh (HP/tablet), gerakan tahan-geser tetap
// menggulir daftar seperti biasa (tak dibajak jadi seleksi).
export function useDragSelect(selectedAssets, setSelectedAssets) {
  // Ref selalu memegang Set seleksi terbaru agar pembacaan sinkron tanpa
  // menjadikan callback bergantung pada nilai yang sering berubah.
  const selRef = useRef(selectedAssets);
  selRef.current = selectedAssets;

  // { active, value(true=select/false=deselect), moved, applied:Set, startId }
  const drag = useRef({ active: false, value: true, moved: false, applied: null, startId: null });

  const boxIdAt = (x, y) => {
    const el = document.elementFromPoint(x, y);
    const box = el && el.closest ? el.closest("[data-select-box][data-asset-id]") : null;
    return box ? box.getAttribute("data-asset-id") : null;
  };

  const apply = useCallback((id) => {
    const d = drag.current;
    if (!id || !d.applied || d.applied.has(id)) return;
    d.applied.add(id);
    setSelectedAssets((prev) => {
      const has = prev.has(id);
      if (d.value === has) return prev; // sudah sesuai arah → tak berubah
      const n = new Set(prev);
      if (d.value) n.add(id); else n.delete(id);
      return n;
    });
  }, [setSelectedAssets]);

  const onPointerDown = useCallback((e) => {
    if (e.pointerType && e.pointerType !== "mouse") return; // sentuh → biarkan gulir
    if (e.button != null && e.button !== 0) return;          // klik kiri saja
    const el = e.target && e.target.closest
      ? e.target.closest("[data-select-box][data-asset-id]") : null;
    if (!el) return;
    const id = el.getAttribute("data-asset-id");
    drag.current = {
      active: true, value: !selRef.current.has(id),
      moved: false, applied: new Set(), startId: id,
    };
  }, []);

  const onPointerMove = useCallback((e) => {
    const d = drag.current;
    if (!d.active) return;
    const id = boxIdAt(e.clientX, e.clientY);
    if (!id) return;
    if (!d.moved) {
      // Gerakan pertama yang mengenai sebuah kotak = mulai men-drag: terapkan ke
      // kotak AWAL juga (native checkbox-nya tak ter-"klik" karena pointerup di
      // kotak lain), lalu ke kotak ini.
      d.moved = true;
      apply(d.startId);
    }
    apply(id);
  }, [apply]);

  const endDrag = useCallback(() => { drag.current.active = false; }, []);

  // Bila drag benar-benar terjadi (moved), tekan native checkbox kotak awal
  // TIDAK boleh ikut men-toggle onChange — cegah di fase capture.
  const onClickCapture = useCallback((e) => {
    if (drag.current.moved) {
      e.preventDefault();
      e.stopPropagation();
      drag.current.moved = false;
    }
  }, []);

  const containerProps = {
    onPointerDown, onPointerMove, onPointerUp: endDrag,
    onPointerLeave: endDrag, onPointerCancel: endDrag, onClickCapture,
  };
  return { containerProps };
}
