import logging
import os
from typing import Optional
from dotenv import load_dotenv

import discord
import sentry_sdk
from discord.ext import commands
from sentry_sdk.integrations.logging import LoggingIntegration

# 環境変数を読み込む
load_dotenv()

# エラーレポート用のUIコンポーネント
class ErrorReportButton(discord.ui.Button):
    def __init__(self, error_id: str):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="詳細なユーザーレポートを報告",
            emoji="📝",
            custom_id=f"error_report:{error_id}"
        )
        self.error_id = error_id

    async def callback(self, interaction: discord.Interaction):
        # モーダルを作成して表示
        modal = ErrorReportModal(self.error_id)
        await interaction.response.send_modal(modal)

class ErrorReportModal(discord.ui.Modal, title="エラー報告フォーム"):
    def __init__(self, error_id: str):
        super().__init__()
        self.error_id = error_id
        
        # テキスト入力フィールドを追加
        self.description = discord.ui.TextInput(
            label="発生した状況",
            placeholder="エラーが発生したときの状況を教えてください",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.description)
        
        self.reproduce_steps = discord.ui.TextInput(
            label="再現手順（任意）",
            placeholder="エラーを再現する手順を教えていただけると助かります",
            style=discord.TextStyle.paragraph,
            required=False
        )
        self.add_item(self.reproduce_steps)

    async def on_submit(self, interaction: discord.Interaction):
        # Sentryにユーザーフィードバックを送信
        if sentry_sdk.Hub.current.client:
            # 関連するエラーイベントIDを使用して新しいメッセージを送信
            with sentry_sdk.push_scope() as scope:
                # ユーザー情報を設定
                scope.set_user({
                    "id": str(interaction.user.id),
                    "username": str(interaction.user.id),  # ユーザーネームの代わりにユーザーIDを設定
                    "email": f"{interaction.user.id}@discord.user"
                })
                
                # フィードバック情報をタグとコンテキストとして設定
                scope.set_tag("feedback_type", "error_report")
                scope.set_tag("original_error_id", self.error_id)
                scope.set_context("user_feedback", {
                    "situation": self.description.value,
                    "reproduction_steps": self.reproduce_steps.value or "未記入",
                    "reported_at": str(discord.utils.utcnow()),
                    "original_error_id": self.error_id
                })
                
                # フィードバックメッセージを送信
                feedback_id = sentry_sdk.capture_message(
                    f"User feedback for error {self.error_id}",
                    level="info"
                )
                
                # 関連するイベントにフィードバックリンクを追加するブレッドクラムを送信
                sentry_sdk.add_breadcrumb(
                    category="feedback",
                    message=f"User provided feedback for error",
                    level="info",
                    data={
                        "feedback_id": feedback_id,
                        "original_error_id": self.error_id,
                        "user": str(interaction.user)
                    }
                )
            
            # ユーザーに完了メッセージを表示
            await interaction.response.send_message("エラー報告ありがとうございます。開発チームに報告しました。", ephemeral=True)
        else:
            await interaction.response.send_message("申し訳ありませんが、現在エラー報告システムが利用できません。", ephemeral=True)

class ErrorReportView(discord.ui.View):
    def __init__(self, error_id: str):
        super().__init__(timeout=None)  # タイムアウトなし
        self.add_item(ErrorReportButton(error_id))

class LoggingCog(commands.Cog):
    """Botの動作をログ出力するCog"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.logger = logging.getLogger("bot")
        self._init_sentry()
        self.bot.on_error = self.on_global_error  # Assign on_global_error method

        
        # 永続的なViewを追加（ボットが再起動してもボタンが機能するために必要）
        bot.add_view(ErrorReportView("dummy"))  # ダミーIDでViewを初期化
    
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
        _, exc_value, _ = hint["exc_info"]  # Removed unused variables
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
                scope.set_user({"id": str(ctx.author.id), "username": str(ctx.author.id)})  # ユーザーネームの代わりにユーザーIDを設定
                scope.set_extra("message_content", ctx.message.content if hasattr(ctx.message, "content") else "No content")
                
                # エラーをキャプチャしてIDを取得
                event_id = sentry_sdk.capture_exception(error)
                self.logger.info(f"Sent error event to Sentry with ID: {event_id}")
                
                # ユーザーにエラーIDを通知
                try:
                    embed = discord.Embed(
                        title="エラーが発生しました",
                        description=f"エラーID: `{event_id}`\n問い合わせの際は、エラーIDも一緒にしていただけると幸いです。\n\nすでにエラーは開発者に報告されていますが、以下のボタンで詳細なユーザーレポートを送信できます。",
                        color=discord.Color.red()
                    )
                    # エラーレポートボタンを追加
                    view = ErrorReportView(event_id)
                    await ctx.send(embed=embed, view=view)
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
                scope.set_user({"id": str(interaction.user.id), "username": str(interaction.user.id)})  # ユーザーネームの代わりにユーザーIDを設定
                scope.set_extra("interaction_data", str(interaction.data) if hasattr(interaction, "data") else "No data")
                
                # エラーをキャプチャしてIDを取得
                event_id = sentry_sdk.capture_exception(error)
                self.logger.info(f"Sent error event to Sentry with ID: {event_id}")
                
                # ユーザーにエラーIDを通知（インタラクションを優先し、失敗したらDMへ）
                try:
                    embed = discord.Embed(
                        title="コマンド実行でエラーが発生しました",
                        description=f"エラーID: `{event_id}`\n問い合わせの際は、エラーIDも一緒にしていただけると幸いです。\n\nすでにエラーは開発者に報告されていますが、以下のボタンで詳細なユーザーレポートを送信できます。",
                        color=discord.Color.red()
                    )
                    
                    # エラーレポートボタンを追加
                    view = ErrorReportView(event_id)
                    
                    # インタラクションの応答状態を確認
                    if not interaction.response.is_done():
                        # まだ応答していない場合は通常の応答として送信
                        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                    else:
                        # 既に応答済みの場合はフォローアップとして送信
                        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                except Exception as e:
                    self.logger.error(f"Failed to send error message via interaction: {e}")
                    # DMを試みる
                    try:
                        await interaction.user.send(embed=embed, view=view)
                    except Exception as dm_error:
                        self.logger.error(f"Failed to send DM with error message: {dm_error}")
    async def on_global_error(self, event_method: str, *args, **kwargs) -> None:
        """Handle global errors."""
        self.logger.error("Global error occurred in %s: %s", event_method, args)

    @commands.command(name="test_sentry")
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

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LoggingCog(bot))