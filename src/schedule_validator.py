"""Validate hard constraints against generated schedule source tables."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime

def _active_reservations(events):
    active=[]
    for event in events:
        if event["event_type"]=="RESERVE": active.append({**event,"active_quantity":float(event["quantity"])})
        elif event["event_type"] in ("RELEASE","CONSUME"):
            left=float(event["quantity"])
            for reserve in active:
                if reserve["lot_id"]!=event["lot_id"] or reserve["material_id"]!=event["material_id"]: continue
                take=min(left,reserve["active_quantity"]); reserve["active_quantity"]-=take; left-=take
                if left<=1e-6: break
    return [event for event in active if event["active_quantity"]>1e-6]

def validate_schedule(tables):
    issues=[]; orders={r["order_id"]:r for r in tables["production_orders"]}; templates={r["route_operation_id"]:r for r in tables["operations"]}; order_ops={r["operation_id"]:r for r in tables["order_operations"]}
    ops={op_id:templates[row["route_operation_id"]] for op_id,row in order_ops.items() if row["route_operation_id"] in templates}
    elig=defaultdict(set)
    for e in tables["eligibility"]: elig[e["route_operation_id"]].add(e["machine_id"])
    calendar={(r["machine_id"],r["shift_date"],int(r["shift_no"])):int(r["capacity_minutes"]) for r in tables["machine_calendars"]}
    downtime=[(r["machine_id"],datetime.fromisoformat(r["start_at"]),datetime.fromisoformat(r["end_at"])) for r in tables.get("machine_downtime",[])]
    changes={(r["from_family"],r["to_family"]):int(r["duration_minutes"]) for r in tables["changeover_matrix"]}
    requirements=defaultdict(list); labor_requirements=defaultdict(list); tool_requirements=defaultdict(list)
    for req in tables.get("material_requirements",[]): requirements[req["operation_id"]].append(req)
    for req in tables.get("labor_requirements",[]): labor_requirements[req["route_operation_id"]].append(req)
    for req in tables.get("tool_requirements",[]): tool_requirements[req["route_operation_id"]].append(req)
    labor_capacity={(r["skill"],r["shift_date"],int(r["shift_no"])):int(r["workers_available"]) for r in tables.get("labor_calendars",[])}
    tool_capacity={(r["tool_id"],r["shift_date"],int(r["shift_no"])):int(r["available_quantity"]) for r in tables.get("tool_availability",[])}
    inventory_events=defaultdict(list)
    for event in tables.get("inventory_transactions",[]): inventory_events[event["operation_id"]].append(event)
    lots={l["lot_id"]:l for l in tables.get("inventory_lots",[])}
    by_machine=defaultdict(list); by_order=defaultdict(list); labor_bookings=defaultdict(list); tool_bookings=defaultdict(list); schedule_rows={r["schedule_id"]:r for r in tables["operation_schedules"]}
    for s in tables["operation_schedules"]:
        start=datetime.fromisoformat(s["start_at"]); end=datetime.fromisoformat(s["end_at"]); op=ops[s["operation_id"]]
        if end<=start: issues.append(f"{s['schedule_id']}: non-positive duration")
        order_op=order_ops.get(s["operation_id"])
        if not order_op or s["machine_id"] not in elig[order_op["route_operation_id"]]: issues.append(f"{s['schedule_id']}: machine not eligible")
        if s["operation_id"] in order_ops and s["order_id"]!=order_op["order_id"]: issues.append(f"{s['schedule_id']}: scheduled operation belongs to another order")
        if start.date().isoformat()!=end.date().isoformat() or start.weekday()==6: issues.append(f"{s['schedule_id']}: outside a working shift")
        else:
            shift=1 if start.hour<14 else 2; shift_start=start.replace(hour=6 if shift==1 else 14,minute=0,second=0); shift_end=shift_start.replace(hour=14 if shift==1 else 22)
            if start<shift_start or end>shift_end or calendar.get((s["machine_id"],start.date().isoformat(),shift),0)==0: issues.append(f"{s['schedule_id']}: outside available machine calendar")
        if any(mid==s["machine_id"] and down_start<end and start<down_end for mid,down_start,down_end in downtime): issues.append(f"{s['schedule_id']}: overlaps machine downtime")
        expected=int(float(op["run_minutes_per_unit"])*int(s["quantity"]))
        if expected!=int(s["run_minutes"]): issues.append(f"{s['schedule_id']}: run duration mismatch")
        if int((end-start).total_seconds()/60)!=int(s["setup_minutes"])+int(s["changeover_minutes"])+int(s["run_minutes"]): issues.append(f"{s['schedule_id']}: scheduled duration does not reconcile")
        for req in requirements[s["operation_id"]]:
            if start.date().isoformat()<req["available_date"]: issues.append(f"{s['schedule_id']}: material {req['material_id']} unavailable at operation start")
            reserved=[e for e in _active_reservations(inventory_events[s["operation_id"]]) if e["material_id"]==req["material_id"]]
            if abs(sum(float(e["active_quantity"]) for e in reserved)-float(req["required_quantity"]))>0.001: issues.append(f"{s['schedule_id']}: material reservation does not cover requirement {req['requirement_id']}")
            for event in reserved:
                lot=lots[event["lot_id"]]; at=datetime.fromisoformat(event["event_at"])
                if datetime.fromisoformat(lot["available_from"])>at or datetime.fromisoformat(lot["expiry_at"])<at: issues.append(f"{s['schedule_id']}: invalid inventory lot availability for {event['lot_id']}")
                if at>start: issues.append(f"{s['schedule_id']}: material reserved after operation start")
        if order_op:
            for req in labor_requirements[order_op["route_operation_id"]]:
                key=(req["skill"],start.date().isoformat(),1 if start.hour<14 else 2)
                labor_bookings[key].append((start,end,int(req["workers_required"]),s["schedule_id"]))
            for req in tool_requirements[order_op["route_operation_id"]]:
                key=(req["tool_id"],start.date().isoformat(),1 if start.hour<14 else 2)
                tool_bookings[key].append((start,end,int(req["units_required"]),s["schedule_id"]))
        by_machine[s["machine_id"]].append((start,end,s["schedule_id"])); by_order[s["order_id"]].append((int(s["sequence_no"]),start,end,s["schedule_id"]))
    for machine,items in by_machine.items():
        items.sort()
        if items and int(schedule_rows[items[0][2]]["changeover_minutes"])!=0: issues.append(f"{items[0][2]}: first scheduled family has an unnecessary changeover")
        for prev,current in zip(items,items[1:]):
            if current[0]<prev[1]: issues.append(f"{current[2]}: overlaps {prev[2]} on {machine}")
            prior_family=ops[schedule_rows[prev[2]]["operation_id"]]["product_family"]
            current_row=schedule_rows[current[2]]
            current_family=ops[current_row["operation_id"]]["product_family"]
            if int(current_row["changeover_minutes"])!=changes.get((prior_family,current_family),0): issues.append(f"{current[2]}: changeover mismatch after {prev[2]}")
    for order,items in by_order.items():
        items.sort()
        expected=sorted(int(op["sequence_no"]) for op in tables["order_operations"] if op["order_id"]==order)
        actual=[x[0] for x in items]
        if actual!=expected: issues.append(f"{order}: scheduled operation sequence is incomplete or duplicated")
        for prev,current in zip(items,items[1:]):
            if current[1]<prev[2]: issues.append(f"{current[3]}: precedence violation after {prev[3]}")
    for label,bookings,capacities in (("labor",labor_bookings,labor_capacity),("tool",tool_bookings,tool_capacity)):
        for key,items in bookings.items():
            points=sorted({item[0] for item in items}|{item[1] for item in items})
            for point in points[:-1]:
                active=[item for item in items if item[0]<=point<item[1]]
                used=sum(item[2] for item in active)
                if used>capacities.get(key,0):
                    issues.append(f"{active[-1][3]}: {label} capacity exceeded for {key[0]}")
                    break
    return issues
