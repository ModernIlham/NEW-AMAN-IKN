import L from "leaflet";
import { toast } from "sonner";
import { buatPemantauLokasi } from "./pantauLokasi";
import { arahGerakSah, langkahJejak, JEJAK_MAKS_TITIK } from "./asetTerdekat";
import { formatJarak } from "./ukurPeta";

const IKON_LOKASI = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/><circle cx="12" cy="12" r="8"/></svg>';
// Ponsel dengan matahari kecil di layarnya = "layar tetap menyala".
const IKON_LAYAR = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="5" y="2" width="14" height="20" rx="2"/><circle cx="12" cy="12" r="2.2"/><path d="M12 6.8v1.2M12 16v1.2M7.6 12h1.2M15.2 12h1.2M9 9l.8.8M14.2 14.2l.8.8M15 9l-.8.8M9.8 14.2l-.8.8"/></svg>';
const IKON_JEJAK = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M8 19h7a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h7"/></svg>';
// Titik biru + kerucut arah gerak (disembunyikan bila arah tak sah).
const HTML_TITIK = '<div style="position:relative;width:16px;height:16px">'
  + '<div data-arah style="display:none;position:absolute;left:50%;top:50%;width:0;height:0;transform-origin:0 0;pointer-events:none">'
  + '<div style="position:absolute;left:-9px;top:-30px;width:0;height:0;border-left:9px solid transparent;border-right:9px solid transparent;border-bottom:22px solid rgba(37,99,235,.55)"></div></div>'
  + '<div style="position:absolute;inset:0;border-radius:50%;background:#2563eb;border:3px solid #fff;box-shadow:0 0 0 2px rgba(37,99,235,.35),0 1px 4px rgba(0,0,0,.4)"></div></div>';
const IKON_IKUTI = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m21 3-6 18-4-8-8-4Z"/></svg>';

