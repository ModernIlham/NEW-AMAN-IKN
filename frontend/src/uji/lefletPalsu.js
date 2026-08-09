/**
 * Tiruan Leaflet untuk uji render jsdom — backlog #346.
 *
 * Leaflet asli menuntut ukuran elemen nyata (getBoundingClientRect jsdom
 * selalu 0×0) dan menyentuh API peramban yang tak ada di jsdom, sehingga
 * `L.map()` sungguhan mustahil di lingkungan uji. Tiruan ini membuat
 * komponen berpeta BISA DIRENDER — dua insiden nyata yang melahirkan
 * backlog ini ("Cannot access before initialization" di Peta Aset, dan
 * `kirimGeserRef` yang tak pernah dideklarasikan di Peta Kolaborasi)
 * sama-sama jatuh SEBELUM Leaflet menggambar apa pun, jadi tiruan dangkal
 * sudah cukup untuk menangkap kelas cacat itu.
 *
 * DESAIN: inti berantai berbasis Proxy — setiap properti/panggilan yang tak
 * dikenal mengembalikan stub berantai lain — plus kembalian KONKRET untuk
 * metode yang hasilnya benar-benar dihitung pemanggil (getZoom + 1,
 * getBounds().contains(), destructuring {lat, lng}). Dua bagian dibuat
 * NYATA, bukan stub:
 *   - `DomUtil.create` membuat elemen DOM sungguhan — kontrol kustom
 *     (`L.Control.extend`) merakit tombolnya lewat sini;
 *   - `Control.extend` mengembalikan konstruktor sungguhan yang menjalankan
 *     `onAdd` saat `addTo` — supaya cacat di badan kontrol ikut terdeteksi.
 *
 * Batas yang diketahui: tak ada event yang benar-benar menembak (m.on(...)
 * tercatat sebagai no-op), jadi uji di atasnya menguji MOUNT + toolbar,
 * bukan interaksi kartografis.
 */

let idBerikut = 1;

function latLng(lat = -1.4, lng = 116.7) {
  return {
    lat,
    lng,
    equals: (b) => !!b && b.lat === lat && b.lng === lng,
    distanceTo: () => 0,
    clone: () => latLng(lat, lng),
    wrap: () => latLng(lat, lng),
  };
}

function titik(x = 0, y = 0) {
  return {
    x,
    y,
    distanceTo: () => 0,
    add: () => titik(x, y),
    subtract: () => titik(x, y),
  };
}

function bounds() {
  return {
    contains: () => true,
    intersects: () => true,
    isValid: () => true,
    pad: () => bounds(),
    extend: () => bounds(),
    getCenter: () => latLng(),
    getSouthWest: () => latLng(-1.5, 116.6),
    getNorthEast: () => latLng(-1.3, 116.8),
    getWest: () => 116.6,
    getEast: () => 116.8,
    getSouth: () => -1.5,
    getNorth: () => -1.3,
    toBBoxString: () => "116.6,-1.5,116.8,-1.3",
  };
}

// Metode yang HASILNYA dipakai berhitung/destrukturisasi oleh pemanggil.
const KEMBALIAN = {
  getZoom: () => 13,
  getMaxZoom: () => 19,
  getMinZoom: () => 3,
  getBoundsZoom: () => 13,
  getZoomScale: () => 1,
  getCenter: () => latLng(),
  getLatLng: () => latLng(),
  getLatLngs: () => [],
  getBounds: () => bounds(),
  getSize: () => titik(800, 600),
  latLngToContainerPoint: () => titik(400, 300),
  latLngToLayerPoint: () => titik(400, 300),
  containerPointToLatLng: () => latLng(),
  layerPointToLatLng: () => latLng(),
  mouseEventToLatLng: () => latLng(),
  mouseEventToContainerPoint: () => titik(400, 300),
  distance: () => 0,
  getLayers: () => [],
  getPane: () => document.createElement("div"),
  getPanes: () => ({}),
  getContainer: () => document.createElement("div"),
  getElement: () => document.createElement("div"),
  hasLayer: () => false,
  listens: () => false,
  toGeoJSON: () => ({ type: "FeatureCollection", features: [] }),
  getRadius: () => 10,
};

function berantai(nama = "") {
  const panggil = (...args) => {
    if (nama === "whenReady" && typeof args[0] === "function") {
      args[0]();
      return berantai();
    }
    // eachLayer: tak ada layer → callback TIDAK dipanggil.
    if (KEMBALIAN[nama]) return KEMBALIAN[nama](...args);
    return berantai();
  };
  return new Proxy(panggil, {
    get(_t, p) {
      if (typeof p === "symbol") {
        return p === Symbol.toPrimitive ? () => 0 : undefined;
      }
      if (p === "then") return undefined; // jangan pernah thenable
      if (p === "options") return {};
      return berantai(String(p));
    },
    set: () => true,
    deleteProperty: () => true,
    construct: () => berantai(nama),
    has: () => true,
  });
}

