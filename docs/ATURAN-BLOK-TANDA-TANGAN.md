# ATURAN SISTEM — Baris Identitas pada Blok Tanda Tangan

**Status:** mengikat. Berlaku pada **setiap** dokumen yang digenerate aplikasi —
PDF maupun Word — di **semua** modul, termasuk modul yang belum ada saat
dokumen ini ditulis.

---

## 1. Aturannya

> Di **blok tanda tangan**, baris identitas hanya dicetak bila nomornya
> **NIP** (termasuk **NI PPPK**) atau **NRP**.
>
> Selain itu — nomor kosong, penanda tangan **Non-ASN**, atau nomor berformat
> **NIK** — blok tanda tangan berisi **nama saja**.

Tidak ada label pengganti, tidak ada garis titik-titik, tidak ada "NIP. -".
Bila tidak layak dicetak, **tidak ada baris sama sekali**.

Permintaan pemilik yang menetapkannya:

> *"apabila pegawai tersebut tidak memiliki informasi mengenai NIP dan/atau
> tergolong sebagai Non-ASN maka di bagian tanda tangan tidak perlu dituliskan,
> jadi hanya tuliskan jika NIP/NRP saja. Jadikan ini aturan sistem dan tulis di
> dalam dokumentasi agar diterapkan saat pembuatan generate PDF/Word dokumen ke
> depannya tanpa terkecuali, khusus di bagian tanda tangan saja."*

## 2. Batas ruang lingkupnya

Aturan ini **hanya** mengenai blok tanda tangan — area nama + garis
pengesahan di kaki dokumen.

**TIDAK** berlaku pada:

| Tempat | Alasan |
|---|---|
| Kolom tabel (mis. daftar pegawai, DBR/KIR, lampiran) | Nomornya di situ adalah **informasi yang diminta**, bukan tanda pengesahan |
| Blok identitas "Nama / NIP / Jabatan" di kepala naskah | Nomornya memang sudah tercetak; yang dibutuhkan **namanya yang benar** — dipakai `label_identitas_cetak` |
| Ekspor Excel/CSV | Data, bukan dokumen bertanda tangan |
| Pesan galat & log | Bukan keluaran dokumen |

## 3. Cara menerapkannya

Satu fungsi, dan **hanya** fungsi itu:

```python
from pegawai_utils import baris_identitas_ttd

{'header': 'Kuasa Pengguna Barang,',
 'nama': kpb["nama"],
 'after': baris_identitas_ttd(kpb["nip"], kpb.get("status_kepegawaian"))}
```

`baris_identitas_ttd` mengembalikan **list** — `[]` bila tidak layak dicetak —
sehingga langsung dapat dipakai sebagai `after` pada `_signature_block`
(PDF) maupun `_sig_cell` (Word). Pemanggil **tidak perlu dan tidak boleh**
menyediakan teks penggantinya sendiri.

Untuk blok yang hanya punya satu baris teks (bukan list), gunakan
`baris_identitas_laporan(nomor, status)` — ia mengembalikan `""` pada kasus
yang sama, dan pemanggil menuliskannya hanya bila tidak kosong.

Bila status kepegawaiannya perlu dicari dulu dari NIP, pada modul laporan
tersedia `_baris_nip_ttd(nip)` (async) yang menelusuri registry pejabat lalu
Master Pegawai.

### Yang dilarang

```python
# ✗ label yang dipatok
'after': ['NIP. ....................']

# ✗ label "netral" berupa garis titik
'after': ['NIP/NIK/NRP. ................']

# ✗ tanda hubung sebagai pengganti
'after': ['NIP/NIK. -']

# ✗ merakit label sendiri
'after': [f"NIP. {nip}"] if nip else []
```

Yang terakhir tampak benar tetapi tetap salah: ia mencetak "NIP." di depan
NRP, dan mencetak NIK penanda tangan Non-ASN.

## 4. Kenapa aturannya seperti ini

**Nomor kosong.** Garis tanda tangan yang kosong diisi tangan setelah dicetak,
jadi tak ada satu pun jalur kode yang bisa mendeteksi jenis nomornya. Label
apa pun di situ adalah tebakan — dan tebakan yang salah untuk sebagian orang.
Pemilik memilih tidak menebak: kosongkan.

**Non-ASN.** Identitas pegawai Non-ASN adalah NIK, yaitu identitas
kependudukan, bukan nomor jabatan. Mencetaknya di dokumen yang beredar luas
membuka data pribadi tanpa keperluan (lihat `docs/DPIA-PELACAKAN-ASET.md`).

**NIK apa pun statusnya.** Termasuk ASN yang di Master Pegawai masih tercatat
NIK karena NIP-nya belum diisi. Nomor yang salah jenis lebih buruk daripada
tidak ada nomor: dokumen resmi jadi menamai nomor seseorang dengan nama yang
bukan namanya.

## 5. Yang menjaganya

`backend/tests/unit/test_label_identitas_pdf.py` menyapu **seluruh** berkas
Python backend (bukan daftar berkas yang harus diingat orang) dan menagih:

- tak ada konstanta berupa label identitas tanpa nomor di mana pun;
- konstanta `PLACEHOLDER_IDENTITAS` sudah tidak ada, dan tidak diimpor
  di berkas mana pun;
- `baris_identitas_ttd` tetap bertanda tangan dua parameter — parameter
  placeholder-nya dihapus, bukan dibiarkan bernilai bawaan kosong, supaya
  pemanggil lama **gagal keras** alih-alih diam-diam mengirim status
  kepegawaian ke slot yang salah;
- pemindaiannya sendiri terbukti menyapu berkas sungguhan dan polanya
  terbukti menangkap — pemindai yang jalurnya salah selalu hijau.

Menambah modul PDF/Word baru **tidak** memerlukan pendaftaran apa pun: karena
pemindaiannya menyapu seluruh backend, modul baru langsung ikut terjaga.
