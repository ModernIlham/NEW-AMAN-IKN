import L from "leaflet";
import { toast } from "sonner";
import { buatPemantauLokasi } from "./pantauLokasi";
import { arahGerakSah } from "./asetTerdekat";

const IKON_LOKASI = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/><circle cx="12" cy="12" r="8"/></svg>';
// Titik biru + kerucut arah gerak (disembunyikan bila arah tak sah).
const HTML_TITIK = '<div style="position:relative;width:16px;height:16px">'
  + '<div data-arah style="display:none;position:absolute;left:50%;top:50%;width:0;height:0;transform-origin:0 0;pointer-events:none">'
  + '<div style="position:absolute;left:-9px;top:-30px;width:0;height:0;border-left:9px solid transparent;border-right:9px solid transparent;border-bottom:22px solid rgba(37,99,235,.55)"></div></div>'
  + '<div style="position:absolute;inset:0;border-radius:50%;background:#2563eb;border:3px solid #fff;box-shadow:0 0 0 2px rgba(37,99,235,.35),0 1px 4px rgba(0,0,0,.4)"></div></div>';

/**
 * Kontrol "Lokasi Anda" bersama Peta Aset & Peta Kolaborasi.
 *
 * SATU tombol, pola yang sudah dikenal dari aplikasi peta umum:
 *   mati            → ketuk: nyalakan GPS + ikuti
 *   aktif, mengikuti→ ketuk: matikan
 *   aktif, peta digeser (tidak mengikuti) → ketuk: kembali ke lokasi Anda
 * Keadaan terbaca dari warna: biru isi = mengikuti, putih ikon biru = aktif
 * tapi peta sedang dilihat di tempat lain, putih ikon gelap = mati.
 *
 * `setTujuan({lat,lng}|null)` menggambar garis pandu dari lokasi Anda ke aset
 * tujuan; diperbarui tiap fix.
 */
