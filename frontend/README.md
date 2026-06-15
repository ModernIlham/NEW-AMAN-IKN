# AMAN Frontend — Aplikasi Manajemen Aset Negara

Frontend React 19 untuk sistem inventarisasi BMN.

## Tech Stack

- **React 19** + **Create React App** (CRACO)
- **TailwindCSS** + **Shadcn/UI** (47 komponen)
- **Recharts** — Chart & grafik
- **Lucide React** — Icon library
- **Axios** — HTTP client
- **date-fns** — Date formatting
- **cmdk** — Command palette
- **Framer Motion** — Animations (via Radix UI)
- **React Virtuoso** — Virtualized lists

## Struktur

```
src/
├── pages/                      # 4 halaman utama
│   ├── LoginPage.jsx           # Login + OTP registration
│   ├── ActivitySelectionPage.jsx  # Pilih/buat kegiatan (1.150 baris)
│   ├── DashboardPage.jsx       # Dashboard utama aset (832 baris)
│   └── InfoPage.jsx            # Halaman info & panduan (556 baris)
│
├── components/
│   ├── assets/                 # 28 komponen aset (7.014 baris)
│   │   ├── AssetForm.jsx       # Form CRUD aset (1.284 baris, 13 section)
│   │   ├── BatchEditPanel.jsx  # Batch edit multi-aset
│   │   ├── VirtualizedAssetTable.jsx  # Tabel virtualized
│   │   ├── VirtualizedMobileCards.jsx # Card mobile virtualized
│   │   ├── AssetGalleryView.jsx       # Gallery view
│   │   ├── AdvancedFilter.jsx  # Filter multi-kriteria
│   │   ├── RekapitulasiPanel.jsx  # Rekapitulasi statistik
│   │   ├── DocumentChecklist.jsx  # Checklist dokumen
│   │   ├── ImportDialog.jsx    # Import CSV/XLSX
│   │   ├── rekapitulasi/       # 5 sub-komponen rekapitulasi
│   │   │   ├── ReportDownloads.jsx   # Download 13+ laporan PDF
│   │   │   ├── SummaryCards.jsx
│   │   │   ├── ConditionBreakdown.jsx
│   │   │   ├── InventoryProgress.jsx
│   │   │   └── TidakDitemukanBreakdown.jsx
│   │   └── ...
│   ├── ui/                     # 47 komponen Shadcn/UI
│   └── BackgroundTaskBar.jsx   # Status bar background tasks
│
├── hooks/                      # 9 custom hooks (973 baris)
│   ├── useWebSocket.js         # Real-time WebSocket
│   ├── useOptimisticQueue.js   # Background save queue
│   ├── useRowLocking.js        # Concurrent editing lock
│   ├── useAssetFilters.js      # Filter state management
│   ├── useDarkMode.js          # Dark/light mode
│   ├── useDragDropImport.js    # Drag & drop import
│   ├── useOfflineSync.js       # Offline sync
│   ├── usePullToRefresh.js     # Pull to refresh mobile
│   └── use-toast.js            # Toast notifications
│
├── lib/
│   └── utils.js                # Utility functions (cn, etc)
│
├── App.js                      # Router (Login, Activity, Dashboard, Info)
├── App.css                     # Custom styles
├── index.js                    # Entry point
└── index.css                   # TailwindCSS imports
```

## Scripts

```bash
yarn install        # Install dependencies
yarn start          # Development server (port 3000)
yarn build          # Production build
yarn test           # Run tests
```

## Environment

File `.env`:
```env
REACT_APP_BACKEND_URL=https://amanikn-inventarisasi.com
```

## Key Features

- **4 halaman**: Login, Pilih Kegiatan, Dashboard Aset, Info
- **28 komponen aset** spesifik inventarisasi BMN
- **Virtualized table & cards** untuk dataset besar (500+ aset)
- **Real-time** WebSocket: user presence, asset changes, row locking
- **Dark mode** toggle
- **Mobile responsive** + gallery view + pull to refresh
- **PWA** service worker untuk caching
- **Background save** dengan optimistic UI
- **13+ download laporan PDF** langsung dari UI
