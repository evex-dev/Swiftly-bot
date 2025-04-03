import logging
import os
import sys
from typing import Optional
from dotenv import load_dotenv

import discord
import sentry_sdk
from discord.ext import commands
from sentry_sdk.integrations.logging import LoggingIntegration

# 環境変数を読み込む
load_dotenv()

class LoggingCog(commands.Cog):
    """Botの動作をログ出力するCog"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.logger = logging.getLogger("bot")
        self._init_sentry()
        
        # グローバルエラーハンドラを設定
        self.old_on_error = bot.on_error
        bot.on_error = self.on_error
    
    def _init_sentry(self) -> None:
        """Sentry SDKの初期化"""
        sentry_dsn = os.getenv("SENTRY_DSN")
        
        if not sentry_dsn:
            self.logger.warning("SENTRY_DSN environment variable is not set. Error tracking disabled.")
            return
            
        # Sentryのロギング統合をセットアップ
        logging_integration = LoggingIntegration(
            level=logging.INFO,  # ログレベルINFO以上をキャプチャ
            event_level=logging.ERROR  # エラーレベル以上をイベントとして送信
        )
        
        # Sentry SDKを初期化
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[logging_integration],
            traces_sample_rate=0.2,  # パフォーマンス追跡のサンプルレート
            environment=os.getenv("BOT_ENV", "development"),
            release=os.getenv("BOT_VERSION", "0.1.0"),
            
            # ユーザーコンテキスト情報を設定
            before_send=self._before_send_event
        )
        
        # 初期化テスト用のイベントを送信
        try:
            sentry_sdk.capture_message("Sentry initialization test", level="info")
            self.logger.info("Sentry error tracking initialized and test event sent")
        except Exception as e:
            self.logger.error(f"Failed to send test event to Sentry: {e}")
            
    def _before_send_event(self, event: dict, hint: Optional[dict]) -> dict:
        """Sentryイベント送信前の処理"""
        if hint and "exc_info" in hint:
            exc_type, exc_value, tb = hint["exc_info"]
            # エラーの種類によって処理を分けることができる
            if isinstance(exc_value, commands.CommandNotFound):
                # コマンドが見つからないエラーは無視する例
                return None
        return event

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        self.logger.info("Bot is ready. Logged in as %s", self.bot.user)
        
        # Sentryに起動イベントを送信
        if sentry_sdk.Hub.current.client:
            sentry_sdk.capture_message(
                f"Bot started successfully: {self.bot.user}",
                level="info",
                contexts={
                    "bot": {
                        "id": str(self.bot.user.id),
                        "name": str(self.bot.user),
                        "guilds": len(self.bot.guilds),
                        "users": sum(guild.member_count for guild in self.bot.guilds),
                        "version": os.getenv("BOT_VERSION", "0.1.0"),
                        "environment": os.getenv("BOT_ENV", "development")
                    }
                }
            )
            self.logger.info("Sent startup event to Sentry")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        self.logger.info("Joined guild: %s (ID: %s)", guild.name, guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        self.logger.info("Removed from guild: %s (ID: %s)", guild.name, guild.id)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        self.logger.info("Member joined: %s (ID: %s) in guild: %s", member.name, member.id, member.guild.name)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        self.logger.info("Member left: %s (ID: %s) from guild: %s", member.name, member.id, member.guild.name)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context) -> None:
        guild_name = ctx.guild.name if ctx.guild else "DM"
        self.logger.info("Command executed: %s by %s (ID: %s) in guild: %s", ctx.command, ctx.author.name, ctx.author.id, guild_name)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        guild_name = ctx.guild.name if ctx.guild else "DM"
        self.logger.error("Command error: %s by %s (ID: %s) in guild: %s - %s", ctx.command, ctx.author.name, ctx.author.id, guild_name, error)
        
        # エラーの種類によって処理を分ける
        if isinstance(error, commands.CommandNotFound):
            # コマンドが見つからない場合は何もしない
            return
            
        # Sentryにエラーイベントを明示的に送信
        if sentry_sdk.Hub.current.client:
            with sentry_sdk.push_scope() as scope:
                # コンテキスト情報を追加
                scope.set_tag("command", str(ctx.command) if ctx.command else "Unknown")
                scope.set_tag("guild", guild_name)
                scope.set_user({"id": str(ctx.author.id), "username": ctx.author.name})
                scope.set_extra("message_content", ctx.message.content if hasattr(ctx.message, "content") else "No content")
                
                # エラーをキャプチャしてIDを取得
                event_id = sentry_sdk.capture_exception(error)
                self.logger.info(f"Sent error event to Sentry with ID: {event_id}")
                
                # ユーザーにエラーIDを通知
                try:
                    embed = discord.Embed(
                        title="エラーが発生しました",
                        description=f"エラーID: `{event_id}`\n問い合わせの際は、エラーIDも一緒にしていただけると幸いです。",
                        color=discord.Color.red()
                    )
                    await ctx.send(embed=embed)
                except Exception as e:
                    self.logger.error(f"Failed to send error message to user: {e}")
                    # バックアップとして通常のメッセージを試す
                    try:
                        await ctx.send(f"エラーが発生しました。\nエラーID: `{event_id}`")
                    except Exception:
                        pass

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command: discord.app_commands.Command) -> None:
        guild_name = interaction.guild.name if interaction.guild else "DM"
        self.logger.info("Command executed: %s by %s (ID: %s) in guild: %s", command.name, interaction.user.name, interaction.user.id, guild_name)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        guild_name = interaction.guild.name if interaction.guild else "DM"
        command_name = interaction.command.name if interaction.command else "Unknown"
        self.logger.error("Command error: %s by %s (ID: %s) in guild: %s - %s", command_name, interaction.user.name, interaction.user.id, guild_name, error)
        
        # Sentryにエラーイベントを明示的に送信
        if sentry_sdk.Hub.current.client:
            with sentry_sdk.push_scope() as scope:
                # コンテキスト情報を追加
                scope.set_tag("command", command_name)
                scope.set_tag("guild", guild_name)
                scope.set_user({"id": str(interaction.user.id), "username": interaction.user.name})
                scope.set_extra("interaction_data", str(interaction.data) if hasattr(interaction, "data") else "No data")
                
                # エラーをキャプチャしてIDを取得
                event_id = sentry_sdk.capture_exception(error)
                self.logger.info(f"Sent error event to Sentry with ID: {event_id}")
                
                # ユーザーにエラーIDをDMで通知
                try:
                    embed = discord.Embed(
                        title="コマンド実行でエラーが発生しました",
                        description=f"エラーID: `{event_id}`\n問い合わせの際は、エラーIDも一緒にしていただけると幸いです。",
                        color=discord.Color.red()
                    )
                    await interaction.user.send(embed=embed)
                except Exception as e:
                    self.logger.error(f"Failed to send error message to user via DM: {e}")

    @commands.command(name="test_sentry")
    async def test_sentry(self, ctx: commands.Context) -> None:
        """Sentryへのテスト接続を行うコマンド（特定ユーザー限定）"""
        if ctx.author.id != 1241397634095120438:
            await ctx.send("❌ このコマンドを実行する権限がありません。")
            return

        try:
            if not sentry_sdk.Hub.current.client:
                await ctx.send("❌ Sentryは初期化されていません。環境変数を確認してください。")
                return
                
            # 情報イベントを送信
            sentry_sdk.capture_message(
                "Manual test event from bot owner",
                level="info",
                contexts={
                    "command": {
                        "channel": str(ctx.channel),
                        "guild": str(ctx.guild) if ctx.guild else "DM",
                        "timestamp": str(ctx.message.created_at)
                    }
                }
            )
            
            # エラーイベントを送信
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("test_type", "manual_error_test")
                scope.set_user({"id": str(ctx.author.id), "username": ctx.author.name})
                try:
                    # テスト用のエラーを意図的に発生させる
                    raise ValueError("This is a test error for Sentry")
                except ValueError as e:
                    sentry_sdk.capture_exception(e)
            
            self.logger.info("Manual Sentry test events sent")
            await ctx.send("✅ Sentryへテストイベントを送信しました。ダッシュボードを確認してください。")
            
        except Exception as e:
            self.logger.error(f"Failed to send manual test event to Sentry: {e}")
            await ctx.send(f"❌ Sentryへのテスト送信に失敗しました: {e}")

    async def on_error(self, event_method: str, *args, **kwargs) -> None:
        """グローバルな未処理例外ハンドラ"""
        error_type, error_value, error_traceback = sys.exc_info()
        self.logger.error(f"Uncaught exception in {event_method}: {error_type.__name__}: {error_value}")
        
        # Sentryにエラーを送信
        if sentry_sdk.Hub.current.client:
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("event", event_method)
                scope.set_extra("traceback", f"{error_type.__name__}: {error_value}")
                
                # エラーをキャプチャ
                event_id = sentry_sdk.capture_exception()
                self.logger.info(f"Sent uncaught error to Sentry with ID: {event_id}")
                
                # コマンド種類を特定してユーザーに通知
                try:
                    if args and len(args) > 0:
                        if isinstance(args[0], commands.Context):
                            # 伝統的なコマンドの場合
                            ctx = args[0]
                            embed = discord.Embed(
                                title="エラーが発生しました",
                                description=f"エラーID: `{event_id}`\n問い合わせの際は、エラーIDも一緒にしていただけると幸いです。",
                                color=discord.Color.red()
                            )
                            await ctx.send(embed=embed)
                        elif isinstance(args[0], discord.Interaction):
                            # スラッシュコマンドの場合
                            interaction = args[0]
                            try:
                                if interaction.response.is_done():
                                    # 既に応答済みの場合はフォローアップとして送信
                                    await interaction.followup.send(
                                        embed=discord.Embed(
                                            title="エラーが発生しました",
                                            description=f"エラーID: `{event_id}`\n問い合わせの際は、エラーIDも一緒にしていただけると幸いです。",
                                            color=discord.Color.red()
                                        ),
                                        ephemeral=True
                                    )
                                else:
                                    # まだ応答していない場合は通常の応答として送信
                                    await interaction.response.send_message(
                                        embed=discord.Embed(
                                            title="エラーが発生しました",
                                            description=f"エラーID: `{event_id}`\n問い合わせの際は、エラーIDも一緒にしていただけると幸いです。",
                                            color=discord.Color.red()
                                        ),
                                        ephemeral=True
                                    )
                            except Exception as e:
                                # インタラクションへの応答が失敗した場合はDMを試みる
                                self.logger.error(f"Failed to send error message via interaction: {e}")
                                try:
                                    await interaction.user.send(
                                        embed=discord.Embed(
                                            title="コマンド実行でエラーが発生しました",
                                            description=f"エラーID: `{event_id}`\n問い合わせの際は、エラーIDも一緒にしていただけると幸いです。",
                                            color=discord.Color.red()
                                        )
                                    )
                                except Exception as dm_error:
                                    self.logger.error(f"Failed to send DM with error message: {dm_error}")
                except Exception as notify_error:
                    self.logger.error(f"Failed to notify user about error: {notify_error}")
        
        # 必要に応じて元のエラーハンドラを呼び出す
        if self.old_on_error:
            try:
                await self.old_on_error(event_method, *args, **kwargs)
            except Exception:
                pass

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LoggingCog(bot))
