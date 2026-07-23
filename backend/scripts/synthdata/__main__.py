"""CLI generator data sintetis AMAN.

Contoh (jalankan dari direktori ``backend``):
    python -m scripts.synthdata --count 500 --profile mixed --seed 42
    python -m scripts.synthdata -n 100000 -p edge --format ndjson --out aset.ndjson
    python -m scripts.synthdata --kind pegawai -n 200 --out pegawai.json

Keluaran default ke stdout (JSON). Untuk volume besar gunakan ``--format
ndjson`` (satu record per baris, hemat memori saat di-stream ke importer).
"""
import argparse
import json
import sys

from .generator import (
    PROFIL_TERSEDIA,
    generate_activity,
    generate_assets,
    generate_pegawai,
    generate_satker,
)


def _build_parser():
    p = argparse.ArgumentParser(
        prog="python -m scripts.synthdata",
        description="Generator data sintetis BMN (OIKN/IKN) — realistis, "
                    "adaptif (registry-driven), & beranomali.")
    p.add_argument("-n", "--count", type=int, default=100,
                   help="jumlah record (default 100)")
    p.add_argument("-p", "--profile", choices=PROFIL_TERSEDIA, default="normal",
                   help="profil data: normal | mixed | edge (default normal)")
    p.add_argument("-s", "--seed", type=int, default=42,
                   help="seed acak — nilai sama → keluaran sama (default 42)")
    p.add_argument("-k", "--kind", choices=["aset", "pegawai", "satker", "kegiatan"],
                   default="aset", help="jenis data (default aset)")
    p.add_argument("-f", "--format", choices=["json", "ndjson"], default="json",
                   help="format keluaran (default json)")
    p.add_argument("-o", "--out", default="-",
                   help="berkas keluaran ('-' = stdout, default)")
    p.add_argument("--activity-id", default=None,
                   help="isi activity_id pada tiap aset (opsional)")
    return p


def _hasilkan(args):
    if args.kind == "aset":
        return generate_assets(args.count, seed=args.seed,
                               profile=args.profile, activity_id=args.activity_id)
    if args.kind == "pegawai":
        return generate_pegawai(args.count, seed=args.seed)
    if args.kind == "satker":
        return generate_satker(args.count, seed=args.seed)
    return generate_activity(args.count, seed=args.seed)


def _tulis(records, fmt, out):
    fh = sys.stdout if out == "-" else open(out, "w", encoding="utf-8")
    try:
        if fmt == "ndjson":
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        else:
            json.dump(records, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    finally:
        if fh is not sys.stdout:
            fh.close()


def main(argv=None):
    args = _build_parser().parse_args(argv)
    records = _hasilkan(args)
    _tulis(records, args.format, args.out)
    if args.out != "-":
        print(f"OK — {len(records)} record '{args.kind}' (profil={args.profile}, "
              f"seed={args.seed}) → {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
