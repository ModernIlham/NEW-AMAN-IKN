"""TGR (Tuntutan Ganti Rugi) aset hilang — ASET-TGR (PP 38/2016; PMK 83/2016).

Temuan audit permohonan aset: penghapusan karena hilang mensyaratkan proses
TGR / surat keterangan bebas TGR, tetapi aplikasi tidak punya register TGR
sama sekali — SK penghapusan aset hilang bisa terbit tanpa satu pun bukti
proses terekam (temuan auditor hampir pasti).

Alur tiket per aset hilang:

  penelusuran → telaah (TPKN) → { tgr_ditetapkan | bebas_tgr }
  tgr_ditetapkan → lunas

Dokumen wajib per keputusan: SKTJM/SK Pembebanan (nomor + nilai ganti rugi)
untuk tgr_ditetapkan; surat keterangan untuk bebas_tgr; bukti setor untuk
lunas. Modul ini murni (tanpa DB/HTTP); penegakan ada di routes/tgr.py dan
gerbang SK di routes/penghapusan.py.
"""

STATUS_TGR = {
    "penelusuran": "Penelusuran",
    "telaah": "Telaah TPKN",
    "tgr_ditetapkan": "TGR Ditetapkan (SKTJM/SK Pembebanan)",
    "bebas_tgr": "Bebas TGR",
    "lunas": "Lunas",
    "dibatalkan": "Dibatalkan",
}

# telaah boleh KEMBALI ke penelusuran (koreksi salah klik — pola register
# penghapusan); keputusan & terminal tidak bisa mundur.
TRANSISI_TGR = {
    "penelusuran": {"telaah", "dibatalkan"},
    "telaah": {"tgr_ditetapkan", "bebas_tgr", "penelusuran"},
    "tgr_ditetapkan": {"lunas"},
    "bebas_tgr": set(),
    "lunas": set(),
    "dibatalkan": set(),
}

# Status yang MEMENUHI syarat SK penghapusan aset hilang: proses TGR sudah
# berkeputusan (ditetapkan/bebas) atau tuntas (lunas).
STATUS_TGR_BERKEPUTUSAN = {"tgr_ditetapkan", "bebas_tgr", "lunas"}


def validate_transisi_tgr(dari: str, ke: str, payload: dict) -> list:
    """Daftar galat transisi tiket TGR — dokumen wajib per keputusan."""
    p = payload or {}
    errors = []
    if ke not in STATUS_TGR:
        return [f"Status tujuan tidak dikenal: {ke}"]
    if ke not in TRANSISI_TGR.get(dari, set()):
        return [f"Transisi {STATUS_TGR.get(dari, dari)} → "
                f"{STATUS_TGR.get(ke, ke)} tidak diizinkan"]
    if ke == "tgr_ditetapkan":
        if not str(p.get("nomor_dokumen") or "").strip():
            errors.append("Nomor SKTJM/SK Pembebanan wajib diisi")
        import math
        try:
            nilai = float(p.get("nilai_ganti_rugi") or 0)
        except (TypeError, ValueError):
            nilai = 0
        # Infinity/NaN LOLOS cek `<= 0` (perbandingannya False) lalu meracuni
        # register → GET /tgr 500 permanen (json.dumps allow_nan=False).
        if not math.isfinite(nilai) or nilai <= 0:
            errors.append("Nilai ganti rugi wajib angka terhingga > 0")
    if ke == "bebas_tgr" and not str(p.get("nomor_dokumen") or "").strip():
        errors.append("Nomor surat keterangan bebas TGR wajib diisi")
    if ke == "lunas" and not str(p.get("nomor_dokumen") or "").strip():
        errors.append("Nomor bukti setor pelunasan wajib diisi")
    return errors


def validate_tiket_tgr_baru(kronologi: str, penanggung_jawab: str) -> list:
    """Kronologi & penanggung jawab wajib — telaah TGR tanpa kronologi
    bukan telaah."""
    errors = []
    if len(str(kronologi or "").strip()) < 10:
        errors.append("Kronologi kehilangan wajib diisi (minimal 10 karakter)")
    if not str(penanggung_jawab or "").strip():
        errors.append("Penanggung jawab (pemegang saat hilang) wajib diisi")
    return errors
