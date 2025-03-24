import discord
from discord.ext import commands, tasks
import datetime
import os
import json

import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont  # Pillowをインポート

class LatencyGraph(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = 'public/latency_data.json'
        self.load_data()
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

    @tasks.loop(hours=1)
    async def update_graph(self):
        # 最新のレイテンシを取得
        latency = self.bot.latency * 1000  # Convert to milliseconds
        self.latencies.append(latency)
        self.timestamps.append(datetime.datetime.now())

        # Keep only the last 7 days of data
        one_week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        self.latencies = [lat for lat, ts in zip(self.latencies, self.timestamps) if ts > one_week_ago]
        self.timestamps = [ts for ts in self.timestamps if ts > one_week_ago]

        # データを保存
        self.save_data()

        # Sort the data by timestamps
        sorted_data = sorted(zip(self.timestamps, self.latencies))
        if sorted_data:  # データが空でないことを確認
            self.timestamps, self.latencies = zip(*sorted_data)

            # Plot the graph
            plt.figure(figsize=(10, 5))
            plt.plot(self.timestamps, self.latencies, marker='o')
            plt.title('Discord Latency Over the Last Week', color='white')
            plt.xlabel('Time')
            plt.ylabel('Latency (ms)')
            plt.grid(True)
            plt.xticks(rotation=45)
            plt.tight_layout()

            # Save the graph
            if not os.path.exists('public'):
                os.makedirs('public')
            plt.savefig('public/graph.png')
            plt.close()

            # Add the last update time using Pillow
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