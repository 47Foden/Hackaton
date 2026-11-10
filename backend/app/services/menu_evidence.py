"""Validate factual evidence against the current ordering catalogue."""
from datetime import date
import math
from urllib.parse import urlparse

FIELDS = ('description', 'caffeine_mg', 'milk', 'allergens')


def validate_evidence(data, catalog):
    by_id = {m.menu_id: m for m in catalog}
    if not isinstance(data, dict) or set(data) != {'schema_version', 'menus'} or data['schema_version'] != 1:
        raise ValueError('Invalid evidence schema')
    if not isinstance(data['menus'], list) or len(data['menus']) != len(by_id):
        raise ValueError('Evidence must cover all catalogue IDs, including unknowns')
    seen = set()
    for row in data['menus']:
        if set(row) != {'menu_id', 'name', 'official_name', 'mapping_note', 'variants'}:
            raise ValueError('Invalid menu evidence fields')
        mid = row['menu_id']
        if mid not in by_id or mid in seen or row['name'] != by_id[mid].name:
            raise ValueError('Unknown, duplicate or mismatched menu ID')
        seen.add(mid)
        if not all(isinstance(row[k], str) and row[k].strip() for k in ('official_name', 'mapping_note')):
            raise ValueError('Missing mapping information')
        temps = {t for t, _ in by_id[mid].variants}
        if set(row['variants']) != temps:
            raise ValueError('Evidence temperatures differ from catalogue')
        for temperature, fields in row['variants'].items():
            if set(fields) != set(FIELDS):
                raise ValueError('Missing evidence fields; use unknown explicitly')
            for field, record in fields.items():
                if not isinstance(record, dict) or set(record) != {'status', 'value', 'source', 'checked_date', 'note'}:
                    raise ValueError('Invalid evidence record')
                if not isinstance(record['note'], str):
                    raise ValueError('Invalid evidence note')
                if record['status'] == 'unknown':
                    if any(record[k] is not None for k in ('value', 'source', 'checked_date')):
                        raise ValueError('Unknown evidence must not carry asserted facts')
                    continue
                if record['status'] != 'verified':
                    raise ValueError('Unsupported evidence status')
                source = record['source']
                if not isinstance(source, str) or urlparse(source).scheme != 'https' or not urlparse(source).netloc:
                    raise ValueError('Verified evidence needs HTTPS provenance')
                try:
                    checked = date.fromisoformat(record['checked_date'])
                except (ValueError, TypeError):
                    raise ValueError('Invalid checked date') from None
                if checked > date.today():
                    raise ValueError('Evidence checked date is in the future')
                value = record['value']
                if field == 'description' and (not isinstance(value, str) or not value.strip()):
                    raise ValueError('Empty description')
                if field == 'caffeine_mg' and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                    raise ValueError('Invalid caffeine amount')
                if field == 'milk' and type(value) is not bool:
                    raise ValueError('Milk must be explicit boolean or unknown')
                if field == 'allergens' and (not isinstance(value, list) or not value or
                        any(not isinstance(x, str) or not x.strip() for x in value)):
                    raise ValueError('Record explicit listed allergens; blank label is unknown')
    return data
