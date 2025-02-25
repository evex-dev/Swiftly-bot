import asyncio
import io
from datetime import datetime
from typing import Final, List, Optional, Tuple
import logging

import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

import discord
from discord.ext import commands

# 定数定義
POLYNOMIAL_DEGREE: Final[int] = 3
PREDICTION_DAYS: Final[int] = 36500  # 100年分
GRAPH_SIZE: Final[Tuple[int, int]] = (12, 8)
PROGRESS_INTERVAL: Final[int] = 10
PROGRESS_DELAY: Final[float] = 0.1

ERROR_MESSAGES: Final[dict] = {
    "insufficient_data": "回帰分析を行うためのデータが不足しています。",
    "no_target_reach": "予測範囲内でその目標値に到達しません。",
    "unexpected": "エラーが発生しました: {}"
}

GRAPH_SETTINGS: Final[dict] = {
    "colors": {
        "actual": "blue",
        "prediction": "red",
        "target": "green",
        "date": "purple"
    },
    "alpha": 0.6,
    "linewidth": 2,
    "fontsize": {
        "label": 14,
        "title": 16
    }
}

logger = logging.getLogger(__name__)

class GrowthPredictor:
    """サーバー成長予測を行うクラス"""

    def __init__(
        self,
        join_dates: List[datetime],
        target: int
    ) -> None:
        self.join_dates = join_dates
        self.target = target
        self.X = np.array([d.toordinal() for d in join_dates]).reshape(-1, 1)
        self.y = np.arange(1, len(join_dates) + 1)

        self.poly = PolynomialFeatures(degree=POLYNOMIAL_DEGREE)
        self.model = LinearRegression()
        self._fit_model()

    def _fit_model(self) -> None:
        """モデルを学習"""
        X_poly = self.poly.fit_transform(self.X)
        self.model.fit(X_poly, self.y)

    def predict_target_date(self) -> Optional[datetime]:
        future_days = np.arange(
            self.X[-1][0],
            self.X[-1][0] + PREDICTION_DAYS
        ).reshape(-1, 1)
        future_days_poly = self.poly.transform(future_days)
        predictions = self.model.predict(future_days_poly)

        for i, pred in enumerate(predictions):
            if pred >= self.target:
                return datetime.fromordinal(int(future_days[i][0]))
        return None

    def create_prediction_plot(
        self,
        target_date: datetime
    ) -> io.BytesIO:
        X_plot = np.linspace(
            self.X[0][0],
            target_date.toordinal(),
            200
        ).reshape(-1, 1)
        X_plot_poly = self.poly.transform(X_plot)
        y_plot = self.model.predict(X_plot_poly)

        plt.figure(figsize=GRAPH_SIZE)

        # 実データのプロット
        plt.scatter(
            self.join_dates,
            self.y,
            color=GRAPH_SETTINGS["colors"]["actual"],
            label="Actual Data",
            alpha=GRAPH_SETTINGS["alpha"]
        )

        # 予測線のプロット
        plt.plot(
            [datetime.fromordinal(int(x[0])) for x in X_plot],
            y_plot,
            color=GRAPH_SETTINGS["colors"]["prediction"],
            label="Prediction",
            linewidth=GRAPH_SETTINGS["linewidth"]
        )

        # 目標値と予測日の線
        plt.axhline(
            y=self.target,
            color=GRAPH_SETTINGS["colors"]["target"],
            linestyle="--",
            label=f"Target: {self.target}",
            linewidth=GRAPH_SETTINGS["linewidth"]
        )
        plt.axvline(
            x=target_date,
            color=GRAPH_SETTINGS["colors"]["date"],
            linestyle="--",
            label=f"Predicted: {target_date.date()}",
            linewidth=GRAPH_SETTINGS["linewidth"]
        )

        # グラフの設定
        plt.xlabel(
            "Join Date",
            fontsize=GRAPH_SETTINGS["fontsize"]["label"]
        )
        plt.ylabel(
            "Member Count",
            fontsize=GRAPH_SETTINGS["fontsize"]["label"]
        )
        plt.title(
            "Server Growth Prediction",
            fontsize=GRAPH_SETTINGS["fontsize"]["title"]
        )
        plt.legend()
        plt.grid(True, linestyle="--", alpha=GRAPH_SETTINGS["alpha"])

        # 画像として保存
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        buf.seek(0)
        plt.close()

        return buf

    def get_model_score(self) -> float:
        X_poly = self.poly.transform(self.X)
        return self.model.score(X_poly, self.y)

class Growth(commands.Cog):
    """サーバーの成長予測機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _show_progress(
        self,
        message: discord.Message
    ) -> None:
        """
        進捗バーを表示

        Parameters
        ----------
        message : discord.Message
            更新するメッセージ
        """
        for i in range(0, 101, PROGRESS_INTERVAL):
            await message.edit(content=f"計算中... {i}%")
            await asyncio.sleep(PROGRESS_DELAY)

    def _create_prediction_embed(
        self,
        target: int,
        target_date: datetime,
        join_dates: List[datetime],
        model_score: float,
        show_graph: bool = True
    ) -> discord.Embed:
        embed = discord.Embed(
            title="Server Growth Prediction",
            description=f"{target}人に達する予測日: {target_date.date()}",
            color=discord.Color.blue()
        )

        if show_graph:
            embed.set_image(url="attachment://growth_prediction.png")

        # フィールドの追加
        fields = {
            "データポイント数": str(len(join_dates)),
            "予測精度": f"{model_score:.2f}",
            "最初の参加日": join_dates[0].strftime("%Y-%m-%d"),
            "最新の参加日": join_dates[-1].strftime("%Y-%m-%d"),
            "予測モデル": f"{POLYNOMIAL_DEGREE}次多項式回帰"
        }

        for name, value in fields.items():
            embed.add_field(name=name, value=value, inline=True)

        embed.set_footer(
            text="この予測は統計モデルに基づくものであり、"
                "実際の結果を保証するものではありません。"
        )

        return embed

    @discord.app_commands.command(
        name="growth",
        description="サーバーの成長を予測します。全サーバー向きです。"
    )
    @discord.app_commands.describe(
        target="目標とするメンバー数",
        show_graph="グラフを表示するかどうか"
    )
    async def growth(
        self,
        interaction: discord.Interaction,
        target: int,
        show_graph: bool = True
    ) -> None:
        try:
            await interaction.response.defer(thinking=True)

            # メンバーの参加日時を取得
            join_dates = [
                m.joined_at for m in interaction.guild.members
                if m.joined_at
            ]
            join_dates.sort()

            if len(join_dates) < 2:
                await interaction.followup.send(
                    ERROR_MESSAGES["insufficient_data"]
                )
                return

            # 進捗表示
            progress_message = await interaction.followup.send(
                "計算中... 0%",
                ephemeral=True
            )

            # 予測の実行
            predictor = GrowthPredictor(join_dates, target)
            await self._show_progress(progress_message)
            target_date = predictor.predict_target_date()

            if not target_date:
                await interaction.followup.send(
                    ERROR_MESSAGES["no_target_reach"]
                )
                return

            # 結果の表示
            embed = self._create_prediction_embed(
                target,
                target_date,
                join_dates,
                predictor.get_model_score(),
                show_graph
            )

            if show_graph:
                file = discord.File(
                    predictor.create_prediction_plot(target_date),
                    filename="growth_prediction.png"
                )
                await interaction.followup.send(embed=embed, file=file)
            else:
                await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error("Error in growth command: %s", e, exc_info=True)
            await interaction.followup.send(
                ERROR_MESSAGES["unexpected"].format(str(e))
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Growth(bot))
