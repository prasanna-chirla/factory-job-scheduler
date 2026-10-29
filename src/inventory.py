"""Finite, lot-level inventory allocation with earliest-expiring-first policy."""
from datetime import datetime, timedelta

def as_datetime(value):
    if isinstance(value,datetime): return value
    return datetime.fromisoformat(value if "T" in value else value+"T00:00:00")

def preview_allocation(requirements, lots, remaining, at):
    """Return FEFO lot allocations for all requirements, or None if short."""
    at=as_datetime(at); staged={}; allocations=[]
    for req in requirements:
        need=float(req["required_quantity"]); mat=req["material_id"]
        candidates=sorted((lot for lot in lots if lot["material_id"]==mat and as_datetime(lot["available_from"])<=at and as_datetime(lot["expiry_at"])>=at),key=lambda x:(x["expiry_at"],x["lot_id"]))
        for lot in candidates:
            available=float(remaining.get(lot["lot_id"],lot["initial_quantity"]))-staged.get(lot["lot_id"],0.0)
            take=min(need,available)
            if take>0:
                staged[lot["lot_id"]]=staged.get(lot["lot_id"],0.0)+take
                allocations.append({"lot_id":lot["lot_id"],"material_id":mat,"quantity":round(take,3),"requirement_id":req["requirement_id"]})
                need=round(need-take,6)
            if need<=1e-6: break
        if need>1e-6: return None
    return allocations

def earliest_allocation_time(requirements, lots, remaining, earliest, horizon_days=366):
    """Find the earliest lot-arrival instant at which all needs can be allocated."""
    earliest=as_datetime(earliest)
    cutoff=earliest+timedelta(days=horizon_days)
    arrivals=sorted({max(earliest,as_datetime(lot["available_from"])) for req in requirements for lot in lots if lot["material_id"]==req["material_id"] and as_datetime(lot["available_from"])<=cutoff})
    for at in arrivals:
        if (at-earliest).days>horizon_days: continue
        if preview_allocation(requirements,lots,remaining,at) is not None: return at
    # Current stock may already cover the demand even when no new receipt event exists.
    return earliest if preview_allocation(requirements,lots,remaining,earliest) is not None else None

def make_inventory_balances(lots, transactions):
    reserved={}; consumed={}
    for event in transactions:
        lot=event["lot_id"]; quantity=float(event["quantity"])
        if event["event_type"]=="RESERVE": reserved[lot]=reserved.get(lot,0.0)+quantity
        elif event["event_type"]=="RELEASE": reserved[lot]=reserved.get(lot,0.0)-quantity
        elif event["event_type"]=="CONSUME":
            reserved[lot]=reserved.get(lot,0.0)-quantity; consumed[lot]=consumed.get(lot,0.0)+quantity
    rows=[]
    for lot in lots:
        r=round(reserved.get(lot["lot_id"],0.0),3); c=round(consumed.get(lot["lot_id"],0.0),3); initial=float(lot["initial_quantity"])
        rows.append({"lot_id":lot["lot_id"],"material_id":lot["material_id"],"initial_quantity":initial,"available_from":lot["available_from"],"reserved_quantity":r,"consumed_quantity":c,"remaining_quantity":round(initial-r-c,3)})
    return rows
