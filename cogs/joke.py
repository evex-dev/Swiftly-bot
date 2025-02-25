import json
import math
import random
import time

import discord
from discord.ext import commands


prog_langs = [
    "C++", "Go", "Java", "JavaScript", "Kotlin",
    "PHP", "Python", "Ruby", "Rust", "Swift", "TypeScript"
]

nice_lang = {
    "C++": "Rust",
    "Go": "Java",
    "Java": "TypeScript",
    "JavaScript": "Go",
    "Kotlin": "PHP",
    "PHP": "Ruby",
    "Python": "JavaScript",
    "Ruby": "C++",
    "Rust": "Python",
    "Swift": "Kotlin",
    "TypeScript": "Swift"
}

bad_lang = {
    "C++": "Ruby",
    "Go": "JavaScript",
    "Java": "Go",
    "JavaScript": "Python",
    "Kotlin": "Swift",
    "PHP": "Kotlin",
    "Python": "Rust",
    "Ruby": "PHP",
    "Rust": "C++",
    "Swift": "TypeScript",
    "TypeScript": "Java"
}

with open("./data/joke.json", "r", encoding="utf-8") as f:
    data = json.load(f)

cpus = data.get("cpus", [])
gpus = data.get("gpus", [])


class LoveCalculator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="love-calculator", description="2人のユーザーを選択して愛の相性を計算します")
    async def love_calculator(self, interaction: discord.Interaction, user1: discord.User, user2: discord.User):
        if user1 == user2:
            embed = discord.Embed(title="💖 Love Calculator 💖", color=discord.Color.pink())
            embed.add_field(name="メッセージ", value="1人目と2人目で同じユーザーが選択されています。", inline=False)
            await interaction.response.send_message(embed=embed)
        else:
            name1 = user1.name
            name2 = user2.name
            love_score = self.K7LoveCalc(name1, name2)
            message = self.get_love_message(name1, name2, love_score[0], love_score[1], love_score[2])
            embed = discord.Embed(title="💖 Love Calculator 💖", color=discord.Color.pink())
            embed.add_field(name="ユーザー1", value=name1, inline=True)
            embed.add_field(name="ユーザー2", value=name2, inline=True)
            embed.add_field(name="相性結果", value=f"**{name1} → {name2}**\n好感度：{love_score[1]}%\n**{name2} → {name1}**\n好感度：{love_score[2]}%", inline=False)
            embed.add_field(name="総合相性（好感度平均）", value=f"{love_score[0]}%", inline=False)
            embed.add_field(name="メッセージ", value=message, inline=False)
            await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(name="fantasy-status", description="特定の人の装備品、攻撃力、守備力、体力を表示する")
    async def fantasy_status(self, interaction: discord.Interaction, user: discord.User):
        name = user.name
        stats = self.K7StatsCalc(name)
        embed = discord.Embed(title="⚔ 異世界ステータスジェネレーター ⚔", color=discord.Color.blue())
        embed.add_field(name="名前", value=name, inline=False)
        embed.add_field(name="装備", value=stats[0], inline=True)
        embed.add_field(name="攻撃力", value=stats[1], inline=True)
        embed.add_field(name="守備力", value=stats[2], inline=True)
        embed.add_field(name="最大HP", value=stats[3], inline=True)
        embed.add_field(name="相性の良い言語（攻撃力 x1.2）", value=nice_lang[stats[0]], inline=True)
        embed.add_field(name="相性の悪い言語（攻撃力 x0.87）", value=bad_lang[stats[0]], inline=True)
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(name="your-cpu-gpu", description="特定の人をCPU、GPUで例えると...？")
    async def your_cpu(self, interaction: discord.Interaction, user: discord.User):
        try:
            name = user.name
            random.seed(name)
            cpu = random.choice(cpus)
            gpu = random.choice(gpus)
            embed = discord.Embed(title="💻 "+name+"をCPU、GPUで例えると...？ 🖥", color=discord.Color.blue())
            embed.add_field(name="CPU", value=cpu, inline=True)
            embed.add_field(name="GPU", value=gpu, inline=True)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"エラーが発生しました: {e}")

    @discord.app_commands.command(name="versus", description="fantasy-statusのステータスをもとに対戦させます。ステータスは固定ですがそれ以外はランダム。")
    async def versus(self, interaction: discord.Interaction, user1: discord.User, user2: discord.User):
        try:
            if user1 == user2:
                embed = discord.Embed(title="⚔ Versus ⚔", color=discord.Color.dark_red())
                embed.add_field(name="メッセージ", value="1人目と2人目で同じユーザーが選択されています。", inline=False)
                await interaction.response.send_message(embed=embed)
            else:
                random.seed(time.time())
                name1 = user1.name
                name2 = user2.name
                stats1 = self.K7StatsCalc(name1)
                stats2 = self.K7StatsCalc(name2)
                hp1 = stats1[3]
                hp2 = stats2[3]
                embed = discord.Embed(title="⚔ Versus ⚔", color=discord.Color.dark_red())
                turn = random.randint(0, 1)
                for _ in range(20):
                    crit = False
                    crit_chance = 0.1
                    if turn:
                        turn_atk = stats1[1]
                        turn_def = stats2[2]
                        if nice_lang[stats1[0]] == stats2[0]:
                            crit_chance = 0.2
                            turn_atk *= 1.2
                        elif bad_lang[stats1[0]] == stats2[0]:
                            crit_chance = 0.05
                            turn_atk *= 0.87
                        if random.random() <= crit_chance:
                            turn_atk *= 2
                            turn_def = 0
                            crit = True
                        damage = math.floor(max(0, turn_atk*(1-(turn_def/100))))
                        hp2 -= damage
                        if crit:
                            embed.add_field(name=f"{name1}のターン", value=f"クリティカルヒット！{name2}に{damage}のダメージ！残りHP：{hp2}", inline=False)
                        else:
                            embed.add_field(name=f"{name1}のターン", value=f"{name2}に{damage}のダメージ！残りHP：{hp2}", inline=False)
                        if hp2 <= 0:
                            embed.add_field(name=f"{name1}の勝利！", value=f"{name1}は{hp1}の体力を残して勝利した！", inline=False)
                            break
                    else:
                        turn_atk = stats2[1]
                        crit_chance = 0.1
                        turn_def = stats1[2]
                        if nice_lang[stats2[0]] == stats1[0]:
                            crit_chance = 0.2
                            turn_atk *= 1.2
                        elif bad_lang[stats2[0]] == stats1[0]:
                            crit_chance = 0.05
                            turn_atk *= 0.87
                        if random.random() <= crit_chance:
                            turn_atk *= 2
                            turn_def = 0
                            crit = True
                        damage = math.floor(max(0, turn_atk*(1-(turn_def/100))))
                        hp1 -= damage
                        if crit:
                            embed.add_field(name=f"{name2}のターン", value=f"クリティカルヒット！{name1}に{damage}のダメージ！残りHP：{hp1}", inline=False)
                        else:
                            embed.add_field(name=f"{name2}のターン", value=f"{name1}に{damage}のダメージ！残りHP：{hp1}", inline=False)
                        if hp1 <= 0:
                            embed.add_field(name=f"{name2}の勝利！", value=f"{name2}は{hp2}の体力を残して勝利した！", inline=False)
                            break
                    turn = not turn
                if hp1 > 0 and hp2 > 0:
                    embed.add_field(name="引き分け", value=f"20ターン以内に戦いが終わらなかった。\n{name1}の体力：{hp1}\n{name2}の体力：{hp2}", inline=False)
                await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"エラーが発生しました: {e}")

    def K7LoveCalc(self, name1: str, name2: str):
        # Use only day of the current date (1～31) as a slight influence
        current_day = int(time.strftime("%d"))
        if name1 > name2:
            base = name1 + name2
        else:
            base = name2 + name1
        # The date adds only a small offset to the seed
        seed_value = hash(base) + current_day
        random.seed(seed_value)

        user1_to_user2_friend = random.randint(0, 100)
        user2_to_user1_friend = random.randint(0, 100)
        love_score = (user1_to_user2_friend + user2_to_user1_friend) // 2
        if name1 > name2:
            return [love_score, user1_to_user2_friend, user2_to_user1_friend]

        return [love_score, user2_to_user1_friend, user1_to_user2_friend]

    def K7StatsCalc(self, name: str):
        # ユーザー名のハッシュ値をシードにして乱数生成
        random.seed(hash(name))
        # 装備はプログラミング言語リストからランダムに選択
        equip = random.choice(prog_langs)
        # 攻撃力は50～150の範囲
        attack = random.randint(50, 150)
        # 守備力は0～100の範囲
        defense = random.randint(0, 100)
        # 最大HPは200～1000の範囲
        max_hp = random.randint(200, 1000)
        return [equip, attack, defense, max_hp]

    def get_love_message(self, user1_name, user2_name, score, user1_to_user2, user2_to_user1):
        if user1_to_user2 - user2_to_user1 > 70:
            return user1_name + "よ、諦めろ。"
        elif user2_to_user1 - user1_to_user2 > 70:
            return user2_name + "よ、諦めろ。"
        elif abs(user1_to_user2 - user2_to_user1) > 50:
            return "視界に入れてない可能性があります。"
        elif abs(user1_to_user2 - user2_to_user1) > 30:
            return "片思いの可能性があります。💔"
        elif score > 80:
            return "素晴らしい相性です！💞"
        elif score > 60:
            return "とても良い相性です！😊"
        elif score > 40:
            return "まあまあの相性です。🙂"
        elif score > 20:
            return "ちょっと微妙かも...😕"

        return "残念ながら、相性はあまり良くないようです。😢"


async def setup(bot):
    await bot.add_cog(LoveCalculator(bot))