export function pasangLokasiSaya(map, { testId = "peta-lokasi-saya", visible = true, onPosisi, tampilAkurasi = true } = {}) {
  let aktif = false;
  let mengikuti = true;
  let menggeser = false;
  let pertama = true;
  let segar = false;
  let posisi = null;
  let marker = null;
  let lingkaran = null;
  let tombol;
  let info;
  let pemantau;
  let tujuan = null;
  let garisTujuan = null;

  function hapusTitik() {
    if (marker) map.removeLayer(marker);
    if (lingkaran) map.removeLayer(lingkaran);
    if (garisTujuan) map.removeLayer(garisTujuan);
    marker = lingkaran = posisi = garisTujuan = null;
    pertama = true;
    onPosisi?.(null);
  }

  function gambarGarisTujuan() {
    if (!posisi || !tujuan) {
      if (garisTujuan) { map.removeLayer(garisTujuan); garisTujuan = null; }
      return;
    }
    const titik = [[posisi.lat, posisi.lng], [tujuan.lat, tujuan.lng]];
    if (!garisTujuan) {
      garisTujuan = L.polyline(titik, {
        color: "#7c3aed", weight: 3, opacity: 0.85, dashArray: "6 8", lineCap: "round", interactive: false,
      }).addTo(map);
    } else {
      garisTujuan.setLatLngs(titik);
    }
  }

  function aturArah(fix) {
    const el = marker?.getElement?.()?.querySelector("[data-arah]");
    if (!el) return;
    if (arahGerakSah(fix)) {
      el.style.display = "block";
      el.style.transform = `rotate(${Math.round(fix.heading)}deg)`;
    } else {
      el.style.display = "none";
    }
  }

  function pusatkan(zoomAwal = false) {
    if (!posisi || !mengikuti) return;
    // Gerakan kamera sendiri tidak mematikan mode ikuti. Tanpa animasi,
    // update GPS berikutnya tidak menumpuk animasi pan pada perangkat lambat.
    menggeser = true;
    try {
      if (zoomAwal) {
        map.fitBounds(lingkaran.getBounds(), {
          maxZoom: Math.max(map.getZoom(), 17), padding: [40, 40], animate: false,
        });
      } else if (!map.getBounds().pad(-0.25).contains([posisi.lat, posisi.lng])) {
        map.panTo([posisi.lat, posisi.lng], { animate: false });
      }
    } finally { menggeser = false; }
  }

  // Pesan singkat di kotak status (±3 dtk) lalu kembali ke status lokasi.
  let teksStatus = "";
  let kabarTimer = null;
  function tulisInfo() {
    const teks = kabarTimer ? info.dataset.kabar : teksStatus;
    if (info.textContent !== teks) info.textContent = teks;
    info.hidden = !teks;
  }
  function kabar(teks, lama = 3000) {
    clearTimeout(kabarTimer);
    info.dataset.kabar = teks;
    kabarTimer = setTimeout(() => { kabarTimer = null; tulisInfo(); }, lama);
    tulisInfo();
  }

  function gayaTombol() {
    let label;
    if (!aktif) {
      tombol.style.background = "#fff";
      tombol.style.color = "#0f172a";
      label = "Tampilkan & ikuti lokasi Anda";
    } else if (mengikuti) {
      tombol.style.background = segar ? "#2563eb" : "#b45309";
      tombol.style.color = "#fff";
      label = "Lokasi aktif & diikuti — ketuk untuk mematikan";
    } else {
      tombol.style.background = "#fff";
      tombol.style.color = segar ? "#2563eb" : "#b45309";
      label = "Kembali ke lokasi Anda";
    }
    tombol.setAttribute("aria-pressed", String(aktif));
    tombol.title = label;
    tombol.setAttribute("aria-label", label);
  }

  function ubahIkuti(nilai) {
    if (mengikuti === nilai) return;
    mengikuti = nilai;
    gayaTombol();
    if (!nilai && aktif) kabar("Peta digeser — ketuk ◎ untuk kembali ke lokasi Anda");
  }

  const gerakanPengguna = () => { if (aktif && !menggeser) ubahIkuti(false); };

  function gambar(fix) {
    posisi = fix;
    const titik = [fix.lat, fix.lng];
    if (!marker) {
      lingkaran = L.circle(titik, {
        radius: Math.max(fix.accuracy, 1), color: "#2563eb", weight: 1,
        fillColor: "#3b82f6", fillOpacity: 0.12, interactive: false,
      }).addTo(map);
      marker = L.marker(titik, {
        keyboard: false, zIndexOffset: 1000,
        icon: L.divIcon({ className: "", html: HTML_TITIK, iconSize: [16, 16], iconAnchor: [8, 8] }),
      }).addTo(map).bindTooltip("Lokasi Anda", { direction: "top" });
    } else {
      marker.setLatLng(titik);
      lingkaran.setLatLng(titik).setRadius(Math.max(fix.accuracy, 1));
    }
    aturArah(fix);
    gambarGarisTujuan();
    pusatkan(pertama);
    pertama = false;
    onPosisi?.(fix);
  }

  function tampilStatus(state) {
    aktif = state.active;
    segar = state.status === "live" || state.status === "weak";
    const akurasi = state.position ? `±${Math.round(state.position.accuracy)} m` : "";
    teksStatus = {
      off: "", searching: "Mencari lokasi…",
      // Peta dengan panel lapangan menampilkan akurasi di panelnya sendiri —
      // kotak status hanya untuk pesan & keadaan bermasalah agar tak
      // menutupi popup pin.
      live: tampilAkurasi ? `Lokasi aktif · ${akurasi}` : "",
      weak: tampilAkurasi ? `Akurasi rendah · ${akurasi}` : "",
      retrying: state.position ? "Mencari sinyal · lokasi terakhir" : "Mencari sinyal lokasi…",
      stale: "Lokasi belum diperbarui · mencari sinyal…", paused: "Lokasi dijeda",
      error: "",
    }[state.status];
    tulisInfo();
    gayaTombol();
    if (!aktif) hapusTitik();
    if (marker) {
      marker.setOpacity(segar ? 1 : 0.45);
      lingkaran.setStyle({ color: segar ? "#2563eb" : "#b45309" });
      const jam = new Date(state.position.timestamp).toLocaleTimeString("id-ID");
      marker.setTooltipContent(`${segar ? "Lokasi Anda" : "Lokasi terakhir"} (${akurasi}) · ${jam}`);
    }
    if (state.status === "error") toast.error(state.message);
  }

  const LokasiControl = L.Control.extend({
    onAdd() {
      // Ukuran tombol dari CSS (`.peta-lokasi-btn` di index.css) agar SAMA
      // dengan tombol zoom +/− : 26/30 px desktop, 36 px HP.
      const wadah = L.DomUtil.create("div", "leaflet-bar peta-lokasi-bar");
      wadah.style.cssText = "position:relative;display:flex;flex-direction:column";
      tombol = L.DomUtil.create("button", "peta-lokasi-btn", wadah);
      tombol.type = "button";
      tombol.setAttribute("data-testid", testId);
      tombol.innerHTML = IKON_LOKASI;
      info = L.DomUtil.create("div", "", wadah);
      info.setAttribute("role", "status");
      info.setAttribute("aria-live", "polite");
      info.setAttribute("aria-atomic", "true");
      info.style.cssText = "position:absolute;left:calc(100% + 6px);top:0;max-width:min(240px,calc(100vw - 110px));width:max-content;background:rgba(255,255,255,.95);color:#0f172a;font:500 11px/1.5 system-ui,sans-serif;padding:5px 8px;border-radius:5px;box-shadow:0 1px 4px #0003;pointer-events:none";
      info.hidden = true;
      gayaTombol();
      pemantau = buatPemantauLokasi({ onPosition: gambar, onStatus: tampilStatus });
      pemantau.setVisible(visible);
      tombol.onclick = () => {
        if (!aktif) {
          mengikuti = true;
          pemantau.start();
        } else if (!mengikuti) {
          mengikuti = true;
          gayaTombol();
          pusatkan(true);
          kabar("Kembali mengikuti lokasi Anda · ketuk lagi untuk mematikan");
        } else {
          pemantau.stop();
          kabar("Lokasi dimatikan");
        }
      };
      L.DomEvent.disableClickPropagation(wadah);
      L.DomEvent.disableScrollPropagation(wadah);
      map.on("movestart", gerakanPengguna);
      return wadah;
    },
    onRemove() {
      map.off("movestart", gerakanPengguna);
      pemantau.destroy();
      tombol.onclick = null;
      clearTimeout(kabarTimer);
    },
  });
  const kontrol = new LokasiControl({ position: "topleft" }).addTo(map);
  return {
    setVisible: (nilai) => pemantau.setVisible(nilai),
    /**
     * Aplikasi akan menggeser peta (mis. fokus ke pin aset): berhenti
     * mengikuti TANPA pesan "Peta digeser" — pesan itu untuk geseran pengguna
     * dan hanya akan menutupi popup yang sedang dibuka.
     */
    berhentiMengikuti() {
      if (!aktif || !mengikuti) return;
      mengikuti = false;
      gayaTombol();
    },
    /** Garis pandu ke aset tujuan; null untuk menghapus. */
    setTujuan(t) {
      const baru = t && Number.isFinite(t.lat) && Number.isFinite(t.lng) ? { lat: t.lat, lng: t.lng } : null;
      const ganti = !!baru && (!tujuan || tujuan.lat !== baru.lat || tujuan.lng !== baru.lng);
      tujuan = baru;
      gambarGarisTujuan();
      // Tujuan baru: tampilkan Anda DAN aset sekaligus. Gerakan kamera ini
      // milik aplikasi, jadi mode ikuti tidak dianggap dimatikan pengguna.
      if (ganti && posisi) {
        menggeser = true;
        try {
          map.fitBounds(L.latLngBounds([[posisi.lat, posisi.lng], [baru.lat, baru.lng]]), {
            padding: [70, 70], maxZoom: 19, animate: false,
          });
        } finally { menggeser = false; }
      }
    },
    destroy: () => kontrol.remove(),
  };
}
