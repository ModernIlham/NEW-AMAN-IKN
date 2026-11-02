import React, { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PengadaanKontrakFields from "../PengadaanKontrakFields";
import pilihan from "../../../lib/jenisDokumenPengadaan.json";

function Form({ jenis = "" }) {
  const [formData, setFormData] = useState({ jenis_dokumen_pengadaan: jenis,
    nomor_kontrak: "KON-1", cara_bayar_kontrak: "Sekaligus" });
  return <PengadaanKontrakFields formData={formData}
    onChange={({ target: { name, value } }) => setFormData(p => ({ ...p, [name]: value }))} />;
}

test.each(["", ...pilihan])("penguncian dan nilai historis untuk %s", async jenis => {
  render(<Form jenis={jenis} />);
  const non = jenis.startsWith("Non Kontrak");
  const nomor = screen.getByLabelText("Nomor Kontrak");
  const bayar = screen.getByLabelText("Cara Bayar Kontrak");
  expect(screen.getByLabelText("Jenis Dokumen Pengadaan")).toHaveValue(jenis);
  expect(nomor.disabled).toBe(non);
  expect(bayar.disabled).toBe(non);
  expect(nomor).toHaveValue("KON-1");
  expect(bayar).toHaveValue("Sekaligus");
  if (non) {
    await userEvent.type(nomor, "tidak boleh");
    expect(nomor).toHaveValue("KON-1");
    expect(screen.getByTestId("asset-non-kontrak-info")).toHaveTextContent("tetap disimpan");
  }
});

test("beralih jenis mengaktifkan kembali isian tanpa kehilangan draft", async () => {
  render(<Form />);
  const jenis = screen.getByLabelText("Jenis Dokumen Pengadaan");
  expect(jenis.options).toHaveLength(5);
  for (const value of pilihan) {
    await userEvent.selectOptions(jenis, value);
    expect(screen.getByLabelText("Nomor Kontrak").disabled).toBe(value.startsWith("Non Kontrak"));
  }
  await userEvent.selectOptions(jenis, "Kontrak BLU");
  await userEvent.type(screen.getByLabelText("Nomor Kontrak"), "-BLU");
  await userEvent.selectOptions(screen.getByLabelText("Cara Bayar Kontrak"), "Bertahap (Termin)");
  await userEvent.selectOptions(jenis, "Non Kontrak BLU");
  await userEvent.selectOptions(jenis, "Kontrak");
  expect(screen.getByLabelText("Nomor Kontrak")).toHaveValue("KON-1-BLU");
  expect(screen.getByLabelText("Cara Bayar Kontrak")).toHaveValue("Bertahap (Termin)");
});
