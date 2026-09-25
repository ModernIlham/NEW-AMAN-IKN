import { bacaMarkerPin, cariIkonPin, IKON_PIN, opsiPinDesain, PIN_BAWAAN, siapkanIkonPin } from "./markerPin";

const desain = (d = {}) => JSON.stringify({ ...PIN_BAWAAN, ...d });
test("katalog unik, berkategori, dan pencarian lintas nama/kategori", () => {
  expect(new Set(IKON_PIN.map(i => i.id)).size).toBe(IKON_PIN.length);
  expect(cariIkonPin("rambu jalan").map(i => i.id)).toEqual(["signpost"]);
  expect(cariIkonPin("", "Kendaraan")).toHaveLength(4);
  expect(cariIkonPin("laptop", "Kendaraan")).toHaveLength(0);
});
test.each(["", "bad", "[]", '{"v":2}', desain({ mode: "custom", image: "https://example.com/x.svg" })])("data invalid/polos menjadi pin bawaan %s", v => {
  expect(bacaMarkerPin(v)).toBeNull();
  expect(opsiPinDesain(v)).toBeNull();
});
test("renderer menyaring HTML/CSS liar dan menjaga status/seleksi/lencana", () => {
  const r = opsiPinDesain(desain({ mode: "text", text: '<img onerror="evil">', strokeColor: 'red;evil', iconColor: '<script>' }), { color: '#2563eb', selected: true, hasPhoto: true, badge: 12 });
  expect(r.html).not.toMatch(/evil|onerror|<script/);
  expect(r.html).toContain('#2563eb');
  expect(r.html).toContain('#f59e0b');
  expect(r.html).toContain('9+');
  expect(r.iconAnchor).toEqual([18, 44]);
});
test("huruf, tanpa lingkaran, stroke nol, dan ikon statis", () => {
  const r = opsiPinDesain(desain({ mode: "text", text: "B2", circle: false, strokeWidth: 0 }));
  expect(r.html).toContain('B2');
  expect(r.html).toContain('background:transparent');
  expect(r.html).toContain('border:0px');
  // CSS Leaflet memberi SVG z-index:200; badan pin harus diturunkan secara
  // eksplisit agar lingkaran, teks, serta lencana tidak tertutup olehnya.
  const div = document.createElement("div"); div.innerHTML = r.html;
  expect(div.querySelector("svg").style.zIndex).toBe("0");
  expect(div.firstElementChild.children[1].style.zIndex).toBe("1");
  expect(opsiPinDesain(desain({ icon: "laptop" })).html).toContain('lucide-laptop');
});
test("unggahan non-gambar/terlalu besar ditolak sebelum decode", async () => {
  await expect(siapkanIkonPin(new File(["<svg/>"], "x.svg", { type: "image/svg+xml" }))).rejects.toThrow("PNG");
  await expect(siapkanIkonPin({ type: "image/png", size: 3 * 1024 * 1024 })).rejects.toThrow("2 MB");
});
