# Yottaflex synthetic manufacturing scheduler

This project creates connected synthetic factory data, produces a draft production schedule, checks hard constraints, evaluates five labelled negative cases, and reports metrics. It uses no external, personal, or confidential data.

## Project layout

```text
yottaflex-manufacturing/
|-- data/
|   |-- master/
|   |   |-- products.csv
|   |   |-- routings.csv
|   |   |-- operations.csv
|   |   |-- machines.csv
|   |   |-- machine_calendars.csv
|   |   |-- machine_eligibility.csv
|   |   |-- labor_calendars.csv
|   |   |-- labor_requirements.csv
|   |   |-- materials.csv
|   |   |-- changeover_matrix.csv
|   |   |-- tools.csv
|   |   |-- tool_requirements.csv
|   |   `-- tool_availability.csv
|   |-- transactions/
|   |   |-- production_orders.csv
|   |   |-- order_operations.csv
|   |   |-- inventory_lots.csv
|   |   |-- material_requirements.csv
|   |   |-- inventory_transactions.csv
|   |   |-- machine_downtime.csv
|   |   `-- reschedule_events.csv
|   |-- output/
|   |   |-- operation_schedules.csv
|   |   |-- inventory_balances.csv
|   |   |-- unscheduled_operations.csv
|   |   |-- validation_report.json
|   |   |-- infeasibility_report.json
|   |   |-- ground_truth_evaluation.json
|   |   |-- metrics.json
|   |   |-- source_manifest.json
|   |   `-- schedule_seed.sql
|   `-- ground_truth/
|       |-- ground_truth.csv
|       `-- ground_truth.json
|-- src/
|   |-- generator.py
|   |-- schemas.py
|   |-- data_validator.py
|   |-- scheduler.py
|   |-- schedule_validator.py
|   |-- inventory.py
|   |-- resources.py
|   |-- ground_truth.py
|   |-- rescheduler.py
|   |-- metrics.py
|   |-- reproducibility.py
|   `-- sql_export.py
|-- tests/
|   |-- test_data_integrity.py
|   |-- test_machine_overlap.py
|   |-- test_precedence.py
|   |-- test_material_availability.py
|   |-- test_machine_calendar.py
|   |-- test_changeover.py
|   |-- test_inventory_allocation.py
|   |-- test_resource_capacity.py
|   |-- test_ground_truth_evaluation.py
|   |-- test_infeasibility_reporting.py
|   |-- test_rescheduling.py
|   `-- test_reproducibility.py
|-- docs/data_dictionary.md
|-- requirements.txt
`-- main.py
```

## Run

Requires Python 3.10 or newer. The project uses only Python's standard library, so it has no third-party runtime dependencies.

### Run with `uv`

If `uv` is not installed, install it by following the [official uv installation instructions](https://docs.astral.sh/uv/getting-started/installation/). From the project folder, run:

```powershell
uv run main.py --out .
uv run python -m unittest discover -s tests -v
```

### Run with standard Python

You can also use a regular Python installation without `uv`:

```powershell
python main.py --out .
python -m unittest discover -s tests -v
```

Defaults: seed `20261022`, 100 SKUs, 40 machines, 500 orders, 200 materials, 400 reusable routing-operation templates, and 2,000 order-operation instances/schedules. A smaller run is:

Each run removes previous generated files from `data/master/`, `data/transactions/`, `data/output/`, and `data/ground_truth/` before writing the new dataset. It keeps `.gitkeep` placeholders and the project source files. Store any files you want to preserve outside these generated-data folders.

```powershell
uv run main.py --out . --skus 8 --machines 8 --orders 20 --materials 16 --seed 20261022
```

## Example successful result

The following is from an actual run using seed `123`:

```powershell
uv run main.py --out . --seed 123
```

```text
Validation: PASS; outputs written beneath <project-folder>\data
```

That run generated **500 production orders** and **2,000 operation schedules**. All 500 orders were fully scheduled, with **0 unscheduled operations**, and the validation report status was **PASS**. The output reports are saved in `data/output/`; review `validation_report.json` for checks, `operation_schedules.csv` for scheduled operations, and `metrics.json` for summary metrics. The exact output folder path depends on where you keep the project.

## Constraints and policies

- A product has an effective-dated routing with four ordered operation templates. Each order creates four immutable `OP-<order-id>-NN` order operations.
- Machine eligibility is an explicit many-to-many bridge. Operations require a process-family-compatible machine. Product family drives the sequence-dependent changeover matrix.
- Machine calendars have two 480-minute shifts Monday through Saturday, with planned downtime. An operation must fit wholly in one available shift.
- Labor is pooled by skill and shift; each operation reserves its required headcount over its full interval. Shared tools have limited copies and per-shift availability; overlapping bookings cannot exceed either resource's capacity.
- Baseline labor pools have six operators and two quality inspectors per shift. The shared milling jig has four copies; the calibration gauge has two.
- The scheduler allocates material from available inventory lots using earliest-expiring-first (FEFO). It reserves lot quantities at schedule creation, records reserve/release events, and calculates remaining balances. Demand cannot drive a lot below zero.
- Released orders are scheduled by urgent priority, due date, then ID. The deterministic greedy scheduler is explainable but does not promise a globally optimal schedule.
- Due-date windows vary by priority: urgent 3-14 days, high 14-35, normal 25-55, and low 40-75 days after order creation.
- `PROVEN_INFEASIBLE` is reserved for hard bounds represented in the input, such as no eligible machine, an operation too long for any shift, insufficient total stock, or insufficient maximum resource capacity. `SEARCH_LIMIT_OR_HEURISTIC_FAILURE` means the greedy search did not find a slot within its horizon; that is not a proof of global infeasibility.

## Disruption and replanning example

The optional flags record an unexpected breakdown and/or delayed delivery, preserve the prior schedule, release its inventory reservations, replan from the updated event state, and write schedule changes:

```powershell
uv run main.py --out . --breakdown-machine MACH-001 --breakdown-start 2026-01-06T09:00:00 --breakdown-duration-minutes 120
uv run main.py --out . --delay-material MAT-0001 --delay-until 2026-01-20T06:00:00
```

The original schedule is saved as `operation_schedules_before_replan.csv`; event and schedule deltas are recorded in `reschedule_events.csv` and `schedule_change_events.csv`. Replanning reruns the whole deterministic schedule against the changed inputs, rather than only shifting the directly affected operation.

## Validation and evaluation

`validation_report.json` reports key integrity and baseline hard-constraint results. `ground_truth/ground_truth.json` contains the separate expected labels and counterfactual witnesses; `ground_truth_evaluation.json` records the validator's observed detections and whether each matched. The five cases cover machine overlap, precedence, material availability, shift calendar, and omitted changeover. A case that cannot be constructed from a small dataset is marked `NOT_APPLICABLE` and counted as skipped; it does not make an otherwise valid schedule fail. The evaluation status is `PASS_WITH_SKIPS` when all applicable cases pass but one or more cases could not be constructed.

`infeasibility_report.json` lists unscheduled operations, reason codes, next-time/search details, and whether due-date feasibility is known. `metrics.json` derives makespan and lateness from schedule records. `source_manifest.json` records deterministic input counts and hashes; regenerate twice with the same configuration and seed to compare its `counts` and `files` values.

See [docs/data_dictionary.md](docs/data_dictionary.md) for field definitions, keys, relationships, and validation rules.
