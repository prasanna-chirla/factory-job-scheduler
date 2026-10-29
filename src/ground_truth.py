"""Counterfactual edge-case fixtures and independent validator evaluation."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timedelta
from .schedule_validator import validate_schedule

PATTERNS={"MACHINE_OVERLAP":"overlaps","PRECEDENCE_VIOLATION":"precedence violation","MATERIAL_EARLY_CONSUMPTION":"material ","OUTSIDE_SHIFT":"outside","CHANGEOVER_OMITTED":"changeover mismatch"}
SCENARIOS=[("MACHINE_OVERLAP","NO_MACHINE_OVERLAP"),("PRECEDENCE_VIOLATION","ROUTING_PRECEDENCE"),("MATERIAL_EARLY_CONSUMPTION","MATERIAL_AVAILABLE_BEFORE_START"),("OUTSIDE_SHIFT","MACHINE_CALENDAR_COVERAGE"),("CHANGEOVER_OMITTED","SEQUENCE_DEPENDENT_CHANGEOVER")]

def _not_applicable(kind, constraint, reason):
    return {"issue_type":kind,"expected_constraint":constraint,"witness":{},"scenario_status":"NOT_APPLICABLE","applicable":False,"detected_violation":False,"detected_constraint":"","test_passed":None,"messages":[reason]}

def _run_case(kind, constraint, fixture, witness):
    matching=[message for message in validate_schedule(fixture) if PATTERNS[kind] in message]
    detected=bool(matching)
    return {"issue_type":kind,"expected_constraint":constraint,"witness":witness,"scenario_status":"PASS" if detected else "FAIL","applicable":True,"detected_violation":detected,"detected_constraint":constraint if detected else "","test_passed":detected,"messages":matching}

def evaluate_required_scenarios(tables):
    """Check each constructible anomaly; mark scenarios unsupported by the input N/A."""
    schedules=tables.get("operation_schedules",[]); cases={}
    if len(schedules)>=2:
        overlap=deepcopy(tables); a,b=overlap["operation_schedules"][:2]
        b["machine_id"]=a["machine_id"]; b["start_at"]=a["start_at"]; b["end_at"]=a["end_at"]
        cases["MACHINE_OVERLAP"]=_run_case("MACHINE_OVERLAP","NO_MACHINE_OVERLAP",overlap,{"schedule_ids":[a["schedule_id"],b["schedule_id"]],"machine_id":a["machine_id"]})
    else:
        cases["MACHINE_OVERLAP"]=_not_applicable("MACHINE_OVERLAP","NO_MACHINE_OVERLAP","At least two scheduled operations are needed to construct an overlap case.")

    precedence=deepcopy(tables); pair=None
    for order_id in {s["order_id"] for s in schedules}:
        rows=sorted((s for s in precedence["operation_schedules"] if s["order_id"]==order_id),key=lambda x:int(x["sequence_no"]))
        if len(rows)>=2: pair=(rows[0],rows[1]); break
    if pair:
        prev,nxt=pair; order_op=next(x for x in precedence["order_operations"] if x["operation_id"]==nxt["operation_id"])
        allowed=[x["machine_id"] for x in precedence["eligibility"] if x["route_operation_id"]==order_op["route_operation_id"] and x["machine_id"]!=prev["machine_id"]]
        if allowed: nxt["machine_id"]=allowed[0]
        begin=datetime.fromisoformat(prev["start_at"]); duration=int(nxt["setup_minutes"])+int(nxt["changeover_minutes"])+int(nxt["run_minutes"])
        nxt["start_at"]=begin.isoformat(timespec="seconds"); nxt["end_at"]=(begin+timedelta(minutes=duration)).isoformat(timespec="seconds")
        cases["PRECEDENCE_VIOLATION"]=_run_case("PRECEDENCE_VIOLATION","ROUTING_PRECEDENCE",precedence,{"predecessor":prev["schedule_id"],"successor":nxt["schedule_id"]})
    else:
        cases["PRECEDENCE_VIOLATION"]=_not_applicable("PRECEDENCE_VIOLATION","ROUTING_PRECEDENCE","At least two ordered operations for one order are needed to construct a precedence case.")

    material=deepcopy(tables); material_pair=next(((s,r) for s in material.get("operation_schedules",[]) for r in material.get("material_requirements",[]) if r["operation_id"]==s["operation_id"]),None)
    if material_pair:
        scheduled,req=material_pair; req["available_date"]=(datetime.fromisoformat(scheduled["start_at"]).date()+timedelta(days=1)).isoformat()
        cases["MATERIAL_EARLY_CONSUMPTION"]=_run_case("MATERIAL_EARLY_CONSUMPTION","MATERIAL_AVAILABLE_BEFORE_START",material,{"schedule_id":scheduled["schedule_id"],"requirement_id":req["requirement_id"]})
    else:
        cases["MATERIAL_EARLY_CONSUMPTION"]=_not_applicable("MATERIAL_EARLY_CONSUMPTION","MATERIAL_AVAILABLE_BEFORE_START","A scheduled operation with a material requirement is needed to construct this case.")

    if schedules:
        calendar=deepcopy(tables); scheduled=calendar["operation_schedules"][0]; start=datetime.fromisoformat(scheduled["start_at"]); duration=int(scheduled["setup_minutes"])+int(scheduled["changeover_minutes"])+int(scheduled["run_minutes"])
        bad_start=start.replace(hour=5,minute=0,second=0); scheduled["start_at"]=bad_start.isoformat(timespec="seconds"); scheduled["end_at"]=(bad_start+timedelta(minutes=duration)).isoformat(timespec="seconds")
        cases["OUTSIDE_SHIFT"]=_run_case("OUTSIDE_SHIFT","MACHINE_CALENDAR_COVERAGE",calendar,{"schedule_id":scheduled["schedule_id"],"proposed_start_at":scheduled["start_at"]})
    else:
        cases["OUTSIDE_SHIFT"]=_not_applicable("OUTSIDE_SHIFT","MACHINE_CALENDAR_COVERAGE","At least one scheduled operation is needed to construct an outside-shift case.")

    changeover=deepcopy(tables); chosen=None; by_machine={}
    for row in changeover.get("operation_schedules",[]): by_machine.setdefault(row["machine_id"],[]).append(row)
    templates={r["route_operation_id"]:r for r in changeover.get("operations",[])}; order_ops={r["operation_id"]:r for r in changeover.get("order_operations",[])}
    matrix={(r["from_family"],r["to_family"]):int(r["duration_minutes"]) for r in changeover.get("changeover_matrix",[])}
    for machine,rows in by_machine.items():
        rows.sort(key=lambda x:x["start_at"])
        for prev,nxt in zip(rows,rows[1:]):
            prior=order_ops.get(prev["operation_id"]); current=order_ops.get(nxt["operation_id"])
            if not prior or not current: continue
            pf=templates[prior["route_operation_id"]]["product_family"]; nf=templates[current["route_operation_id"]]["product_family"]
            if matrix.get((pf,nf),0)>0 and int(nxt["changeover_minutes"])>0: chosen=(prev,nxt,matrix[(pf,nf)]); break
        if chosen: break
    if chosen:
        prev,nxt,required=chosen; nxt["changeover_minutes"]=0
        nxt["end_at"]=(datetime.fromisoformat(nxt["end_at"])-timedelta(minutes=required)).isoformat(timespec="seconds")
        cases["CHANGEOVER_OMITTED"]=_run_case("CHANGEOVER_OMITTED","SEQUENCE_DEPENDENT_CHANGEOVER",changeover,{"previous_schedule_id":prev["schedule_id"],"schedule_id":nxt["schedule_id"],"required_minutes":required})
    else:
        cases["CHANGEOVER_OMITTED"]=_not_applicable("CHANGEOVER_OMITTED","SEQUENCE_DEPENDENT_CHANGEOVER","No machine has consecutive scheduled jobs from different product families, so there is no required changeover to omit.")

    definitions=[]; observed=[]
    for i,(kind,constraint) in enumerate(SCENARIOS,1):
        result=cases[kind]; sid=f"EDGE-{i:03d}"
        definitions.append({"scenario_id":sid,"issue_type":kind,"expected_violation":True,"expected_constraint":constraint,"applicable":result["applicable"],"scenario_status":result["scenario_status"],"witness":result["witness"]})
        observed.append({"scenario_id":sid,**result})
    failures=sum(x["scenario_status"]=="FAIL" for x in observed); skipped=sum(x["scenario_status"]=="NOT_APPLICABLE" for x in observed)
    status="FAIL" if failures else "PASS_WITH_SKIPS" if skipped else "PASS"
    return definitions,{"status":status,"scenario_count":len(observed),"passed_count":sum(x["scenario_status"]=="PASS" for x in observed),"skipped_count":skipped,"failed_count":failures,"results":observed}
