"""Build master data first, then transactions, schedules, reports, and truth labels."""
from __future__ import annotations
import csv, json, random
from datetime import date, datetime, time, timedelta
from pathlib import Path
from .schemas import TABLES, write_csv
from .scheduler import schedule_orders
from .data_validator import validate_data
from .schedule_validator import validate_schedule
from .metrics import calculate_metrics
from .reproducibility import build_manifest
from .sql_export import export_sql
from .ground_truth import evaluate_required_scenarios
from .rescheduler import apply_replan_event

BASE=date(2026,1,5)

def _clear_generated_files(data_root: Path) -> None:
    """Remove previous generated data, retaining .gitkeep placeholders."""
    for folder_name in ("master", "transactions", "output", "ground_truth"):
        folder = data_root / folder_name
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if path.is_file() and path.name != ".gitkeep":
                path.unlink()

def _dump_json(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")

def build_dataset(root:Path, seed=20261022, sku_count=100, machine_count=40, order_count=500, material_count=200, breakdown=None, material_delay=None):
    rng=random.Random(seed); data=root/"data"; master=data/"master"; txn=data/"transactions"; output=data/"output"; truth_dir=data/"ground_truth"
    _clear_generated_files(data)
    for folder in (master,txn,output,truth_dir): folder.mkdir(parents=True,exist_ok=True)
    products=[]; routings=[]; operations=[]; order_operations=[]; execution_operations=[]; machines=[]; materials=[]; calendars=[]; downtime=[]; changes=[]; eligibility=[]; labor_calendars=[]; labor_requirements=[]; tools=[]; tool_requirements=[]; tool_availability=[]
    for i in range(1,sku_count+1):
        sku=f"SKU-{i:04d}"; family=(i-1)%4+1; pid=f"PROD-2026-{i:06d}"; rid=f"ROUTE-{sku}-01"
        products.append(dict(product_id=pid,sku=sku,description=f"Synthetic product {sku}",family=f"F{family}",status="ACTIVE"))
        routings.append(dict(routing_id=rid,product_id=pid,revision=1,effective_from=BASE.isoformat(),effective_to="",status="ACTIVE"))
    for i in range(1,machine_count+1): machines.append(dict(machine_id=f"MACH-{i:03d}",name=f"Cell {i:02d}",process_family=(i-1)%4+1,capacity_units_per_shift=rng.choice([8,10,12,16]),status="ACTIVE"))
    for i in range(1,material_count+1): materials.append(dict(material_id=f"MAT-{i:04d}",name=f"Material {i:03d}",unit="kg",status="ACTIVE"))
    for a in range(1,5):
        for b in range(1,5): changes.append(dict(changeover_id=f"CO-F{a}-F{b}",from_family=f"F{a}",to_family=f"F{b}",duration_minutes=0 if a==b else 10+abs(a-b)*8,effective_from=BASE.isoformat(),effective_to=""))
    # Routing operation templates are master data, independent of individual orders.
    for i in range(1,sku_count+1):
        sku=f"SKU-{i:04d}"; family=(i-1)%4+1; rid=f"ROUTE-{sku}-01"
        for step,(name,rate,setup) in enumerate(zip(("Prepare","Machine","Finish","Inspect"),(7,11,6,4),(20,35,25,15)),1):
            pf=(family+step-2)%4+1; route_op_id=f"ROUTEOP-{i:04d}-{step:02d}"
            operations.append(dict(route_operation_id=route_op_id,routing_id=rid,sequence_no=step,name=name,process_family=pf,product_family=f"F{family}",run_minutes_per_unit=rate,setup_minutes=setup))
            skill="quality_inspector" if step==4 else "operator"
            labor_requirements.append(dict(labor_requirement_id=f"LABREQ-{i:04d}-{step:02d}",route_operation_id=route_op_id,skill=skill,workers_required=1 if step!=2 else 2))
            if step==2: tool_requirements.append(dict(tool_requirement_id=f"TOOLREQ-{i:04d}-{step:02d}",route_operation_id=route_op_id,tool_id="TOOL-MILL-JIG",units_required=1))
            if step==4: tool_requirements.append(dict(tool_requirement_id=f"TOOLREQ-{i:04d}-{step:02d}",route_operation_id=route_op_id,tool_id="TOOL-CALIBRATION",units_required=1))
    # Machine calendar source is also emitted as a normalized downtime transaction.
    for machine in machines:
        mid=int(machine["machine_id"].split("-")[1])
        for offset in range(84):
            day=BASE+timedelta(days=offset)
            if day.weekday()==6: continue
            for shift in (1,2):
                down=(mid*17+offset*7+shift*3)%131==0
                start=time(6 if shift==1 else 14); end=time(14 if shift==1 else 22)
                cal_id=f"CAL-{mid:03d}-{offset+1:03d}-{shift}"
                calendars.append(dict(calendar_id=cal_id,machine_id=machine["machine_id"],shift_date=day.isoformat(),shift_no=shift,start_at=datetime.combine(day,start).isoformat(),end_at=datetime.combine(day,end).isoformat(),capacity_minutes=0 if down else 480,availability="DOWNTIME" if down else "AVAILABLE",reason="PLANNED_MAINTENANCE" if down else ""))
                if down: downtime.append(dict(downtime_id=f"DT-{mid:03d}-{offset+1:03d}-{shift}",machine_id=machine["machine_id"],start_at=datetime.combine(day,start).isoformat(),end_at=datetime.combine(day,end).isoformat(),reason="PLANNED_MAINTENANCE"))
                if mid==1:
                    for skill,workers in (("operator",6),("quality_inspector",2)):
                        labor_calendars.append(dict(labor_calendar_id=f"LAB-{skill}-{offset+1:03d}-{shift}",skill=skill,shift_date=day.isoformat(),shift_no=shift,start_at=datetime.combine(day,start).isoformat(),end_at=datetime.combine(day,end).isoformat(),workers_available=workers))
    tools=[dict(tool_id="TOOL-MILL-JIG",name="Shared milling jig",copies=4,status="ACTIVE"),dict(tool_id="TOOL-CALIBRATION",name="Calibration gauge",copies=2,status="ACTIVE")]
    for offset in range(84):
        day=BASE+timedelta(days=offset)
        if day.weekday()==6: continue
        for shift in (1,2):
            for tool in tools:
                unavailable=tool["tool_id"]=="TOOL-MILL-JIG" and (offset*7+shift*11)%173==0
                tool_availability.append(dict(tool_availability_id=f"TA-{tool['tool_id']}-{offset+1:03d}-{shift}",tool_id=tool["tool_id"],shift_date=day.isoformat(),shift_no=shift,available_quantity=0 if unavailable else tool["copies"]))
    machine_family={m["machine_id"]:m["process_family"] for m in machines}
    lots=[]
    for mi,material in enumerate(materials,1):
        for n in range(1,4):
            available=BASE+timedelta(days=(mi*3+n*5)%24)
            available_at=datetime.combine(available,time(6 if n<3 else 14))
            lots.append(dict(lot_id=f"LOT-{mi:04d}-{n:02d}",material_id=material["material_id"],initial_quantity=10000,available_from=available_at.isoformat(timespec="seconds"),expiry_at=datetime.combine(available+timedelta(days=365),time(23,59,59)).isoformat(timespec="seconds"),reserved_quantity=0,consumed_quantity=0,remaining_quantity=10000,status="AVAILABLE"))
    lot_dates={}
    for lot in lots: lot_dates.setdefault(lot["material_id"],[]).append(lot["available_from"])
    orders=[]; requirements=[]
    operation_template={(o["routing_id"],int(o["sequence_no"])):o for o in operations}
    for i in range(1,order_count+1):
        pidx=(i*37-1)%sku_count+1; pid=f"PROD-2026-{pidx:06d}"; rid=f"ROUTE-SKU-{pidx:04d}-01"; quantity=rng.randint(3,15)
        created=BASE+timedelta(days=rng.randint(0,12)); urgent=i%37==0
        priority="URGENT" if urgent else rng.choice(["HIGH","NORMAL","NORMAL","LOW"])
        due_window={"URGENT":(3,14),"HIGH":(14,35),"NORMAL":(25,55),"LOW":(40,75)}[priority]
        due=created+timedelta(days=rng.randint(*due_window))
        oid=f"ORD-2026-{i:06d}"
        orders.append(dict(order_id=oid,product_id=pid,routing_id=rid,quantity=quantity,order_date=created.isoformat(),due_date=due.isoformat(),priority=priority,status="RELEASED"))
        for step in range(1,5):
            template=operation_template[(rid,step)]; opid=f"OP-{oid}-{step:02d}"
            order_operations.append(dict(operation_id=opid,order_id=oid,routing_id=rid,route_operation_id=template["route_operation_id"],sequence_no=step,status="PLANNED"))
            execution_operations.append({**template,"operation_id":opid,"order_id":oid})
            midx=((pidx*7+step*13-1)%material_count)+1; material_id=f"MAT-{midx:04d}"; qty_per_unit=round(0.1+((pidx+step)%8)*0.05,2)
            earliest_lot=min(lot_dates[material_id]); requirements.append(dict(requirement_id=f"REQ-{oid}-{step:02d}",order_id=oid,operation_id=opid,material_id=material_id,quantity_per_unit=qty_per_unit,required_quantity=round(qty_per_unit*quantity,3),unit="kg",available_date=earliest_lot[:10],available_at=earliest_lot))
    # Bridge table connects route operation templates to eligible machines.
    for op in operations:
        for mid,pf in machine_family.items():
            if pf==int(op["process_family"]): eligibility.append(dict(route_operation_id=op["route_operation_id"],machine_id=mid,effective_from=BASE.isoformat(),effective_to=""))
    tables={"products":products,"routings":routings,"operations":operations,"order_operations":order_operations,"machines":machines,"machine_calendars":calendars,"materials":materials,"changeover_matrix":changes,"production_orders":orders,"inventory_lots":lots,"material_requirements":requirements,"machine_downtime":downtime,"eligibility":eligibility,"machine_eligibility":eligibility,"labor_calendars":labor_calendars,"labor_requirements":labor_requirements,"tools":tools,"tool_requirements":tool_requirements,"tool_availability":tool_availability}
    def run_scheduler():
        return schedule_orders(orders,execution_operations,calendars,eligibility,requirements,changes,labor_calendars,labor_requirements,tools,tool_requirements,tool_availability,lots,downtime)
    baseline=run_scheduler(); schedule_before_replan=[]; reschedule_events=[]; schedule_changes=[]
    if breakdown or material_delay:
        schedule_before_replan=baseline["operation_schedules"]
        scheduled,reschedule_events,schedule_changes=apply_replan_event(breakdown,material_delay,machines,materials,downtime,lots,requirements,baseline,run_scheduler)
    else: scheduled=baseline
    schedules=scheduled["operation_schedules"]; tables["operation_schedules"]=schedules; tables["inventory_transactions"]=scheduled["inventory_transactions"]; tables["inventory_balances"]=scheduled["inventory_balances"]; tables["unscheduled_operations"]=scheduled["unscheduled_operations"]
    tables["machine_eligibility"]=eligibility
    for table,rows in (("products",products),("routings",routings),("operations",operations),("machines",machines),("machine_calendars",calendars),("materials",materials),("changeover_matrix",changes),("machine_eligibility",eligibility),("labor_calendars",labor_calendars),("labor_requirements",labor_requirements),("tools",tools),("tool_requirements",tool_requirements),("tool_availability",tool_availability)):
        fields=TABLES[table]
        write_csv(master/f"{table}.csv",rows,fields)
    for table in ("production_orders","order_operations","inventory_lots","material_requirements","machine_downtime","inventory_transactions"):
        write_csv(txn/f"{table}.csv",tables[table],TABLES[table])
    write_csv(txn/"reschedule_events.csv",reschedule_events,TABLES["reschedule_events"])
    write_csv(output/"operation_schedules.csv",schedules,TABLES["operation_schedules"])
    write_csv(output/"schedule_change_events.csv",schedule_changes,TABLES["schedule_change_events"])
    snapshot_path=output/"operation_schedules_before_replan.csv"
    if schedule_before_replan: write_csv(snapshot_path,schedule_before_replan,TABLES["operation_schedules"])
    elif snapshot_path.exists(): snapshot_path.unlink()
    write_csv(output/"inventory_balances.csv",scheduled["inventory_balances"])
    write_csv(output/"unscheduled_operations.csv",scheduled["unscheduled_operations"],TABLES["unscheduled_operations"])
    definitions,evaluation=evaluate_required_scenarios(tables)
    truth_csv=[{**{k:v for k,v in row.items() if k!="witness"},"witness_json":json.dumps(row["witness"],sort_keys=True)} for row in definitions]
    write_csv(truth_dir/"ground_truth.csv",truth_csv); _dump_json(truth_dir/"ground_truth.json",definitions)
    _dump_json(output/"ground_truth_evaluation.json",evaluation)
    _dump_json(output/"rescheduling_report.json",{"event_count":len(reschedule_events),"changed_operation_count":len(schedule_changes),"events":reschedule_events})
    data_issues=validate_data(tables); schedule_issues=validate_schedule(tables)
    infeasibility={"status":"NONE" if not scheduled["unscheduled_operations"] else "HAS_UNSCHEDULED_OPERATIONS","classification_note":"PROVEN_INFEASIBLE denotes a hard bound such as no eligible machine, excessive non-preemptive duration, or insufficient total stock. SEARCH_LIMIT_OR_HEURISTIC_FAILURE means this greedy search did not find a slot within its horizon; it is not proof that no schedule exists.","unscheduled_operations":scheduled["unscheduled_operations"]}
    _dump_json(output/"infeasibility_report.json",infeasibility)
    passed=not data_issues and not schedule_issues and evaluation["status"] in ("PASS","PASS_WITH_SKIPS")
    validation={"status":"PASS" if passed else "FAIL","seed":seed,"checks":{"master_and_transaction_integrity":"PASS" if not data_issues else "FAIL","schedule_hard_constraints":"PASS" if not schedule_issues else "FAIL","ground_truth_evaluation":evaluation["status"]},"issues":{"data":data_issues,"schedule":schedule_issues},"row_counts":{k:len(v) for k,v in tables.items() if k!="eligibility"}}
    metrics=calculate_metrics(orders,schedules); metrics["seed"]=seed; metrics["anomaly_case_count"]=len(definitions); metrics["unscheduled_operation_count"]=len(scheduled["unscheduled_operations"]); metrics["inventory_lot_count"]=len(lots)
    export_sql({"products":products,"routings":routings,"operations":operations,"machines":machines,"machine_calendars":calendars,"materials":materials,"changeover_matrix":changes,"machine_eligibility":eligibility,"labor_calendars":labor_calendars,"labor_requirements":labor_requirements,"tools":tools,"tool_requirements":tool_requirements,"tool_availability":tool_availability,"production_orders":orders,"order_operations":order_operations,"inventory_lots":lots,"material_requirements":requirements,"inventory_transactions":scheduled["inventory_transactions"],"machine_downtime":downtime,"operation_schedules":schedules},output/"schedule_seed.sql")
    _dump_json(output/"validation_report.json",validation); _dump_json(output/"metrics.json",metrics)
    manifest=build_manifest(data,seed,validation["row_counts"]); _dump_json(output/"source_manifest.json",manifest)
    return {"validation":validation,"metrics":metrics,"manifest":manifest,"ground_truth_evaluation":evaluation,"infeasibility":infeasibility}
