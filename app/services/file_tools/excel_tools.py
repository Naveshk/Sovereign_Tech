from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


def _convert_value(value: Any) -> Any:
    """Convert common string values to useful spreadsheet types without guessing."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text:
        return None

    # Preserve leading-zero identifiers and non-numeric strings.
    if re.fullmatch(r"-?\d+", text):
        try:
            return int(text)
        except ValueError:
            return text
    if re.fullmatch(r"-?(?:\d+\.\d*|\.\d+)%", text):
        try:
            return float(text[:-1]) / 100.0
        except ValueError:
            return text
    if re.fullmatch(r"-?(?:\d+\.\d*|\.\d+)", text):
        try:
            return float(text)
        except ValueError:
            return text

    # Only convert ISO-like dates; ambiguous dates stay as text.
    try:
        parsed = pd.to_datetime(text, errors="raise")
        if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", text):
            return parsed.to_pydatetime()
    except Exception:
        pass

    return value


def _normalize_records(records: list[dict[str, Any]] | dict[str, Any] | None) -> list[dict[str, Any]]:
    if records is None:
        return []
    if isinstance(records, dict):
        records = [records]
    normalized: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        normalized.append({str(k): _convert_value(v) for k, v in record.items()})
    return normalized


def _safe_sheet_name(name: str, used: set[str]) -> str:
    name = re.sub(r"[\[\]:*?/\\]", "_", str(name or "Data")).strip() or "Data"
    base = name[:31]
    candidate = base
    i = 2
    while candidate in used:
        suffix = f"_{i}"
        candidate = (base[: 31 - len(suffix)] + suffix)
        i += 1
    used.add(candidate)
    return candidate


def _format_sheet(ws, title: str | None = None) -> None:
    header_row = 1
    if title:
        ws.insert_rows(1)
        ws["A1"] = title
        ws["A1"].font = Font(bold=True, size=16)
        ws["A1"].alignment = Alignment(vertical="center")
        header_row = 2
        ws.freeze_panes = "A3"
    else:
        ws.freeze_panes = "A2"

    if ws.max_row >= header_row:
        thin = Side(style="thin", color="D9E1F2")
        for cell in ws[header_row]:
            if cell.value is not None:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="334155")
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = Border(top=thin, bottom=thin, left=thin, right=thin)
        for row in ws.iter_rows(min_row=header_row + 1):
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                cell.border = Border(bottom=thin)

        if ws.max_column:
            ws.auto_filter.ref = f"A{header_row}:{get_column_letter(ws.max_column)}{ws.max_row}"

        for col_idx in range(1, ws.max_column + 1):
            letter = get_column_letter(col_idx)
            values = [str(ws.cell(r, col_idx).value or "") for r in range(header_row, min(ws.max_row, header_row + 100) + 1)]
            width = min(max(max((len(v) for v in values), default=10) + 2, 10), 45)
            ws.column_dimensions[letter].width = width


def generate_excel_from_records(
    output_path: str,
    records: list[dict[str, Any]],
    sheet_name: str = "Data",
    title: str | None = None,
    summary: dict[str, Any] | None = None,
) -> dict:
    """Deterministically create a professional workbook from structured records."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = _safe_sheet_name(sheet_name, set())

    records = _normalize_records(records)
    keys: list[str] = []
    for record in records:
        for key in record:
            if key not in keys:
                keys.append(key)

    if keys:
        ws.append(keys)
        for record in records:
            ws.append([record.get(k) for k in keys])
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
            for cell in row:
                if isinstance(cell.value, float) and 0 <= cell.value <= 1:
                    header = str(ws.cell(1, cell.column).value or "").lower()
                    if any(token in header for token in ("percent", "%", "rate", "ratio", "completion")):
                        cell.number_format = "0.00%"
    else:
        ws.append(["Value"])
        ws.append(["No structured records were extracted."])

    _format_sheet(ws, title)

    if summary:
        sws = wb.create_sheet("Summary")
        sws["A1"] = "Summary"
        sws["A1"].font = Font(bold=True, size=16)
        row = 3
        for key, value in summary.items():
            sws.cell(row, 1, str(key))
            sws.cell(row, 2, value)
            row += 1
        _format_sheet(sws)

    wb.save(path)
    # Validate that the workbook can be reopened.
    check = load_workbook(path, read_only=True, data_only=False)
    try:
        if not check.sheetnames or check.active.max_row < 1:
            raise ValueError("Generated workbook is empty or invalid.")
    finally:
        check.close()

    return {
        "filename": path.name,
        "file_path": str(path),
        "file_type": "xlsx",
        "title": title or path.stem,
        "records_count": len(records),
        "columns": keys,
    }


