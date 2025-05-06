import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput

class VulnerabilityReportModal(Modal, title="脆弱性報告フォーム"):
    vulnerability_title = TextInput(
        label="脆弱性のタイトル",
        placeholder="簡潔に脆弱性の内容を表すタイトルを入力してください",
        required=True,
        max_length=100
    )
    
    vulnerability_description = TextInput(
        label="脆弱性の詳細",
        placeholder="詳細な脆弱性の内容を記入してください",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=4000
    )
    
    reproduction_steps = TextInput(
        label="再現手順",
        placeholder="この脆弱性を再現するための手順を記入してください",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=4000
    )
    
    additional_info = TextInput(
        label="追加情報",
        placeholder="その他の情報（ブラウザ、OS、デバイスなど）があれば記入してください",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=1000
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # 脆弱性報告を送信するサーバーとチャンネルのID
        report_server_id = 1270365453910540298
        report_channel_id = 1356663401111359549
        
        # 報告用埋め込みの作成
        embed = discord.Embed(
            title=f"脆弱性報告: {self.vulnerability_title.value}",
            color=discord.Color.red()
        )
        
        embed.add_field(name="報告者", value=f"{interaction.user.name} (ID: {interaction.user.id})", inline=False)
        embed.add_field(name="脆弱性の詳細", value=self.vulnerability_description.value, inline=False)
        embed.add_field(name="再現手順", value=self.reproduction_steps.value, inline=False)
        
        if self.additional_info.value:
            embed.add_field(name="追加情報", value=self.additional_info.value, inline=False)
        
        # 報告が行われたサーバーとチャンネルの情報を追加
        guild_name = interaction.guild.name if interaction.guild else "DMチャンネル"
        guild_id = interaction.guild.id if interaction.guild else "なし"
        embed.add_field(name="報告元", value=f"サーバー: {guild_name} (ID: {guild_id})", inline=False)
        
        embed.set_footer(text=f"報告日時: {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
        # 指定されたチャンネルに報告を送信
        try:
            report_server = interaction.client.get_guild(report_server_id)
            if report_server:
                report_channel = report_server.get_channel(report_channel_id)
                if report_channel:
                    await report_channel.send(embed=embed)
                    await interaction.response.send_message("脆弱性の報告ありがとうございます。報告内容は開発チームに送信されました。", ephemeral=True)
                    return
            
            # チャンネルが見つからない場合
            await interaction.response.send_message("報告の送信中にエラーが発生しました。開発者に連絡してください。", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"エラーが発生しました: {str(e)}", ephemeral=True)
    
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"フォームの送信中にエラーが発生しました: {str(error)}", ephemeral=True)

class VulnerabilityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="vuln", description="ボットの脆弱性を報告します")
    async def vulnerability_report(self, interaction: discord.Interaction):
        # プライバシーモードのユーザーを無視
        privacy_cog = self.bot.get_cog("Privacy")
        if privacy_cog and privacy_cog.is_private_user(interaction.user.id):
            return

        modal = VulnerabilityReportModal()
        await interaction.response.send_modal(modal)

async def setup(bot):
    await bot.add_cog(VulnerabilityCog(bot))