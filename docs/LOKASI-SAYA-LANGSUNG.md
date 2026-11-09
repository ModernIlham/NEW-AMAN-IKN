# Pembaruan lokasi saat perjalanan

Fitur **Lokasi Anda** pada Peta Aset dan Peta Kolaborasi memantau posisi perangkat
selama pengguna mengaktifkannya dan peta terlihat. Tekan tombol lokasi untuk
memulai, izinkan akses lokasi, lalu titik dan lingkaran akurasi diperbarui
otomatis. Tekan lagi untuk berhenti, termasuk ketika pencarian belum selesai.

Kamera mengikuti titik jika mendekati tepi bagian tengah peta. Menggeser atau
memperbesar peta secara manual menghentikan mode ikuti kamera; pemantauan titik
tetap berjalan. Tombol panah **Pusatkan dan ikuti lokasi Anda** mengaktifkannya
kembali. Zoom awal menyesuaikan lingkaran akurasi agar pembacaan kasar tidak
terlihat seolah presisi. Pembaruan berikutnya mempertahankan zoom.

## Praktik yang diterapkan

| Kebutuhan | Implementasi |
| --- | --- |
| Posisi terus berubah saat perjalanan | Satu `navigator.geolocation.watchPosition`, `enableHighAccuracy: true`, `maximumAge: 0`, timeout per pembacaan 15 detik. Tidak menggunakan polling `getCurrentPosition`. |
| Posisi lama tidak menimpa yang baru | Validasi rentang koordinat, akurasi finite/nonnegatif, timestamp, umur maksimal 15 detik dan toleransi jam ke depan 5 detik. Pembacaan dengan timestamp yang sama/lebih lama diabaikan. |
| Perjalanan tidak membeku saat akurasi memburuk | Menggunakan posisi terbaru yang valid, bukan posisi paling akurat sepanjang sesi. Akurasi >100 m diberi keterangan “Akurasi rendah”; lingkaran selalu memperlihatkan ketidakpastian. |
| Hemat render dan memori | Pembaruan tampilan maksimal sekali per detik, menggabungkan pembacaan rapat dan tetap menggambar yang terakhir. Memindahkan marker/radius yang sama, tanpa membuat ulang peta/layer aset atau memicu render React pada setiap fix. |
| Kamera tetap nyaman | Pan hanya ketika titik keluar dari bagian tengah 50% peta. Tanpa antrean animasi; tidak melakukan zoom ulang setiap fix. Interaksi manual memberi pengguna kendali kamera. |
| GPS timeout/tidak tersedia | Watch dibersihkan lalu dicoba ulang dengan jeda 2, 4, 8, 16, maksimal 30 detik. Jeda kembali 2 detik setelah berhasil. Gangguan sementara tampil di status tanpa toast berulang. |
| Browser diam tanpa callback | Setelah 30 detik tanpa fix valid, lokasi ditandai belum diperbarui dan watch dipulihkan. Titik terakhir dipudarkan, lingkaran berubah kuning, tooltip menyebut “Lokasi terakhir” dan waktu pembacaan. |
| Hemat baterai saat tidak dipakai | GPS dan timer dijeda saat tab tersembunyi, `pagehide`, atau Peta Aset disembunyikan melalui keep-alive. Dilanjutkan dengan watch baru saat terlihat kembali jika fitur masih diaktifkan. |
| Tidak bocor setelah berhenti | Toggle mati, kontrol dilepas, dan `map.remove()` membersihkan watch, timer, serta listener. Token generasi membuang callback terlambat dari watch yang sudah dihentikan. |
| Izin dan kompatibilitas | Aktivasi hanya melalui tindakan pengguna. API tidak tersedia, HTTP tidak aman, dan izin ditolak mendapat pesan yang dapat ditindaklanjuti. Penolakan izin menghentikan retry sampai pengguna mengaktifkan kembali fitur. Tidak bergantung pada Permissions API atau Battery API. |
| Aksesibilitas | Tombol HTML asli dengan area sentuh 44×44, dukungan keyboard, `aria-pressed`, nama yang jelas, dan status `aria-live="polite"`. |
| Privasi | Koordinat fitur ini hanya berada di memori tab; tidak dikirim ke backend, tidak disimpan sebagai riwayat perjalanan, dan tidak mengubah koordinat aset. Permintaan ubin peta ke penyedia peta tetap mengikuti area yang dilihat. |

