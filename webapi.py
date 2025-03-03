from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import sqlite3
from typing import Final, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import logging
from pathlib import Path
import json
import uvicorn
from dotenv import load_dotenv
import os
from fastapi.responses import HTMLResponse, FileResponse
from fastapi import Request

load_dotenv()

security = HTTPBasic()

APP_TITLE: Final[str] = "Server Board API"
HOST: Final[str] = "localhost"
PORT: Final[int] = 8000

PATHS: Final[dict] = {
    "db": Path(__file__).parent / "data/server_board.db",
    "user_count": Path(__file__).parent / "data/user_count.json",
    "public": Path(__file__).parent / "public"
}

TIME_UNITS: Final[Dict[str, int]] = {
    "days": 24 * 60 * 60,
    "hours": 60 * 60,
    "minutes": 60,
    "seconds": 1
}

ERROR_MESSAGES: Final[dict] = {
    "db_not_found": "DBファイルが見つかりません: {}",
    "table_not_found": "サーバーテーブルが存在しません",
    "server_not_found": "サーバーが見つかりません",
    "user_count_not_found": "ユーザー数ファイルが見つかりません: {}",
    "db_error": "DBエラー: {}",
    "json_error": "JSONデコードエラー: {}",
    "unexpected": "予期せぬエラー: {}"
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s:     %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

class Server(BaseModel):
    """サーバー情報モデル"""

    server_id: int = Field(..., description="サーバーID")
    server_name: str = Field(..., description="サーバー名")
    icon_url: Optional[str] = Field(None, description="アイコンURL")
    description: Optional[str] = Field(None, description="説明")
    last_up_time: Optional[datetime] = Field(None, description="最終アップ時間")
    registered_at: datetime = Field(..., description="登録日時")
    invite_url: Optional[str] = Field(None, description="招待URL")
    time_since_last_up: Optional[str] = Field(None, description="最終アップからの経過時間")

class DatabaseManager:
    """DB操作を管理するクラス"""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            raise HTTPException(
                status_code=500,
                detail=ERROR_MESSAGES["db_not_found"].format(self.db_path)
            )

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def check_table_exists(self, conn: sqlite3.Connection) -> None:
        """テーブルの存在確認"""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='servers'"
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=500,
                detail=ERROR_MESSAGES["table_not_found"]
            )

    async def get_all_servers(self) -> List[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                self.check_table_exists(conn)
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT * FROM servers
                    ORDER BY
                        CASE WHEN last_up_time IS NULL THEN 0 ELSE 1 END DESC,
                        last_up_time DESC,
                        registered_at DESC
                """)
                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            logger.error("Database error: %s", e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=ERROR_MESSAGES["db_error"].format(str(e))
            ) from e

    async def get_server(self, server_id: int) -> Dict[str, Any]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM servers WHERE server_id = ?",
                    (server_id,)
                )
                if server := cursor.fetchone():
                    return dict(server)

                raise HTTPException(
                    status_code=404,
                    detail=ERROR_MESSAGES["server_not_found"]
                )

        except sqlite3.Error as e:
            logger.error("Database error: %s", e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=ERROR_MESSAGES["db_error"].format(str(e))
            ) from e

class TimeCalculator:
    """時間計算を行うクラス"""

    @staticmethod
    def calculate_time_ago(last_up: datetime) -> str:
        delta = datetime.now() - last_up

        if delta.days > 0:
            return f"{delta.days}日前"

        seconds = delta.seconds
        for unit, threshold in TIME_UNITS.items():
            if seconds >= threshold:
                value = seconds // threshold
                if unit == "days":
                    return f"{value}日前"
                elif unit == "hours":
                    return f"{value}時間前"
                elif unit == "minutes":
                    return f"{value}分前"
                else:
                    return f"{value}秒前"

        return "たった今"

class UserCountManager:
    """ユーザー数管理を行うクラス"""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    async def get_total_users(self) -> int:
        if not self.file_path.exists():
            raise HTTPException(
                status_code=500,
                detail=ERROR_MESSAGES["user_count_not_found"].format(
                    self.file_path
                )
            )

        try:
            data = json.loads(self.file_path.read_text(encoding="utf-8"))
            return data.get("total_users", 0)

        except json.JSONDecodeError as e:
            logger.error("JSON decode error: %s", e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=ERROR_MESSAGES["json_error"].format(str(e))
            ) from e

class ServerBoardAPI:
    """サーバーボードAPIを管理するクラス"""

    def __init__(self) -> None:
        self.app = FastAPI(title=APP_TITLE)
        self.db = DatabaseManager(PATHS["db"])
        self.user_count = UserCountManager(PATHS["user_count"])
        self.time_calc = TimeCalculator()
        self._setup_middleware()
        self._setup_routes()
        logger.info("Database path: %s", PATHS['db'])
        logger.info("User count file path: %s", PATHS['user_count'])
        logger.info("Public directory path: %s", PATHS['public'])

    def _setup_middleware(self) -> None:
        """ミドルウェアの設定"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )

    def _setup_routes(self) -> None:
        """ルーティングの設定"""
        self.app.get("/api/servers")(self.get_servers)
        self.app.get("/api/servers/{server_id}")(self.get_server)
        self.app.get("/api/users")(self.get_total_users)
        self.app.get("/admin/requests")(self.get_requests)
        self.app.delete("/admin/requests/{user_id}/{message}/{date}")(self.delete_request)
        self.app.mount(
            "/",
            StaticFiles(directory=PATHS["public"], html=True),
            name="static"
        )

    def _process_server_data(
        self,
        servers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        for server in servers:
            if last_up_str := server.get("last_up_time"):
                last_up = datetime.fromisoformat(last_up_str)
                server["time_since_last_up"] = self.time_calc.calculate_time_ago(
                    last_up
                )
            else:
                server["time_since_last_up"] = None
        return servers

    async def get_servers(self) -> List[Server]:
        """全サーバー情報を取得するエンドポイント"""
        try:
            servers = await self.db.get_all_servers()
            if not servers:
                return []

            processed_servers = self._process_server_data(servers)
            return [Server(**server) for server in processed_servers]

        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=ERROR_MESSAGES["unexpected"].format(str(e))
            ) from e

    async def get_server(self, server_id: int) -> Server:
        """
        指定したサーバーの情報を取得するエンドポイント

        Parameters
        ----------
        server_id : int
            サーバーID
        """
        try:
            server = await self.db.get_server(server_id)
            return Server(**server)

        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=ERROR_MESSAGES["unexpected"].format(str(e))
            ) from e

    async def get_total_users(self) -> Dict[str, int]:
        """総ユーザー数を取得するエンドポイント"""
        try:
            total = await self.user_count.get_total_users()
            return {"total_users": total}

        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=ERROR_MESSAGES["unexpected"].format(str(e))
            ) from e

    async def get_requests(self, credentials: HTTPBasicCredentials = Depends(security)) -> List[Dict[str, Any]]:
        """リクエスト内容を取得するエンドポイント"""
        try:
            conn = sqlite3.connect('data/request.db')
            conn.row_factory = sqlite3.Row  # Add this line to enable row as dictionary
            c = conn.cursor()
            c.execute("SELECT * FROM requests")
            requests = [dict(row) for row in c.fetchall()]
            conn.close()
            return requests

        except sqlite3.Error as e:
            logger.error("Database error: %s", e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=ERROR_MESSAGES["db_error"].format(str(e))
            ) from e

    async def delete_request(self, user_id: int, message: str, date: str, credentials: HTTPBasicCredentials = Depends(security)) -> Dict[str, str]:
        """リクエストを削除するエンドポイント"""
        self.basic_auth(credentials)
        try:
            conn = sqlite3.connect('data/request.db')
            c = conn.cursor()
            logger.info(f"Deleting request with user_id={user_id}, message={message}, date={date}")
            c.execute("DELETE FROM requests WHERE user_id = ? AND message = ? AND date = ?", (user_id, message, date))
            conn.commit()
            conn.close()
            return {"message": "リクエストが削除されました"}

        except sqlite3.Error as e:
            logger.error("Database error: %s", e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=ERROR_MESSAGES["db_error"].format(str(e))
            ) from e

    def basic_auth(self, credentials: HTTPBasicCredentials = Depends(security)) -> None:
        """Basic認証の検証"""
        correct_username = os.getenv("BASIC_AUTH_USERNAME")
        correct_password = os.getenv("BASIC_AUTH_PASSWORD")
        if credentials.username != correct_username or credentials.password != correct_password:
            raise HTTPException(
                status_code=401,
                detail="認証に失敗しました",
                headers={"WWW-Authenticate": "Basic"}
            )

# APIインスタンスの作成
api = ServerBoardAPI()
app = api.app

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