// Kontrol bersama Peta Aset dan Peta Kolaborasi; lifecycle mengikuti Leaflet.
export function pasangLokasiSaya(map, { testId = "peta-lokasi-saya", visible = true, onPosisi } = {}) {
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
  let tombolLayar;
  let tombolJejak;
  // Jejak perjalanan sesi ini — HANYA di memori tab, hilang saat dimatikan.
  let jejak = null;      // L.polyline
  let titikJejak = [];
  let panjangJejak = 0;
  let jejakTampil = true;
  // Screen Wake Lock: opsional, hanya atas permintaan pengguna.
  let mauLayarNyala = false;
  let kunciLayar = null;
  const dukungKunciLayar = typeof navigator !== "undefined" && !!navigator.wakeLock;

  function hapusTitik() {
    if (marker) map.removeLayer(marker);
    if (lingkaran) map.removeLayer(lingkaran);
    if (jejak) map.removeLayer(jejak);
    marker = lingkaran = posisi = jejak = null;
    titikJejak = [];
    panjangJejak = 0;
    pertama = true;
    onPosisi?.(null);
  }

  function catatJejak(fix) {
    const langkah = langkahJejak(titikJejak[titikJejak.length - 1], fix);
    if (langkah === null) return;
    titikJejak.push({ lat: fix.lat, lng: fix.lng });
    panjangJejak += langkah;
    if (titikJejak.length > JEJAK_MAKS_TITIK) titikJejak.shift();
    if (!jejak) {
      jejak = L.polyline([], { color: "#2563eb", weight: 3, opacity: 0.6, dashArray: "1 6", lineCap: "round", interactive: false });
      if (jejakTampil) jejak.addTo(map);
    }
    jejak.setLatLngs(titikJejak.map((t) => [t.lat, t.lng]));
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

  let memintaKunci = false;
  async function mintaKunciLayar() {
    if (!dukungKunciLayar || !mauLayarNyala || !aktif || kunciLayar || memintaKunci
        || document.visibilityState === "hidden") return;
    memintaKunci = true;
    try {
      const k = await navigator.wakeLock.request("screen");
      // Pengguna mematikan / lokasi berhenti selama permintaan berjalan.
      if (!mauLayarNyala || !aktif) { k.release?.().catch?.(() => {}); return; }
      kunciLayar = k;
      // Sistem bisa melepas sendiri (baterai lemah, tab disembunyikan).
      k.addEventListener?.("release", () => { if (kunciLayar === k) kunciLayar = null; });
    } catch {
      kunciLayar = null; // ditolak (mode hemat daya) — fitur lain tetap jalan
      if (mauLayarNyala) {
        ubahLayar(false);
        kabar("Perangkat menolak menjaga layar tetap menyala (mode hemat daya?)");
      }
    } finally {
      memintaKunci = false;
    }
  }
  function lepasKunciLayar() {
    const k = kunciLayar;
    kunciLayar = null;
    k?.release?.().catch?.(() => {});
  }
  // Kunci layar dilepas OS saat tab tersembunyi; minta lagi saat kembali.
  const saatTerlihat = () => { if (document.visibilityState === "visible") mintaKunciLayar(); };
  function ubahLayar(nilai, beriKabar = false) {
    mauLayarNyala = nilai;
    gayaTombol(tombolLayar, nilai);
    labelTombol(tombolLayar, nilai ? "Layar tetap menyala (aktif) — ketuk untuk mematikan" : "Biarkan layar tetap menyala selama lokasi aktif");
    if (nilai) mintaKunciLayar(); else lepasKunciLayar();
    if (beriKabar) kabar(nilai ? "Layar tetap menyala selama lokasi aktif (lebih boros baterai)" : "Layar boleh padam lagi seperti biasa");
  }
  function ubahJejakTampil(nilai, beriKabar = false) {
    jejakTampil = nilai;
    gayaTombol(tombolJejak, nilai);
    labelTombol(tombolJejak, nilai ? "Sembunyikan garis jejak perjalanan" : "Tampilkan garis jejak perjalanan");
    if (jejak) { if (nilai) jejak.addTo(map); else map.removeLayer(jejak); }
    if (beriKabar) {
      kabar(nilai
        ? `Jejak: garis putus-putus jalur yang sudah Anda lalui${panjangJejak >= 1 ? ` (${formatJarak(panjangJejak)})` : " — mulai tercatat saat Anda berjalan"}`
        : "Garis jejak disembunyikan (tetap dicatat)");
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

  // Keadaan tombol HARUS terbaca sekilas: menyala = latar biru isi + ikon
  // putih; mati = latar putih + ikon gelap (dulu biru muda vs putih — terlalu
  // mirip di layar luar ruangan sehingga pengguna tak tahu mana yang aktif).
  function gayaTombol(el, tekan, peringatan = false) {
    el.setAttribute("aria-pressed", String(tekan));
    el.style.background = tekan ? (peringatan ? "#b45309" : "#2563eb") : "#fff";
    el.style.color = tekan ? "#fff" : "#0f172a";
  }
  function labelTombol(el, label) {
    el.title = label;
    el.setAttribute("aria-label", label);
  }

  // Penjelasan singkat EFEK tiap ketukan di kotak status (±3 dtk), lalu
  // kembali ke status lokasi. Di HP tak ada hover, jadi title/tooltip tak
  // pernah terlihat — tanpa ini ikon jejak/layar/ikuti tak bisa dipahami.
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
  // Legenda SEKALI per sesi saat lokasi pertama kali dinyalakan.
  const KUNCI_LEGENDA = "aman_lokasi_legenda";
  function legendaSekali() {
    try {
      if (sessionStorage.getItem(KUNCI_LEGENDA)) return;
      sessionStorage.setItem(KUNCI_LEGENDA, "1");
    } catch { /* tanpa storage: tetap tampilkan */ }
    kabar("Tombol di bawah: ➤ ikuti lokasi · 〰 jejak jalur Anda · 📱 layar tetap menyala. Biru = aktif.", 7000);
  }

  function ubahIkuti(nilai, beriKabar = false) {
    const berubah = mengikuti !== nilai;
    mengikuti = nilai;
    gayaTombol(ikuti, nilai);
    labelTombol(ikuti, nilai ? "Mengikuti lokasi Anda — ketuk untuk memusatkan ulang" : "Pusatkan peta dan ikuti lokasi Anda");
    if (beriKabar && berubah) {
      kabar(nilai ? "Ikuti: peta bergeser otomatis mengikuti Anda" : "Ikuti berhenti karena peta digeser — ketuk ➤ untuk mengikuti lagi");
    }
  }

  const gerakanPengguna = () => { if (aktif && !menggeser) ubahIkuti(false, true); };

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
    catatJejak(fix);
    pusatkan(pertama);
    pertama = false;
    onPosisi?.(fix);
  }

  const teksJejak = () => (panjangJejak >= 1 ? ` · jejak ${formatJarak(panjangJejak)}` : "");

  function tampilStatus(state) {
    aktif = state.active;
    const segar = state.status === "live" || state.status === "weak";
    const akurasi = state.position ? `±${Math.round(state.position.accuracy)} m` : "";
    const pesan = {
      off: "", searching: "Mencari lokasi…",
      live: `Lokasi aktif · ${akurasi}${teksJejak()}`, weak: `Akurasi rendah · ${akurasi}${teksJejak()}`,
      retrying: state.position ? "Mencari sinyal · lokasi terakhir" : "Mencari sinyal lokasi…",
      stale: "Lokasi belum diperbarui · mencari sinyal…", paused: "Lokasi dijeda",
      error: "",
    }[state.status];
    teksStatus = pesan;
    tulisInfo();
    labelTombol(tombol, aktif ? "Matikan lokasi Anda" : "Tampilkan lokasi Anda di peta");
    gayaTombol(tombol, aktif, aktif && !segar);
    ikuti.hidden = !aktif;
    ikuti.disabled = !posisi;
    tombolJejak.hidden = !aktif;
    tombolLayar.hidden = !aktif || !dukungKunciLayar;
    if (aktif) mintaKunciLayar(); else lepasKunciLayar();
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
      // dengan tombol zoom +/− : 30 px desktop, 36 px HP.
      const wadah = L.DomUtil.create("div", "leaflet-bar peta-lokasi-bar");
      wadah.style.cssText = "position:relative;display:flex;flex-direction:column";
      function buatTombol(label, ikon, id) {
        const el = L.DomUtil.create("button", "peta-lokasi-btn", wadah);
        el.type = "button";
        el.title = label;
        el.setAttribute("aria-label", label);
        el.setAttribute("aria-pressed", "false");
        el.setAttribute("data-testid", id);
        el.innerHTML = ikon;
        return el;
      }
      tombol = buatTombol("Tampilkan lokasi Anda", IKON_LOKASI, testId);
      ikuti = buatTombol("Pusatkan dan ikuti lokasi Anda", IKON_IKUTI, `${testId}-ikuti`);
      ikuti.hidden = true;
      tombolJejak = buatTombol("Sembunyikan jejak perjalanan", IKON_JEJAK, `${testId}-jejak`);
      tombolJejak.hidden = true;
      tombolLayar = buatTombol("Biarkan layar tetap menyala selama lokasi aktif", IKON_LAYAR, `${testId}-layar`);
      tombolLayar.hidden = true;
      info = L.DomUtil.create("div", "", wadah);
      info.setAttribute("role", "status");
      info.setAttribute("aria-live", "polite");
      info.setAttribute("aria-atomic", "true");
      info.style.cssText = "position:absolute;left:calc(100% + 6px);top:0;max-width:min(240px,calc(100vw - 110px));width:max-content;background:rgba(255,255,255,.95);color:#0f172a;font:500 11px/1.5 system-ui,sans-serif;padding:5px 8px;border-radius:5px;box-shadow:0 1px 4px #0003;pointer-events:none";
      info.hidden = true;
      pemantau = buatPemantauLokasi({ onPosition: gambar, onStatus: tampilStatus });
      pemantau.setVisible(visible);
      tombol.onclick = () => {
        if (aktif) { pemantau.stop(); kabar("Lokasi dimatikan — GPS berhenti, jejak dihapus"); }
        else { ubahIkuti(true); pemantau.start(); if (aktif) legendaSekali(); }
      };
      ikuti.onclick = () => {
        const sudah = mengikuti;
        ubahIkuti(true, true);
        if (sudah) kabar("Peta dipusatkan ke lokasi Anda");
        pusatkan(true);
      };
      tombolJejak.onclick = () => ubahJejakTampil(!jejakTampil, true);
      tombolLayar.onclick = () => ubahLayar(!mauLayarNyala, true);
      ubahJejakTampil(true);
      ubahLayar(false);
      document.addEventListener("visibilitychange", saatTerlihat);
      L.DomEvent.disableClickPropagation(wadah);
      L.DomEvent.disableScrollPropagation(wadah);
      map.on("movestart", gerakanPengguna);
      return wadah;
    },
    onRemove() {
      map.off("movestart", gerakanPengguna);
      document.removeEventListener("visibilitychange", saatTerlihat);
      pemantau.destroy();
      lepasKunciLayar();
      tombol.onclick = ikuti.onclick = tombolJejak.onclick = tombolLayar.onclick = null;
      clearTimeout(kabarTimer);
    },
  });
  const kontrol = new LokasiControl({ position: "topleft" }).addTo(map);
  return { setVisible: (nilai) => pemantau.setVisible(nilai), destroy: () => kontrol.remove() };
}
