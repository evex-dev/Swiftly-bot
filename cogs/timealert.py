import discord
from discord.ext import commands, tasks
import sqlite3
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

class TimeAlert(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect("timealerts.db")
        self.cursor = self.conn.cursor()
        self.cursor.execute("""CREATE TABLE IF NOT EXISTS alerts
                               (channel_id INTEGER, alert_time TEXT)""")
        self.conn.commit()
        self.check_alerts.start()

    @commands.has_permissions(administrator=True)
    @discord.app_commands.command(name="time-signal", description="指定したチャンネルと時間に時報を設定します")
    async def time_signal(self, interaction: discord.Interaction, channel: discord.TextChannel, time: str) -> None:
        try:
            datetime.strptime(time, "%H:%M")
        except ValueError:
            await interaction.response.send_message("時間のフォーマットが正しくありません。正しいフォーマットは HH:MM です。", ephemeral=False)
            return

        self.cursor.execute("SELECT COUNT(*) FROM alerts WHERE channel_id = ?", (channel.id,))
        count = self.cursor.fetchone()[0]
        if count >= 3:
            await interaction.response.send_message("このチャンネルにはすでに3つの時報が設定されています。", ephemeral=False)
            return

        self.cursor.execute("INSERT INTO alerts (channel_id, alert_time) VALUES (?, ?)", (channel.id, time))
        self.conn.commit()
        await interaction.response.send_message(f"{channel.mention} に {time} の時報を設定しました。/remove-time-signalで、登録を解除できます。", ephemeral=False)

    @commands.has_permissions(administrator=True)
    @discord.app_commands.command(name="remove-time-signal", description="指定したチャンネルの時報を解除します")
    async def remove_time_signal(self, interaction: discord.Interaction, channel: discord.TextChannel, time: str) -> None:
        try:
            datetime.strptime(time, "%H:%M")
        except ValueError:
            await interaction.response.send_message("時間のフォーマットが正しくありません。正しいフォーマットは HH:MM です。", ephemeral=False)
            return

        self.cursor.execute("DELETE FROM alerts WHERE channel_id = ? AND alert_time = ?", (channel.id, time))
        self.conn.commit()
        await interaction.response.send_message(f"{channel.mention} の {time} の時報を解除しました。", ephemeral=False)

    @tasks.loop(minutes=1)
    async def check_alerts(self):
        now = datetime.now(JST).strftime("%H:%M")
        self.cursor.execute("SELECT channel_id FROM alerts WHERE alert_time = ?", (now,))
        channels = self.cursor.fetchall()
        for channel_id in channels:
            channel = self.bot.get_channel(channel_id[0])
            if channel:
                await channel.send(f"時報です！現在の時刻は {now} です。")

    @check_alerts.before_loop
    async def before_check_alerts(self):
        await self.bot.wait_until_ready()

    def cog_unload(self):
        self.check_alerts.cancel()
        self.conn.close()

async def setup(bot):
    await bot.add_cog(TimeAlert(bot))