const DomUtil = {
  create(tag, kelas, induk) {
    const el = document.createElement(tag || "div");
    if (kelas) el.className = kelas;
    if (induk && typeof induk.appendChild === "function") induk.appendChild(el);
    return el;
  },
  addClass(el, k) {
    try { el.classList.add(...String(k).split(/\s+/).filter(Boolean)); } catch { /* stub */ }
  },
  removeClass(el, k) {
    try { el.classList.remove(...String(k).split(/\s+/).filter(Boolean)); } catch { /* stub */ }
  },
  hasClass(el, k) {
    try { return el.classList.contains(k); } catch { return false; }
  },
  empty(el) {
    try { el.innerHTML = ""; } catch { /* stub */ }
  },
  remove(el) {
    try { el.remove(); } catch { /* stub */ }
  },
  setOpacity() {},
  setTransform() {},
  setPosition() {},
  getPosition: () => titik(),
  toFront() {},
  toBack() {},
};

const DomEvent = {};
[
  "on", "off", "stop", "stopPropagation", "preventDefault",
  "disableClickPropagation", "disableScrollPropagation",
  "addListener", "removeListener",
].forEach((n) => { DomEvent[n] = () => DomEvent; });

function extendKelas(def = {}) {
  function Kelas(opsi) {
    this.options = { ...(def.options || {}), ...(opsi || {}) };
    if (typeof def.initialize === "function") {
      try { def.initialize.apply(this, arguments); } catch { /* stub */ }
    }
  }
  Object.assign(Kelas.prototype, def, {
    addTo(peta) {
      try { if (typeof this.onAdd === "function") this.onAdd(peta); } catch { /* stub */ }
      return this;
    },
    remove() {
      try { if (typeof this.onRemove === "function") this.onRemove(); } catch { /* stub */ }
      return this;
    },
  });
  Kelas.extend = extendKelas;
  return Kelas;
}

const control = () => berantai("control");
["scale", "zoom", "layers", "attribution"].forEach((n) => {
  control[n] = () => berantai(`control.${n}`);
});

const IconDefault = extendKelas({});
IconDefault.mergeOptions = () => {};
IconDefault.imagePath = "";

const L = {
  map: () => berantai("map"),
  tileLayer: () => berantai("tileLayer"),
  marker: () => berantai("marker"),
  divIcon: (o) => ({ options: o || {}, __divIcon: true }),
  icon: (o) => ({ options: o || {}, __icon: true }),
  layerGroup: () => berantai("layerGroup"),
  featureGroup: () => berantai("featureGroup"),
  geoJSON: () => berantai("geoJSON"),
  polyline: () => berantai("polyline"),
  polygon: () => berantai("polygon"),
  rectangle: () => berantai("rectangle"),
  circle: () => berantai("circle"),
  circleMarker: () => berantai("circleMarker"),
  popup: () => berantai("popup"),
  tooltip: () => berantai("tooltip"),
  canvas: () => berantai("canvas"),
  svg: () => berantai("svg"),
  markerClusterGroup: () => berantai("markerClusterGroup"),
  latLng: (a, b) => {
    if (Array.isArray(a)) return latLng(Number(a[0]), Number(a[1]));
    if (a && typeof a === "object") return latLng(Number(a.lat), Number(a.lng));
    return latLng(Number(a), Number(b));
  },
  latLngBounds: () => bounds(),
  point: (x, y) => titik(x, y),
  control,
  Control: { extend: extendKelas },
  Class: { extend: extendKelas },
  Handler: { extend: extendKelas },
  LayerGroup: extendKelas({}),
  Icon: Object.assign(extendKelas({}), { Default: IconDefault }),
  DomUtil,
  DomEvent,
  Browser: { mobile: false, touch: false, retina: false, pointer: false },
  Util: {
    stamp: (o) => {
      if (!o.__idPalsu) {
        try { o.__idPalsu = idBerikut; idBerikut += 1; } catch { return idBerikut; }
      }
      return o.__idPalsu;
    },
    throttle: (fn) => fn,
    extend: Object.assign,
  },
  CRS: { EPSG3857: {} },
  version: "tiruan-uji",
};
L.noConflict = () => L;

// `import L from "leaflet"` (interop Babel): default DAN namespace sama-sama L.
module.exports = L;
module.exports.default = L;
