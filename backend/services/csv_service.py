import csv
import io
from datetime import datetime

EXPECTED_HEADERS = {
    "name", "category_id", "sku", "barcode", "quantity",
    "unit", "cost_per_unit", "expiry_date", "storage_location",
    "supplier", "notes",
}


def parse_expiry(value: str | None) -> datetime | None:
    if not value or not str(value).strip():
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt)
        except ValueError:
            continue
    return None


def parse_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value, default=None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_csv_content(file_bytes: bytes):
    """Parse uploaded CSV into a list of normalized item dicts."""
    content = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        raise ValueError("CSV file is empty or has no header row.")

    items = []
    errors = []
    for idx, row in enumerate(reader, start=2):
        if not row.get("name"):
            errors.append(f"Row {idx}: missing required 'name' column.")
            continue
        items.append({
            "name": row.get("name", "").strip(),
            "category_id": parse_int(row.get("category_id")),
            "sku": row.get("sku"), 
            "barcode": row.get("barcode"),
            "quantity": parse_float(row.get("quantity")),
            "unit": row.get("unit") or "units",
            "cost_per_unit": parse_float(row.get("cost_per_unit")),
            "expiry_date": parse_expiry(row.get("expiry_date")),
            "storage_location": row.get("storage_location"),
            "supplier": row.get("supplier"),
            "notes": row.get("notes"),
        })

    return {"items": items, "errors": errors}