Implementasi bersama berada di `frontend/src/lib/pantauLokasi.js` (lifecycle GPS)
dan `frontend/src/lib/lokasiSayaPeta.js` (kontrol/layer Leaflet), sehingga kedua
peta memakai aturan yang sama. Fitur pengiriman posisi perangkat di halaman
Lacak serta pengambilan GPS untuk formulir/kamera memiliki tujuan dan lifecycle
tersendiri.

## Kerja lapangan dari Lokasi Anda (Peta Aset)

Dirancang ulang November 2026 setelah umpan balik pemilik: jejak perjalanan,
tombol ikuti terpisah, dan tombol "layar tetap menyala" **dihapus** karena tidak
menjawab kebutuhan lapangan. Yang tersisa berpusat pada tiga pertanyaan petugas:
*aset apa di dekat saya?*, *di mana aset X?*, dan *titik aset ini salah/belum
ada*.

**Satu tombol ◎** (seukuran tombol zoom, kelas `.peta-lokasi-btn`):

| Keadaan tombol | Ketuk → |
| --- | --- |
| Putih, ikon gelap (mati) | Nyalakan GPS + ikuti lokasi |
| Biru isi (aktif & mengikuti) | Matikan lokasi |
| Putih, ikon biru (aktif, peta sedang digeser) | Kembali ke lokasi Anda & ikuti lagi |

Menggeser peta sendiri memunculkan pesan "Peta digeser — ketuk ◎ untuk kembali";
gerakan peta oleh aplikasi (fokus pin, tambah aset) berhenti mengikuti tanpa
pesan agar tidak menutupi popup.

**Panel lapangan** (tengah atas, hanya saat lokasi aktif):

| Fitur | Perilaku |
| --- | --- |
| Ringkasan | "N aset ≤ 50 m · terdekat X m" + pil **GPS ±N m** (hijau ≤ 8 m, kuning ≤ 30 m, merah > 30 m). |
| Aset terdekat | 5 terdekat (5 km) + jarak & panah arah; ketuk = fokus pin (daftar dilipat agar popup bisa diketuk); 🧭 = pandu; ✎ = edit. Filter "hanya yang belum diinventarisasi" diingat. |
| **Pandu ke aset** | Garis ungu putus-putus Anda → aset, jarak & arah mata angin langsung; peta menampilkan keduanya. **Tiba** bila jarak ≤ max(5 m, akurasi GPS): getar sekali, judul "Anda di lokasi …", tombol **Edit / foto aset** dan **Titik = lokasi saya**. Aset > 300 m: tautan **Rute Google Maps**. Mematikan lokasi menghentikan pandu. |
| **Titik = lokasi saya** | Di panel saat tiba & di popup pin. Dua ketuk (ketuk kedua menyebut jarak pemindahan). Jalur simpan sama dengan geser pin (antrean OCC, jalan luring). **Gerbang akurasi ≤ 8 m**, sama dengan rana Mode Kamera Penuh. |
| **Tambah aset di lokasi saya** | Membuka popup "Aset baru di titik ini" (nama + foto, sama dengan tekan-lama peta) tepat di titik GPS Anda. Gerbang ≤ 8 m. |
| Popup pin | "📍 X m dari Anda · arah (GPS ±N m)" + **Pandu ke sini** + **Titik = lokasi saya**; > 300 m: Rute Google Maps. |
| Kerucut arah gerak | Dari `coords.heading` hanya saat kecepatan ≥ 0,7 m/s. |
| Jam perangkat meleset | Selisih jam perangkat vs GPS dipelajari dari dua fix konsisten — fix tak lagi ditolak semua sebagai basi. |

