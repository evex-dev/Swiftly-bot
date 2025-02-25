import json
import time
from typing import Optional

import aiohttp
import discord
from discord.ext import commands

# 定数定義
API_URL = "https://js-sandbox.evex.land/"
SUPPORT_FOOTER = "API Powered by EvexDevelopers"


class Sandbox(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def create_result_embed(
        self,
        result: Optional[dict] = None,
        error: Optional[str] = None,
        elapsed_time: float = 0.0
    ) -> discord.Embed:
        if error:
            embed = discord.Embed(
                title="エラー",
                description=error,
                color=discord.Color.red()
            )
        else:
            embed = discord.Embed(
                title="実行結果",
                color=discord.Color.green()
            )
            if result:
                embed.add_field(
                    name="終了コード",
                    value=result.get("exitcode", "N/A"),
                    inline=False
                )
                embed.add_field(
                    name="出力",
                    value=f"```{result.get('message', '')}```",
                    inline=False
                )

        embed.add_field(
            name="実行時間",
            value=f"{elapsed_time:.2f} 秒",
            inline=False
        )
        embed.set_footer(text=SUPPORT_FOOTER)
        return embed

    async def execute_code(self, code: str) -> tuple[Optional[dict], Optional[str], float]:
        headers = {"Content-Type": "application/json"}
        payload = {"code": code}

        try:
            start_time = time.monotonic()
            async with self.session.post(API_URL, json=payload, headers=headers) as response:
                end_time = time.monotonic()
                elapsed_time = end_time - start_time

                if response.status == 200:
                    result = await response.text()
                    return json.loads(result), None, elapsed_time
                return None, "コードの実行に失敗しました。", elapsed_time
        except aiohttp.ClientError as e:
            return None, f"API通信エラー: {e}", 0.0
        except json.JSONDecodeError:
            return None, "APIからの応答の解析に失敗しました。", 0.0
        except Exception as e:
            return None, f"予期せぬエラー: {e}", 0.0

    @discord.app_commands.command(
        name="sandbox",
        description="JavaScript コードをサンドボックスで実行し、結果を返します。"
    )
    async def sandbox(self, ctx: discord.Interaction, code: str) -> None:
        await ctx.response.defer(thinking=True)
        result, error, elapsed_time = await self.execute_code(code)
        embed = await self.create_result_embed(result, error, elapsed_time)
        await ctx.followup.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        if message.content.startswith("?sandbox"):
            code = message.content[len("?sandbox "):].strip()
            if not code:
                await message.channel.send("実行するコードを入力してください。")
                return

            progress_message = await message.channel.send("実行中...")
            result, error, elapsed_time = await self.execute_code(code)
            embed = await self.create_result_embed(result, error, elapsed_time)
            await progress_message.edit(content=None, embed=embed)

    async def cog_unload(self) -> None:
        if not self.session.closed:
            await self.session.close()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Sandbox(bot))
