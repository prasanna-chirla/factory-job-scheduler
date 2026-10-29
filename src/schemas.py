"""Column definitions and CSV output helpers for the synthetic plant dataset."""
from __future__ import annotations
import csv
from pathlib import Path

TABLES = {
    "products": ["product_id", "sku", "description", "family", "status"],
    "routings": ["routing_id", "product_id", "revision", "effective_from", "effective_to", "status"],
    "operations": ["route_operation_id", "routing_id", "sequence_no", "name", "process_family", "product_family", "run_minutes_per_unit", "setup_minutes"],
    "machines": ["machine_id", "name", "process_family", "capacity_units_per_shift", "status"],
    "machine_calendars": ["calendar_id", "machine_id", "shift_date", "shift_no", "start_at", "end_at", "capacity_minutes", "availability", "reason"],
    "materials": ["material_id", "name", "unit", "status"],
    "changeover_matrix": ["changeover_id", "from_family", "to_family", "duration_minutes", "effective_from", "effective_to"],
    "machine_eligibility": ["route_operation_id", "machine_id", "effective_from", "effective_to"],
    "labor_calendars": ["labor_calendar_id", "skill", "shift_date", "shift_no", "start_at", "end_at", "workers_available"],
    "labor_requirements": ["labor_requirement_id", "route_operation_id", "skill", "workers_required"],
    "tools": ["tool_id", "name", "copies", "status"],
    "tool_requirements": ["tool_requirement_id", "route_operation_id", "tool_id", "units_required"],
    "tool_availability": ["tool_availability_id", "tool_id", "shift_date", "shift_no", "available_quantity"],
    "reschedule_events": ["event_id", "event_type", "event_at", "entity_type", "entity_id", "old_value", "new_value", "affected_operation_count", "status"],
    "production_orders": ["order_id", "product_id", "routing_id", "quantity", "order_date", "due_date", "priority", "status"],
    "order_operations": ["operation_id", "order_id", "routing_id", "route_operation_id", "sequence_no", "status"],
    "inventory_lots": ["lot_id", "material_id", "initial_quantity", "available_from", "expiry_at", "reserved_quantity", "consumed_quantity", "remaining_quantity", "status"],
    "material_requirements": ["requirement_id", "order_id", "operation_id", "material_id", "quantity_per_unit", "required_quantity", "unit", "available_date", "available_at"],
    "inventory_transactions": ["transaction_id", "lot_id", "material_id", "order_id", "operation_id", "schedule_id", "event_type", "quantity", "event_at", "allocation_policy"],
    "machine_downtime": ["downtime_id", "machine_id", "start_at", "end_at", "reason"],
    "operation_schedules": ["schedule_id", "order_id", "operation_id", "machine_id", "sequence_no", "start_at", "end_at", "quantity", "setup_minutes", "changeover_minutes", "run_minutes", "status"],
    "unscheduled_operations": ["order_id", "operation_id", "reason_codes", "classification", "next_possible_time", "can_meet_due_date", "details_json"],
    "schedule_change_events": ["event_id", "schedule_id", "event_type", "old_machine_id", "new_machine_id", "old_start_at", "new_start_at", "reason"],
    "ground_truth_evaluation": ["scenario_id", "issue_type", "detected_violation", "detected_constraint", "test_passed", "messages_json"],
}

def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    fields = fields or (list(rows[0]) if rows else [])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
