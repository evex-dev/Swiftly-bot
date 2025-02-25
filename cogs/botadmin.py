import discord
from discord.ext import commands
from discord.ui import View, Button

class BotAdmin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def cog_check(self, ctx):
        return ctx.author.id == 1241397634095120438

    @discord.app_commands.command(name="botadmin", description="Bot管理コマンド")
    async def botadmin_command(self, interaction: discord.Interaction, option: str):
        if interaction.user.id != 1241397634095120438:
            embed = discord.Embed(title="エラー", description="このコマンドを使用する権限がありません。", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if option == "servers":
            embeds = []
            embed = discord.Embed(title="参加中のサーバー", color=discord.Color.blue())
            for i, guild in enumerate(self.bot.guilds):
                member_count = len(guild.members)
                owner = guild.owner
                created_at = guild.created_at.strftime("%Y-%m-%d")
                value = f"ID: {guild.id}\nオーナー: {owner}\nメンバー数: {member_count}\n作成日: {created_at}"
                embed.add_field(name=guild.name, value=value, inline=False)
                if (i + 1) % 10 == 0 or i == len(self.bot.guilds) - 1:
                    embeds.append(embed)
                    embed = discord.Embed(title="参加中のサーバー (続き)", color=discord.Color.blue())
            await self.send_paginated_response(interaction, embeds)
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
            embed = discord.Embed(title="デバッグ情報", description=debug_info, color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        elif option.startswith("say:"):
            message = option[4:]
            await interaction.channel.send(message)
            embed = discord.Embed(title="Sayコマンド", description="sayを出力しました", color=discord.Color.green())
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(title="エラー", description="無効なオプションです。", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def send_paginated_response(self, interaction, embeds):
        current_page = 0

        async def update_message():
            for item in view.children:
                if isinstance(item, Button):
                    item.disabled = False
            if current_page == 0:
                view.children[0].disabled = True
            if current_page == len(embeds) - 1:
                view.children[1].disabled = True
            await interaction.edit_original_response(embed=embeds[current_page], view=view)

        async def next_page(interaction):
            nonlocal current_page
            current_page += 1
            await update_message()

        async def previous_page(interaction):
            nonlocal current_page
            current_page -= 1
            await update_message()

        view = View()
        view.add_item(Button(label="前へ", style=discord.ButtonStyle.primary, disabled=True, custom_id="previous_page"))
        view.add_item(Button(label="次へ", style=discord.ButtonStyle.primary, custom_id="next_page"))

        async def button_callback(interaction):
            if interaction.data["custom_id"] == "previous_page":
                await previous_page(interaction)
            elif interaction.data["custom_id"] == "next_page":
                await next_page(interaction)
            await interaction.response.defer()  # インタラクションに対する応答を行う

        view.children[0].callback = button_callback
        view.children[1].callback = button_callback

        await interaction.response.send_message(embed=embeds[current_page], view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(BotAdmin(bot))
