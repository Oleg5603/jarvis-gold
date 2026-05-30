"""
Оркестратор AI-команды прогрева лидов (РОП).
Запуск: python warming_pipeline/orchestrator.py
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
CONFIG_FILE = ROOT / "warming_pipeline" / "agents_group.json"
LOGS_DIR = ROOT / "warming_pipeline" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOGS_DIR / f"warming_{datetime.now():%Y%m%d_%H%M%S}.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("warming_rop")


def load_config() -> dict:
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


async def run_agent(agent_cfg: dict) -> bool:
    agent_id = agent_cfg["id"]
    module_path = ROOT / agent_cfg["module"]
    log_file = LOGS_DIR / f"{agent_id}_{datetime.now():%Y%m%d_%H%M%S}.log"

    log.info(f"▶ {agent_cfg['name']}")

    for attempt in range(1, agent_cfg.get("retry", 1) + 1):
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(module_path),
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
                log.info(f"  ✅ {agent_cfg['name']} — готово")
                return True
            else:
                log.warning(f"  ⚠ {agent_id} код {proc.returncode}, попытка {attempt}")
        except Exception as e:
            log.error(f"  {agent_id} ошибка: {e}, попытка {attempt}")

        await asyncio.sleep(2)

    log.error(f"  ❌ {agent_cfg['name']} — все попытки исчерпаны")
    return False


async def run_warming():
    config = load_config()
    agents_by_id = {a["id"]: a for a in config["agents"]}
    results: dict[str, bool] = {}

    # Проверяем наличие лидов на входе
    input_file = ROOT / config["files"]["input"]
    if not input_file.exists():
        log.error(f"Нет файла лидов: {input_file}")
        log.error("Сначала запустите: python leads_pipeline/orchestrator.py")
        sys.exit(1)

    leads = json.loads(input_file.read_text(encoding="utf-8"))
    if not leads:
        log.warning("ready_for_crm.json пуст — нечего прогревать")
        sys.exit(0)

    log.info("=" * 60)
    log.info(f"AI-команда прогрева: {config['group']}")
    log.info(f"Лидов на входе: {len(leads)}")
    log.info(f"Агентов в команде: {len(config['agents'])}")
    log.info("=" * 60)

    for stage_idx, stage in enumerate(config["pipeline_order"], 1):
        log.info(f"\n--- Этап {stage_idx}: {stage} ---")

        runnable = []
        for agent_id in stage:
            agent = agents_by_id[agent_id]
            failed_deps = [d for d in agent.get("depends_on", []) if results.get(d) is False]
            if failed_deps:
                log.warning(f"  Пропуск {agent_id}: упали зависимости {failed_deps}")
                results[agent_id] = False
            else:
                runnable.append(agent)

        if not runnable:
            continue

        tasks = [run_agent(a) for a in runnable]
        stage_results = await asyncio.gather(*tasks, return_exceptions=True)

        for agent, result in zip(runnable, stage_results):
            results[agent["id"]] = result is True

    log.info("\n" + "=" * 60)
    log.info("ИТОГИ КОМАНДЫ:")
    for agent_id, ok in results.items():
        emoji = "✅" if ok else "❌"
        log.info(f"  {emoji} {agents_by_id[agent_id]['name']}")

    report_file = ROOT / config["files"]["report"]
    if report_file.exists():
        try:
            report = json.loads(report_file.read_text(encoding="utf-8"))
            log.info(f"\n🎯 Готово к отправке: {report.get('ready_to_send', 0)} лидов")
            log.info(f"📋 Скриптов написано: {report.get('scripts_written', 0)}")
            log.info(f"📅 Последовательностей: {report.get('sequences_built', 0)}")
        except Exception:
            pass
    log.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_warming())
