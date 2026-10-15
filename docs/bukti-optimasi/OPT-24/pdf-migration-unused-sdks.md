# Migrasi PDF dan pengurangan SDK yang terbukti tidak dipakai

Tiga konsumen PyPDF2 berpindah ke pypdf: overlay nomor halaman ekspor aset,
penggabungan LHI, dan import parser pada tes executive summary historis.
Overlay memasukkan halaman ke `PdfWriter` sebelum `merge_page`, sesuai API
pypdf yang berlaku, dan menyalin metadata dokumen ReportLab. LHI memakai
`PdfWriter.append`, mempertahankan urutan setiap bagian dan memberi metadata
judul/pembuat yang jelas.

Perubahan hanya menulis ulang **PDF laporan yang baru dibuat server**. Jalur
unggah, kompresi, tanda tangan, dan pembacaan attachment existing tidak berubah.

`backend/tests/contract/test_generated_pdf.py`: **2 tes lulus** pada Mongo/GridFS
nyata melalui aplikasi ASGI, menggunakan pypdf 6.7.4 pada baseline lokal:

- Ekspor 40 aset menghasilkan beberapa halaman landscape, nomor `Halaman N dari M`
  benar, teks/urutan aset dan font Helvetica tetap ada, metadata ReportLab utuh,
  halaman dapat diraster ulang dengan PDFium. Satker lain mendapat 403.
- LHI lengkap dibandingkan dengan 12 bagian yang benar-benar dirender terpisah
  (sampul, BAHI, RHI, enam DBHI, DBKP, SP Hasil, SP Pelaksanaan). Jumlah/urutan
  halaman, teks, media box, dan font identik; sampul/tengah/akhir dapat diraster.
- SHA256 dan unduhan attachment original dengan fixture byte mirip ByteRange
  tetap persis sama setelah ekspor. Fixture tersebut bukan tanda tangan
  kriptografis; tes membuktikan jalur migrasi tidak menyentuh original.

Sebanyak **37 tes unit** urutan/tata letak laporan dan statistik/filter juga lulus.
Tes historis yang membutuhkan server/data eksternal tidak dijalankan; parser
importnya dimigrasikan agar tidak memerlukan paket lama.

Inventaris AST backend/scripts mencakup import di fungsi dan try, serta setiap
`__import__`/`import_module`. Setelah migrasi, tidak ada import PyPDF2, litellm,
jose, atau ecdsa. Satu import dinamis server hanya memuat daftar eksplisit jobs,
webp_converter, dan routes.backup; situs lain merupakan tes dengan nama modul
literal. Pencarian teks di backend/scripts/frontend/.github juga tidak menemukan
pemakaian runtime keempat SDK selain input dependensi.

Metadata distribusi baseline menunjukkan tidak ada reverse requirement untuk
PyPDF2, litellm, atau python-jose. Satu-satunya pemakai ecdsa adalah python-jose
yang ikut dihapus. Ini membenarkan penghapusan empat pin tersebut, **bukan**
penghapusan otomatis dependensi transitif lain. OpenAI/rsa/pyasn1 dipertahankan
sambil resolver memeriksa graph lock final. Hasil mesin dan daftar situs dinamis
ada di [`unused-sdk-inventory.json`](unused-sdk-inventory.json).

Pemilik lockfile memperbarui input/lock sebagai satu kelompok, menjalankan audit,
instalasi bersih dan suite gabungan. Bukti baseline di sini harus dilengkapi uji
pada versi pypdf dalam lock final sebelum produksi.
