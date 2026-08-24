from __future__ import annotations

from .core import SetParameter


def stability_neighbours(parameters: list[SetParameter], best: dict[str, str]) -> list[tuple[str, list[SetParameter]]]:
    """One-factor neighbours around the best point: current-step/current+step."""
    jobs: list[tuple[str, list[SetParameter]]] = []
    for changed in parameters:
        if not changed.optimize or not changed.step:
            continue
        try:
            center, step = float(best.get(changed.name, changed.value)), float(changed.step)
        except ValueError:
            continue
        if step <= 0:
            continue
        for direction in (-1, 1):
            value = center + direction * step
            try:
                if changed.start and value < float(changed.start): continue
                if changed.stop and value > float(changed.stop): continue
            except ValueError:
                continue
            rendered = str(int(value)) if value.is_integer() else f"{value:.10g}"
            variant = [SetParameter(item.name, rendered if item.name == changed.name else best.get(item.name, item.value))
                       for item in parameters]
            jobs.append((f"{changed.name}={'-' if direction < 0 else '+'}{changed.step}", variant))
    return jobs
