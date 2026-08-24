from pathlib import Path
from ea_optimizer_lab.report import BacktestSummary, OptimizationResult
from ea_optimizer_lab.storage import HistoryStore

def test_history_stores_results(tmp_path: Path):
    store=HistoryStore(tmp_path/"history.db")
    store.add_optimization("XAUUSD","H1","ea.ex4",[OptimizationResult(1,100,30,1.5,10,{"FAST":"5"})])
    store.add_validation("XAUUSD","H1","ea.ex4","forward",BacktestSummary(50,20,1.3,12),"passed")
    assert [row[1] for row in store.recent_runs()]==["forward","train"]
