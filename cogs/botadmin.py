import discord
from discord.ext import commands
from discord.ui import Button, View

class ServerListView(View):
    def __init__(self, pages, interaction):
        super().__init__(timeout=60)
        self.pages = pages
        self.current_page = 0
        self.interaction = interaction
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if self.current_page > 0:
            self.add_item(Button(label="前へ", custom_id="prev", style=discord.ButtonStyle.primary))
        if self.current_page < len(self.pages) - 1:
            self.add_item(Button(label="次へ", custom_id="next", style=discord.ButtonStyle.primary))

    async def interaction_check(self, button_interaction: discord.Interaction) -> bool:
        return button_interaction.user.id == self.interaction.user.id

    async def prev_callback(self, interaction: discord.Interaction):
        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    async def next_callback(self, interaction: discord.Interaction):
        self.current_page = min(len(self.pages) - 1, self.current_page + 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

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
            guilds = list(self.bot.guilds)
            pages = []
            
            # 10サーバーごとにページを作成
            for i in range(0, len(guilds), 10):
                embed = discord.Embed(title=f"参加中のサーバー ({i//10 + 1}/{(len(guilds)-1)//10 + 1}ページ)", 
                                    color=discord.Color.blue())
                
                for guild in guilds[i:i+10]:
                    member_count = len(guild.members)
                    owner = guild.owner
                    created_at = guild.created_at.strftime("%Y-%m-%d")
                    value = f"ID: {guild.id}\nオーナー: {owner}\nメンバー数: {member_count}\n作成日: {created_at}"
                    embed.add_field(name=guild.name, value=value, inline=False)
                
                pages.append(embed)

            view = ServerListView(pages, interaction)
            await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)

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
