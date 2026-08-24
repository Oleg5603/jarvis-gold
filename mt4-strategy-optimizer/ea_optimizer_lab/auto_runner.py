from __future__ import annotations
import json, subprocess, time
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from .core import SetParameter, build_mt4_config, safe_export
from .report import parse_backtest_report, parse_optimization_report
from .validation import stability_neighbours

def _launch(terminal: Path, config: Path, timeout: int) -> None:
    args=[str(terminal)]
    if (terminal.parent/"EA_OPTIMIZER_TEST_TERMINAL.txt").exists(): args.append("/portable")
    args.append(str(config.resolve()))
    process=subprocess.Popen(args,cwd=str(terminal.parent))
    process.wait(timeout=timeout)

def _status(path: Path, stage: str, state: str, **details) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({"updated_at":time.time(),"stage":stage,"state":state,**details},ensure_ascii=False,indent=2),encoding="utf-8")

def run_auto_job(job_path: Path) -> None:
    job=json.loads(job_path.read_text(encoding="utf-8")); status=Path(job["status"])
    terminal=Path(job["terminal"]); run_dir=job_path.parent/"auto"; run_dir.mkdir(parents=True,exist_ok=True)
    params=[SetParameter(**item) for item in job["parameters"]]; comments=job["comments"]
    started,finished=date.fromisoformat(job["date_from"]),date.fromisoformat(job["date_to"])
    split=started+(finished-started)*7//10; data_dir=terminal.parent
    try:
        _status(status,"train","running")
        _launch(terminal,Path(job["train_config"]),job.get("timeout",21600))
        results=parse_optimization_report(Path(job["train_report"])); best=results[0]
        forward_set=data_dir/"tester"/"EA_Auto_Forward.set"
        best_params=[SetParameter(p.name,best.inputs.get(p.name,p.value)) for p in params]
        safe_export(Path(job["source_set"]),forward_set,comments,best_params)
        forward_report,forward_config=terminal.parent/"auto-forward.htm",run_dir/"forward.ini"
        build_mt4_config(forward_config,expert_name=job["expert_name"],preset_name=forward_set.name,
                         symbol=job["symbol"],timeframe=job["timeframe"],model=job["model"],spread=job["spread"],deposit=job["deposit"],
                         date_from=split+timedelta(days=1),date_to=finished,optimize=False,report=forward_report)
        _status(status,"forward","running",best_pass=best.pass_no)
        _launch(terminal,forward_config,job.get("timeout",21600)); forward=parse_backtest_report(forward_report)
        if not forward.passed:
            _status(status,"forward","failed",profit=forward.profit,pf=forward.profit_factor,dd=forward.drawdown_pct); return
        neighbours=stability_neighbours(params,best.inputs); passed=0
        for index,(label,variant) in enumerate(neighbours,1):
            preset=data_dir/"tester"/f"EA_Auto_Stability_{index}.set"; report=terminal.parent/f"auto-stability-{index}.htm"; config=run_dir/f"stability-{index}.ini"
            safe_export(Path(job["source_set"]),preset,comments,variant)
            build_mt4_config(config,expert_name=job["expert_name"],preset_name=preset.name,symbol=job["symbol"],timeframe=job["timeframe"],
                             model=job["model"],spread=job["spread"],deposit=job["deposit"],date_from=split+timedelta(days=1),date_to=finished,optimize=False,report=report)
            _status(status,"stability","running",current=index,total=len(neighbours),variant=label)
            _launch(terminal,config,job.get("timeout",21600))
            passed+=int(parse_backtest_report(report).passed)
        ratio=passed/len(neighbours) if neighbours else 0
        _status(status,"complete","passed" if ratio>=.7 else "failed",best_pass=best.pass_no,forward=asdict(forward),stability_passed=passed,stability_total=len(neighbours))
    except Exception as exc:
        _status(status,"error","failed",error=str(exc))
