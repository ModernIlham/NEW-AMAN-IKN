import { bacaMarkerPin, cariIkonPin, IKON_PIN, KATEGORI_PIN, opsiPinDesain, PIN_BAWAAN, siapkanIkonPin } from "./markerPin";

const desain = (d = {}) => JSON.stringify({ ...PIN_BAWAAN, ...d });
test("katalog unik, berkategori, dan pencarian lintas nama/kategori", () => {
  expect(new Set(IKON_PIN.map(i => i.id)).size).toBe(IKON_PIN.length);
  expect(cariIkonPin("rambu jalan").map(i => i.id)).toEqual(["signpost"]);
  expect(IKON_PIN).toHaveLength(421);
  expect(KATEGORI_PIN).toHaveLength(25);
  expect(cariIkonPin("desain marker pin").map(i => i.id)).toEqual(["designpin"]);
  expect(cariIkonPin("", "Kendaraan")).toHaveLength(14);
  expect(cariIkonPin("laptop", "Kendaraan")).toHaveLength(0);
  expect(cariIkonPin("pemadam api").map(i => i.id)).toEqual(["extinguisher"]);
  for (const ikon of IKON_PIN) {
    expect(ikon.Icon).toBeTruthy();
    expect(opsiPinDesain(desain({ icon: ikon.id })).html).toContain("lucide-");
    expect(bacaMarkerPin(desain({ icon: ikon.id })).icon).toBe(ikon.id);
  }
});

test.each([0, 3])("lencana kamera berupa SVG lingkaran dan tidak digantikan komentar %s", badge => {
  const div = document.createElement("div");
  div.innerHTML = opsiPinDesain(desain({ icon: "router" }), { hasPhoto: true, badge }).html;
  const foto = div.querySelector('[data-marker-badge="photo"]');
  expect(foto.style.borderRadius).toBe("50%");
  expect(foto.style.width).toBe("14px");
  expect(foto.querySelector("svg circle").getAttribute("r")).toBe("4");
  expect(div.innerHTML).not.toContain("▣");
  const komentar = div.querySelector('[data-marker-badge="comment"]');
  if (badge) {
    expect(komentar.textContent.trim()).toBe("3");
    expect(komentar.style.left).toBe("-6px");
  } else expect(komentar).toBeNull();
  expect(opsiPinDesain(desain(), { hasPhoto: false }).html).not.toContain('data-marker-badge="photo"');
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
