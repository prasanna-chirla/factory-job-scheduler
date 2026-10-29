"""A deterministic, earliest-feasible shift scheduler for the synthetic dataset."""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, time, timedelta

SHIFT_STARTS = (time(6), time(14))
SHIFT_MINUTES = 480

def schedule_orders(orders, operations, calendars, eligibility, material_requirements, changeovers):
    """Assign each ordered operation to a compatible available shift.

    Operations are non-preemptive and must fit wholly in one 8-hour shift.
    Machine capacity is reserved in minutes, respecting planned downtime,
    routing precedence, material availability, and sequence-dependent setup.
    """
    by_order=defaultdict(list)
    for op in operations: by_order[op["order_id"]].append(op)
    for ops in by_order.values(): ops.sort(key=lambda x:x["sequence_no"])
    reqs=defaultdict(list)
    for req in material_requirements: reqs[(req["order_id"],req["operation_id"])].append(req)
    eligible=defaultdict(list)
    for row in eligibility: eligible[row["route_operation_id"]].append(row["machine_id"])
    cal={(r["machine_id"],r["shift_date"],int(r["shift_no"])):int(r["capacity_minutes"]) for r in calendars}
    used=defaultdict(int); last_family={}; last_end={}; output=[]; change={(r["from_family"],r["to_family"]):int(r["duration_minutes"]) for r in changeovers}
    order_map={o["order_id"]:o for o in orders}
    for order in sorted(orders,key=lambda o:(0 if o["priority"]=="URGENT" else 1,o["due_date"],o["order_id"])):
        ready=datetime.combine(date.fromisoformat(order["order_date"]),time(0))
        for op in by_order[order["order_id"]]:
            material_dates=[date.fromisoformat(r["available_date"]) for r in reqs[(order["order_id"],op["operation_id"])] ]
            material_ready=datetime.combine(max(material_dates),time(0)) if material_dates else ready
            earliest=max(ready,material_ready); candidates=[]
            for machine in sorted(eligible[op["route_operation_id"]]):
                prior=last_family.get(machine)
                co=change.get((prior,f"F{op['process_family']}"),0) if prior else 0
                run=int(float(op["run_minutes_per_unit"])*int(order["quantity"]))
                duration=int(op["setup_minutes"])+co+run
                if duration>SHIFT_MINUTES: continue
                probe=earliest.date()
                for _ in range(366):
                    if probe.weekday()!=6:
                        for shift,shift_start in enumerate(SHIFT_STARTS,1):
                            key=(machine,probe.isoformat(),shift)
                            cap=cal.get(key,0)
                            shift_origin=datetime.combine(probe,shift_start)
                            if cap-used[key]>=duration:
                                begin=max(shift_origin+timedelta(minutes=used[key]),earliest)
                                shift_limit=shift_origin+timedelta(minutes=cap)
                                if begin+timedelta(minutes=duration)>shift_limit: continue
                                if last_end.get(machine) and begin<last_end[machine]: continue
                                candidates.append((begin,machine,shift,duration,co,run,key)); break
                        if candidates and candidates[-1][0].date()==probe: break
                    probe+=timedelta(days=1)
            if not candidates: raise ValueError(f"No feasible shift/machine for {op['operation_id']} (duration or calendar capacity)")
            begin,machine,shift,duration,co,run,key=min(candidates,key=lambda x:(x[0],x[1],x[2]))
            end=begin+timedelta(minutes=duration); used[key]=max(used[key],int((end-datetime.combine(begin.date(),SHIFT_STARTS[shift-1])).total_seconds()/60)); last_family[machine]=f"F{op['process_family']}"; last_end[machine]=end
            output.append(dict(schedule_id=f"SCH-2026-{len(output)+1:06d}",order_id=order["order_id"],operation_id=op["operation_id"],machine_id=machine,sequence_no=op["sequence_no"],start_at=begin.isoformat(timespec="seconds"),end_at=end.isoformat(timespec="seconds"),quantity=order["quantity"],setup_minutes=op["setup_minutes"],changeover_minutes=co,run_minutes=run,status="PLANNED"))
            ready=end
    return output
