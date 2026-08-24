from __future__ import annotations
import json, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from .report import BacktestSummary, OptimizationResult

class HistoryStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True); self.path = path
        with self.connect() as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY,created_at TEXT,symbol TEXT,timeframe TEXT,expert TEXT,stage TEXT,status TEXT,details TEXT); CREATE TABLE IF NOT EXISTS results(id INTEGER PRIMARY KEY,run_id INTEGER,pass_no INTEGER,score REAL,profit REAL,trades INTEGER,profit_factor REAL,drawdown_pct REAL,inputs TEXT);""")
    def connect(self): return sqlite3.connect(self.path)
    def add_optimization(self, symbol, timeframe, expert, results: list[OptimizationResult]):
        with self.connect() as db:
            cur=db.execute("INSERT INTO runs(created_at,symbol,timeframe,expert,stage,status,details) VALUES(?,?,?,?,?,?,?)",(datetime.now(timezone.utc).isoformat(),symbol,timeframe,expert,"train","complete",json.dumps({"passes":len(results)})))
            rid=cur.lastrowid
            db.executemany("INSERT INTO results(run_id,pass_no,score,profit,trades,profit_factor,drawdown_pct,inputs) VALUES(?,?,?,?,?,?,?,?)",[(rid,r.pass_no,r.score,r.profit,r.trades,r.profit_factor,r.drawdown_pct,json.dumps(r.inputs,ensure_ascii=False)) for r in results[:20]])
            return rid
    def add_validation(self,symbol,timeframe,expert,stage,summary: BacktestSummary|None,status,details=None):
        payload=details or {}
        if summary: payload.update(profit=summary.profit,trades=summary.trades,profit_factor=summary.profit_factor,drawdown_pct=summary.drawdown_pct)
        with self.connect() as db:
            return db.execute("INSERT INTO runs(created_at,symbol,timeframe,expert,stage,status,details) VALUES(?,?,?,?,?,?,?)",(datetime.now(timezone.utc).isoformat(),symbol,timeframe,expert,stage,status,json.dumps(payload,ensure_ascii=False))).lastrowid
    def recent_runs(self,limit=50):
        with self.connect() as db: return db.execute("SELECT created_at,stage,status,symbol,timeframe,expert,details FROM runs ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
