import sys
from pathlib import Path
from ea_optimizer_lab.auto_runner import run_auto_job

job = Path(sys.argv[1])
if job.is_file():
    run_auto_job(job)
