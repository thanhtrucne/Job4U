"""Build the browser address catalogue from the supplied Vietnamese Excel file.

Usage (PowerShell):
    python scripts/build_vn_address_data.py "P:\download\final_danh-muc-phuong-xa_moi.xlsx"
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile


NAMESPACE = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def cell_column(reference: str) -> str:
    return "".join(character for character in reference if character.isalpha())


def main(source: Path) -> None:
    with ZipFile(source) as archive:
        shared = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
        strings = ["".join(item.itertext()) for item in shared.findall("x:si", NAMESPACE)]
        sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    provinces: OrderedDict[str, dict] = OrderedDict()
    for row in sheet.findall(".//x:sheetData/x:row", NAMESPACE):
        values: dict[str, str] = {}
        for cell in row.findall("x:c", NAMESPACE):
            value = cell.find("x:v", NAMESPACE)
            if value is None:
                continue
            raw = value.text or ""
            values[cell_column(cell.attrib["r"])] = strings[int(raw)] if cell.attrib.get("t") == "s" else raw

        # Rows start at 4. D = province name, C = province code,
        # I = new ward code and J = new ward name in the supplied workbook.
        province_name, province_code = values.get("D", "").strip(), values.get("C", "").strip()
        ward_name, ward_code = values.get("J", "").strip(), values.get("I", "").strip()
        if not province_name or not ward_name or not province_code.isdigit():
            continue
        province = provinces.setdefault(province_code, {"code": province_code, "name": province_name, "wards": []})
        province["wards"].append({"code": ward_code, "name": ward_name})

    output = Path(__file__).resolve().parents[1] / "frontend" / "data" / "vn_admin_units.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"provinces": list(provinces.values())}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(provinces)} provinces and {sum(len(item['wards']) for item in provinces.values())} wards to {output}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Pass the path to final_danh-muc-phuong-xa_moi.xlsx")
    main(Path(sys.argv[1]))
