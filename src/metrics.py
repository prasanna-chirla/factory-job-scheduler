"""Derived schedule and service metrics."""
from datetime import date, datetime

def calculate_metrics(orders, schedules):
    by_order={}
    for row in schedules: by_order.setdefault(row["order_id"],[]).append(row)
    completion={k:max(datetime.fromisoformat(x["end_at"]) for x in v) for k,v in by_order.items() if sorted(int(x["sequence_no"]) for x in v)==[1,2,3,4]}
    starts=[datetime.fromisoformat(x["start_at"]) for x in schedules]; ends=[datetime.fromisoformat(x["end_at"]) for x in schedules]
    late=[o for o in orders if o["order_id"] in completion and completion[o["order_id"]].date()>date.fromisoformat(o["due_date"])]
    late_days=sum(max(0,(completion[o["order_id"]].date()-date.fromisoformat(o["due_date"])).days) for o in late)
    scheduled_orders=len(completion)
    return {"order_count":len(orders),"fully_scheduled_order_count":scheduled_orders,"unscheduled_order_count":len(orders)-scheduled_orders,"scheduled_operation_count":len(schedules),"makespan_hours":round((max(ends)-min(starts)).total_seconds()/3600,2) if starts else 0,"late_order_count":len(late),"total_late_days":late_days,"on_time_rate":round((scheduled_orders-len(late))/scheduled_orders,4) if scheduled_orders else 0.0}
