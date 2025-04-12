import asyncio
import io
from datetime import datetime
from typing import Final, List, Optional, Tuple
import logging

import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
import pandas as pd
from prophet import Prophet

import discord
from discord.ext import commands


POLYNOMIAL_DEGREE: Final[int] = 3
PREDICTION_DAYS: Final[int] = 304  # 最大3ヶ月分
GRAPH_SIZE: Final[Tuple[int, int]] = (10, 6)  # グラフサイズを調整
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

PROPHET_CONFIG: Final[dict] = {
    "n_changepoints": 25,
    "changepoint_prior_scale": 0.05,
    "seasonality_mode": "additive",
    "weekly_seasonality": {
        "name": "weekly",
        "period": 7,
        "fourier_order": 3
    }
}

logger = logging.getLogger(__name__)

class GrowthPredictor:
    """サーバー成長予測を行うクラス"""

    def __init__(
        self,
        join_dates: List[datetime],
        target: int,
        model_type: str = "polynomial"
    ) -> None:
        self.join_dates = join_dates
        self.target = target
        self.model_type = model_type

        if model_type == "polynomial":
            self.X = np.array([d.toordinal() for d in join_dates]).reshape(-1, 1)
            self.y = np.arange(1, len(join_dates) + 1)

            self.poly = PolynomialFeatures(degree=POLYNOMIAL_DEGREE)
            self.model = LinearRegression()
            self._fit_polynomial_model()
        elif model_type == "prophet":
            self.df = self._prepare_prophet_data()

    def _fit_polynomial_model(self) -> None:
        """モデルを学習"""
        X_poly = self.poly.fit_transform(self.X)
        self.model.fit(X_poly, self.y)

    def _prepare_prophet_data(self) -> pd.DataFrame:
        return pd.DataFrame({
            "ds": [d.strftime("%Y-%m-%d") for d in self.join_dates],
            "y": np.arange(1, len(self.join_dates) + 1)
        })

    async def fit_prophet_model(self) -> Prophet:
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

    async def predict(self, model: Optional[Prophet] = None) -> Optional[datetime]:
        if self.model_type == "polynomial":
            future_days = np.arange(
                self.X[-1][0],
                self.X[-1][0] + PREDICTION_DAYS
            ).reshape(-1, 1)
            future_days_poly = self.poly.transform(future_days)
            predictions = self.model.predict(future_days_poly)

            for i, pred in enumerate(predictions):
                if pred >= self.target:
                    return datetime.fromordinal(int(future_days[i][0]))
        elif self.model_type == "prophet":
            future = model.make_future_dataframe(periods=PREDICTION_DAYS)
            forecast = await asyncio.to_thread(model.predict, future)
            for _, row in forecast.iterrows():
                if row["yhat"] >= self.target:
                    return row["ds"]
        return None

    async def generate_plot(self, target_date: datetime, model: Optional[Prophet] = None) -> io.BytesIO:
        if self.model_type == "polynomial":
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
        elif self.model_type == "prophet":
            forecast = await asyncio.to_thread(model.predict, model.make_future_dataframe(periods=PREDICTION_DAYS))
            plt.figure(figsize=GRAPH_SIZE)
            plt.scatter(
                self.join_dates,
                np.arange(1, len(self.join_dates) + 1),
                color=GRAPH_SETTINGS["colors"]["actual"],
                label="Actual Data",
                alpha=GRAPH_SETTINGS["alpha"]
            )
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
        plt.xlabel("Join Date", fontsize=GRAPH_SETTINGS["fontsize"]["label"])
        plt.ylabel("Member Count", fontsize=GRAPH_SETTINGS["fontsize"]["label"])
        plt.title("Server Growth Prediction", fontsize=GRAPH_SETTINGS["fontsize"]["title"])
        plt.legend()
        plt.grid(True, linestyle="--", alpha=GRAPH_SETTINGS["alpha"])

        # 画像として保存
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        buf.seek(0)
        plt.close()

        return buf

    def get_model_score(self) -> float:
        if self.model_type == "polynomial":
            X_poly = self.poly.transform(self.X)
            return self.model.score(X_poly, self.y)
        return 0.0

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

    async def _fetch_all_join_dates(self, guild: discord.Guild) -> List[datetime]:
        """
        サーバーの全てのメンバーの参加日時を取得

        Parameters
        ----------
        guild : discord.Guild
            対象のサーバー

        Returns
        -------
        List[datetime]
            参加日時のリスト
        """
        join_dates = []
        async for member in guild.fetch_members(limit=None):
            if member.joined_at:
                join_dates.append(member.joined_at)
        join_dates.sort()
        return join_dates

    @discord.app_commands.command(
        name="growth",
        description="サーバーの成長を予測します。モデルを選択可能です。"
    )
    @discord.app_commands.describe(
        model="使用するモデル (polynomial または prophet)",
        target="目標とするメンバー数",
        show_graph="グラフを表示するかどうか"
    )
    async def growth(
        self,
        interaction: discord.Interaction,
        model: str,
        target: int,
        show_graph: bool = True
    ) -> None:
        try:
            await interaction.response.defer(thinking=True)

            # メンバーの参加日時を取得
            join_dates = await self._fetch_all_join_dates(interaction.guild)

            if len(join_dates) < 2:
                await interaction.followup.send(ERROR_MESSAGES["insufficient_data"])
                return

            # 予測の実行
            predictor = GrowthPredictor(join_dates, target, model)

            if model == "prophet":
                prophet_model = await predictor.fit_prophet_model()
                target_date = await predictor.predict(prophet_model)
            else:
                target_date = await predictor.predict()

            if not target_date:
                await interaction.followup.send(ERROR_MESSAGES["no_target_reach"])
                return

            # 結果の表示
            embed = discord.Embed(
                title="Server Growth Prediction",
                description=f"{target}人に達する予測日: {target_date.date()}",
                color=discord.Color.blue()
            )

            if show_graph:
                if model == "prophet":
                    file = discord.File(
                        await predictor.generate_plot(target_date, prophet_model),
                        filename="growth_prediction.png"
                    )
                else:
                    file = discord.File(
                        await predictor.generate_plot(target_date),
                        filename="growth_prediction.png"
                    )
                embed.set_image(url="attachment://growth_prediction.png")
                await interaction.followup.send(embed=embed, file=file)
            else:
                await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error("Error in growth command: %s", e, exc_info=True)
            await interaction.followup.send(ERROR_MESSAGES["unexpected"].format(str(e)))
            
async def setup(bot: commands.Bot):
    await bot.add_cog(Growth(bot))