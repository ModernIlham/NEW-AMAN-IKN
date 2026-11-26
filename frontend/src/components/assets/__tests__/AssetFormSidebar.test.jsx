import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import AssetFormSidebar from "../AssetFormSidebar";
let mockMounts;
jest.mock("../AssetForm", () => function Form({ isOpen, alwaysExpanded }) {
  const { useState, useEffect } = require("react");
  const [brand, setBrand] = useState("Awal"), [tab, setTab] = useState("basic"), [checklist, setChecklist] = useState("STNK");
  useEffect(() => { mockMounts++; }, []);
  return <aside data-open={isOpen} data-expanded={alwaysExpanded}><input aria-label="Merek" value={brand} onChange={e => setBrand(e.target.value)} /><button onClick={() => setTab("dokumen")}>Dokumen</button><span>{tab}</span><input aria-label="Draf dokumen" value={checklist} onChange={e => setChecklist(e.target.value)} /></aside>;
});
beforeEach(() => { mockMounts = 0; });
test("resize desktop/mobile dan hide mempertahankan satu pemilik draf, tab, dan elemen fokus", () => {
  const { rerender } = render(<AssetFormSidebar isDesktop panelVisible isOpen />);
  const brand = screen.getByLabelText("Merek"), documentDraft = screen.getByLabelText("Draf dokumen");
  fireEvent.change(brand, { target: { value: "Merek belum disimpan" } }); fireEvent.click(screen.getByText("Dokumen")); fireEvent.change(documentDraft, { target: { value: "STNK, kunci cadangan" } }); documentDraft.focus();
  for (const props of [{ isDesktop: false, panelVisible: true, isOpen: true }, { isDesktop: true, panelVisible: true, isOpen: true }, { isDesktop: true, panelVisible: false, isOpen: true }, { isDesktop: false, panelVisible: false, isOpen: true }]) {
    rerender(<AssetFormSidebar {...props} />);
    expect(document.querySelectorAll("aside")).toHaveLength(1); expect(screen.getByLabelText("Merek")).toBe(brand); expect(brand).toHaveValue("Merek belum disimpan"); expect(screen.getByText("dokumen")).toBeInTheDocument(); expect(documentDraft).toHaveValue("STNK, kunci cadangan"); expect(document.activeElement).toBe(documentDraft);
  }
  expect(mockMounts).toBe(1); expect(screen.getByTestId("asset-form-sidebar").style.contain).toBe("");
});
test("desktop panel terbuka mandiri, mobile memakai status overlay tanpa unmount saat ditutup", () => {
  const { rerender } = render(<AssetFormSidebar isDesktop panelVisible isOpen={false} />);
  expect(document.querySelector("aside")).toHaveAttribute("data-open", "true"); expect(document.querySelector("aside")).toHaveAttribute("data-expanded", "true");
  rerender(<AssetFormSidebar isDesktop={false} panelVisible isOpen={false} />); expect(document.querySelector("aside")).toHaveAttribute("data-open", "false"); expect(document.querySelector("aside")).toHaveAttribute("data-expanded", "false"); expect(mockMounts).toBe(1);
});

describe("mount pertama form tertutup ditunda ke waktu senggang", () => {
  let idle;
  beforeEach(() => {
    idle = [];
    window.requestIdleCallback = jest.fn((fn) => { idle.push(fn); return idle.length; });
    window.cancelIdleCallback = jest.fn();
  });
  afterEach(() => { delete window.requestIdleCallback; delete window.cancelIdleCallback; });

  test("HP tertutup: form belum dirender saat muat, ter-mount saat senggang", () => {
    render(<AssetFormSidebar isDesktop={false} panelVisible={false} isOpen={false} />);
    expect(document.querySelector("aside")).toBeNull();
    expect(window.requestIdleCallback).toHaveBeenCalledWith(expect.any(Function), { timeout: 3000 });
    const { act } = require("react");
    act(() => idle.forEach((fn) => fn()));
    expect(document.querySelector("aside")).toHaveAttribute("data-open", "false");
    expect(mockMounts).toBe(1);
  });

  test("dibuka sebelum senggang: ter-mount SEKETIKA, lalu tak pernah dilepas saat ditutup", () => {
    const { rerender } = render(<AssetFormSidebar isDesktop={false} panelVisible={false} isOpen={false} />);
    rerender(<AssetFormSidebar isDesktop={false} panelVisible={false} isOpen />);
    expect(document.querySelector("aside")).toHaveAttribute("data-open", "true");
    fireEvent.change(screen.getByLabelText("Merek"), { target: { value: "Draf HP" } });
    rerender(<AssetFormSidebar isDesktop={false} panelVisible={false} isOpen={false} />);
    expect(screen.getByLabelText("Merek")).toHaveValue("Draf HP");
    expect(mockMounts).toBe(1);
  });

  test("desktop dengan panel terlihat dirender langsung tanpa menunggu", () => {
    render(<AssetFormSidebar isDesktop panelVisible isOpen={false} />);
    expect(document.querySelector("aside")).toHaveAttribute("data-expanded", "true");
    expect(window.requestIdleCallback).not.toHaveBeenCalled();
  });
});
