import re
import discord
import os
from discord import app_commands
from discord.ext import commands
import urllib.parse

import asyncpg
from dotenv import load_dotenv

class GGRKS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.enabled_guilds = set()  # 有効化されているサーバーのIDを格納
        # DB接続用のプール
        self.db_pool = None
        # dotenvから環境変数の読み込み（cog_loadで実施）
        
    async def cog_load(self):
        load_dotenv()
        self.db_pool = await asyncpg.create_pool(
            host=os.environ.get("DB_HOST"),
            port=os.environ.get("DB_PORT"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"),
            database="ggrks"
        )
        await self._init_db()
        await self._load_enabled_guilds()

    async def cog_unload(self):
        if self.db_pool:
            await self.db_pool.close()

    async def _init_db(self):
        """非同期でデータベースの初期化とテーブル作成"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS enabled_guilds (
                    guild_id BIGINT PRIMARY KEY
                )
            """)
            # ユニーク制約を追加
            await conn.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'enabled_guilds_guild_id_key'
                    ) THEN
                        ALTER TABLE enabled_guilds
                        ADD CONSTRAINT enabled_guilds_guild_id_key UNIQUE (guild_id);
                    END IF;
                END $$;
            """)

    async def _load_enabled_guilds(self):
        """非同期でデータベースから有効なギルドIDを読み込む"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT guild_id FROM enabled_guilds")
            for record in rows:
                self.enabled_guilds.add(record["guild_id"])

    async def _save_guild_state(self, guild_id, enabled):
        """非同期でギルドの状態をデータベースに保存"""
        async with self.db_pool.acquire() as conn:
            if enabled:
                await conn.execute("""
                    INSERT INTO enabled_guilds (guild_id) VALUES ($1)
                    ON CONFLICT (guild_id) DO NOTHING
                """, guild_id)
            else:
                await conn.execute("DELETE FROM enabled_guilds WHERE guild_id = $1", guild_id)

    # 管理者権限チェック関数
    def _is_administrator(self, interaction: discord.Interaction) -> bool:
        """ユーザーが管理者権限を持っているかチェック"""
        if interaction.user.guild_permissions.administrator:
            return True
        return False

    @app_commands.command(name="ggrks-enable", description="「〜って何？」「〜って誰？」などの質問に対してGoogle検索を促す機能を有効化します")
    async def ggrks_enable(self, interaction: discord.Interaction):
        # 管理者権限チェック
        if not self._is_administrator(interaction):
            await interaction.response.send_message("このコマンドはサーバー管理者のみが実行できます。", ephemeral=True)
            return
            
        self.enabled_guilds.add(interaction.guild_id)
        await self._save_guild_state(interaction.guild_id, True)
        await interaction.response.send_message("GGRKSモードを有効化しました。", ephemeral=True)

    @app_commands.command(name="ggrks-disable", description="「〜って何？」「〜って誰？」などの質問に対してGoogle検索を促す機能を無効化します")
    async def ggrks_disable(self, interaction: discord.Interaction):
        # 管理者権限チェック
        if not self._is_administrator(interaction):
            await interaction.response.send_message("このコマンドはサーバー管理者のみが実行できます。", ephemeral=True)
            return
            
        if interaction.guild_id in self.enabled_guilds:
            self.enabled_guilds.remove(interaction.guild_id)
            await self._save_guild_state(interaction.guild_id, False)
            await interaction.response.send_message("GGRKSモードを無効化しました。", ephemeral=True)
        else:
            await interaction.response.send_message("GGRKSモードは既に無効化されています。", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # 自身のメッセージには反応しない
        if message.author.bot:
            return
            
        # 有効化されていないサーバーでは動作しない
        if message.guild.id not in self.enabled_guilds:
            return
            
        # 「〜って何？」「〜って誰？」のパターンを検出
        pattern = r'(.+)って(何|なに|誰|だれ|どこ|どんな|どうやって|どうすれば|どうすると|どのように|何故|なぜ|どうして).*[？\?]$'
        match = re.search(pattern, message.content)
        
        if match:
            search_term = match.group(1).strip()
            # Google検索用URLを作成
            encoded_term = urllib.parse.quote(search_term)
            google_url = f"https://www.google.com/search?q={encoded_term}"
            
            # 返信メッセージを送信
            await message.reply(f"自分で調べることは非常に大切です。\n{google_url}")

async def setup(bot):
    await bot.add_cog(GGRKS(bot))