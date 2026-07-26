// L.ImageOverlay.Rotated — overlay gambar yang bisa diputar/di-skew lewat TIGA
// titik kontrol (kiri-atas, kanan-atas, kiri-bawah) alih-alih dua.
//
// DI-VENDOR dari paket `leaflet-imageoverlay-rotated` v0.2.1 karya
// Iván Sánchez Ortega (lisensi Beerware, "THE BEER-WARE LICENSE" Rev 42 —
// bebas dipakai untuk apa pun). Alasan vendoring, bukan dependensi npm:
// paket aslinya menulis langsung ke GLOBAL `L` tanpa mengimpor leaflet,
// sehingga `import` di bundler CRA lolos build tetapi meledak saat runtime
// ("L is not defined") — kelas kegagalan senyap yang justru ingin kita
// hindari. Versi ini modul ES murni: leaflet diimpor eksplisit.
// Perubahan dari asli: pembungkus modul + impor; badan kelas tidak diubah.
import L from "leaflet";

L.ImageOverlay.Rotated = L.ImageOverlay.extend({

  initialize: function (image, topleft, topright, bottomleft, options) {
    if (typeof image === "string") {
      this._url = image;
    } else {
      // Anggap parameter pertama HTMLImageElement / HTMLCanvasElement.
      this._rawImage = image;
    }
    this._topLeft = L.latLng(topleft);
    this._topRight = L.latLng(topright);
    this._bottomLeft = L.latLng(bottomleft);
    L.setOptions(this, options);
  },

  onAdd: function (map) {
    if (!this._image) {
      this._initImage();
      if (this.options.opacity < 1) {
        this._updateOpacity();
      }
    }
    if (this.options.interactive) {
      L.DomUtil.addClass(this._rawImage, "leaflet-interactive");
      this.addInteractiveTarget(this._rawImage);
    }
    map.on("zoomend resetview", this._reset, this);
    this.getPane().appendChild(this._image);
    this._reset();
  },

  onRemove: function (map) {
    map.off("zoomend resetview", this._reset, this);
    L.ImageOverlay.prototype.onRemove.call(this, map);
  },

  _initImage: function () {
    let img = this._rawImage;
    if (this._url) {
      img = L.DomUtil.create("img");
      img.style.display = "none"; // sembunyikan sampai transform pertama
      if (this.options.crossOrigin) {
        img.crossOrigin = "";
      }
      img.src = this._url;
      this._rawImage = img;
    }
    L.DomUtil.addClass(img, "leaflet-image-layer");

    // `this._image` dipakai ulang metode kelas induk — namanya harus tetap,
    // meski di sini isinya <div> pembungkus.
    const div = (this._image = L.DomUtil.create(
      "div",
      "leaflet-image-layer " + (this._zoomAnimated ? "leaflet-zoom-animated" : "")
    ));
    this._updateZIndex();
    div.appendChild(img);
    div.onselectstart = L.Util.falseFn;
    div.onmousemove = L.Util.falseFn;
    img.onload = function () {
      this._reset();
      img.style.display = "block";
      this.fire("load");
    }.bind(this);
    // Tambahan dari vendoring: tanpa onerror, gambar 404/rusak tinggal
    // display:none selamanya — overlay kosong TANPA satu pun sinyal
    // (temuan tinjauan). Pemakai layer menangkap event "error" ini.
    img.onerror = function () {
      this.fire("error");
    }.bind(this);
    img.alt = this.options.alt;
  },

  _reset: function () {
    const div = this._image;
    if (!this._map) {
      return;
    }

    // Proyeksikan titik kontrol ke koordinat piksel layer.
    const pxTopLeft = this._map.latLngToLayerPoint(this._topLeft);
    const pxTopRight = this._map.latLngToLayerPoint(this._topRight);
    const pxBottomLeft = this._map.latLngToLayerPoint(this._bottomLeft);
    // Sudut kanan-bawah disimpulkan (jajar genjang).
    const pxBottomRight = pxTopRight.subtract(pxTopLeft).add(pxBottomLeft);

    const pxBounds = L.bounds([pxTopLeft, pxTopRight, pxBottomLeft, pxBottomRight]);
    const size = pxBounds.getSize();
    const pxTopLeftInDiv = pxTopLeft.subtract(pxBounds.min);

    // LatLngBounds dibutuhkan animasi zoom kelas induk.
    this._bounds = L.latLngBounds(
      this._map.layerPointToLatLng(pxBounds.min),
      this._map.layerPointToLatLng(pxBounds.max)
    );

    L.DomUtil.setPosition(div, pxBounds.min);
    div.style.width = size.x + "px";
    div.style.height = size.y + "px";

    const imgW = this._rawImage.width;
    const imgH = this._rawImage.height;
    if (!imgW || !imgH) {
      return; // gambar belum termuat
    }

    const vectorX = pxTopRight.subtract(pxTopLeft);
    const vectorY = pxBottomLeft.subtract(pxTopLeft);

    this._rawImage.style.transformOrigin = "0 0";
    // Matriks affine hasil penyederhanaan skew/rotasi/skala.
    this._rawImage.style.transform =
      "matrix(" +
      vectorX.x / imgW + ", " + vectorX.y / imgW + ", " +
      vectorY.x / imgH + ", " + vectorY.y / imgH + ", " +
      pxTopLeftInDiv.x + ", " + pxTopLeftInDiv.y + ")";
  },

  reposition: function (topleft, topright, bottomleft) {
    this._topLeft = L.latLng(topleft);
    this._topRight = L.latLng(topright);
    this._bottomLeft = L.latLng(bottomleft);
    this._reset();
  },

  setUrl: function (url) {
    this._url = url;
    if (this._rawImage) {
      this._rawImage.src = url;
    }
    return this;
  },
});

L.imageOverlay.rotated = function (imgSrc, topleft, topright, bottomleft, options) {
  return new L.ImageOverlay.Rotated(imgSrc, topleft, topright, bottomleft, options);
};

export default L.ImageOverlay.Rotated;
