"""Tes util murni Timeline Aset (timeline_utils) — tanpa Mongo."""
from timeline_utils import (MODUL_LABEL, buat_event, event_dari_riwayat,
                            event_psp_siman, identitas_aset, info_psp_siman,
                            label_transaksi_buku, query_identitas,
                            ringkas_per_modul, ringkas_perubahan_audit,
                            urut_events)


def test_identitas_aset_normalisasi_casing():
    """Casing campuran (NUP vs nup, asset_code vs kode_barang) dinormalkan."""
    a = identitas_aset({"kode_register": " ABC123 ", "asset_code": "3050104001",
                        "NUP": " 7 "})
    assert a == {"kode_register": "ABC123", "asset_code": "3050104001",
                 "nup": "7"}
    b = identitas_aset({"kode_barang": "3050104001", "nup": "7"})
    assert b["asset_code"] == "3050104001" and b["nup"] == "7"
    assert identitas_aset(None) == {"kode_register": "", "asset_code": "",
                                    "nup": ""}
    # NUP kapital menang bila keduanya ada (dokumen assets)
    assert identitas_aset({"NUP": "1", "nup": "2"})["nup"] == "1"


def test_query_identitas_prioritas_register():
    """kode_register prioritas + fallback kode+NUP dalam satu $or (aset lama
    pra-SIMAN tanpa kode_register tetap terjaring)."""
    q = query_identitas({"kode_register": "R1", "asset_code": "K1", "nup": "5"})
    assert q == {"$or": [{"kode_register": "R1"},
                         {"asset_code": "K1", "NUP": "5"}]}
    assert query_identitas({"kode_register": "R1"}) == {"kode_register": "R1"}
    assert query_identitas({"asset_code": "K1", "nup": "5"}) == {
        "asset_code": "K1", "NUP": "5"}
    assert query_identitas({"asset_code": "K1"}) == {"asset_code": "K1"}
    # Identitas tak memadai → {} (pemanggil TIDAK boleh query)
    assert query_identitas({}) == {}
    assert query_identitas(None) == {}


def test_urut_events_terbaru_dulu_kosong_di_akhir():
    e1 = buat_event("aset", "a", "lama", tanggal="2024-01-01")
    e2 = buat_event("aset", "b", "baru", tanggal="2026-07-19T10:00:00")
    e3 = buat_event("aset", "c", "tanpa tanggal")
    hasil = urut_events([e1, e3, e2])
    assert [e["judul"] for e in hasil] == ["baru", "lama", "tanpa tanggal"]
    assert urut_events([]) == []
    assert urut_events(None) == []


def test_ringkas_per_modul_dan_label():
    ev = [buat_event("inventarisasi", "x", "a"),
          buat_event("inventarisasi", "y", "b"),
          buat_event("bast", "z", "c")]
    assert ringkas_per_modul(ev) == {"inventarisasi": 2, "bast": 1}
    # Semua kunci modul yang dipakai event punya label UI
    for m in ringkas_per_modul(ev):
        assert m in MODUL_LABEL


def test_info_dan_event_psp_siman():
    """Data referensi SIMAN V2 (no_psp dkk.) terekstrak jadi info + event."""
    sub = {"referensi": {"no_psp": "S-11/MK.6/2023", "tanggal_psp": "2023-05-02",
                         "status_penggunaan": "Digunakan Sendiri",
                         "status_bmn": "Aktif"}}
    info = info_psp_siman(sub)
    assert info["no_psp"] == "S-11/MK.6/2023"
    assert info["status_penggunaan"] == "Digunakan Sendiri"
    ev = event_psp_siman(sub)
    assert len(ev) == 1 and ev[0]["modul"] == "siman"
    assert "S-11/MK.6/2023" in ev[0]["judul"]
    assert ev[0]["tanggal"] == "2023-05-02"
    # Tanpa nomor PSP → tak ada event; tanpa isi bermakna → info {}
    assert event_psp_siman({"referensi": {"status_bmn": "Aktif"}}) == []
    assert info_psp_siman({"referensi": {}}) == {}
    assert info_psp_siman(None) == {}
    # Placeholder "belum PSP" dari SIMAN ("-"/"Tidak Ada Inputan") BUKAN
    # nomor PSP — jangan bikin event "PSP menurut SIMAN" palsu.
    assert event_psp_siman({"referensi": {"no_psp": "-"}}) == []
    assert event_psp_siman(
        {"referensi": {"no_psp": "Tidak Ada Inputan"}}) == []
    assert info_psp_siman({"referensi": {"no_psp": "-"}}) == {}