Logika murni: `frontend/src/lib/asetTerdekat.js`; panel:
`components/assets/PanelLapanganPeta.jsx`; kontrol & garis pandu:
`lib/lokasiSayaPeta.js` (`setTujuan`, `berhentiMengikuti`). Peta Kolaborasi
memakai kontrol yang sama tanpa panel (kotak status tetap menampilkan akurasi).

## Batas perangkat dan koneksi

- Gunakan **HTTPS** pada produksi; `localhost` dapat dipakai saat pengembangan.
  Pengguna harus mengizinkan lokasi di browser dan mengaktifkan layanan lokasi
  perangkat. Kebijakan browser/perusahaan atau iframe dapat memblokirnya.
- Frekuensi callback dan akurasi ditentukan OS, browser, perangkat, serta
  lingkungan. Batas render satu detik bukan jaminan mendapatkan fix GPS setiap
  detik. Desktop tanpa GPS sering memakai Wi-Fi/IP dengan akurasi lebih rendah.
- Di dalam gedung, terowongan, mode hemat daya, atau ketika GPS dimatikan,
  pembaruan dapat terlambat/tidak tersedia. Aplikasi memperlihatkan keadaan
  tersebut dan mencoba pulih; tidak membuat koordinat perkiraan seolah fix baru.
- Pembacaan lokasi dapat berlanjut tanpa internet jika penyedia lokasi perangkat
  mendukungnya. Ubin peta yang belum tersedia tetap memerlukan jaringan; fitur
  ini tidak menambahkan unduhan peta offline.
- Browser/PWA tidak menjamin pelacakan ketika layar terkunci atau aplikasi
  berada di latar belakang. Implementasi ini sengaja menjeda GPS saat halaman
  tersembunyi. Jika kebutuhan berikutnya mencakup perjalanan saat layar mati,
  gunakan aplikasi native dengan layanan lokasi latar belakang, izin sesuai OS,
  dan pengaturan konsumsi daya khusus. Tidak ada implementasi web yang menjamin
  pembaruan pada semua kondisi/perangkat.

## Verifikasi

Uji otomatis memakai penyedia geolokasi simulasi untuk perjalanan, callback
rapat, data rusak/basi/tidak berurutan, sinyal terputus, retry, izin ditolak,
perpindahan visibilitas, serta pembatalan dan callback terlambat. Uji integrasi
kontrol memakai **Leaflet asli** di jsdom, tanpa mengakses penyedia ubin.

```bash
cd frontend
CI=true npm test -- --watchAll=false --runInBand --runTestsByPath \
  src/lib/pantauLokasi.test.js src/lib/lokasiSayaPeta.test.js \
  src/components/assets/__tests__/AssetMapFullViewRender.test.jsx \
  src/pages/__tests__/PetaKolaborasiRender.test.jsx
```

Sebelum rilis, lakukan uji perangkat nyata melalui HTTPS: Chrome Android,
Safari iOS, browser desktop utama, serta mode PWA bila digunakan. Periksa
berjalan/berkendara sebagai penumpang, diam, masuk gedung, izin ditolak/dicabut,
GPS mati/hidup, jaringan putus, berpindah tab, layar terkunci lalu kembali,
dan membuka/menutup kedua peta berulang kali. Pantau apakah titik/radius sesuai,
status kehilangan fix terlihat, pemulihan berjalan, kamera menghormati interaksi
manual, serta indikator lokasi OS berhenti setelah fitur dimatikan. Ukur baterai
dan respons perangkat kelas rendah pada sesi lapangan yang representatif;
pengujian otomatis tidak membuktikan akurasi GPS atau konsumsi daya perangkat.
