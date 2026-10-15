"""File snapshot→XLSX builders, without Mongo cursors or shared workbooks."""
import io
import json

from kodefikasi_utils import LEVEL_LABELS


def append_snapshot_rows(path, rows):
    written = 0
    with open(path, "a", encoding="utf-8") as output:
        for row in rows:
            line = json.dumps(row, ensure_ascii=False, default=str) + "\n"
            output.write(line)
            written += len(line.encode())
    return written


def _rows(path):
    with open(path, encoding="utf-8") as source:
        for line in source:
            yield json.loads(line)


def build_kodefikasi_xlsx(path, bentuk):
    from openpyxl import Workbook
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Kodefikasi")
    if bentuk == "datar":
        sheet.append(["Kode", "Uraian", "Level", "Kode Induk"])
        for row in _rows(path):
            level = row.get("level")
            sheet.append([row.get("kode", ""), row.get("uraian", ""),
                          f"{level} {LEVEL_LABELS.get(level, '')}".strip(), row.get("parent_kode") or ""])
    else:
        descriptions = {row["kode"]: row.get("uraian", "") for row in _rows(path)}
        sheet.append(["Kode Golongan", "Nama Golongan", "Kode Bidang", "Nama Bidang",
            "Kode Kelompok", "Nama Kelompok", "Kode Sub Kelompok", "Nama Sub Kelompok",
            "Kode Barang", "Nama Barang", "Satuan", "Dasar", "Jenis BMN", "TB/STB", "Bukti Kepemilikan"])
        for row in _rows(path):
            if row.get("level") != 5:
                continue
            code = row.get("kode", "")
            gol, bidang, kelompok, sub = code[:1], code[:3], code[:5], code[:7]
            sheet.append([gol, descriptions.get(gol, ""), bidang, descriptions.get(bidang, ""),
                kelompok, descriptions.get(kelompok, ""), sub, descriptions.get(sub, ""),
                code, row.get("uraian", ""), row.get("satuan", ""), row.get("dasar", ""),
                row.get("jenis_bmn", ""), row.get("tb_stb", ""), row.get("bukti_kepemilikan", "")])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()
