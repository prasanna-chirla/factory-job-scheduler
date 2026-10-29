# Data dictionary and relationships

Dates use ISO `YYYY-MM-DD`; plant timestamps use local ISO 8601. IDs are immutable. Empty effective-to fields mean open-ended. CSV files are UTF-8 with headers. Synthetic baseline statuses are uppercase enums.

## Master data

| File | Primary key and fields | Relationships and validation |
|---|---|---|
| `products.csv` | `product_id` (`PROD-2026-NNNNNN`), unique SKU, description, family F1-F4, lifecycle status | Product 1:N Routing. |
| `routings.csv` | `routing_id` (`ROUTE-<sku>-NN`), product FK, revision, effective dates, lifecycle status | Revision unique per product; effective start <= end; order route must belong to product. |
| `operations.csv` | `route_operation_id` (`ROUTEOP-NNNN-NN`), routing FK, sequence, operation name, process family, product family, run minutes/unit, setup minutes | Four templates per routing; unique sequence within routing; positive run and nonnegative setup. |
| `machines.csv` | `machine_id` (`MACH-NNN`), name, process family, units/shift capacity, lifecycle status | Process family must match eligible operation template. |
| `machine_calendars.csv` | `calendar_id`, machine FK, date, shift number, start/end, capacity minutes, availability, reason | Unique machine/date/shift; shift 1 or 2; 0-480 minutes; downtime capacity is zero. |
| `machine_eligibility.csv` | Composite key (`route_operation_id`,`machine_id`), effective dates | Operation-template N:M Machine bridge. |
| `labor_calendars.csv` | `labor_calendar_id`, skill, date, shift, start/end, workers available | Unique skill/date/shift; nonnegative headcount. |
| `labor_requirements.csv` | `labor_requirement_id`, operation-template FK, skill, required workers | Required workers > 0; each execution reserves the skill pool over its interval. |
| `materials.csv` | `material_id` (`MAT-NNNN`), name, unit, status | Unit must match lot and requirement records. |
| `changeover_matrix.csv` | `changeover_id`, directed from/to product-family pair, duration, effective dates | One effective directed pair; nonnegative duration; same family is zero. |
| `tools.csv` | `tool_id`, name, copies, status | Copies > 0. |
| `tool_requirements.csv` | `tool_requirement_id`, operation-template FK, tool FK, units required | Units > 0; tool use is reserved during the operation interval. |
| `tool_availability.csv` | `tool_availability_id`, tool FK, date, shift, available quantity | Unique tool/date/shift; quantity between zero and tool copy count. |

## Transactions

| File | Primary key and fields | Relationships and validation |
|---|---|---|
| `production_orders.csv` | `order_id` (`ORD-2026-NNNNNN`), product/routing FKs, quantity, order/due dates, priority, lifecycle status | Quantity > 0; order date <= due date; routing belongs to product. Baseline due windows vary by priority as documented in README. |
| `order_operations.csv` | `operation_id` (`OP-<order-id>-NN`), order/routing/template FKs, sequence, status | Four ordered steps per baseline order; template routing and sequence must agree. |
| `inventory_lots.csv` | `lot_id`, material FK, initial quantity, available-from timestamp, expiry timestamp, opening reserved/consumed/remaining quantities, status | Lot balance nonnegative; available-from <= expiry. |
| `material_requirements.csv` | `requirement_id`, order/order-operation/material FKs, quantity per unit, required quantity, unit, available date/time | Required = per-unit quantity x order quantity; unit agrees with Material. |
| `inventory_transactions.csv` | `transaction_id`, lot/material/order/operation/schedule references, event type, quantity, event time, allocation policy | Append-only `RESERVE`, `RELEASE`, or `CONSUME` events; FEFO is the reservation policy. |
| `machine_downtime.csv` | `downtime_id`, machine FK, start/end, reason | Positive interval. Planned downtime is also visible as zero-capacity calendar shifts. Unexpected downtime is appended as an event. |
| `reschedule_events.csv` | `event_id`, event type/time, affected entity, old/new value, affected count, status | Records requested breakdown or delivery-delay events and replan outcome. |

## Outputs

`operation_schedules.csv` uses `schedule_id` (`SCH-2026-NNNNNN`) and references one order operation, order, and machine. It stores sequence, start/end, quantity and setup/changeover/run minute components. Duration must reconcile; operations must fit machine, labor, and tool calendars, preserve precedence, have eligible materials reserved, and include the directed changeover.

`inventory_balances.csv` contains per-lot initial, reserved, consumed, and remaining quantities. Remaining = initial - reserved - consumed and cannot be negative. `schedule_change_events.csv` records replan deltas; `operation_schedules_before_replan.csv` preserves the prior schedule when replanning was requested.

`ground_truth/ground_truth.json` contains expected counterfactual labels and witnesses, isolated from scheduler inputs. `ground_truth_evaluation.json` records observed validator messages and per-case pass/fail. `infeasibility_report.json` lists unscheduled order operations, reason codes, detail JSON, next possible time if known, due-date feasibility, and whether the condition is proven under modeled inputs or is a search-limit/heuristic failure.