# New preferred name; kept separate so legacy callers remain compatible.
generate_excel = generate_excel_from_records


def markdown_table_to_records(markdown: str) -> list[dict[str, Any]]:
    """Parse one or more simple Markdown tables into dynamic records."""
    lines = [line.strip() for line in (markdown or "").splitlines()]
    blocks: list[list[list[str]]] = []
    current: list[list[str]] = []

    def flush():
        nonlocal current
        if current:
            blocks.append(current)
            current = []

    for line in lines:
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and not all(set(c) <= set("-: ") for c in cells):
                current.append(cells)
        else:
            flush()
    flush()

    records: list[dict[str, Any]] = []
    for rows in blocks:
        if len(rows) < 2:
            continue
        headers = rows[0]
        for row in rows[1:]:
            padded = row + [""] * (len(headers) - len(row))
            records.append({headers[i]: _convert_value(padded[i]) for i in range(len(headers))})
    return records


def dataframe_to_records(path: str) -> list[dict[str, Any]]:
    p = Path(path)
    if p.suffix.lower() == ".csv":
        df = pd.read_csv(p)
    else:
        frames = []
        with pd.ExcelFile(p) as xls:
            for sheet in xls.sheet_names:
                df = pd.read_excel(p, sheet_name=sheet)
                if not df.empty:
                    df = df.copy()
                    df.insert(0, "_source_sheet", sheet)
                    frames.append(df)
        if not frames:
            return []
        df = pd.concat(frames, ignore_index=True)
    return [{str(k): _convert_value(v) for k, v in row.items()} for row in df.to_dict(orient="records")]


def inspect_excel(path: str) -> dict:
    """Inspect XLSX/XLS/CSV while retaining the existing return schema."""
    p = Path(path)
    sheets = []
    if p.suffix.lower() == ".csv":
        df = pd.read_csv(p)
        sheets.append(_inspect_dataframe(df, p.name))
    else:
        with pd.ExcelFile(p) as xls:
            for sheet in xls.sheet_names:
                df = pd.read_excel(p, sheet_name=sheet)
                sheets.append(_inspect_dataframe(df, sheet))
    return {"file": p.name, "sheet_count": len(sheets), "sheets": sheets}


def _inspect_dataframe(df: pd.DataFrame, name: str) -> dict:
    numeric = df.select_dtypes(include="number")
    numeric_summary = {}
    for col in numeric.columns:
        s = numeric[col].dropna()
        if len(s):
            numeric_summary[str(col)] = {
                "min": float(s.min()),
                "max": float(s.max()),
                "mean": float(s.mean()),
                "sum": float(s.sum()),
            }
    return {
        "name": str(name),
        "rows": int(len(df)),
        "columns": [str(c) for c in df.columns],
        "dtypes": {str(c): str(t) for c, t in df.dtypes.items()},
        "missing": {str(c): int(v) for c, v in df.isna().sum().items() if int(v)},
        "duplicates": int(df.duplicated().sum()),
        "numeric_summary": numeric_summary,
        "sample_rows": df.head(8).fillna("").astype(str).to_dict(orient="records"),
    }


def json_to_excel(output_path: str, data: list[dict[str, Any]] | dict[str, Any], title: str | None = None) -> dict:
    return generate_excel_from_records(output_path, _normalize_records(data), title=title)


def markdown_table_to_excel(output_path: str, markdown: str, title: str | None = None) -> dict:
    return generate_excel_from_records(output_path, markdown_table_to_records(markdown), title=title)
