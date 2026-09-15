const LABEL_IDENTITAS = new Set(["NIP", "NIK", "NI PPPK", "NRP", "No. Identitas"]);

/** API menghitung label dari nomor utuh sebelum masking. Respons lama tanpa
 * label tidak boleh ditebak sebagai NIP hanya dari nomor yang sudah disamarkan. */
export function teksIdentitasTtd(signer) {
  const nomor = String(signer?.nip || "").trim();
  if (!nomor) return "";
  const label = LABEL_IDENTITAS.has(signer?.label_identitas)
    ? signer.label_identitas : "No. Identitas";
  return `${label} ${nomor}`;
}
