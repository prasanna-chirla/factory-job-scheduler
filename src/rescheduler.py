"""Minimal event-driven replanning with append-only schedule and inventory history."""
from copy import deepcopy
from datetime import datetime
from .inventory import make_inventory_balances

def apply_replan_event(breakdown, material_delay, machines, materials, downtime, lots, requirements, baseline, scheduler, event_seq=1):
    """Apply one disruption, rerun the greedy schedule, and return auditable deltas."""
    events=[]; now=None
    if breakdown:
        start=datetime.fromisoformat(breakdown["start_at"]); end=datetime.fromisoformat(breakdown["end_at"])
        if breakdown["machine_id"] not in {m["machine_id"] for m in machines}: raise ValueError("Breakdown machine_id is unknown")
        if end<=start: raise ValueError("Breakdown end_at must be later than start_at")
        now=start.isoformat(timespec="seconds"); did=f"DT-UNPLANNED-{event_seq:04d}"
        downtime.append(dict(downtime_id=did,machine_id=breakdown["machine_id"],start_at=now,end_at=end.isoformat(timespec="seconds"),reason=breakdown.get("reason","UNPLANNED_BREAKDOWN")))
        events.append(dict(event_id=f"RSE-{event_seq:04d}",event_type="UNPLANNED_DOWNTIME",event_at=now,entity_type="Machine",entity_id=breakdown["machine_id"],old_value="AVAILABLE",new_value=f"DOWN_UNTIL_{end.isoformat(timespec='seconds')}",affected_operation_count=0,status="RECORDED"))
    if material_delay:
        mid=material_delay["material_id"]; until=datetime.fromisoformat(material_delay["delay_until"])
        if mid not in {m["material_id"] for m in materials}: raise ValueError("Material delay material_id is unknown")
        changed=[]
        for lot in lots:
            if lot["material_id"]==mid and datetime.fromisoformat(lot["available_from"])<until:
                changed.append((lot["lot_id"],lot["available_from"])); lot["available_from"]=until.isoformat(timespec="seconds")
        if not changed: raise ValueError("No lot availability was changed; delay_until must be later than current lot availability")
        now=now or until.isoformat(timespec="seconds")
        available=min(l["available_from"] for l in lots if l["material_id"]==mid)
        for req in requirements:
            if req["material_id"]==mid: req["available_at"]=available; req["available_date"]=available[:10]
        events.append(dict(event_id=f"RSE-{event_seq+len(events):04d}",event_type="MATERIAL_DELIVERY_DELAY",event_at=until.isoformat(timespec="seconds"),entity_type="Material",entity_id=mid,old_value="|".join(x[1] for x in changed),new_value=until.isoformat(timespec="seconds"),affected_operation_count=0,status="RECORDED"))
    replanned=scheduler()
    old_by_op={r["operation_id"]:r for r in baseline["operation_schedules"]}; new_by_op={r["operation_id"]:r for r in replanned["operation_schedules"]}
    reason=";".join(e["event_type"] for e in events)
    deltas=[]
    for opid in sorted(set(old_by_op)|set(new_by_op)):
        old=old_by_op.get(opid); new=new_by_op.get(opid)
        changed=old is None or new is None or any(old[k]!=new[k] for k in ("machine_id","start_at","end_at"))
        if not changed: continue
        deltas.append(dict(event_id=f"SCHG-{len(deltas)+1:06d}",schedule_id=(new or old)["schedule_id"],event_type="ADDED" if old is None else "UNSCHEDULED" if new is None else "RESCHEDULED",old_machine_id=old["machine_id"] if old else "",new_machine_id=new["machine_id"] if new else "",old_start_at=old["start_at"] if old else "",new_start_at=new["start_at"] if new else "",reason=reason))
    # Preserve original reservations, release them as explicit events, then apply new reservations.
    historical=deepcopy(baseline["inventory_transactions"]); release_events=[]
    for row in historical:
        release_events.append({"transaction_id":"","lot_id":row["lot_id"],"material_id":row["material_id"],"order_id":row["order_id"],"operation_id":row["operation_id"],"schedule_id":row["schedule_id"],"event_type":"RELEASE","quantity":row["quantity"],"event_at":now or row["event_at"],"allocation_policy":"REPLAN_RELEASE"})
    # Keep schedule state changes separate from append-only inventory transactions.
    inventory_history=historical+release_events+replanned["inventory_transactions"]
    for i,row in enumerate(inventory_history,1): row["transaction_id"]=f"INVTX-{i:07d}"
    for e in events:
        e["affected_operation_count"]=len(deltas)
        e["status"]="REPLANNED"
    replanned["inventory_transactions"]=inventory_history
    replanned["inventory_balances"]=make_inventory_balances(lots,inventory_history)
    return replanned,events,deltas