def test_event_dari_riwayat_pola_umum():
    doc = {"riwayat": [
        {"status": "diusulkan", "tanggal": "2026-01-01T00:00:00", "oleh": "a"},
        {"status": "sk_terbit", "tanggal": "2026-02-01T00:00:00",
         "catatan": "SK 12/2026"},
        "bukan-dict-diabaikan"]}
    ev = event_dari_riwayat(doc, "penghapusan", "Usulan penghapusan",
                            ref_id="U1")
    assert len(ev) == 2
    assert ev[0]["judul"] == "Usulan penghapusan: diusulkan"
    assert ev[1]["detail"] == "SK 12/2026" and ev[1]["ref_id"] == "U1"
    assert event_dari_riwayat({}, "x", "y") == []


def test_label_transaksi_dan_ringkas_audit():
    assert label_transaksi_buku("301") == "Penghapusan"
    assert label_transaksi_buku("999") == "Transaksi 999"
    assert label_transaksi_buku("") == "Transaksi"
    r = ringkas_perubahan_audit([
        {"field": "condition", "from": "Baik", "to": "RR"},
        {"field": "location"}, {"field": "user"}, {"field": "status"},
        {"field": "brand"}, {"bukan_field": 1}])
    assert r.startswith("Field berubah: condition, location, user, status")
    assert "+1 lainnya" in r
    assert ringkas_perubahan_audit([]) == ""
    assert ringkas_perubahan_audit(None) == ""


def test_susun_kelompok_lintas_kegiatan():
    """Kelompok kode+NUP di >1 kegiatan dikenali; 1 kegiatan disaring."""
    from timeline_utils import susun_kelompok_lintas_kegiatan
    groups = [
        {"_id": {"kode": "3050104001", "nup": "7"}, "n": 2,
         "kegiatan": ["K1", "K2"],
         "docs": [
             {"id": "A1", "activity_id": "K1", "asset_name": "Lemari",
              "kode_register": "", "inventory_status": "Sudah",
              "condition": "Baik", "updated_at": "2024-03-01"},
             {"id": "A2", "activity_id": "K2", "asset_name": "Lemari",
              "kode_register": "REG77", "inventory_status": "Sudah",
              "condition": "RR", "updated_at": "2026-02-01"}]},
        # Satu kegiatan saja (dobel entri di kegiatan sama) → disaring
        {"_id": {"kode": "3050104002", "nup": "1"}, "n": 2,
         "kegiatan": ["K1"], "docs": []},
    ]
    info = {"K1": {"ticket_number": "INV-2024-001", "name": "IP 2024",
                   "status_pengesahan": "disahkan"},
            "K2": {"ticket_number": "INV-2026-003", "name": "IP 2026",
                   "status_pengesahan": ""}}
    hasil = susun_kelompok_lintas_kegiatan(groups, info)
    assert len(hasil) == 1
    k = hasil[0]
    assert k["asset_code"] == "3050104001" and k["jumlah_kegiatan"] == 2
    # Nama & register terisi dari dokumen mana pun yang punya nilai
    assert k["asset_name"] == "Lemari" and k["kode_register"] == "REG77"
    # Terbaru dulu + info kegiatan tergabung
    assert k["kegiatan"][0]["asset_id"] == "A2"
    assert k["kegiatan"][0]["ticket_number"] == "INV-2026-003"
    assert k["kegiatan"][1]["status_pengesahan"] == "disahkan"
    assert susun_kelompok_lintas_kegiatan([]) == []
    assert susun_kelompok_lintas_kegiatan(None) == []


