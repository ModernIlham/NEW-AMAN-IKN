import { toast } from "sonner";

/**
 * Deteksi versi baru TANPA pengguna harus menghapus cache.
 *
 * Masalah: build CRA memberi hash pada semua aset (main.<hash>.js) sehingga
 * aset otomatis bust-cache — tapi index.html sendiri bisa tersimpan di cache
 * browser/host, sehingga setelah deploy pengguna tetap memuat bundle LAMA
 * sampai mereka menghapus cache manual.
 *
 * Solusi: secara berkala (dan saat tab kembali fokus / online) ambil
 * /index.html dengan cache:'no-store', bandingkan nama bundle main.<hash>.js
 * di dalamnya dengan bundle yang SEDANG berjalan. Beda → versi baru sudah
 * terpasang di server → tampilkan toast permanen dengan tombol "Muat Ulang"
 * (fetch index.html cache:'reload' menyegarkan entri cache HTTP, lalu
 * location.reload() memuat bundle baru). Tidak pernah memaksa reload otomatis
 * agar input yang sedang diketik/antrean offline tidak terganggu.
 */
const CHECK_INTERVAL_MS = 5 * 60 * 1000; // 5 menit
let notifiedFor = null; // hash versi baru yang sudah ditoast (anti-duplikat)

function currentMainBundle() {
  const s = document.querySelector('script[src*="/static/js/main."]');
  if (!s) return null; // mode dev (bundle.js) / struktur tak dikenal → nonaktif
  const m = s.src.match(/main\.[A-Za-z0-9]+\.js/);
  return m ? m[0] : null;
}

async function latestMainBundle() {
  const res = await fetch(`/index.html?_=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) return null;
  const html = await res.text();
  const m = html.match(/main\.[A-Za-z0-9]+\.js/);
  return m ? m[0] : null;
}

async function checkOnce() {
  if (typeof navigator !== "undefined" && navigator.onLine === false) return;
  const current = currentMainBundle();
  if (!current) return;
  let latest = null;
  try {
    latest = await latestMainBundle();
  } catch { return; /* offline/transient — coba lagi nanti */ }
  if (!latest || latest === current || notifiedFor === latest) return;
  notifiedFor = latest;
  toast.info("Versi baru aplikasi tersedia.", {
    id: "app-update-available",
    duration: Infinity,
    action: {
      label: "Muat Ulang",
      onClick: async () => {
        // Segarkan entri cache index.html lalu muat ulang → bundle baru terpakai
        try { await fetch("/index.html", { cache: "reload" }); } catch { /* tetap reload */ }
        window.location.reload();
      },
    },
  });
}

/** Pasang pemeriksa versi: interval + saat tab kembali terlihat + saat online. */
export function startUpdateCheck() {
  if (typeof window === "undefined") return () => {};
  const onVisible = () => { if (document.visibilityState === "visible") checkOnce(); };
  const interval = setInterval(checkOnce, CHECK_INTERVAL_MS);
  document.addEventListener("visibilitychange", onVisible);
  window.addEventListener("online", checkOnce);
  // Pemeriksaan pertama sesaat setelah aplikasi siap
  const t = setTimeout(checkOnce, 15000);
  return () => {
    clearInterval(interval);
    clearTimeout(t);
    document.removeEventListener("visibilitychange", onVisible);
    window.removeEventListener("online", checkOnce);
  };
}

export default startUpdateCheck;
