import asyncio
import io
from datetime import datetime
from typing import Final, Optional, List
import logging

import discord
from discord.ext import commands
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from prophet import Prophet


GRAPH_SIZE: Final[tuple] = (12, 8)
PREDICTION_DAYS: Final[int] = 92  # 約3ヶ月
MIN_DATA_POINTS: Final[int] = 2

PROPHET_CONFIG: Final[dict] = {
    "n_changepoints": 100,
    "changepoint_prior_scale": 0.1,
    "seasonality_mode": "multiplicative",
    "weekly_seasonality": {
        "name": "weekly",
        "period": 7,
        "fourier_order": 3
    }
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

ERROR_MESSAGES: Final[dict] = {
    "insufficient_data": "予測を行うためのデータが不足しています。",
    "no_target_reach": "予測範囲内でその目標値に到達しません。",
    "unexpected": "エラーが発生しました: {}"
}

logger = logging.getLogger(__name__)

class GrowthPredictor:
    """成長予測を行うクラス"""

    def __init__(
        self,
        join_dates: List[datetime],
        target: int
    ) -> None:
        self.join_dates = join_dates
        self.target = target
        self.df = self._prepare_data()

    def _prepare_data(self) -> pd.DataFrame:
        """データフレームを準備"""
        return pd.DataFrame({
            "ds": [d.strftime("%Y-%m-%d") for d in self.join_dates],
            "y": np.arange(1, len(self.join_dates) + 1)
        })

    async def fit_model(self) -> Prophet:
        self.df["ds"] = pd.to_datetime(self.df["ds"])
        model = Prophet(
            n_changepoints=PROPHET_CONFIG["n_changepoints"],
            changepoint_prior_scale=PROPHET_CONFIG["changepoint_prior_scale"],
            seasonality_mode=PROPHET_CONFIG["seasonality_mode"]
        )

        weekly = PROPHET_CONFIG["weekly_seasonality"]
        model.add_seasonality(
            name=weekly["name"],
            period=weekly["period"],
            fourier_order=weekly["fourier_order"]
        )

        await asyncio.to_thread(model.fit, self.df)
        return model

    async def predict(
        self,
        model: Prophet
    ) -> pd.DataFrame:
        future = model.make_future_dataframe(
            periods=PREDICTION_DAYS
        )
        return await asyncio.to_thread(model.predict, future)

    def find_target_date(
        self,
        forecast: pd.DataFrame
    ) -> Optional[datetime]:
        for _, row in forecast.iterrows():
            if row["yhat"] >= self.target:
                return row["ds"]
        return None

    async def generate_plot(
        self,
        forecast: pd.DataFrame,
        target_date: datetime
    ) -> io.BytesIO:
        return await asyncio.to_thread(
            self._generate_plot,
            forecast,
            target_date
        )

    def _generate_plot(
        self,
        forecast: pd.DataFrame,
        target_date: datetime
    ) -> io.BytesIO:
        """グラフ生成の実装"""
        plt.figure(figsize=GRAPH_SIZE)

        # 実データのプロット
        plt.scatter(
            self.join_dates,
            np.arange(1, len(self.join_dates) + 1),
            color=GRAPH_SETTINGS["colors"]["actual"],
            label="Actual Data",
            alpha=GRAPH_SETTINGS["alpha"]
        )

        # 予測線のプロット
        plt.plot(
            forecast["ds"],
            forecast["yhat"],
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
            "Server Growth Prediction with Prophet",
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

class ProphetGrowth(commands.Cog):
    """Prophet成長予測機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _create_prediction_embed(
        self,
        target: int,
        target_date: datetime,
        join_dates: List[datetime],
        show_graph: bool = True
    ) -> discord.Embed:
        """予測結果のEmbedを作成"""
        embed = discord.Embed(
            title="Server Growth Prediction with Prophet",
            description=f"{target}人に達する予測日: {target_date.date()}",
            color=discord.Color.blue()
        )

        if show_graph:
            embed.set_image(url="attachment://prophet_growth_prediction.png")

        fields = {
            "データポイント数": str(len(join_dates)),
            "最初の参加日": join_dates[0].strftime("%Y-%m-%d"),
            "最新の参加日": join_dates[-1].strftime("%Y-%m-%d"),
            "予測モデル": "Prophet"
        }

        for name, value in fields.items():
            embed.add_field(name=name, value=value, inline=True)

        embed.set_footer(
            text="この予測は統計モデルに基づくものであり、"
                "実際の結果を保証するものではありません。\n"
                "Hosted by TechFish_Lab"
        )

        return embed

    @discord.app_commands.command(
        name="prophet_growth",
        description="サーバーの成長を予測します。Prophetは大規模サーバー向けです。"
    )
    @discord.app_commands.describe(
        target="目標とするメンバー数",
        show_graph="グラフを表示するかどうか"
    )
    async def prophet_growth(
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

            if len(join_dates) < MIN_DATA_POINTS:
                await interaction.followup.send(
                    ERROR_MESSAGES["insufficient_data"]
                )
                return

            # 進捗表示
            progress = await interaction.followup.send(
                "データを処理中... 0%"
            )

            # 予測の実行
            predictor = GrowthPredictor(join_dates, target)
            model = await predictor.fit_model()

            await progress.edit(content="データを処理中... 50%")

            forecast = await predictor.predict(model)
            target_date = predictor.find_target_date(forecast)

            await progress.edit(content="データを処理中... 75%")

            if not target_date:
                await progress.edit(
                    content=ERROR_MESSAGES["no_target_reach"]
                )
                return

            # 結果の表示
            embed = self._create_prediction_embed(
                target,
                target_date,
                join_dates,
                show_graph
            )

            if show_graph:
                file = discord.File(
                    await predictor.generate_plot(forecast, target_date),
                    filename="prophet_growth_prediction.png"
                )
                await interaction.followup.send(
                    embed=embed,
                    file=file
                )
            else:
                await progress.edit(content=None, embed=embed)

        except Exception as e:
            logger.error("Error in prophet_growth: %s", e, exc_info=True)
            await interaction.followup.send(
                ERROR_MESSAGES["unexpected"].format(str(e))
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ProphetGrowth(bot))
