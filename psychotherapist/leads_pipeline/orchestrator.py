"""
Оркестратор мульти-агентной системы поиска лидов.
Запуск: python leads_pipeline/orchestrator.py
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
CONFIG_FILE = ROOT / "leads_pipeline" / "agents_group.json"
LOGS_DIR = ROOT / "leads_pipeline" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOGS_DIR / f"orchestrator_{datetime.now():%Y%m%d_%H%M%S}.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("orchestrator")


def load_config() -> dict:
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def merge_leads_files(file_path: Path) -> None:
    """Monitor и Forum Hunter пишут в один файл параллельно — мерджим без потерь."""
    tmp = file_path.with_suffix(".tmp.json")
    if not tmp.exists():
        return
    existing = json.loads(file_path.read_text(encoding="utf-8")) if file_path.exists() else []
    new_items = json.loads(tmp.read_text(encoding="utf-8"))
    seen_urls = {l.get("url") for l in existing}
    merged = existing + [l for l in new_items if l.get("url") not in seen_urls]
    file_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.unlink()


async def run_agent(agent_cfg: dict, config: dict) -> bool:
    agent_id = agent_cfg["id"]
    module_path = ROOT / agent_cfg["module"]
    log_file = LOGS_DIR / f"{agent_id}_{datetime.now():%Y%m%d_%H%M%S}.log"

    log.info(f"▶ Запуск: {agent_cfg['name']}")

    for attempt in range(1, agent_cfg.get("retry", 1) + 1):
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(module_path),
                "--config", str(CONFIG_FILE),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(ROOT),
            )
            timeout = agent_cfg.get("timeout_sec", 120)
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                log.error(f"  {agent_id}: timeout ({timeout}s), попытка {attempt}")
                continue

            with open(log_file, "ab") as f:
                f.write(stdout)

            if proc.returncode == 0:
                log.info(f"  ✅ {agent_cfg['name']} — успешно")
                return True
            else:
                log.warning(f"  ⚠ {agent_id} вернул код {proc.returncode}, попытка {attempt}")
        except Exception as e:
            log.error(f"  {agent_id} ошибка: {e}, попытка {attempt}")

        await asyncio.sleep(3)

    log.error(f"  ❌ {agent_cfg['name']} — все попытки исчерпаны")
    return False


async def run_pipeline():
    config = load_config()
    agents_by_id = {a["id"]: a for a in config["agents"]}
    results: dict[str, bool] = {}

    log.info("=" * 60)
    log.info(f"Запуск пайплайна: {config['group']}")
    log.info(f"Этапов: {len(config['pipeline_order'])}")
    log.info("=" * 60)

    for stage_idx, stage in enumerate(config["pipeline_order"], 1):
        log.info(f"\n--- Этап {stage_idx}: {stage} ---")

        # Пропускаем агентов, чьи зависимости провалились
        runnable = []
        for agent_id in stage:
            agent = agents_by_id[agent_id]
            deps = agent.get("depends_on", [])
            failed_deps = [d for d in deps if results.get(d) is False]
            if failed_deps:
                log.warning(f"  Пропуск {agent_id}: упали зависимости {failed_deps}")
                results[agent_id] = False
            else:
                runnable.append(agent)

        if not runnable:
            continue

        # Параллельный запуск агентов в этапе
        tasks = [run_agent(a, config) for a in runnable]
        stage_results = await asyncio.gather(*tasks, return_exceptions=True)

        for agent, result in zip(runnable, stage_results):
            results[agent["id"]] = result is True

        # Мердж raw_leads.json если нужно
        raw_leads = ROOT / "leads_pipeline" / "raw_leads.json"
        merge_leads_files(raw_leads)

    log.info("\n" + "=" * 60)
    log.info("ИТОГИ ПАЙПЛАЙНА:")
    for agent_id, ok in results.items():
        emoji = "✅" if ok else "❌"
        log.info(f"  {emoji} {agents_by_id[agent_id]['name']}")

    crm_file = ROOT / "leads_pipeline" / "ready_for_crm.json"
    if crm_file.exists():
        crm_data = json.loads(crm_file.read_text(encoding="utf-8"))
        log.info(f"\n🎯 Готовых лидов: {len(crm_data)}")
    log.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_pipeline())
