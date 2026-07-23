"""Utilitas pengembangan AMAN (bukan bagian runtime aplikasi).

Paket ini berisi perkakas bantu pengembangan/pengujian — mis. generator data
sintetis (``scripts.synthdata``). Modul di sini TIDAK di-import oleh
``server.py`` maupun route mana pun, jadi aman diubah tanpa memengaruhi
perilaku aplikasi di produksi.
"""
