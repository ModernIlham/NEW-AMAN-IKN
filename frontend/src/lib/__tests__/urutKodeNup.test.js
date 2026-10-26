import fs from "fs";
import path from "path";
import { angkaIdentitas } from "../urutKodeNup";
import { sortSnapshotRows } from "../querySnapshotAset";
import { buatCacheQuerySnapshot, queryHalamanSnapshot } from "../cacheQuerySnapshot";
const fixture = JSON.parse(fs.readFileSync(path.resolve(__dirname, "../../../../backend/tests/fixtures/urut_kode_nup.json"), "utf8"));

test.each([["002", "2"], [2, "2"], ["2.0", "2"], ["000", "0"], [null, null],
  [undefined, null], ["", null], ["-1", null], [true, null], ["1e3", null], ["2.5", null],
  ["9".repeat(100), "9".repeat(100)]])("identitas %p tidak kehilangan presisi", (value, expected) => {
  expect(angkaIdentitas(value)).toBe(expected);
});

test.each(["code_nup_asc", "code_nup_desc"])("snapshot biasa dan cache pagination mengikuti kontrak server: %s", async sort => {
  const original = JSON.stringify(fixture.rows);
  expect(sortSnapshotRows(fixture.rows, sort).map(row => row.id)).toEqual(fixture[sort]);
  expect(JSON.stringify(fixture.rows)).toBe(original);
  const rows = [...fixture.rows.map(row => ({ ...row, location: "Gedung Uji" })),
    { id: "tidak-ikut", location: "Gedung Lain" }];
  const source = { keys: jest.fn(async () => rows.map(row => row.id)),
    rows: jest.fn(async ids => ids.map(id => rows.find(row => row.id === id))) };
  const options = { source, cache: buatCacheQuerySnapshot(), scope: "satker-a", meta: { userId: "uji" },
    query: { filters: { location: ["Gedung Uji"] }, sort }, size: 5, batchSize: 3 };
  const actual = [];
  for (const page of [1, 2, 3]) {
    const result = await queryHalamanSnapshot({ ...options, page });
    expect(result.total).toBe(fixture.rows.length);
    if (page > 1) expect(result.timing.cacheHit).toBe(true);
    actual.push(...result.items.map(row => row.id));
  }
  expect(actual).toEqual(fixture[sort]);
  const inverse = sort === "code_nup_asc" ? "code_nup_desc" : "code_nup_asc";
  const next = await queryHalamanSnapshot({ ...options, query: { ...options.query, sort: inverse } });
  expect(next.timing.baseCacheHit).toBe(true);
  expect(next.items.map(row => row.id)).toEqual(fixture[inverse].slice(0, 5));
});
