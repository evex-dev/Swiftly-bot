import discord
from discord.ext import commands, tasks
import datetime
import os
import json
import asyncio

import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont  # Pillowをインポート

class LatencyGraph(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = 'public/latency_data.json'
        self.load_data()
        self.last_update = None
        self.update_graph.start()

    def load_data(self):
        """JSONファイルからデータを読み込む"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.timestamps = [datetime.datetime.fromisoformat(ts) for ts in data['timestamps']]
                    self.latencies = data['latencies']
            else:
                self.latencies = []
                self.timestamps = []
                # 公開ディレクトリを作成
                if not os.path.exists('public'):
                    os.makedirs('public')
        except Exception as e:
            print(f"データの読み込み中にエラーが発生しました: {e}")
            self.latencies = []
            self.timestamps = []

    def save_data(self):
        """データをJSONファイルに保存する"""
        try:
            data = {
                'timestamps': [ts.isoformat() for ts in self.timestamps],
                'latencies': self.latencies
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"データの保存中にエラーが発生しました: {e}")

    @tasks.loop(minutes=5)
    async def update_graph(self):
        # 前回の更新から1時間経過したかチェック
        current_time = datetime.datetime.now()
        if self.last_update is None or (current_time - self.last_update).total_seconds() >= 3600:
            # 最新のレイテンシを取得
            latency = self.bot.latency * 1000  # Convert to milliseconds
            self.latencies.append(latency)
            self.timestamps.append(current_time)

            # Keep only the last 7 days of data
            one_week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
            self.latencies = [lat for lat, ts in zip(self.latencies, self.timestamps) if ts > one_week_ago]
            self.timestamps = [ts for ts in self.timestamps if ts > one_week_ago]

            # データを保存
            self.save_data()

            # グラフを更新
            await self.generate_graph()
            
            # 最終更新時刻を記録
            self.last_update = current_time
            print(f"グラフを更新しました: {self.last_update.strftime('%Y-%m-%d %H:%M:%S')}")

    @update_graph.before_loop
    async def before_update_graph(self):
        await self.bot.wait_until_ready()
        # Botの起動直後に最初のデータポイントを追加
        if not self.latencies or not self.timestamps:
            latency = self.bot.latency * 1000
            self.latencies.append(latency)
            self.timestamps.append(datetime.datetime.now())
            self.save_data()
            await self.generate_graph()
            self.last_update = datetime.datetime.now()

    async def generate_graph(self):
        """グラフを生成して保存する"""
        if not self.latencies or not self.timestamps:
            return
            
        # データを時間順にソート
        sorted_data = sorted(zip(self.timestamps, self.latencies))
        self.timestamps, self.latencies = zip(*sorted_data)

        # グラフをプロット
        plt.figure(figsize=(10, 5))
        plt.plot(self.timestamps, self.latencies, marker='o')
        plt.title('Discord Latency Over the Last Week', color='white')
        plt.xlabel('Time')
        plt.ylabel('Latency (ms)')
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()

        # グラフを保存
        if not os.path.exists('public'):
            os.makedirs('public')
        plt.savefig('public/graph.png')
        plt.close()

        # 最終更新時刻を画像に追加
        last_update = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        img = Image.open('public/graph.png')
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        text = f'Last updated: {last_update}'
        textbbox = draw.textbbox((0, 0), text, font=font)
        textwidth, textheight = textbbox[2] - textbbox[0], textbbox[3] - textbbox[1]
        width, height = img.size
        x = width - textwidth - 10
        y = height - textheight - 10
        draw.text((x, y), text, font=font, fill='white')
        img.save('public/graph.png')

async def setup(bot):
    await bot.add_cog(LatencyGraph(bot))