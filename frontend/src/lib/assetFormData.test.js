import { buildAssetPatch, buildEditFormData, emptyAssetForm } from "./assetFormData";
import { ASSET_SCALAR_FIELDS } from "./assetFields";

const base = () => ({ ...emptyAssetForm("k1"), asset_code: "301", asset_name: "Meja", version: 4 });
function patch(formData, original, options = {}) {
  return buildAssetPatch({ formData, original, autoStatus: formData.inventory_status,
    assetVersion: original.version, ...options });
}

test("new forms have independent media arrays and retain established defaults", () => {
  const first = emptyAssetForm("k1"), second = emptyAssetForm("k2");
  first.photos.push("new"); first.document_checklist.push({ name: "custom" });
  expect(second.photos).toEqual([]); expect(second.document_checklist).toEqual([]);
  expect(second).toMatchObject({ condition: "Baik", status: "Aktif", stiker_photo_index: null,
    inventory_status: "Belum Diinventarisasi", activity_id: "k2" });
});

test("edit initialization preserves custom operational values, checklist and nullable zero", () => {
  const checklist = [{ name: "Arsip khusus", checked: true }];
  const result = buildEditFormData({ asset_code: "301", document_checklist: checklist,
    operasional_jenis: "Kegiatan/Acara/Kebutuhan", stiker_photo_index: 0 }, "k1");
  expect(result.operasional_jenis).toBe("Unit/Tempat/Tugas");
  expect(result.stiker_photo_index).toBe(0); expect(result.document_checklist).toBe(checklist);
  expect(buildEditFormData({ operasional_jenis: "Tempat khusus" }).operasional_jenis).toBe("Tempat khusus");
});

test("all registered scalar fields participate in partial patch and explicit clear", () => {
  for (const key of ASSET_SCALAR_FIELDS) {
    const original = { ...base(), [key]: "before" };
    const edited = { ...original, [key]: "after" };
    expect(patch(edited, original)).toEqual({ [key]: "after" });
    expect(patch({ ...original, [key]: "" }, original)).toEqual({ [key]: "" });
  }
});

test("empty/null scalar equivalence and numeric strings retain the legacy diff contract", () => {
  const original = { ...base(), notes: null, purchase_price: 0 };
  expect(patch({ ...original, notes: "", purchase_price: "0" }, original)).toEqual({});
  expect(patch({ ...original, notes: "clearable", purchase_price: "0" }, original)).toEqual({ notes: "clearable" });
  expect(patch({ ...original, notes: null }, { ...original, notes: "before" })).toEqual({ notes: null });
});

test("automatic inventory status overrides the scalar draft only when changed", () => {
  const original = base();
  expect(patch(original, original, { autoStatus: "Ditemukan" })).toEqual({ inventory_status: "Ditemukan" });
  expect(patch({ ...original, inventory_status: "Ditemukan" }, original,
    { autoStatus: original.inventory_status })).toEqual({});
});

test("unknown fields and unloaded media are absent from ordinary scalar edits", () => {
  const original = { ...base(), _photoCount: 3 };
  const result = patch({ ...original, asset_name: "New", photos: ["placeholder"],
    document_checklist: [{ name: "Not loaded" }], unknown: "never send" }, original);
  expect(result).toEqual({ asset_name: "New" });
});

test("photo order, removals, new bytes and version fence remain positional", () => {
  const original = { ...base(), _photoCount: 3 };
  const result = patch({ ...original, thumbnail_index: 1, stiker_photo_index: null }, original, {
    photosModified: true, mediaLoaded: true,
    photoItems: [{ type: "existing", originalIndex: 2 }, { type: "new", newData: "raw" },
      { type: "existing", originalIndex: 0 }], compressedNewPhotos: ["compressed"],
  });
  expect(result.photo_ops).toEqual({ keep: [2, 0], add: ["compressed"], thumbnail_index: 1, base_version: 4 });
  expect(result.thumbnail_index).toBe(1);
});

test("offline additions with unloaded media preserve every known server photo", () => {
  const original = { ...base(), _photoCount: 3 };
  expect(patch(original, original, { photosModified: true, mediaLoaded: false,
    photoItems: [{ type: "new", newData: "raw" }], compressedNewPhotos: ["compressed"] }).photo_ops)
    .toEqual({ keep: [0, 1, 2], add: ["compressed"], thumbnail_index: 0, base_version: 4 });
});

test("explicit media deletion and nullable cover clear remain present", () => {
  const original = { ...base(), stiker_photo_index: 1 };
  const result = patch({ ...original, stiker_photo_index: null }, original,
    { photosModified: true, mediaLoaded: true, photoItems: [] });
  expect(result).toMatchObject({ stiker_photo_index: null,
    photo_ops: { keep: [], add: [], base_version: 4 } });
});

test("prepared checklist sentinels are retained and unchanged checklist stays omitted", () => {
  const original = base();
  const checklist = [{ name: "STNK", checked: false, photos: ["__existing__:0"],
    documents: [{ name: "STNK.pdf", data: "__existing__:0" }] }];
  expect(patch(original, original, { checklistModified: true, cleanedChecklist: checklist }))
    .toEqual({ document_checklist: checklist });
  expect(patch(original, original, { cleanedChecklist: checklist })).toEqual({});
});

test("builder leaves original and prepared media immutable", () => {
  const original = Object.freeze(base());
  const items = Object.freeze([Object.freeze({ type: "existing", originalIndex: 1 })]);
  const added = Object.freeze(["prepared"]);
  expect(patch(original, original, { photosModified: true, mediaLoaded: true,
    photoItems: items, compressedNewPhotos: added }).photo_ops.keep).toEqual([1]);
  expect(items).toHaveLength(1); expect(added).toEqual(["prepared"]);
});
