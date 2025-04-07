import discord
from discord.ext import commands, tasks
import sqlite3
import json
import datetime

DB_PATH = "data/analytics.db"

class AnalyticsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        self.db.row_factory = sqlite3.Row
        self.initialize_db()
        self.data_collection_loop.start()

    def initialize_db(self):
        c = self.db.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS analytics_enabled (
                guild_id INTEGER PRIMARY KEY
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS message_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                timestamp TIMESTAMP,
                response_time REAL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS analytics_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                timestamp TIMESTAMP,
                total_members INTEGER,
                active_members INTEGER,
                messages_per_day INTEGER,
                growth_rate REAL,
                new_members_this_week INTEGER,
                engagement INTEGER,
                daily_messages TEXT,
                daily_active_users TEXT,
                average_response_time REAL,
                member_engagement_rate REAL
            )
        """)
        self.db.commit()

    @discord.app_commands.command(name="analytics", description="Enable or disable data collection for this guild.")
    @discord.app_commands.choices(action=[
        discord.app_commands.Choice(name="enable", value="enable"),
        discord.app_commands.Choice(name="disable", value="disable"),
    ])
    async def analytics_command(self, interaction: discord.Interaction, action: discord.app_commands.Choice[str]):
        guild_id = interaction.guild.id
        c = self.db.cursor()
        if action.value == "enable":
            c.execute("INSERT OR IGNORE INTO analytics_enabled (guild_id) VALUES (?)", (guild_id,))
            self.db.commit()
            await interaction.response.send_message("Analytics collection enabled for this guild.")
        elif action.value == "disable":
            c.execute("DELETE FROM analytics_enabled WHERE guild_id = ?", (guild_id,))
            self.db.commit()
            await interaction.response.send_message("Analytics collection disabled for this guild.")
        else:
            await interaction.response.send_message("Unknown action. Please specify 'enable' or 'disable'.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        now = datetime.datetime.now(datetime.timezone.utc)
        response_time = None
        if message.reference and message.reference.resolved:
            referenced: discord.Message = message.reference.resolved
            if isinstance(referenced, discord.Message):
                delta = (message.created_at - referenced.created_at).total_seconds()
                response_time = delta if delta >= 0 else None
        c = self.db.cursor()
        c.execute("""
            INSERT INTO message_log (guild_id, user_id, timestamp, response_time)
            VALUES (?, ?, ?, ?)
        """, (message.guild.id, message.author.id, now, response_time))
        self.db.commit()

    async def update_analytics(self, guild_id: int):
        c = self.db.cursor()
        now = datetime.datetime.now(datetime.timezone.utc)
        one_day_ago = now - datetime.timedelta(days=1)
        seven_days_ago = now - datetime.timedelta(days=7)
        one_year_ago = now - datetime.timedelta(days=365)

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return

        try:
            total_members = guild.member_count
        except Exception:
            total_members = 0

        c.execute("""
            SELECT COUNT(*) as count FROM message_log 
            WHERE guild_id = ? AND timestamp >= ?
        """, (guild_id, one_day_ago))
        messages_per_day = c.fetchone()["count"]

        c.execute("""
            SELECT COUNT(DISTINCT user_id) as count FROM message_log 
            WHERE guild_id = ? AND timestamp >= ?
        """, (guild_id, one_day_ago))
        active_members = c.fetchone()["count"]

        new_members_this_week = 0
        for member in guild.members:
            if member.joined_at:
                joined_at = member.joined_at.replace(tzinfo=datetime.timezone.utc) if member.joined_at.tzinfo is None else member.joined_at
                if joined_at >= seven_days_ago:
                    new_members_this_week += 1

        growth_rate = (new_members_this_week / total_members * 100) if total_members > 0 else 0
        engagement = int((active_members / total_members * 100)) if total_members > 0 else 0

        daily_messages = {}
        daily_active_users = {}
        for i in range(7):
            day = (now - datetime.timedelta(days=i)).date()
            start_day = datetime.datetime.combine(day, datetime.time.min, tzinfo=datetime.timezone.utc)
            end_day = datetime.datetime.combine(day, datetime.time.max, tzinfo=datetime.timezone.utc)
            c.execute("""
                SELECT COUNT(*) as count FROM message_log
                WHERE guild_id = ? AND timestamp BETWEEN ? AND ?
            """, (guild_id, start_day, end_day))
            daily_messages[str(day)] = c.fetchone()["count"]
            c.execute("""
                SELECT COUNT(DISTINCT user_id) as count FROM message_log
                WHERE guild_id = ? AND timestamp BETWEEN ? AND ?
            """, (guild_id, start_day, end_day))
            daily_active_users[str(day)] = c.fetchone()["count"]

        c.execute("""
            SELECT AVG(response_time) as avg_rt FROM message_log
            WHERE guild_id = ? AND timestamp >= ? AND response_time IS NOT NULL
        """, (guild_id, one_day_ago))
        avg_response_time = c.fetchone()["avg_rt"]
        if avg_response_time is None:
            avg_response_time = 0

        member_engagement_rate = (active_members / total_members * 100) if total_members > 0 else 0

        c.execute("""
            INSERT INTO analytics_data (
                guild_id, timestamp, total_members, active_members, messages_per_day,
                growth_rate, new_members_this_week, engagement, daily_messages, daily_active_users,
                average_response_time, member_engagement_rate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            guild_id, now, total_members, active_members, messages_per_day,
            growth_rate, new_members_this_week, engagement,
            json.dumps(daily_messages), json.dumps(daily_active_users),
            avg_response_time, member_engagement_rate
        ))
        self.db.commit()

        c.execute("DELETE FROM message_log WHERE timestamp < ?", (one_year_ago,))
        c.execute("DELETE FROM analytics_data WHERE timestamp < ?", (one_year_ago,))
        self.db.commit()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        now = datetime.datetime.now(datetime.timezone.utc)
        response_time = None
        if message.reference and message.reference.resolved:
            referenced: discord.Message = message.reference.resolved
            if isinstance(referenced, discord.Message):
                delta = (message.created_at - referenced.created_at).total_seconds()
                response_time = delta if delta >= 0 else None
        c = self.db.cursor()
        c.execute("""
            INSERT INTO message_log (guild_id, user_id, timestamp, response_time)
            VALUES (?, ?, ?, ?)
        """, (message.guild.id, message.author.id, now, response_time))
        self.db.commit()

        # Trigger analytics update
        await self.update_analytics(message.guild.id)

    @tasks.loop(minutes=10)
    async def data_collection_loop(self):
        c = self.db.cursor()
        c.execute("SELECT guild_id FROM analytics_enabled")
        rows = c.fetchall()
        for row in rows:
            await self.update_analytics(row["guild_id"])

async def setup(bot: commands.Bot):
    await bot.add_cog(AnalyticsCog(bot))
