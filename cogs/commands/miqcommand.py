import discord
from discord import app_commands
from discord.ext import commands
import os
import tempfile
import io
import aiohttp
from PIL import Image
from lib.miq import MakeItQuote

class MiqCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.miq = MakeItQuote()  # MakeItQuoteジェネレーターを初期化
    
    @app_commands.command(name="miq", description="指定したユーザーと内容でmiq画像を生成します")
    async def miq_command(self, interaction: discord.Interaction, user: discord.User, content: str):
        # 画像生成に時間がかかる可能性があるため、レスポンスを遅延させる
        await interaction.response.defer()
        
        # ユーザーの表示名を取得
        author_name = user.display_name
        
        try:
            # ユーザーのアバター画像を取得（サイズを大きめに指定）
            avatar_url = user.display_avatar.with_size(512).url
            
            # アバター画像をダウンロード
            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url) as resp:
                    if resp.status != 200:
                        raise Exception(f"アバター画像の取得に失敗しました。ステータスコード: {resp.status}")
                    avatar_data = await resp.read()
            
            # バイナリデータから画像オブジェクトを作成
            avatar_image = Image.open(io.BytesIO(avatar_data))
            
            # 画像を保存する一時ファイルを作成
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                temp_path = tmp.name
            
            # 引用画像を生成（ユーザーのアバターを背景に使用）
            self.miq.save_quote(
                quote=content,
                author=author_name,
                output_path=temp_path,
                background_image=avatar_image
            )
            
            # 画像ファイルを読み込む
            with open(temp_path, 'rb') as f:
                image_data = io.BytesIO(f.read())
            
            # 送信するファイルを作成
            file = discord.File(image_data, filename="quote.png")
            
            # 画像を含むレスポンスを送信
            await interaction.followup.send(file=file)
            
            # 一時ファイルを削除
            os.unlink(temp_path)
        
        except Exception as e:
            await interaction.followup.send(f"エラーが発生しました: {str(e)}", ephemeral=True)
    
async def setup(bot):
    await bot.add_cog(MiqCommand(bot))
