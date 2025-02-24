# Swiftly DiscordBot.
# Developed by: TechFish_1
import asyncio
import os
import json
import sqlite3
import time

import dotenv
import discord
from discord.ext import commands
import logging
from logging.handlers import TimedRotatingFileHandler

logging.getLogger('discord').setLevel(logging.WARNING)

last_status_update = 0

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True

client = discord.AutoShardedClient(intents=intents, shard_count=10)
bot = commands.Bot(command_prefix="sw!", intents=intents, client=client)

# tokenを.envファイルから取得
dotenv.load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ログの設定
log_dir = "./log"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# すべてのログを1つのファイルに記録
log_handler = TimedRotatingFileHandler(
    f"{log_dir}/logs.log", when="midnight", interval=1, backupCount=7, encoding="utf-8")
log_handler.setLevel(logging.DEBUG)
log_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# コマンド実行履歴のログ
command_log_handler = TimedRotatingFileHandler(
    f"{log_dir}/commands.log", when="midnight", interval=1, backupCount=7, encoding="utf-8")
command_log_handler.setLevel(logging.INFO)
command_log_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# ロガーの設定
logger = logging.getLogger('bot')
logger.setLevel(logging.WARNING)
logger.addHandler(log_handler)
logger.addHandler(command_log_handler)

# discord ロガーの設定を変更
logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('discord').addHandler(log_handler)
logging.getLogger('discord').addHandler(command_log_handler)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")

    # cogsフォルダからCogを非同期でロード
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            extension_name = filename[:-3]
            try:
                await bot.load_extension(f"cogs.{extension_name}")
                print(f"Loaded: cogs.{extension_name}")
            except Exception as e:
                print(f"Failed to load: cogs.{extension_name} - {e}")

    # アプリコマンドを同期（slashコマンド等）
    await bot.tree.sync()

    # 初回のユーザー数を集計して書き込み
    await update_user_count()

    # JSONファイルからユーザー数を読み込み、ステータスを更新
    with open("user_count.json", "r", encoding="utf-8") as fp:
        data = json.load(fp)
        user_count = data.get("total_users", 0)
        await bot.change_presence(activity=discord.Game(name=f"{user_count}人のユーザー数"))


@bot.event
async def on_member_join(_):
    await update_user_count()
    await update_bot_status()


@bot.event
async def on_member_remove(_):
    await update_user_count()
    await update_bot_status()


async def update_user_count():
    # サーバー参加者を集計（重複ユーザーは1度のみカウント）
    unique_users = set()
    for guild in bot.guilds:
        for member in guild.members:
            unique_users.add(member.id)
    user_count = len(unique_users)
    print(f"Unique user count: {user_count}")

    # JSONファイルに書き込み
    with open("user_count.json", "w", encoding="utf-8") as f:
        json.dump({"total_users": user_count}, f, ensure_ascii=False, indent=4)


# 連続で参加した時に頻繁に更新するとあれなので5秒
async def update_bot_status():
    global last_status_update
    current_time = time.time()
    if current_time - last_status_update < 5:
        return

    with open("user_count.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        user_count = data.get("total_users", 0)
        await bot.change_presence(activity=discord.Game(name=f"{user_count}人のユーザー数"))

    last_status_update = current_time


@bot.event
async def on_command_completion(ctx):
    logging.getLogger('commands').info(f"Command executed: {ctx.command}")


@bot.event
async def on_command_error(ctx, error):
    logging.getLogger('commands').error(f"Error: {error}")
    await ctx.send("エラーが発生しました")

# データベース接続をグローバルに保持
DB_PATH = "prohibited_channels.db"
db_conn = None


def get_db_connection():
    global db_conn
    if db_conn is None:
        db_conn = sqlite3.connect(DB_PATH)
    return db_conn


async def check_prohibited_channel(guild_id: int, channel_id: int) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM prohibited_channels WHERE guild_id = ? AND channel_id = ?",
            (str(guild_id), str(channel_id))
        )
        return cursor.fetchone() is not None
    except Exception as e:
        logging.getLogger('bot').error(f"Prohibited channel check error: {e}")
        return False


@bot.check
async def prohibit_commands_in_channels(ctx):
    # DMの場合はコマンドを許可
    if ctx.guild is None:
        return True

    try:
        if ctx.command and ctx.command.name == "set_prohibited_channel":
            return True

        is_prohibited = await check_prohibited_channel(ctx.guild.id, ctx.channel.id)
        if is_prohibited:
            await ctx.send("このチャンネルではコマンドの実行が禁止されています。")
            return False
        return True

    except Exception as e:
        logging.getLogger('bot').error(f"Prohibited channel check error: {e}")
        return True


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    logging.getLogger('commands').error(f"App command error: {error}")
    await interaction.response.send_message("エラーが発生しました", ephemeral=True)


async def check_slash_command(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return True

    # set_prohibited_channelコマンドは常に許可
    if interaction.command and interaction.command.name == "set_prohibited_channel":
        return True

    is_prohibited = await check_prohibited_channel(interaction.guild_id, interaction.channel_id)
    if is_prohibited:
        await interaction.response.send_message("このチャンネルではコマンドの実行が禁止されています。", ephemeral=True)
        return False
    return True

bot.tree.interaction_check = check_slash_command

if __name__ == "__main__":
    asyncio.run(bot.start(TOKEN))
