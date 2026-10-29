from datetime import datetime

def schedule_tables(second_machine="MACH-001", second_start="2026-01-05T06:20:00", second_family=1, second_change=0, second_date="2026-01-05", material_available="2026-01-05"):
    operations=[
        dict(route_operation_id="ROUTEOP-1",routing_id="ROUTE-SKU-0001-01",sequence_no=1,name="Cut",process_family=1,product_family="F1",run_minutes_per_unit=5,setup_minutes=5),
        dict(route_operation_id="ROUTEOP-2",routing_id="ROUTE-SKU-0001-01",sequence_no=2,name="Finish",process_family=second_family,product_family="F2" if second_family==2 else "F1",run_minutes_per_unit=5,setup_minutes=5),
    ]
    calendars=[]
    for machine in ("MACH-001","MACH-002"):
        for shift,start,end in ((1,"06:00:00","14:00:00"),(2,"14:00:00","22:00:00")):
            calendars.append(dict(machine_id=machine,shift_date="2026-01-05",shift_no=shift,capacity_minutes=480,start_at=f"2026-01-05T{start}",end_at=f"2026-01-05T{end}"))
    second_machine=second_machine
    schedules=[
        dict(schedule_id="SCH-1",order_id="ORD-1",operation_id="OP-ORD-1-01",machine_id="MACH-001",sequence_no=1,start_at="2026-01-05T06:00:00",end_at="2026-01-05T06:20:00",quantity=3,setup_minutes=5,changeover_minutes=0,run_minutes=15,status="PLANNED"),
        dict(schedule_id="SCH-2",order_id="ORD-1",operation_id="OP-ORD-1-02",machine_id=second_machine,sequence_no=2,start_at=second_start,end_at="2026-01-05T06:40:00",quantity=3,setup_minutes=5,changeover_minutes=second_change,run_minutes=15,status="PLANNED"),
    ]
    order_operations=[dict(operation_id="OP-ORD-1-01",order_id="ORD-1",routing_id="ROUTE-SKU-0001-01",route_operation_id="ROUTEOP-1",sequence_no=1),dict(operation_id="OP-ORD-1-02",order_id="ORD-1",routing_id="ROUTE-SKU-0001-01",route_operation_id="ROUTEOP-2",sequence_no=2)]
    return {"operations":operations,"order_operations":order_operations,"operation_schedules":schedules,"production_orders":[dict(order_id="ORD-1",due_date="2026-01-10",order_date="2026-01-05",quantity=3)],"eligibility":[dict(route_operation_id=o["route_operation_id"],machine_id=m) for o,m in zip(operations,("MACH-001",second_machine))],"machine_calendars":calendars,"changeover_matrix":[dict(from_family="F1",to_family="F2",duration_minutes=20),dict(from_family="F1",to_family="F1",duration_minutes=0)],"material_requirements":[dict(operation_id="OP-ORD-1-02",material_id="MAT-0001",available_date=material_available,required_quantity=0)]}
