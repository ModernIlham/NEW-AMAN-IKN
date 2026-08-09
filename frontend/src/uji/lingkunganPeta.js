/**
 * Pemasang API peramban yang TIDAK disediakan jsdom — pasangan lefletPalsu
 * untuk uji render halaman berpeta (backlog #346).
 *
 * Panggil dari `beforeAll` berkas uji. Keduanya idempoten dan tidak butuh
 * pembongkaran: jsdom dibuang utuh per berkas uji.
 */

/**
 * WebSocket tiruan: konstruktor tercatat, tak pernah benar-benar konek.
 * Mengembalikan larik instans supaya uji bisa menegaskan "halaman memasang
 * socket ke URL yang benar" tanpa server. Dipakai halaman yang menarik
 * `useWebSocket` (Dashboard); halaman peta publik tak memakainya — stub ini
 * tetap dipasang supaya penambahan realtime di kemudian hari tidak membuat
 * uji rendernya meledak dengan "WebSocket is not defined".
 */
export function pasangWebSocketPalsu() {
  const dibuat = [];
  class WebSocketPalsu {
    constructor(url, protokol) {
      this.url = url;
      this.protocol = protokol || "";
      this.readyState = WebSocketPalsu.CONNECTING;
      this.onopen = null;
      this.onmessage = null;
      this.onerror = null;
      this.onclose = null;
      dibuat.push(this);
    }

    send() {}

    close() {
      this.readyState = WebSocketPalsu.CLOSED;
      if (typeof this.onclose === "function") this.onclose({ code: 1000 });
    }

    addEventListener() {}

    removeEventListener() {}
  }
  WebSocketPalsu.CONNECTING = 0;
  WebSocketPalsu.OPEN = 1;
  WebSocketPalsu.CLOSING = 2;
  WebSocketPalsu.CLOSED = 3;
  global.WebSocket = WebSocketPalsu;
  return dibuat;
}

/**
 * IndexedDB tiruan yang GAGAL-CEPAT: `open()` memicu `onerror` asinkron.
 *
 * Sengaja bukan tiruan sukses — IDB sukses menuntut implementasi transaksi/
 * store/index sungguhan, jauh melampaui kebutuhan uji render. Seluruh
 * pemakai `idb` di repo menjaga galatnya (mis. `getSnapshotAssets` →
 * `catch { return null; }`), jadi jalur gagal justru jalur yang DETERMINISTIK:
 * halaman harus tetap berdiri saat penyimpanan luring tak tersedia — persis
 * perilaku mode penyamaran Safari/Firefox di lapangan.
 */
export function pasangIndexedDbPalsu() {
  const buatPermintaanGagal = () => {
    const req = {
      onerror: null,
      onsuccess: null,
      onupgradeneeded: null,
      onblocked: null,
      error: new Error("indexedDB tiruan: sengaja gagal (lihat lingkunganPeta.js)"),
      result: undefined,
    };
    setTimeout(() => {
      if (typeof req.onerror === "function") req.onerror({ target: req });
    }, 0);
    return req;
  };
  global.indexedDB = {
    open: buatPermintaanGagal,
    deleteDatabase: buatPermintaanGagal,
  };
  return global.indexedDB;
}
