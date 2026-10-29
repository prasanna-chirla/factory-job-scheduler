"""Interval capacity checks for labor pools and shared tools."""
from datetime import datetime

def fits_capacity(bookings, key, start, end, needed, capacity):
    if needed<=0: return True
    if capacity<needed: return False
    points={start}
    for bstart,bend,units in bookings.get(key,[]):
        if bstart<end and start<bend:
            points.add(max(start,bstart))
            if bend<end: points.add(bend)
    for instant in points:
        occupied=sum(units for bstart,bend,units in bookings.get(key,[]) if bstart<=instant<bend)
        if occupied+needed>capacity: return False
    return True

def build_capacity_map(rows, resource_field, capacity_field):
    return {(row[resource_field],row["shift_date"],int(row["shift_no"])):int(row[capacity_field]) for row in rows}

def parse_intervals(rows, start_field="start_at", end_field="end_at"):
    return [(r["machine_id"],datetime.fromisoformat(r[start_field]),datetime.fromisoformat(r[end_field])) for r in rows]
