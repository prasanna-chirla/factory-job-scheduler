"""Earliest-feasible job-shop scheduler with machine, labor, tool, and lot constraints."""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from .inventory import earliest_allocation_time, preview_allocation, make_inventory_balances
from .resources import fits_capacity

SHIFT_STARTS=(time(6),time(14)); SHIFT_MINUTES=480

def schedule_orders(orders, operations, calendars, eligibility, material_requirements, changeovers,
                    labor_calendars, labor_requirements, tools, tool_requirements, tool_availability,
                    lots, downtime, horizon_days=366):
    """Schedule operations serially by priority/due date, reserving all shared resources.

    The heuristic is not an optimal solver. Failure to find a slot is reported with
    evidence and classified separately from provable hard infeasibility.
    """
    by_order=defaultdict(list); order_by_id={o["order_id"]:o for o in orders}
    for op in operations: by_order[op["order_id"]].append(op)
    for items in by_order.values(): items.sort(key=lambda x:int(x["sequence_no"]))
    reqs=defaultdict(list)
    for req in material_requirements: reqs[(req["order_id"],req["operation_id"])].append(req)
    eligible=defaultdict(list)
    for row in eligibility: eligible[row["route_operation_id"]].append(row["machine_id"])
    labor_req=defaultdict(list)
    for row in labor_requirements: labor_req[row["route_operation_id"]].append(row)
    tool_req=defaultdict(list)
    for row in tool_requirements: tool_req[row["route_operation_id"]].append(row)
    calendar={(r["machine_id"],r["shift_date"],int(r["shift_no"])):int(r["capacity_minutes"]) for r in calendars}
    labor_capacity={(r["skill"],r["shift_date"],int(r["shift_no"])):int(r["workers_available"]) for r in labor_calendars}
    tool_capacity={(r["tool_id"],r["shift_date"],int(r["shift_no"])):int(r["available_quantity"]) for r in tool_availability}
    change={(r["from_family"],r["to_family"]):int(r["duration_minutes"]) for r in changeovers}
    remaining={lot["lot_id"]:float(lot["initial_quantity"]) for lot in lots}
    machine_used=defaultdict(int); last_family={}; last_end={}; labor_bookings=defaultdict(list); tool_bookings=defaultdict(list)
    downtime_intervals=[(d["machine_id"],datetime.fromisoformat(d["start_at"]),datetime.fromisoformat(d["end_at"])) for d in downtime]
    schedules=[]; inventory_events=[]; unscheduled=[]; blocked_orders=set(); machine_ids=sorted({r["machine_id"] for r in calendars})
    for order in sorted(orders,key=lambda o:(0 if o["priority"]=="URGENT" else 1,o["due_date"],o["order_id"])):
        ready=datetime.combine(date.fromisoformat(order["order_date"]),time(0)); blocked=False
        for op in by_order[order["order_id"]]:
            if blocked:
                unscheduled.append(_unscheduled(order,op,["PREDECESSOR_UNSCHEDULED"],"HEURISTIC_OR_DEPENDENCY_BLOCKED",None,None,{"blocked_by_order":True})); continue
            route_op=op["route_operation_id"]; need_rows=reqs[(order["order_id"],op["operation_id"])]; machines=sorted(eligible[route_op]); reason_codes=set(); proven=[]
            if not machines:
                unscheduled.append(_unscheduled(order,op,["NO_ELIGIBLE_MACHINE"],"PROVEN_INFEASIBLE",None,False,{"routing_operation_id":route_op,"required_process_family":op["process_family"],"due_date":order["due_date"]})); blocked=True; blocked_orders.add(order["order_id"]); continue
            material_ready=earliest_allocation_time(need_rows,lots,remaining,ready,horizon_days)
            if need_rows and material_ready is None:
                shortages=[]
                for req in need_rows:
                    available=sum(remaining.get(l["lot_id"],0) for l in lots if l["material_id"]==req["material_id"])
                    if available+1e-6<float(req["required_quantity"]): shortages.append({"material_id":req["material_id"],"required_quantity":float(req["required_quantity"]),"remaining_quantity":round(available,3)})
                reason="INSUFFICIENT_INVENTORY" if shortages else "MATERIAL_NOT_AVAILABLE_WITHIN_SEARCH_HORIZON"
                next_material=earliest_allocation_time(need_rows,lots,remaining,ready,36500) if not shortages else None
                can_meet=False if next_material and next_material.date()>date.fromisoformat(order["due_date"]) else (False if shortages else None)
                unscheduled.append(_unscheduled(order,op,[reason],"PROVEN_INFEASIBLE" if shortages else "SEARCH_LIMIT_OR_HEURISTIC_FAILURE",next_material.isoformat(timespec="seconds") if next_material else "",can_meet,{"material_shortages":shortages,"due_date":order["due_date"],"search_horizon_days":horizon_days,"next_material_time":next_material.isoformat(timespec="seconds") if next_material else None})); blocked=True; blocked_orders.add(order["order_id"]); continue
            earliest=max(ready,material_ready or ready); candidates=[]; saw_calendar=False; saw_labor=False; saw_tool=False
            for machine in machines:
                previous=last_family.get(machine); family=op["product_family"]
                co=change.get((previous,family),0) if previous else 0
                run=int(float(op["run_minutes_per_unit"])*int(order["quantity"])); duration=int(op["setup_minutes"])+co+run
                if duration>SHIFT_MINUTES:
                    proven.append({"machine_id":machine,"reason":"OPERATION_EXCEEDS_SHIFT","duration_minutes":duration}); continue
                probe=earliest.date()
                for _ in range(horizon_days+1):
                    if probe.weekday()!=6:
                        for shift,shift_start in enumerate(SHIFT_STARTS,1):
                            key=(machine,probe.isoformat(),shift); capacity=calendar.get(key,0)
                            if capacity>0: saw_calendar=True
                            if capacity-machine_used[key]<duration:
                                continue
                            origin=datetime.combine(probe,shift_start); limit=origin+timedelta(minutes=capacity)
                            begin=max(origin+timedelta(minutes=machine_used[key]),earliest)
                            # Move past any known or newly recorded outage that intersects this operation.
                            for _move in range(len(downtime_intervals)+1):
                                conflict=next((end for mid,start,end in downtime_intervals if mid==machine and start<begin+timedelta(minutes=duration) and begin<end),None)
                                if conflict is None: break
                                begin=max(begin,conflict)
                            if machine in last_end and begin<last_end[machine]: continue
                            # If a shared worker/tool pool is busy at this instant, advance to
                            # a reservation boundary inside the same shift instead of wasting it.
                            resource_ok=False
                            max_tries=2+sum(len(x) for x in labor_bookings.values())+sum(len(x) for x in tool_bookings.values())
                            static_resource_block=False
                            for _resource_try in range(max_tries):
                                end=begin+timedelta(minutes=duration)
                                if end>limit: break
                                blocked_ends=[]
                                for lr in labor_req[route_op]:
                                    rkey=(lr["skill"],probe.isoformat(),shift); cap=labor_capacity.get(rkey,0)
                                    if cap<int(lr["workers_required"]): saw_labor=True; static_resource_block=True; break
                                    if not fits_capacity(labor_bookings,rkey,begin,end,int(lr["workers_required"]),cap):
                                        saw_labor=True
                                        blocked_ends.extend(bend for bstart,bend,_ in labor_bookings.get(rkey,[]) if bend>begin and bstart<end)
                                if static_resource_block: break
                                for tr in tool_req[route_op]:
                                    tkey=(tr["tool_id"],probe.isoformat(),shift); cap=tool_capacity.get(tkey,0)
                                    if cap<int(tr["units_required"]): saw_tool=True; static_resource_block=True; break
                                    if not fits_capacity(tool_bookings,tkey,begin,end,int(tr["units_required"]),cap):
                                        saw_tool=True
                                        blocked_ends.extend(bend for bstart,bend,_ in tool_bookings.get(tkey,[]) if bend>begin and bstart<end)
                                if static_resource_block: break
                                if not blocked_ends:
                                    resource_ok=True; break
                                begin=min(x for x in blocked_ends if x>begin)
                            if not resource_ok or static_resource_block: continue
                            end=begin+timedelta(minutes=duration)
                            allocation=preview_allocation(need_rows,lots,remaining,begin)
                            if allocation is None: continue
                            candidates.append((begin,machine,shift,duration,co,run,key,end,allocation)); break
                        if candidates and candidates[-1][0].date()==probe: break
                    probe+=timedelta(days=1)
            if not candidates:
                if proven and len(proven)==len(machines):
                    unscheduled.append(_unscheduled(order,op,["OPERATION_EXCEEDS_SHIFT"],"PROVEN_INFEASIBLE",None,False,{"machine_limits":proven})); blocked=True; blocked_orders.add(order["order_id"]); continue
                hard_resource_limits=[]
                for lr in labor_req[route_op]:
                    maximum=max((cap for (skill,_,_),cap in labor_capacity.items() if skill==lr["skill"]),default=0)
                    if maximum<int(lr["workers_required"]): hard_resource_limits.append({"resource":"LABOR","skill":lr["skill"],"required":int(lr["workers_required"]),"maximum_available":maximum})
                for tr in tool_req[route_op]:
                    maximum=max((cap for (tool,_,_),cap in tool_capacity.items() if tool==tr["tool_id"]),default=0)
                    if maximum<int(tr["units_required"]): hard_resource_limits.append({"resource":"TOOL","tool_id":tr["tool_id"],"required":int(tr["units_required"]),"maximum_available":maximum})
                if hard_resource_limits:
                    codes=["LABOR_CAPACITY_INSUFFICIENT" if r["resource"]=="LABOR" else "TOOL_CAPACITY_INSUFFICIENT" for r in hard_resource_limits]
                    unscheduled.append(_unscheduled(order,op,codes,"PROVEN_INFEASIBLE",None,False,{"resource_limits":hard_resource_limits,"due_date":order["due_date"]})); blocked=True; blocked_orders.add(order["order_id"]); continue
                if not saw_calendar: reason_codes.add("NO_AVAILABLE_MACHINE_CALENDAR")
                if labor_req[route_op] and saw_labor: reason_codes.add("LABOR_CAPACITY_BLOCKED")
                if tool_req[route_op] and saw_tool: reason_codes.add("SHARED_TOOL_CAPACITY_BLOCKED")
                if not reason_codes: reason_codes.add("NO_FEASIBLE_SLOT_WITHIN_SEARCH_HORIZON")
                search_cutoff=(earliest+timedelta(days=horizon_days)).isoformat(timespec="seconds")
                unscheduled.append(_unscheduled(order,op,sorted(reason_codes),"SEARCH_LIMIT_OR_HEURISTIC_FAILURE","",None,{"eligible_machines":machines,"required_duration_minutes":duration,"search_horizon_days":horizon_days,"search_cutoff":search_cutoff,"due_date":order["due_date"],"resource_checks":{"calendar_seen":saw_calendar,"labor_block_seen":saw_labor,"tool_block_seen":saw_tool}})); blocked=True; blocked_orders.add(order["order_id"]); continue
            begin,machine,shift,duration,co,run,key,end,allocation=min(candidates,key=lambda x:(x[0],x[1],x[2]))
            machine_used[key]=max(machine_used[key],int((end-datetime.combine(begin.date(),SHIFT_STARTS[shift-1])).total_seconds()/60)); last_family[machine]=op["product_family"]; last_end[machine]=end
            for lr in labor_req[route_op]: labor_bookings[(lr["skill"],begin.date().isoformat(),shift)].append((begin,end,int(lr["workers_required"])))
            for tr in tool_req[route_op]: tool_bookings[(tr["tool_id"],begin.date().isoformat(),shift)].append((begin,end,int(tr["units_required"])))
            sid=f"SCH-2026-{len(schedules)+1:06d}"
            schedules.append(dict(schedule_id=sid,order_id=order["order_id"],operation_id=op["operation_id"],machine_id=machine,sequence_no=op["sequence_no"],start_at=begin.isoformat(timespec="seconds"),end_at=end.isoformat(timespec="seconds"),quantity=order["quantity"],setup_minutes=op["setup_minutes"],changeover_minutes=co,run_minutes=run,status="PLANNED"))
            for allocation_row in allocation:
                remaining[allocation_row["lot_id"]]-=allocation_row["quantity"]
                inventory_events.append(dict(transaction_id=f"INVTX-{len(inventory_events)+1:07d}",lot_id=allocation_row["lot_id"],material_id=allocation_row["material_id"],order_id=order["order_id"],operation_id=op["operation_id"],schedule_id=sid,event_type="RESERVE",quantity=allocation_row["quantity"],event_at=begin.isoformat(timespec="seconds"),allocation_policy="FEFO"))
            ready=end
    balances=make_inventory_balances(lots,inventory_events)
    return {"operation_schedules":schedules,"inventory_transactions":inventory_events,"inventory_balances":balances,"unscheduled_operations":unscheduled}

def _unscheduled(order,op,reasons,classification,next_time,can_meet,details):
    return {"order_id":order["order_id"],"operation_id":op["operation_id"],"reason_codes":"|".join(reasons),"classification":classification,"next_possible_time":next_time or "","can_meet_due_date":"UNKNOWN" if can_meet is None else str(bool(can_meet)).upper(),"details_json":__import__("json").dumps(details,sort_keys=True)}
