import asyncio
import io

import discord
from discord.ext import commands
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from prophet import Prophet


class ProphetGrowth(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="prophet_growth", description="サーバーの成長を予測します。Prophetは大規模サーバー向けです。")
    async def prophet_growth(self, interaction: discord.Interaction, target: int, show_graph: bool = True):
        await interaction.response.defer(thinking=True)

        try:
            guild = interaction.guild
            members = guild.members
            join_dates = [m.joined_at for m in members if m.joined_at]
            join_dates.sort()

            if len(join_dates) < 2:
                await interaction.followup.send("予測を行うためのデータが不足しています。")
                return

            data = {"ds": [d.strftime("%Y-%m-%d") for d in join_dates], "y": np.arange(1, len(join_dates) + 1)}
            df = pd.DataFrame(data)

            # Send initial progress message
            progress_message = await interaction.followup.send("データを処理中... 0%")

            # Fit the model asynchronously
            model = await self.fit_model(df)

            # Update progress
            await progress_message.edit(content="データを処理中... 50%")

            future = model.make_future_dataframe(periods=92)
            # 予測処理を非同期で実行
            forecast = await self.predict_model(model, future)

            # Update progress
            await progress_message.edit(content="データを処理中... 75%")

            found_date = self.find_target_date(forecast, target)

            if not found_date:
                await progress_message.edit(content="予測範囲内でその目標値に到達しません。")
                return

            if show_graph:
                # Generate the plot asynchronously
                buf = await self.generate_plot(join_dates, forecast, target, found_date)
                file = discord.File(buf, filename="prophet_growth_prediction.png")

                embed = discord.Embed(title="Server Growth Prediction with Prophet", description=f"{target}人に達する予測日: {found_date}", color=discord.Color.blue())
                embed.set_image(url="attachment://prophet_growth_prediction.png")
                embed.add_field(name="データポイント数", value=str(len(join_dates)), inline=True)
                embed.add_field(name="最初の参加日", value=join_dates[0].strftime("%Y-%m-%d"), inline=True)
                embed.add_field(name="最新の参加日", value=join_dates[-1].strftime("%Y-%m-%d"), inline=True)
                embed.add_field(name="予測モデル", value="Prophet", inline=True)
                embed.set_footer(
                    text="この予測は統計モデルに基づくものであり、実際の結果を保証するものではありません。\nHosted by TechFish_Lab")

                await interaction.followup.send(embed=embed, file=file)
            else:
                embed = discord.Embed(title="Server Growth Prediction", description=f"{target}人に達する予測日: {found_date}", color=discord.Color.green())
                embed.add_field(name="データポイント数", value=str(len(join_dates)), inline=True)
                embed.add_field(name="最初の参加日", value=join_dates[0].strftime("%Y-%m-%d"), inline=True)
                embed.add_field(name="最新の参加日", value=join_dates[-1].strftime("%Y-%m-%d"), inline=True)
                embed.add_field(name="予測モデル", value="Prophet", inline=True)
                embed.set_footer(
                    text="この予測は統計モデルに基づくものであり、実際の結果を保証するものではありません。\nHosted by TechFish_Lab")
                await progress_message.edit(content=None, embed=embed)
        except Exception as e:
            await interaction.followup.send(f"エラーが発生しました: {e}")

    async def fit_model(self, df):
        # 文字列の日付をdatetime型に変換（必要に応じて）
        df["ds"] = pd.to_datetime(df["ds"])
        # 改善されたモデル設定: changepointsの数を増やし、より詳細な週次季節性を追加
        model = Prophet(
            n_changepoints=100,
            changepoint_prior_scale=0.1,
            seasonality_mode="multiplicative"
        )
        model.add_seasonality(name="weekly", period=7, fourier_order=3)
        await asyncio.to_thread(model.fit, df)
        return model

    async def predict_model(self, model, future):
        return await asyncio.to_thread(model.predict, future)

    def find_target_date(self, forecast, target):
        return next((row["ds"] for _, row in forecast.iterrows() if row["yhat"] >= target), None)

    async def generate_plot(self, join_dates, forecast, target, found_date):
        return await asyncio.to_thread(self._generate_plot, join_dates, forecast, target, found_date)

    def _generate_plot(self, join_dates, forecast, target, found_date):
        plt.figure(figsize=(12, 8))
        plt.scatter(join_dates, np.arange(1, len(join_dates) + 1), color="blue", label="Actual Data", alpha=0.6)
        plt.plot(forecast["ds"], forecast["yhat"], color="red", label="Prediction", linewidth=2)
        plt.axhline(y=target, color="green", linestyle="--", label=f"Target: {target}", linewidth=2)
        plt.axvline(x=found_date, color="purple", linestyle="--", label=f"Predicted: {found_date}", linewidth=2)
        plt.xlabel("Join Date", fontsize=14)
        plt.ylabel("Member Count", fontsize=14)
        plt.title("Server Growth Prediction with Prophet", fontsize=16)
        plt.legend()
        plt.grid(True, linestyle="--", alpha=0.7)

        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        buf.seek(0)
        plt.close()
        return buf


async def setup(bot):
    await bot.add_cog(ProphetGrowth(bot))
