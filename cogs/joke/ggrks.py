import re
import discord
import sqlite3
import os
from discord import app_commands
from discord.ext import commands
import urllib.parse

class GGRKS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.enabled_guilds = set()  # 有効化されているサーバーのIDを格納
        
        # データベースファイルのパスを設定
        self.db_path = os.path.join('data', 'ggrks.db')
        
        # データディレクトリが存在しない場合は作成
        os.makedirs(os.path.join('data'), exist_ok=True)
        
        # データベース接続とテーブル作成
        self._init_db()
        
        # 起動時に有効なギルドを読み込む
        self._load_enabled_guilds()

    def _init_db(self):
        """データベース初期化とテーブル作成"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # enabled_guildsテーブルが存在しなければ作成
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS enabled_guilds (
            guild_id INTEGER PRIMARY KEY
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def _load_enabled_guilds(self):
        """データベースから有効なギルドIDを読み込む"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT guild_id FROM enabled_guilds')
        for (guild_id,) in cursor.fetchall():
            self.enabled_guilds.add(guild_id)
        
        conn.close()
    
    def _save_guild_state(self, guild_id, enabled):
        """ギルドの状態をデータベースに保存"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if enabled:
            # UPSERTを使用 (SQLite 3.24.0以降)
            cursor.execute('''
            INSERT INTO enabled_guilds (guild_id) VALUES (?)
            ON CONFLICT(guild_id) DO NOTHING
            ''', (guild_id,))
        else:
            cursor.execute('DELETE FROM enabled_guilds WHERE guild_id = ?', (guild_id,))
        
        conn.commit()
        conn.close()

    @app_commands.command(name="ggrks-enable", description="「〜って何？」「〜って誰？」などの質問に対してGoogle検索を促す機能を有効化します")
    async def ggrks_enable(self, interaction: discord.Interaction):
        self.enabled_guilds.add(interaction.guild_id)
        self._save_guild_state(interaction.guild_id, True)
        await interaction.response.send_message("GGRKSモードを有効化しました。", ephemeral=True)

    @app_commands.command(name="ggrks-disable", description="「〜って何？」「〜って誰？」などの質問に対してGoogle検索を促す機能を無効化します")
    async def ggrks_disable(self, interaction: discord.Interaction):
        if interaction.guild_id in self.enabled_guilds:
            self.enabled_guilds.remove(interaction.guild_id)
            self._save_guild_state(interaction.guild_id, False)
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