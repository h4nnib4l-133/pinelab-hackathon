import json
import os
import sqlite3
from contextlib import asynccontextmanager

import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, model_validator

CSV_DIR = "data/csv"
MCP_TOOLS_PATH = "mcp_server.json"
DB_PATH = "alerts.db"


class AnalyticsRequest(BaseModel):
    file_name: str | None = None
    metric: str | None = None
    column: str | None = None
    function_code: str

    @model_validator(mode="after")
    def check_file_or_metric(self):
        if not self.file_name and not self.metric:
            raise ValueError("Either 'file_name' or 'metric' must be provided.")
        return self


class AnalyticsResponse(BaseModel):
    file_name: str
    result: dict
    error: str | None = None


class CreateAlertRequest(BaseModel):
    job_name: str
    schedule: str
    file_name: str
    function_code: str
    condition_code: str
    slack_channel: str | None = None


class CloseAlertResponse(BaseModel):
    job_name: str
    status: str


def list_csv_headers():
    headers_map = {}
    try:
        for fname in os.listdir(CSV_DIR):
            if fname.endswith(".csv"):
                path = os.path.join(CSV_DIR, fname)
                try:
                    cols = pd.read_csv(path, nrows=0).columns.tolist()
                    headers_map[fname.rsplit(".", 1)[0]] = cols
                except Exception:
                    headers_map[fname.rsplit(".", 1)[0]] = []
    except FileNotFoundError:
        pass
    return headers_map


def patch_mcp_tools_with_headers():
    headers_map = list_csv_headers()
    all_headers = sorted(set(h for cols in headers_map.values() for h in cols))

    if not os.path.exists(MCP_TOOLS_PATH):
        return

    with open(MCP_TOOLS_PATH, "r") as f:
        tools_data = json.load(f)

    for tool in tools_data.get("functions", []):
        if tool["name"] == "run_analysis":
            props = tool["parameters"]["properties"]
            if "column" in props:
                props["column"]["enum"] = all_headers

    with open(MCP_TOOLS_PATH, "w") as f:
        json.dump(tools_data, f, indent=2)


scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    patch_mcp_tools_with_headers()
    init_db()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            job_name TEXT PRIMARY KEY,
            schedule TEXT,
            file_name TEXT,
            function_code TEXT,
            condition_code TEXT,
            slack_channel TEXT
        )
    """
    )
    conn.commit()
    conn.close()


@app.post("/functions/run_analysis", response_model=AnalyticsResponse)
def run_analysis(req: AnalyticsRequest):
    if req.file_name:
        filename = req.file_name
    elif req.metric:
        headers_map = list_csv_headers()
        for fname, headers in headers_map.items():
            if any(req.metric.lower() in h.lower() for h in headers):
                filename = fname
                break
        else:
            raise HTTPException(404, "No CSV found matching the metric")
    else:
        raise HTTPException(400, "Missing file_name or metric")

    path = os.path.join(CSV_DIR, f"{filename}.csv")
    if not os.path.exists(path):
        raise HTTPException(404, "CSV file not found")

    try:
        df = pd.read_csv(path)
        local_env = {}
        exec(req.function_code, {"pd": pd}, local_env)
        if "analyze" not in local_env:
            raise ValueError("No `analyze(df)` function defined.")
        result = local_env["analyze"](df)
        return AnalyticsResponse(file_name=filename, result=result)
    except Exception as e:
        return AnalyticsResponse(file_name=filename, result={}, error=str(e))


@app.post("/functions/create_alert")
def create_alert(req: CreateAlertRequest):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            INSERT INTO alerts (job_name, schedule, file_name, function_code, condition_code, slack_channel)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                req.job_name,
                req.schedule,
                req.file_name,
                req.function_code,
                req.condition_code,
                req.slack_channel,
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Alert with this job_name already exists")
    finally:
        conn.close()

    cron_parts = req.schedule.split()
    if len(cron_parts) != 5:
        raise HTTPException(400, "Invalid cron format")

    scheduler.add_job(
        run_alert_job,
        CronTrigger.from_crontab(req.schedule),
        id=req.job_name,
        args=[req.job_name],
        replace_existing=True,
    )

    return {"status": "scheduled", "job_name": req.job_name}


@app.delete("/functions/close_alert/{job_name}", response_model=CloseAlertResponse)
def close_alert(job_name: str):
    try:
        scheduler.remove_job(job_name)
    except Exception:
        raise HTTPException(404, "Job not found")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("DELETE FROM alerts WHERE job_name = ?", (job_name,))
    conn.commit()
    conn.close()

    if cur.rowcount == 0:
        raise HTTPException(404, "Alert not found in DB")

    return CloseAlertResponse(job_name=job_name, status="closed")


def run_alert_job(job_name: str):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT file_name, function_code, condition_code FROM alerts WHERE job_name = ?",
        (job_name,),
    ).fetchone()
    conn.close()

    if not row:
        return

    file_name, func_code, cond_code = row
    path = os.path.join(CSV_DIR, f"{file_name}.csv")
    if not os.path.exists(path):
        return

    try:
        df = pd.read_csv(path)
        local_env = {}
        exec(func_code, {"pd": pd}, local_env)
        result = local_env["analyze"](df)
        if eval(cond_code, {}, {"result": result}):
            print(f"[ALERT] {job_name} triggered: {result}")
    except Exception as e:
        print(f"[ERROR] Alert {job_name} failed: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("MCPTools:app", host="0.0.0.0", port=8000, reload=True)