def test_urut_events_seri_tanggal_sama_terbaru_di_atas():
    """CACAT YANG DILAPORKAN. Satu aset menerima tujuh BAST pada hari yang
    SAMA (B-017 s.d. B-023, 4 Agustus 2026). Karena `tanggal` hanya berisi
    HARI, ketujuhnya seri; `list.sort` yang stabil lalu mempertahankan urutan
    MASUK yang menaik, sehingga BAST TERBARU mendarat di paling bawah —
    kebalikan dari yang dijanjikan timeline "terbaru dulu".
    """
    from timeline_utils import buat_event, urut_events
    # Dibuat berurutan sepanjang hari; dimasukkan menaik seperti dari Mongo.
    masuk = [buat_event("bast", "serah_terima", f"BAST B-{17 + i:03d}",
                        tanggal="2026-08-04",
                        urut=f"2026-08-04T{9 + i:02d}:00:00")
             for i in range(7)]
    judul = [e["judul"] for e in urut_events(masuk)]
    assert judul[0] == "BAST B-023", judul
    assert judul[-1] == "BAST B-017", judul
    assert judul == sorted(judul, reverse=True)


def test_urut_events_pemecah_seri_tak_menggeser_antar_tanggal():
    """Pemecah seri hanya boleh berlaku DI DALAM tanggal yang sama. Bila ia
    ikut menentukan antar-tanggal, event lama ber-`urut` besar akan melompati
    event baru — kerusakan yang lebih parah daripada cacat aslinya."""
    from timeline_utils import buat_event, urut_events
    lama = buat_event("bast", "x", "lama", tanggal="2026-08-01",
                      urut="9999-12-31T23:59:59")
    baru = buat_event("bast", "x", "baru", tanggal="2026-08-04", urut="")
    assert [e["judul"] for e in urut_events([lama, baru])] == ["baru", "lama"]


def test_urut_events_tanpa_pemecah_seri_tetap_aman():
    """Event lama (dan modul yang belum memasok `urut`) tak boleh meledak."""
    from timeline_utils import urut_events
    hasil = urut_events([
        {"tanggal": "2026-08-04", "judul": "a"},      # tanpa kunci `urut`
        {"tanggal": "2026-08-05", "judul": "b", "urut": None},
    ])
    assert [e["judul"] for e in hasil] == ["b", "a"]


def test_buat_event_selalu_punya_kunci_urut():
    """Kunci harus SELALU ada — pengurut membacanya untuk setiap event, dan
    bentuk yang tak seragam membuat konsumen lain (frontend, ekspor) harus
    menebak."""
    from timeline_utils import buat_event
    assert buat_event("aset", "x", "judul")["urut"] == ""
    assert buat_event("aset", "x", "judul", urut=" 2026 ")["urut"] == "2026"


def test_event_dari_riwayat_urut_berpadding_nol():
    """Indeks dipakai sebagai pemecah seri; tanpa nol di depan, langkah ke-10
    dibandingkan lebih KECIL daripada ke-9 secara leksikal."""
    from timeline_utils import event_dari_riwayat, urut_events
    doc = {"riwayat": [{"status": f"langkah-{i}", "tanggal": "2026-08-04"}
                       for i in range(12)]}
    ev = event_dari_riwayat(doc, "penghapusan", "Usulan", ref_id="u1")
    assert ev[0]["urut"] == "000000" and ev[11]["urut"] == "000011"
    urut = [e["judul"] for e in urut_events(ev)]
    assert urut[0].endswith("langkah-11"), urut[0]
    assert urut[-1].endswith("langkah-0"), urut[-1]
