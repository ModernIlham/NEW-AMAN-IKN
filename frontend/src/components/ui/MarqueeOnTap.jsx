import { useCallback, useRef, useState } from "react";

/**
 * Teks satu baris yang, KETIKA DIKLIK/DITAP, berjalan (marquee) untuk
 * menampilkan bagian yang terpotong — lalu kembali. Dipakai untuk judul
 * panjang di daftar/kartu yang di layar sempit ter-`truncate` sehingga
 * informasinya tak terbaca penuh.
 *
 * Perilaku:
 * - Default: satu baris ter-truncate (ellipsis). `title` mengaktifkan tooltip
 *   bawaan peramban di desktop (hover) sebagai bonus.
 * - Tap 1: bila teks memang melebihi kotak, ia meluncur pelan sampai ujung
 *   kanan terlihat, berhenti sejenak, lalu kembali. Bila tidak melebihi kotak,
 *   tap tidak melakukan apa-apa (tak ada yang perlu ditampilkan).
 * - Tap saat sedang berjalan: langsung reset ke awal.
 *
 * Aksesibilitas: elemen ber-`role="button"` + `tabIndex` sehingga bisa
 * dipicu dengan Enter/Spasi, dan menghormati `prefers-reduced-motion`.
 */
export default function MarqueeOnTap({ text, className = "", as: Tag = "p" }) {
  const wrapRef = useRef(null);
  const innerRef = useRef(null);
  const [jalan, setJalan] = useState(false);

  const mainkan = useCallback(() => {
    const wrap = wrapRef.current;
    const inner = innerRef.current;
    if (!wrap || !inner) return;
    const lebih = inner.scrollWidth - wrap.clientWidth;
    if (lebih <= 2) return; // muat penuh — tak ada yang perlu digulir

    // Toggle: kalau sedang berjalan, reset.
    if (jalan) {
      inner.style.transition = "none";
      inner.style.transform = "translateX(0)";
      setJalan(false);
      return;
    }

    const kurangiGerak = window.matchMedia?.(
      "(prefers-reduced-motion: reduce)"
    )?.matches;

    setJalan(true);
    // Durasi proporsional dengan jarak (± 40 px/detik, min 1,2 dtk).
    const durasi = kurangiGerak ? 0 : Math.max(1.2, lebih / 40);
    inner.style.transition = `transform ${durasi}s linear`;
    inner.style.transform = `translateX(-${lebih}px)`;

    const kembali = () => {
      inner.style.transition = `transform ${durasi}s linear`;
      inner.style.transform = "translateX(0)";
      const selesai = () => {
        inner.removeEventListener("transitionend", selesai);
        setJalan(false);
      };
      inner.addEventListener("transitionend", selesai);
    };
    // Diam sebentar di ujung sebelum kembali.
    window.setTimeout(kembali, (durasi + 0.6) * 1000);
  }, [jalan]);

  const onKey = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      mainkan();
    }
  };

  return (
    <Tag
      ref={wrapRef}
      className={`overflow-hidden whitespace-nowrap cursor-pointer select-none ${className}`}
      title={text}
      role="button"
      tabIndex={0}
      onClick={mainkan}
      onKeyDown={onKey}
      data-marquee={jalan ? "jalan" : "diam"}
    >
      <span ref={innerRef} className="inline-block will-change-transform">
        {text}
      </span>
    </Tag>
  );
}
