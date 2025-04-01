from datetime import datetime
import io
from typing import Final, List, Tuple
import logging

import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.arima.model import ARIMA
import discord
from discord.ext import commands


POSSIBLE_ORDERS: Final[List[Tuple[int, int, int]]] = [
    (0, 1, 0), (1, 1, 0), (1, 1, 1), (2, 1, 0)
]
FORECAST_DAYS: Final[int] = 365
GRAPH_SIZE: Final[Tuple[int, int]] = (8, 5)
ERROR_MESSAGES: Final[dict] = {
    "insufficient_data": "回帰分析を行うためのデータが不足しています。",
    "no_target_reach": "予測範囲内でその目標値に到達しません。",
    "general_error": "エラーが発生しました: {}"
}
FOOTER_TEXT: Final[str] = "この予測は統計モデルに基づくものであり、実際の結果を保証するものではありません。この機能はベータバージョンです。"

logger = logging.getLogger(__name__)

class ARIMAGrowth(commands.Cog):
    """ARIMAモデルサーバー成長予測"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _get_join_dates(self, guild: discord.Guild) -> List[datetime]:
        """メンバーの参加日時を取得して並べ替え"""
        join_dates = [m.joined_at for m in guild.members if m.joined_at]
        join_dates.sort()
        return join_dates

    async def _find_best_arima_order(
        self,
        data: np.ndarray,
        possible_orders: List[Tuple[int, int, int]] = POSSIBLE_ORDERS
    ) -> Tuple[Tuple[int, int, int], float]:
        """最適なARIMAモデルのパラメータを見つける"""
        best_order = possible_orders[0]  # デフォルト値を設定
        best_aic = float("inf")

        for order in possible_orders:
            try:
                temp_model = ARIMA(data, order=order)
                temp_fit = temp_model.fit()
                if temp_fit.aic < best_aic:
                    best_aic = temp_fit.aic
                    best_order = order
            except Exception as e:
                logger.warning("Failed to fit ARIMA model with order %s: %s", order, e)
                continue

        return best_order, best_aic

    async def _create_prediction_graph(
        self,
        join_dates: List[datetime],
        y: np.ndarray,
        predictions: np.ndarray,
        target: int,
        found_date: datetime
    ) -> io.BytesIO:
        """予測グラフを生成"""
        plt.figure(figsize=GRAPH_SIZE)

        # 実データのプロット
        plt.scatter(join_dates, y, color="blue", label="Actual Data", alpha=0.6)

        # 予測データのプロット
        pred_dates = [
            datetime.fromordinal(int(join_dates[-1].toordinal() + i))
            for i in range(len(predictions))
        ]
        plt.plot(pred_dates, predictions, color="red", label="Prediction", linewidth=2)

        # 目標値と予測日のライン
        plt.axhline(
            y=target,
            color="green",
            linestyle="--",
            label=f"Target: {target}",
            linewidth=2
        )
        plt.axvline(
            x=found_date,
            color="purple",
            linestyle="--",
            label=f"Predicted: {found_date.date()}",
            linewidth=2
        )

        # グラフの設定
        plt.xlabel("Join Date")
        plt.ylabel("Member Count")
        plt.title("Server Growth Prediction (ARIMA)")
        plt.legend()
        plt.grid(True, linestyle="--", alpha=0.7)

        # グラフをバイトデータとして保存
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        buf.seek(0)
        plt.close()

        return buf

    async def _create_response_embed(
        self,
        target: int,
        found_date: datetime,
        join_dates: List[datetime],
        best_order: Tuple[int, int, int],
        model_aic: float
    ) -> discord.Embed:
        """レスポンス用のEmbedを作成"""
        embed = discord.Embed(
            title="Server Growth Prediction (ARIMA)",
            description=f"{target}人に達する予測日: {found_date.date()}",
            color=discord.Color.blue()
        )

        # フィールドの追加
        fields = {
            "データポイント数": str(len(join_dates)),
            "最適パラメータ": str(best_order),
            "AIC": f"{model_aic:.2f}",
            "最初の参加日": join_dates[0].strftime("%Y-%m-%d"),
            "最新の参加日": join_dates[-1].strftime("%Y-%m-%d"),
            "予測モデル": "ARIMA"
        }

        for name, value in fields.items():
            embed.add_field(name=name, value=value, inline=True)

        embed.set_footer(text=FOOTER_TEXT)
        return embed

    @discord.app_commands.command(
        name="arima_growth",
        description="サーバーの成長をARIMAモデルで予測します。"
    )
    async def arima_growth(
        self,
        interaction: discord.Interaction,
        target: int,
        show_graph: bool = True
    ) -> None:
        """
        ARIMAモデルを使用してサーバーの成長を予測

        Parameters
        ----------
        interaction : discord.Interaction
            インタラクションコンテキスト
        target : int
            目標メンバー数
        show_graph : bool, optional
            グラフを表示するかどうか, by default True
        """
        try:
            await interaction.response.defer(thinking=True)

            # メンバーの参加日時を取得
            join_dates = await self._get_join_dates(interaction.guild)
            if len(join_dates) < 2:
                await interaction.followup.send(ERROR_MESSAGES["insufficient_data"])
                return

            # データの準備
            X = np.array([d.toordinal() for d in join_dates]).reshape(-1, 1)
            y = np.arange(1, len(join_dates) + 1)

            # 最適なARIMAパラメータを見つける best_aic
            best_order, _ = await self._find_best_arima_order(y)

            # ARIMAモデルのフィッティングと予測
            model = ARIMA(y, order=best_order)
            model_fit = model.fit()
            predictions = model_fit.forecast(steps=FORECAST_DAYS)

            # 目標達成日を見つける
            found_date = None
            for i, pred in enumerate(predictions):
                if pred >= target:
                    found_date = datetime.fromordinal(int(X[-1][0] + i))
                    break

            if not found_date:
                await interaction.followup.send(ERROR_MESSAGES["no_target_reach"])
                return

            # レスポンスの作成
            embed = await self._create_response_embed(
                target, found_date, join_dates, best_order, model_fit.aic
            )

            if show_graph:
                # グラフの生成
                buf = await self._create_prediction_graph(
                    join_dates, y, predictions, target, found_date
                )
                file = discord.File(buf, filename="arima_growth_prediction.png")
                embed.set_image(url="attachment://arima_growth_prediction.png")
                await interaction.followup.send(embed=embed, file=file)
            else:
                await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error("Error in arima_growth command: %s", e, exc_info=True)
            await interaction.followup.send(ERROR_MESSAGES["general_error"].format(str(e)))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ARIMAGrowth(bot))
