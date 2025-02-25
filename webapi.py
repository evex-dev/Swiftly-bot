from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import sqlite3
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import os
import json

app = FastAPI(title="Server Board API")

# データベースファイルのパスを絶対パスで設定
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_board.db")
USER_COUNT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_count.json")

# CORSミドルウェアの設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Server(BaseModel):
    server_id: int
    server_name: str
    icon_url: Optional[str] = None
    description: Optional[str] = None
    last_up_time: Optional[datetime] = None
    registered_at: datetime
    invite_url: Optional[str] = None
    time_since_last_up: Optional[str] = None  # 最後のupからの経過時間を文字列で保持


@app.get("/api/servers", response_model=List[Server])
async def get_servers():
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=500, detail=f"Database file not found at {DB_PATH}")

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='servers'")
            if not cursor.fetchone():
                raise HTTPException(status_code=500, detail="Servers table does not exist")

            cursor.execute("""
                SELECT * FROM servers
                ORDER BY
                    CASE WHEN last_up_time IS NULL THEN 0 ELSE 1 END DESC,
                    last_up_time DESC,
                    registered_at DESC
            """)
            servers = cursor.fetchall()

            if not servers:
                return []

            current_time = datetime.now()
            result = []

            for server in servers:
                server_dict = dict(server)
                if server_dict["last_up_time"]:
                    last_up = datetime.fromisoformat(
                        server_dict["last_up_time"])
                    delta = current_time - last_up

                    if delta.days > 0:
                        time_str = f"{delta.days}日前"
                    elif delta.seconds >= 3600:
                        hours = delta.seconds // 3600
                        time_str = f"{hours}時間前"
                    elif delta.seconds >= 60:
                        minutes = delta.seconds // 60
                        time_str = f"{minutes}分前"
                    else:
                        time_str = f"{delta.seconds}秒前"

                    server_dict["time_since_last_up"] = time_str
                else:
                    server_dict["time_since_last_up"] = None

                result.append(server_dict)

            return result

    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}") from e


@app.get("/api/servers/{server_id}", response_model=Server)
async def get_server(server_id: int):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM servers WHERE server_id = ?", (server_id,))
            server = cursor.fetchone()

            if server is None:
                raise HTTPException(status_code=404, detail="Server not found")

            return dict(server)
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}") from e


@app.get("/api/users")
async def get_total_users():
    if not os.path.exists(USER_COUNT_PATH):
        raise HTTPException(status_code=500, detail=f"User count file not found at {USER_COUNT_PATH}")

    try:
        with open(USER_COUNT_PATH, "r", encoding="utf-8") as file:
            data = json.load(file)
            return {"total_users": data.get("total_users", 0)}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Error reading user count file: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}") from e

# 静的ファイルの設定（APIエンドポイントの後に配置）
app.mount("/", StaticFiles(directory="public", html=True), name="static")

if __name__ == "__main__":
    print(f"Database path: {DB_PATH}")
    print(f"Database exists: {os.path.exists(DB_PATH)}")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
