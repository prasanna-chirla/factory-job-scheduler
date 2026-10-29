"""Command-line entry point for Yottaflex synthetic manufacturing scheduling."""
import argparse
from pathlib import Path
from src.generator import build_dataset

def main():
    parser=argparse.ArgumentParser(description="Generate reproducible synthetic production scheduling data")
    parser.add_argument("--out",default=".",help="project root for data/ output")
    parser.add_argument("--seed",type=int,default=20261022)
    parser.add_argument("--skus",type=int,default=100)
    parser.add_argument("--machines",type=int,default=40)
    parser.add_argument("--orders",type=int,default=500)
    parser.add_argument("--materials",type=int,default=200)
    parser.add_argument("--breakdown-machine",help="optional unplanned breakdown machine, e.g. MACH-001")
    parser.add_argument("--breakdown-start",help="optional local ISO timestamp, e.g. 2026-02-01T09:00:00")
    parser.add_argument("--breakdown-duration-minutes",type=int,default=120)
    parser.add_argument("--delay-material",help="optional material ID to delay, e.g. MAT-0001")
    parser.add_argument("--delay-until",help="optional delayed delivery local ISO timestamp")
    args=parser.parse_args()
    if bool(args.breakdown_machine)!=bool(args.breakdown_start): parser.error("--breakdown-machine and --breakdown-start must be supplied together")
    if bool(args.delay_material)!=bool(args.delay_until): parser.error("--delay-material and --delay-until must be supplied together")
    if args.breakdown_duration_minutes<=0: parser.error("--breakdown-duration-minutes must be positive")
    breakdown={"machine_id":args.breakdown_machine,"start_at":args.breakdown_start,"end_at":None,"reason":"UNPLANNED_BREAKDOWN"} if args.breakdown_machine else None
    if breakdown:
        from datetime import datetime, timedelta
        breakdown["end_at"]=(datetime.fromisoformat(breakdown["start_at"])+timedelta(minutes=args.breakdown_duration_minutes)).isoformat(timespec="seconds")
    delay={"material_id":args.delay_material,"delay_until":args.delay_until} if args.delay_material else None
    result=build_dataset(Path(args.out),args.seed,args.skus,args.machines,args.orders,args.materials,breakdown,delay)
    print(f"Validation: {result['validation']['status']}; outputs written beneath {Path(args.out).resolve() / 'data'}")
    if result["validation"]["status"]!="PASS": raise SystemExit(1)

if __name__=="__main__": main()
