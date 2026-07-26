import { sudutKeLatLng, latLngKeSudut } from "../denahOverlay";

const SUDUT = { tl: [116.70, -1.39], tr: [116.71, -1.39], bl: [116.70, -1.40] };

test("sudutKeLatLng membalik lon-first server ke lat-first Leaflet", () => {
  expect(sudutKeLatLng(SUDUT)).toEqual({
    tl: [-1.39, 116.70], tr: [-1.39, 116.71], bl: [-1.40, 116.70],
  });
});

test("bolak-balik sudut ↔ latlng identik", () => {
  expect(latLngKeSudut(sudutKeLatLng(SUDUT))).toEqual(SUDUT);
});

test("latLngKeSudut menerima objek L.LatLng {lat, lng}", () => {
  const dariMarker = {
    tl: { lat: -1.39, lng: 116.70 },
    tr: { lat: -1.39, lng: 116.71 },
    bl: { lat: -1.40, lng: 116.70 },
  };
  expect(latLngKeSudut(dariMarker)).toEqual(SUDUT);
});

test("data rusak menghasilkan null, bukan NaN diam-diam", () => {
  expect(sudutKeLatLng(null)).toBeNull();
  expect(sudutKeLatLng({ tl: [1, 2] })).toBeNull();               // kurang kunci
  expect(sudutKeLatLng({ ...SUDUT, tr: ["x", 1] })).toBeNull();   // bukan angka
  expect(latLngKeSudut({ ...sudutKeLatLng(SUDUT), bl: {} })).toBeNull();
});
