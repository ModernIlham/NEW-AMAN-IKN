import L from "leaflet";
import { toast } from "sonner";
import { buatPemantauLokasi } from "./pantauLokasi";

const IKON_LOKASI = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/><circle cx="12" cy="12" r="8"/></svg>';
const IKON_IKUTI = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m21 3-6 18-4-8-8-4Z"/></svg>';

// Kontrol bersama Peta Aset dan Peta Kolaborasi; lifecycle mengikuti Leaflet.
export function pasangLokasiSaya(map, { testId = "peta-lokasi-saya", visible = true } = {}) {
  let aktif = false;
  let mengikuti = true;
  let menggeser = false;
  let pertama = true;
  let posisi = null;
  let marker = null;
  let lingkaran = null;
  let tombol;
  let ikuti;
  let info;
  let pemantau;

  function hapusTitik() {
    if (marker) map.removeLayer(marker);
    if (lingkaran) map.removeLayer(lingkaran);
    marker = lingkaran = posisi = null;
    pertama = true;
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

  function ubahIkuti(nilai) {
    mengikuti = nilai;
    ikuti.setAttribute("aria-pressed", String(nilai));
    ikuti.style.color = nilai ? "#2563eb" : "#475569";
    ikuti.style.background = nilai ? "#eff6ff" : "#fff";
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
        keyboard: false,
        icon: L.divIcon({
          className: "",
          html: '<div style="width:16px;height:16px;border-radius:50%;background:#2563eb;border:3px solid #fff;box-shadow:0 0 0 2px rgba(37,99,235,.35),0 1px 4px rgba(0,0,0,.4)"></div>',
          iconSize: [16, 16], iconAnchor: [8, 8],
        }),
      }).addTo(map).bindTooltip("Lokasi Anda", { direction: "top" });
    } else {
      marker.setLatLng(titik);
      lingkaran.setLatLng(titik).setRadius(Math.max(fix.accuracy, 1));
    }
    pusatkan(pertama);
    pertama = false;
  }

  function tampilStatus(state) {
    aktif = state.active;
    const segar = state.status === "live" || state.status === "weak";
    const akurasi = state.position ? `±${Math.round(state.position.accuracy)} m` : "";
    const pesan = {
      off: "", searching: "Mencari lokasi…",
      live: `Lokasi aktif · ${akurasi}`, weak: `Akurasi rendah · ${akurasi}`,
      retrying: state.position ? "Mencari sinyal · lokasi terakhir" : "Mencari sinyal lokasi…",
      stale: "Lokasi belum diperbarui · mencari sinyal…", paused: "Lokasi dijeda",
      error: "",
    }[state.status];
    if (info.textContent !== pesan) info.textContent = pesan;
    info.hidden = !pesan;
    const label = aktif ? "Matikan pembaruan lokasi Anda" : "Tampilkan lokasi Anda";
    tombol.title = label;
    tombol.setAttribute("aria-label", label);
    tombol.setAttribute("aria-pressed", String(aktif));
    tombol.style.background = aktif ? "#eff6ff" : "#fff";
    tombol.style.color = aktif ? (segar ? "#2563eb" : "#b45309") : "#0f172a";
    ikuti.hidden = !aktif;
    ikuti.disabled = !posisi;
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
      const wadah = L.DomUtil.create("div", "leaflet-bar");
      wadah.style.cssText = "position:relative;display:flex;flex-direction:column";
      function buatTombol(label, ikon, id) {
        const el = L.DomUtil.create("button", "", wadah);
        el.type = "button";
        el.title = label;
        el.setAttribute("aria-label", label);
        el.setAttribute("aria-pressed", "false");
        el.setAttribute("data-testid", id);
        el.style.cssText = "width:44px;height:44px;min-width:44px;min-height:44px;border:0;border-radius:2px;background:#fff;color:#0f172a;cursor:pointer;vertical-align:middle;padding:12px";
        el.innerHTML = ikon;
        return el;
      }
      tombol = buatTombol("Tampilkan lokasi Anda", IKON_LOKASI, testId);
      ikuti = buatTombol("Pusatkan dan ikuti lokasi Anda", IKON_IKUTI, `${testId}-ikuti`);
      ikuti.hidden = true;
      info = L.DomUtil.create("div", "", wadah);
      info.setAttribute("role", "status");
      info.setAttribute("aria-live", "polite");
      info.setAttribute("aria-atomic", "true");
      info.style.cssText = "position:absolute;left:50px;top:0;max-width:min(220px,calc(100vw - 120px));width:max-content;background:rgba(255,255,255,.95);color:#0f172a;font:500 11px/1.5 system-ui,sans-serif;padding:5px 8px;border-radius:5px;box-shadow:0 1px 4px #0003;pointer-events:none";
      info.hidden = true;
      pemantau = buatPemantauLokasi({ onPosition: gambar, onStatus: tampilStatus });
      pemantau.setVisible(visible);
      tombol.onclick = () => {
        if (aktif) pemantau.stop();
        else { ubahIkuti(true); pemantau.start(); }
      };
      ikuti.onclick = () => { ubahIkuti(true); pusatkan(true); };
      L.DomEvent.disableClickPropagation(wadah);
      L.DomEvent.disableScrollPropagation(wadah);
      map.on("movestart", gerakanPengguna);
      return wadah;
    },
    onRemove() {
      map.off("movestart", gerakanPengguna);
      pemantau.destroy();
      tombol.onclick = ikuti.onclick = null;
    },
  });
  const kontrol = new LokasiControl({ position: "topleft" }).addTo(map);
  return { setVisible: (nilai) => pemantau.setVisible(nilai), destroy: () => kontrol.remove() };
}
