"""Master/transaction primary key, foreign key, and basic value validation."""
from __future__ import annotations

def validate_data(tables):
    issues=[]
    primary={"products":"product_id","routings":"routing_id","operations":"route_operation_id","order_operations":"operation_id","machines":"machine_id","machine_calendars":"calendar_id","materials":"material_id","changeover_matrix":"changeover_id","production_orders":"order_id","inventory_lots":"lot_id","material_requirements":"requirement_id","machine_downtime":"downtime_id","operation_schedules":"schedule_id","labor_calendars":"labor_calendar_id","labor_requirements":"labor_requirement_id","tools":"tool_id","tool_requirements":"tool_requirement_id","tool_availability":"tool_availability_id","inventory_transactions":"transaction_id"}
    for table,key in primary.items():
        values=[r[key] for r in tables.get(table,[])]
        if len(values)!=len(set(values)): issues.append(f"{table}: duplicate {key}")
    for table,columns in (("machine_eligibility",("route_operation_id","machine_id")),("material_requirements",("order_id","operation_id","material_id")),("tool_availability",("tool_id","shift_date","shift_no")),("labor_calendars",("skill","shift_date","shift_no"))):
        keys=[tuple(row[c] for c in columns) for row in tables.get(table,[])]
        if len(keys)!=len(set(keys)): issues.append(f"{table}: duplicate composite key")
    ids={t:{r[k] for r in rows} for t,k in primary.items() for rows in [tables.get(t,[])]}
    fk=[("routings","product_id","products"),("operations","routing_id","routings"),("order_operations","order_id","production_orders"),("order_operations","routing_id","routings"),("order_operations","route_operation_id","operations"),("machine_calendars","machine_id","machines"),("inventory_lots","material_id","materials"),("production_orders","product_id","products"),("production_orders","routing_id","routings"),("material_requirements","order_id","production_orders"),("material_requirements","operation_id","order_operations"),("material_requirements","material_id","materials"),("machine_eligibility","route_operation_id","operations"),("machine_eligibility","machine_id","machines"),("labor_requirements","route_operation_id","operations"),("tool_requirements","route_operation_id","operations"),("tool_requirements","tool_id","tools"),("tool_availability","tool_id","tools"),("operation_schedules","order_id","production_orders"),("operation_schedules","operation_id","order_operations"),("operation_schedules","machine_id","machines"),("machine_downtime","machine_id","machines"),("inventory_transactions","lot_id","inventory_lots"),("inventory_transactions","material_id","materials"),("inventory_transactions","order_id","production_orders"),("inventory_transactions","operation_id","order_operations")]
    for table,col,parent in fk:
        if any(row[col] not in ids[parent] for row in tables.get(table,[])): issues.append(f"{table}.{col}: orphan {parent} reference")
    for o in tables.get("production_orders",[]):
        if int(o["quantity"])<=0 or o["order_date"]>o["due_date"]: issues.append(f"{o['order_id']}: invalid quantity or date order")
    products={r["product_id"]:r for r in tables.get("products",[])}
    for route in tables.get("routings",[]):
        if route["product_id"] in products and not route["effective_to"] and route["status"]=="ACTIVE" and not products[route["product_id"]]["status"]=="ACTIVE":
            issues.append(f"{route['routing_id']}: active route belongs to inactive product")
    routes={r["routing_id"]:r for r in tables.get("routings",[])}
    for order in tables.get("production_orders",[]):
        route=routes.get(order["routing_id"])
        if route and route["product_id"]!=order["product_id"]: issues.append(f"{order['order_id']}: route does not belong to product")
    template_by_id={o["route_operation_id"]:o for o in tables.get("operations",[])}
    order_ops_by_order={}
    for op in tables.get("order_operations",[]):
        order_ops_by_order.setdefault(op["order_id"],[]).append(op)
        order=next((o for o in tables.get("production_orders",[]) if o["order_id"]==op["order_id"]),None)
        template=template_by_id.get(op["route_operation_id"])
        if order and op["routing_id"]!=order["routing_id"]: issues.append(f"{op['operation_id']}: order operation route mismatch")
        if template and template["routing_id"]!=op["routing_id"]: issues.append(f"{op['operation_id']}: routing operation template mismatch")
    for order_id,items in order_ops_by_order.items():
        sequences=sorted(int(x["sequence_no"]) for x in items)
        if sequences!=[1,2,3,4]: issues.append(f"{order_id}: expected four ordered operations")
    lots={}
    for lot in tables.get("inventory_lots",[]): lots[lot["material_id"]]=lots.get(lot["material_id"],0)+float(lot["initial_quantity"])
    demand={}
    for req in tables.get("material_requirements",[]): demand[req["material_id"]]=demand.get(req["material_id"],0)+float(req["required_quantity"])
    for mid,quantity in demand.items():
        if quantity>lots.get(mid,0): issues.append(f"{mid}: aggregate requirements exceed inventory lots")
    order_quantities={r["order_id"]:int(r["quantity"]) for r in tables.get("production_orders",[])}
    for req in tables.get("material_requirements",[]):
        expected=round(float(req["quantity_per_unit"])*order_quantities.get(req["order_id"],0),3)
        if abs(expected-float(req["required_quantity"]))>0.001: issues.append(f"{req['requirement_id']}: material quantity does not reconcile")
    lot_by_id={l["lot_id"]:l for l in tables.get("inventory_lots",[])}
    events=tables.get("inventory_transactions",[])
    reserved={}; consumed={}
    for event in events:
        if event["event_type"] not in ("RESERVE","CONSUME","RELEASE"): issues.append(f"{event['transaction_id']}: invalid inventory event")
        if event["event_type"]=="RESERVE": reserved[event["lot_id"]]=reserved.get(event["lot_id"],0)+float(event["quantity"])
        elif event["event_type"] in ("RELEASE","CONSUME"):
            reserved[event["lot_id"]]=reserved.get(event["lot_id"],0)-float(event["quantity"])
            if event["event_type"]=="CONSUME": consumed[event["lot_id"]]=consumed.get(event["lot_id"],0)+float(event["quantity"])
    for lot_id,quantity in reserved.items():
        if quantity>float(lot_by_id[lot_id]["initial_quantity"])+1e-6: issues.append(f"{lot_id}: reservations exceed lot quantity")
    for lot in tables.get("inventory_lots",[]):
        if float(lot["initial_quantity"])<0 or float(lot["remaining_quantity"])<0: issues.append(f"{lot['lot_id']}: negative inventory quantity")
        if lot["available_from"]>lot["expiry_at"]: issues.append(f"{lot['lot_id']}: availability is after expiry")
    for balance in tables.get("inventory_balances",[]):
        if float(balance["remaining_quantity"])<0: issues.append(f"{balance['lot_id']}: inventory balance is negative")
        if abs(float(balance["initial_quantity"])-float(balance["reserved_quantity"])-float(balance["consumed_quantity"])-float(balance["remaining_quantity"]))>0.001: issues.append(f"{balance['lot_id']}: inventory balance does not reconcile")
        if abs(float(balance["reserved_quantity"])-reserved.get(balance["lot_id"],0))>0.001: issues.append(f"{balance['lot_id']}: reservation events do not reconcile")
        if abs(float(balance["consumed_quantity"])-consumed.get(balance["lot_id"],0))>0.001: issues.append(f"{balance['lot_id']}: consumption events do not reconcile")
    if tables.get("unscheduled_operations"): issues.append(f"{len(tables['unscheduled_operations'])} operations are unscheduled")
    tool_counts={t["tool_id"]:int(t["copies"]) for t in tables.get("tools",[])}
    for row in tables.get("tool_availability",[]):
        if int(row["available_quantity"])<0 or int(row["available_quantity"])>tool_counts.get(row["tool_id"],0): issues.append(f"{row['tool_availability_id']}: invalid tool availability")
    for row in tables.get("labor_calendars",[]):
        if int(row["workers_available"])<0: issues.append(f"{row['labor_calendar_id']}: negative worker availability")
    return issues
