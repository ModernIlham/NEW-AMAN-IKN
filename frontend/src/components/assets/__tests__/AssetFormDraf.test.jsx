import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AssetForm from "../AssetForm";
import { emptyAssetForm } from "../../../lib/assetFormData";
import { bacaDraf, tulisDraf, hapusDraf } from "../../../lib/drafAset";
import axios from "axios";
jest.mock("axios", () => {
  const api = { get: jest.fn(), post: jest.fn(), interceptors: { request: { use: jest.fn() } } };
  return { ...api, create: () => api };
});
jest.mock("../../../lib/drafAset", () => ({ bacaDraf: jest.fn(), tulisDraf: jest.fn(), hapusDraf: jest.fn() }));
jest.mock("../FullCameraSheet", () => () => null);
jest.mock("date-fns/locale", () => ({ id: {} }));
beforeEach(() => {
  localStorage.setItem("user", JSON.stringify({ id: "audit-user" }));
  axios.get.mockResolvedValue({ data: { items: [] } });
  tulisDraf.mockImplementation(async (key, value, revision) => ({ key, value, revision: revision + 1 }));
  hapusDraf.mockResolvedValue();
  window.HTMLElement.prototype.scrollIntoView = () => {};
});
afterEach(() => localStorage.removeItem("user"));

test("formulir menawarkan pemulihan nama dan foto setelah dibuka ulang", async () => {
  const photo = "data:image/jpeg;base64,Zm90bw==";
  bacaDraf.mockResolvedValue({ revision: 1, value: {
    formData: { ...emptyAssetForm("k1"), asset_name: "Kursi belum dikirim", photos: [photo] },
    photoItems: [], original: null, photosModified: true, checklistModified: false,
    mediaLoaded: false, checklistFullLoaded: false, assetVersion: 1,
  } });
  render(<AssetForm isOpen activity={{ id: "k1" }} categories={[]} onClose={jest.fn()} />);
  fireEvent.click(await screen.findByRole("button", { name: "Pulihkan draf" }));
  await waitFor(() => expect(document.querySelector('input[name="asset_name"]')).toHaveValue("Kursi belum dikirim"));
  expect(document.querySelector(`img[src="${photo}"]`)).toBeInTheDocument();
  expect(screen.getByTestId("asset-draft-status")).toHaveTextContent("Draf tersimpan");
});
