import discord
from discord.ext import commands
import matplotlib.pyplot as plt
import numpy as np
import io
import traceback
import random
import os
from dotenv import load_dotenv
from lib.emotion_ai import get_emotion_scores
import matplotlib as mpl
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.font_manager as fm

class EmotionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        load_dotenv()
        self.setup_custom_font()
        self.set_plot_params()

    def setup_custom_font(self):
        custom_font_path = "./assets/fonts/NotoSansJP-VariableFont_wght.ttf"
        if os.path.exists(custom_font_path):
            try:
                fm.fontManager.addfont(custom_font_path)
                font_prop = fm.FontProperties(fname=custom_font_path)
                plt.rcParams['font.family'] = font_prop.get_name()
                plt.rcParams['font.sans-serif'] = [font_prop.get_name()]
                mpl.rcParams['pdf.fonttype'] = 42
                mpl.rcParams['ps.fonttype'] = 42
                mpl.rcParams['font.family'] = font_prop.get_name()
                mpl.rcParams['font.sans-serif'] = [font_prop.get_name()]
            except Exception as e:
                print(f"カスタムフォントの登録に失敗しました: {e}")

    def set_plot_params(self):
        plt.style.use('default')
        plt.rcParams['axes.facecolor'] = '#36393F'
        plt.rcParams['figure.facecolor'] = '#36393F'
        plt.rcParams['axes.edgecolor'] = '#ffffff'
        plt.rcParams['axes.labelcolor'] = 'white'
        plt.rcParams['xtick.color'] = 'white'
        plt.rcParams['ytick.color'] = 'white'

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'ボットの準備完了。ログイン名: {self.bot.user}')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        if message.reference and message.content == "おきもち":
            referenced_msg = await message.channel.fetch_message(message.reference.message_id)
            if not referenced_msg.content:
                await message.reply("テキストメッセージにのみ反応できます。")
                return

            text = referenced_msg.content
            try:
                emotion_scores = get_emotion_scores(text)
                emotion_scores = {k: v for k, v in emotion_scores.items() if k.lower() != 'neutral'}
                if not emotion_scores:
                    await message.reply("感情スコアを取得できませんでした。別のテキストで試してください。")
                    return

                top_emotions = self.get_top_emotions(emotion_scores, 5)
                scaled_emotions = self.scale_emotion_scores(top_emotions)
                fig = self.create_emotion_polygon(scaled_emotions)

                buf = io.BytesIO()
                plt.savefig(buf, format='png', dpi=100)
                buf.seek(0)
                plt.close(fig)

                file = discord.File(buf, filename='emotions.png')
                embed = discord.Embed(title="感情分析結果", description=f'メッセージ: "{text}"', color=discord.Color.blue())
                embed.set_image(url="attachment://emotions.png")
                embed.set_footer(text="Transplanted by tako")
                await message.reply(embed=embed, file=file)
            except KeyError as ke:
                print(f"キーエラーが発生しました: {ke}")
                traceback.print_exc()
                await message.reply(f"感情解析中にキーエラーが発生しました: {ke}")
            except Exception as e:
                print(f"エラーが発生しました: {e}")
                traceback.print_exc()
                await message.reply(f"処理中にエラーが発生しました: {e}")

    def get_top_emotions(self, emotion_scores, n=5):
        if not emotion_scores:
            raise ValueError("感情スコアが空です")

        filtered_scores = {k: v for k, v in emotion_scores.items() if k.lower() != 'neutral'}
        non_zero_scores = {k: v for k, v in filtered_scores.items() if v > 0.001}
        if not non_zero_scores:
            non_zero_scores = filtered_scores

        top_n = sorted(non_zero_scores.items(), key=lambda x: x[1], reverse=True)[:min(n, len(non_zero_scores))]
        if not top_n:
            raise ValueError("有効な感情スコアがありません")

        return dict(top_n)

    def scale_emotion_scores(self, scores):
        if not scores:
            return {}

        max_val = max(scores.values())
        if max_val > 0:
            return {k: v / max_val for k, v in scores.items()}

        return scores

    def create_emotion_polygon(self, emotion_scores):
        if not emotion_scores:
            raise ValueError("感情スコアが空です")

        emotion_scores = {k: v for k, v in emotion_scores.items() if k.lower() != 'neutral'}
        emotion_names_ja = {
            "amaze": "Amazement",
            "anger": "Anger",
            "dislike": "Dislike",
            "excite": "Excitement",
            "fear": "Fear",
            "joy": "Joy",
            "like": "Like",
            "relief": "Relief",
            "sad": "Sadness",
            "shame": "Shame"
        }

        japanese_scores = {emotion_names_ja.get(k, k): v for k, v in emotion_scores.items()}
        items = list(japanese_scores.items())
        random.shuffle(items)
        emotion_scores = dict(items)

        categories = list(emotion_scores.keys())
        values = [emotion_scores[cat] for cat in categories]

        if len(categories) < 1:
            raise ValueError("表示する感情がありません")

        num_categories = len(categories)
        if num_categories == 1:
            fig, ax = plt.subplots(figsize=(12, 8))
            color = '#5865F2'
            bar = ax.bar([categories[0]], [values[0]], width=0.5, color=color, alpha=0.9)
            ax.set_ylim(0, 1.1)
            for spine in ax.spines.values():
                spine.set_color('#ffffff')
            plt.title(f"感情分析結果: {categories[0]}", fontsize=18, color='white', fontweight='bold')
            ax.text(0, values[0] + 0.05, f"{values[0]:.2f}", ha='center', fontsize=14, color='#7289DA')
            ax.yaxis.grid(True, linestyle='-', alpha=0.7, color='white', linewidth=1.5)
            ax.set_facecolor('#36393F')
            fig.patch.set_facecolor('#36393F')
            return fig

        angles = np.linspace(0, 2 * np.pi, num_categories, endpoint=False).tolist()
        values += values[:1]
        angles += angles[:1]

        fig, ax = plt.subplots(figsize=(12, 9), subplot_kw={'projection': 'polar'})
        ax.set_facecolor('#36393F')
        fig.patch.set_facecolor('#36393F')
        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)

        colors = [(0.35, 0.4, 0.95, 0.7), (0.45, 0.6, 0.95, 0.8), (0.55, 0.7, 0.95, 0.9)]
        cmap = LinearSegmentedColormap.from_list('custom_cmap', colors, N=256)

        line = ax.plot(angles, values, linewidth=4, linestyle='-', color='#7289DA')[0]
        ax.fill(angles, values, alpha=0.7, color='#5865F2')
        ax.scatter(angles[:-1], values[:-1], s=180, c='#40E0D0', alpha=1.0, edgecolors='#00BFFF', linewidth=3, zorder=10)
        ax.grid(True, color='white', alpha=0.7, linestyle='-', linewidth=1.5)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=24)
        ax.set_ylim(0, 1)
        ax.set_rticks([0.25, 0.5, 0.75, 1.0])
        gridlines = ax.yaxis.get_gridlines()
        for gl in gridlines:
            gl.set_color('white')
            gl.set_alpha(0.6)
            gl.set_linestyle('-')
            gl.set_linewidth(1.5)
        ax.set_yticklabels([])
        ax.tick_params(labelsize=40, colors='white', grid_color='white')
        ax.spines['polar'].set_visible(False)

        return fig

async def setup(bot):
    await bot.add_cog(EmotionCog(bot))
