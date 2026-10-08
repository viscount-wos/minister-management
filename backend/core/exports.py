"""Spreadsheet export helpers shared by event modules: user text must never run as a formula (M5)."""
import csv
import io

FORMULA_TRIGGERS = ('=', '+', '-', '@', '\t', '\r')


def csv_safe(value):
    """CSV cell: text starting with = + - @ TAB or CR gets a leading apostrophe (OWASP CSV injection)."""
    if isinstance(value, str) and value[:1] in FORMULA_TRIGGERS:
        return "'" + value
    return value


def to_csv_bytes(header, rows):
    """UTF-8 with BOM (Excel opens it with the right encoding, as tyrantpoll's export did)."""
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(header)
    for row in rows:
        w.writerow(['' if v is None else csv_safe(v) for v in row])
    return out.getvalue().encode('utf-8-sig')


def append_safe(ws, row):
    """openpyxl append; strings that a spreadsheet could evaluate become quote-prefixed text cells."""
    ws.append(row)
    for cell in ws[ws.max_row]:
        v = cell.value
        if isinstance(v, str) and v[:1] in FORMULA_TRIGGERS:
            cell.data_type = 's'
            cell.quotePrefix = True
