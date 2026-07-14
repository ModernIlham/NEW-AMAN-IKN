import { bolehSalinKoordinat } from "./salinKonteks";

const NOW = 1_700_000_000_000;
const ctx = (over = {}) => ({ koordinat_latitude: "-6.175110", koordinat_longitude: "106.865036", ts: NOW, ...over });

test("konteks baru + koordinat form kosong → boleh salin", () => {
  expect(bolehSalinKoordinat(ctx(), "", "", NOW)).toBe(true);
  expect(bolehSalinKoordinat(ctx(), null, undefined, NOW)).toBe(true);
});

test("koordinat form sudah terisi → JANGAN timpa", () => {
  expect(bolehSalinKoordinat(ctx(), "-6.2", "106.9", NOW)).toBe(false);
  expect(bolehSalinKoordinat(ctx(), "-6.2", "", NOW)).toBe(false);   // salah satu terisi pun cukup
  expect(bolehSalinKoordinat(ctx(), "", "106.9", NOW)).toBe(false);
});

test("konteks basi (di luar ambang) → jangan salin koordinat", () => {
  const tuaMs = 31 * 60 * 1000; // 31 menit > default 30 menit
  expect(bolehSalinKoordinat(ctx({ ts: NOW - tuaMs }), "", "", NOW)).toBe(false);
  // tepat di ambang → masih boleh
  expect(bolehSalinKoordinat(ctx({ ts: NOW - 30 * 60 * 1000 }), "", "", NOW)).toBe(true);
});

test("ambang bisa dikustom", () => {
  const t = NOW - 10 * 60 * 1000; // 10 menit
  expect(bolehSalinKoordinat(ctx({ ts: t }), "", "", NOW, 5 * 60 * 1000)).toBe(false);
  expect(bolehSalinKoordinat(ctx({ ts: t }), "", "", NOW, 15 * 60 * 1000)).toBe(true);
});

test("konteks tanpa koordinat / tanpa ts / null → tidak boleh", () => {
  expect(bolehSalinKoordinat(null, "", "", NOW)).toBe(false);
  expect(bolehSalinKoordinat({ ts: NOW }, "", "", NOW)).toBe(false);                       // tak ada koordinat
  expect(bolehSalinKoordinat(ctx({ ts: undefined }), "", "", NOW)).toBe(false);            // tak ada ts
  expect(bolehSalinKoordinat(ctx({ koordinat_latitude: "" }), "", "", NOW)).toBe(false);   // lat kosong
});

test("ts di masa depan (jam perangkat mundur) → aman, tak dianggap segar", () => {
  expect(bolehSalinKoordinat(ctx({ ts: NOW + 60000 }), "", "", NOW)).toBe(false);
});
