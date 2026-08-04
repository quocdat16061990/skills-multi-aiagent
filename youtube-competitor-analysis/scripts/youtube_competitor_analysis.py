#!/usr/bin/env python3
"""CLI orchestration; emits exactly one JSON object to stdout."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from datetime import datetime, timezone

from youtube_collector import collect_channel
from metrics import analyze
from content_classifier import classify_all, load_config
from excel_report import write_report


def parser():
    p=argparse.ArgumentParser(description="Phân tích dữ liệu YouTube công khai và xuất Excel")
    p.add_argument("url")
    p.add_argument("--limit",type=int,default=50,choices=range(1,101),metavar="1-100")
    p.add_argument("--output-dir",default="./output")
    p.add_argument("--dry-run",action="store_true")
    p.add_argument("--config")
    return p


def run(args):
    cfg=load_config(args.config)
    collected=collect_channel(args.url,args.limit)
    rows=classify_all(collected["videos"],cfg)
    stats=analyze(rows)
    warnings=list(collected.get("warnings",[]))
    result={"status":"ok","source":collected.get("source"),"counts":{"videos":len(rows),"shorts":sum(r["type"]=="short" for r in rows),"long_form":sum(r["type"]=="long-form" for r in rows)},"warnings":warnings,"output":None}
    if args.dry_run:
        result["dry_run"]=True; result["preview"]={"channel":collected["channel"],"metrics":stats}
        return result
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path=out/f"youtube_competitor_analysis_{stamp}.xlsx"
    write_report(path,collected["channel"],rows,stats,cfg,collected)
    result["output"]=str(path.resolve())
    return result


def main(argv=None):
    try:
        print(json.dumps(run(parser().parse_args(argv)),ensure_ascii=False,default=str))
        return 0
    except Exception as e:
        print(json.dumps({"status":"error","error":type(e).__name__,"message":str(e)},ensure_ascii=False))
        return 1
if __name__=="__main__": raise SystemExit(main())
