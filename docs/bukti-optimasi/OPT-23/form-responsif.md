# Satu pemilik form pada breakpoint responsif

Smoke aplikasi nyata menemukan dua instance `AssetForm`: satu dalam wrapper desktop tersembunyi dan satu mobile. Pengguna mengedit merek/tab/checklist pada satu instance tetapi resize menampilkan state instance lain. Pembacaan geometri terhadap elemen DOM pertama yang tersembunyi sempat memberi hasil positif palsu dengan lebar nol.

Dashboard kini merender satu `AssetFormSidebar` pada posisi React yang tetap. Breakpoint hanya mengubah lebar, containment dan `alwaysExpanded`; mobile mempertahankan fixed aside, desktop mempertahankan panel 320px/hide. Containment dilepas di mobile agar aside tidak terpotong oleh wrapper nol lebar. Tidak ada key breakpoint atau pemindahan semua state form.

Uji wrapper dua kasus memverifikasi satu mount/identitas node, draf merek/dokumen, tab, fokus dan hide/show selama pergantian desktop/mobile. Smoke root memakai form aplikasi nyata: **17,75 detik PASS** dengan checklist yang benar-benar terlihat (`clientWidth>0`) pada 320/360/768/1440 × light/dark; STNK tidak dicentang dan item tambahan tetap sama ketika melewati breakpoint. Alur keyboard foto/checkbox, simpan HTTP readback, dan preflight ubah massal juga lulus. Artefak sesi lokal root: `/workspace/.aman/browser-wave2/hasil.json`; gate final/build dicatat terpisah oleh root.
