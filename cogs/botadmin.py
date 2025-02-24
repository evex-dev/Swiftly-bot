import discord
from discord.ext import commands


class BotAdmin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def cog_check(self, ctx):
        return ctx.author.id == 1241397634095120438

    @discord.app_commands.command(name="botadmin", description="Bot管理コマンド")
    async def botadmin_command(self, interaction: discord.Interaction, option: str):
        if interaction.user.id != 1241397634095120438:
            embed = discord.Embed(
                title="エラー", description="このコマンドを使用する権限がありません。", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if option == "servers":
            embed = discord.Embed(title="参加中のサーバー", color=discord.Color.blue())
            for guild in self.bot.guilds:
                member_count = len(guild.members)
                owner = guild.owner
                created_at = guild.created_at.strftime("%Y-%m-%d")
                value = f"ID: {guild.id}\nオーナー: {owner}\nメンバー数: {member_count}\n作成日: {created_at}"
                embed.add_field(name=guild.name, value=value, inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        elif option == "debug":
            cogs = ", ".join(self.bot.cogs.keys())
            shard_info = (
                f"Shard ID: {self.bot.shard_id}\n"
                f"Shard Count: {self.bot.shard_count}\n"
            ) if self.bot.shard_id is not None else "Sharding is not enabled."
            debug_info = (
                f"Bot Name: {self.bot.user.name}\n"
                f"Bot ID: {self.bot.user.id}\n"
                f"Latency: {self.bot.latency * 1000:.2f} ms\n"
                f"Guild Count: {len(self.bot.guilds)}\n"
                f"Loaded Cogs: {cogs}\n"
                f"{shard_info}"
            )
            embed = discord.Embed(
                title="デバッグ情報", description=debug_info, color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        elif option.startswith("say:"):
            message = option[4:]
            await interaction.channel.send(message)
            embed = discord.Embed(
                title="Sayコマンド", description="sayを出力しました", color=discord.Color.green())
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="エラー", description="無効なオプションです。", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(BotAdmin(bot))
