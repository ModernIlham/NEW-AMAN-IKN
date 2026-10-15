import { hargaEksak, bandingkanHargaEksak as compare } from "../hargaEksak";
import { filterSnapshotRows, sortSnapshotRows } from "../querySnapshotAset";

test.each([undefined, null, "", " ", "abc", "1,00", "NaN", NaN, Infinity, "-Infinity", true, false,
  "12345678901234567890123456789012345", "1e6145", "1e-6177"])("harga tidak valid %p menjadi nol", value => {
  expect(compare(value, "0")).toBe(0);
});
test.each([
  ["9007199254740992.01", "9007199254740992.02", -1],
  ["-2.50", "-2.5", 0], ["-0.01", "0", -1], ["1e3", "1000.0", 0],
  [".0005", "4.99e-4", 1], ["+42.000", "42", 0],
  ["9999999999999999999999999999999999", "9999999999999999999999999999999998", 1],
  ["1e6144", "9e6143", 1], ["1e-6176", "0", 1],
  ["10000000000000000000000000000000000", "1e34", 0],
])("harga %s dibanding %s tetap eksak", (a, b, expected) => expect(compare(a, b)).toBe(expected));

test("harga ID tie stabil dua arah dan batas nol/negatif/presisi besar konsisten pada snapshot", () => {
  const rows = [{ id: "z", purchase_price: "9007199254740992.01" },
    { id: "b", purchase_price: "9007199254740992.02" }, { id: "a", purchase_price: "9007199254740992.02" },
    { id: "negative", purchase_price: "-1.5" }, { id: "empty", purchase_price: "" }, { id: "invalid", purchase_price: "abc" }];
  expect(sortSnapshotRows(rows, "price_asc").map(r => r.id)).toEqual(["negative", "empty", "invalid", "z", "a", "b"]);
  expect(sortSnapshotRows(rows, "price_desc").map(r => r.id)).toEqual(["a", "b", "z", "empty", "invalid", "negative"]);
  expect(filterSnapshotRows(rows, { filters: { priceMin: "9007199254740992.02" } }).map(r => r.id)).toEqual(["b", "a"]);
  expect(filterSnapshotRows(rows, { filters: { priceMax: "0" } }).map(r => r.id)).toEqual(["negative", "empty", "invalid"]);
  expect(hargaEksak("1e6144").sign).toBe(1);
});
