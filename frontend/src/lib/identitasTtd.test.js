import { teksIdentitasTtd } from "./identitasTtd";

test.each(["NIP", "NIK", "NI PPPK", "NRP", "No. Identitas"])(
  "label %s mengikuti server tanpa membuka nomor tersembunyi", (label) => {
    expect(teksIdentitasTtd({ nip: "••••••001", label_identitas: label }))
      .toBe(`${label} ••••••001`);
  });

test.each([undefined, "", "label tidak dikenal"])("respons lama/asing %s memakai label netral", (label) => {
  expect(teksIdentitasTtd({ nip: "••••001", label_identitas: label }))
    .toBe("No. Identitas ••••001");
});

test.each([undefined, null, {}, { nip: " " }, { label_identitas: "NIK" }])(
  "nomor kosong tidak diberi baris identitas: %s", (signer) => {
    expect(teksIdentitasTtd(signer)).toBe("");
  });
