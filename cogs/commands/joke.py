import json
import math
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Final, Dict, List, Tuple
import logging

import discord
from discord.ext import commands


PROG_LANGS: Final[List[str]] = [
    "C++", "Go", "Java", "JavaScript", "Kotlin",
    "PHP", "Python", "Ruby", "Rust", "Swift", "TypeScript"
]

NICE_LANG: Final[Dict[str, str]] = {
    "C++": "Rust", "Go": "Java", "Java": "TypeScript",
    "JavaScript": "Go", "Kotlin": "PHP", "PHP": "Ruby",
    "Python": "JavaScript", "Ruby": "C++", "Rust": "Python",
    "Swift": "Kotlin", "TypeScript": "Swift"
}

BAD_LANG: Final[Dict[str, str]] = {
    "C++": "Ruby", "Go": "JavaScript", "Java": "Go",
    "JavaScript": "Python", "Kotlin": "Swift", "PHP": "Kotlin",
    "Python": "Rust", "Ruby": "PHP", "Rust": "C++",
    "Swift": "TypeScript", "TypeScript": "Java"
}

BATTLE_CONFIG: Final[dict] = {
    "max_turns": 20,
    "crit_rates": {
        "normal": 0.1,
        "advantage": 0.2,
        "disadvantage": 0.05
    },
    "damage_multipliers": {
        "advantage": 1.2,
        "disadvantage": 0.87,
        "critical": 2.0
    }
}

LOVE_MESSAGES: Final[Dict[str, str]] = {
    "one_sided_high": "{}よ、諦めろ。",
    "one_sided_medium": "視界に入れてない可能性があります。",
    "one_sided_low": "片思いの可能性があります。💔",
    "mutual_excellent": "素晴らしい相性です！💞",
    "mutual_good": "とても良い相性です！😊",
    "mutual_average": "まあまあの相性です。🙂",
    "mutual_poor": "ちょっと微妙かも...😕",
    "mutual_bad": "残念ながら、相性はあまり良くないようです。😢"
}

logger = logging.getLogger(__name__)

class BattleSystem:
    """戦闘システムを管理するクラス"""

    def __init__(
        self,
        attacker: Tuple[str, List],
        defender: Tuple[str, List]
    ) -> None:
        self.attacker_name, self.attacker_stats = attacker
        self.defender_name, self.defender_stats = defender
        self.turn_log = []

    def calculate_damage(
        self,
        atk: int,
        def_: int,
        attacker_lang: str,
        defender_lang: str
    ) -> Tuple[int, bool]:
        crit_rate = BATTLE_CONFIG["crit_rates"]["normal"]
        damage_mult = 1.0

        if NICE_LANG[attacker_lang] == defender_lang:
            crit_rate = BATTLE_CONFIG["crit_rates"]["advantage"]
            damage_mult = BATTLE_CONFIG["damage_multipliers"]["advantage"]
        elif BAD_LANG[attacker_lang] == defender_lang:
            crit_rate = BATTLE_CONFIG["crit_rates"]["disadvantage"]
            damage_mult = BATTLE_CONFIG["damage_multipliers"]["disadvantage"]

        is_crit = random.random() <= crit_rate
        if is_crit:
            damage_mult = BATTLE_CONFIG["damage_multipliers"]["critical"]
            def_ = 0

        damage = math.floor(max(0, atk * damage_mult * (1 - (def_ / 100))))
        return damage, is_crit

class JokeCommands(commands.Cog):
    """ジョーク系コマンドを提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._load_data()

    def _load_data(self) -> None:
        """データファイルを読み込む"""
        try:
            with open(Path("data/joke.json"), encoding="utf-8") as f:
                data = json.load(f)
                self.cpus = data.get("cpus", [])
                self.gpus = data.get("gpus", [])
        except Exception as e:
            logger.error("Error loading joke data: %s", e, exc_info=True)
            self.cpus = []
            self.gpus = []

    def _create_love_embed(
        self,
        user1: discord.User,
        user2: discord.User,
        scores: List[int]
    ) -> discord.Embed:
        """Love Calculator用のEmbedを作成"""
        embed = discord.Embed(
            title="💖 Love Calculator 💖",
            color=discord.Color.pink()
        )
        embed.add_field(name="ユーザー1", value=user1.name, inline=True)
        embed.add_field(name="ユーザー2", value=user2.name, inline=True)
        embed.add_field(
            name="相性結果",
            value=(
                f"**{user1.name} → {user2.name}**\n"
                f"好感度：{scores[1]}%\n"
                f"**{user2.name} → {user1.name}**\n"
                f"好感度：{scores[2]}%"
            ),
            inline=False
        )
        embed.add_field(
            name="総合相性（好感度平均）",
            value=f"{scores[0]}%",
            inline=False
        )
        embed.add_field(
            name="メッセージ",
            value=self._get_love_message(
                user1.name, user2.name,
                scores[0], scores[1], scores[2]
            ),
            inline=False
        )
        return embed

    def _create_status_embed(
        self,
        user: discord.User,
        stats: List
    ) -> discord.Embed:
        """ステータス表示用のEmbedを作成"""
        embed = discord.Embed(
            title="⚔ 異世界ステータスジェネレーター ⚔",
            color=discord.Color.blue()
        )
        embed.add_field(name="名前", value=user.name, inline=False)
        embed.add_field(name="装備", value=stats[0], inline=True)
        embed.add_field(name="攻撃力", value=stats[1], inline=True)
        embed.add_field(name="守備力", value=stats[2], inline=True)
        embed.add_field(name="最大HP", value=stats[3], inline=True)
        embed.add_field(
            name="相性の良い言語（攻撃力 x1.2）",
            value=NICE_LANG[stats[0]],
            inline=True
        )
        embed.add_field(
            name="相性の悪い言語（攻撃力 x0.87）",
            value=BAD_LANG[stats[0]],
            inline=True
        )
        return embed

    def _calculate_love_score(
        self,
        name1: str,
        name2: str
    ) -> List[int]:
        current_day = datetime.now().day
        base = max(name1, name2) + min(name1, name2)
        seed_value = hash(base) + current_day
        random.seed(seed_value)

        score1 = random.randint(0, 100)
        score2 = random.randint(0, 100)
        total = (score1 + score2) // 2

        return [
            total,
            score1 if name1 > name2 else score2,
            score2 if name1 > name2 else score1
        ]

    def _calculate_stats(self, name: str) -> List:
        """ユーザーのステータスを計算"""
        random.seed(hash(name))
        return [
            random.choice(PROG_LANGS),
            random.randint(50, 150),
            random.randint(0, 100),
            random.randint(200, 1000)
        ]

    def _get_love_message(
        self,
        user1_name: str,
        user2_name: str,
        score: int,
        score1: int,
        score2: int
    ) -> str:
        """相性に応じたメッセージを取得"""
        diff = abs(score1 - score2)

        if score1 - score2 > 70:
            return LOVE_MESSAGES["one_sided_high"].format(user1_name)
        elif score2 - score1 > 70:
            return LOVE_MESSAGES["one_sided_high"].format(user2_name)
        elif diff > 50:
            return LOVE_MESSAGES["one_sided_medium"]
        elif diff > 30:
            return LOVE_MESSAGES["one_sided_low"]

        if score > 80:
            return LOVE_MESSAGES["mutual_excellent"]
        elif score > 60:
            return LOVE_MESSAGES["mutual_good"]
        elif score > 40:
            return LOVE_MESSAGES["mutual_average"]
        elif score > 20:
            return LOVE_MESSAGES["mutual_poor"]

        return LOVE_MESSAGES["mutual_bad"]

    @discord.app_commands.command(
        name="love-calculator",
        description="2人のユーザーを選択して愛の相性を計算します"
    )
    async def love_calculator(
        self,
        interaction: discord.Interaction,
        user1: discord.User,
        user2: discord.User
    ) -> None:
        """愛の相性を計算するコマンド"""
        try:
            if user1 == user2:
                embed = discord.Embed(
                    title="💖 Love Calculator 💖",
                    description="1人目と2人目で同じユーザーが選択されています。",
                    color=discord.Color.pink()
                )
                await interaction.response.send_message(embed=embed)
                return

            scores = self._calculate_love_score(user1.name, user2.name)
            embed = self._create_love_embed(user1, user2, scores)
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error("Error in love calculator: %s", e, exc_info=True)
            await interaction.response.send_message(
                f"エラーが発生しました: {e}",
                ephemeral=True
            )

    @discord.app_commands.command(
        name="fantasy-status",
        description="特定の人の装備品、攻撃力、守備力、体力を表示する"
    )
    async def fantasy_status(
        self,
        interaction: discord.Interaction,
        user: discord.User
    ) -> None:
        """ファンタジーステータスを表示するコマンド"""
        try:
            stats = self._calculate_stats(user.name)
            embed = self._create_status_embed(user, stats)
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error("Error in fantasy status: %s", e, exc_info=True)
            await interaction.response.send_message(
                f"エラーが発生しました: {e}",
                ephemeral=True
            )

    @discord.app_commands.command(
        name="your-cpu-gpu",
        description="特定の人をCPU、GPUで例えると...？"
    )
    async def your_cpu(
        self,
        interaction: discord.Interaction,
        user: discord.User
    ) -> None:
        """ユーザーに対応するCPU/GPUを表示するコマンド"""
        try:
            random.seed(user.name)
            embed = discord.Embed(
                title=f"💻 {user.name}をCPU、GPUで例えると...？ 🖥",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="CPU",
                value=random.choice(self.cpus),
                inline=True
            )
            embed.add_field(
                name="GPU",
                value=random.choice(self.gpus),
                inline=True
            )
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error("Error in cpu/gpu command: %s", e, exc_info=True)
            await interaction.response.send_message(
                f"エラーが発生しました: {e}",
                ephemeral=True
            )

    @discord.app_commands.command(
        name="versus",
        description="fantasy-statusのステータスをもとに対戦させます。"
    )
    async def versus(
        self,
        interaction: discord.Interaction,
        user1: discord.User,
        user2: discord.User
    ) -> None:
        """ユーザー同士の対戦を実行するコマンド"""
        try:
            if user1 == user2:
                embed = discord.Embed(
                    title="⚔ Versus ⚔",
                    description="1人目と2人目で同じユーザーが選択されています。",
                    color=discord.Color.dark_red()
                )
                await interaction.response.send_message(embed=embed)
                return

            random.seed(time.time())
            stats1 = self._calculate_stats(user1.name)
            stats2 = self._calculate_stats(user2.name)

            battle = BattleSystem(
                (user1.name, stats1),
                (user2.name, stats2)
            )

            embed = discord.Embed(
                title="⚔ Versus ⚔",
                color=discord.Color.dark_red()
            )

            hp1 = stats1[3]
            hp2 = stats2[3]
            turn = random.randint(0, 1)

            for _ in range(BATTLE_CONFIG["max_turns"]):
                if turn:
                    damage, is_crit = battle.calculate_damage(
                        stats1[1], stats2[2],
                        stats1[0], stats2[0]
                    )
                    hp2 -= damage
                    msg = (
                        "クリティカルヒット！" if is_crit else ""
                    ) + f"{user2.name}に{damage}のダメージ！残りHP：{hp2}"
                    embed.add_field(
                        name=f"{user1.name}のターン",
                        value=msg,
                        inline=False
                    )
                    if hp2 <= 0:
                        embed.add_field(
                            name=f"{user1.name}の勝利！",
                            value=f"{user1.name}は{hp1}の体力を残して勝利した！",
                            inline=False
                        )
                        break
                else:
                    damage, is_crit = battle.calculate_damage(
                        stats2[1], stats1[2],
                        stats2[0], stats1[0]
                    )
                    hp1 -= damage
                    msg = (
                        "クリティカルヒット！" if is_crit else ""
                    ) + f"{user1.name}に{damage}のダメージ！残りHP：{hp1}"
                    embed.add_field(
                        name=f"{user2.name}のターン",
                        value=msg,
                        inline=False
                    )
                    if hp1 <= 0:
                        embed.add_field(
                            name=f"{user2.name}の勝利！",
                            value=f"{user2.name}は{hp2}の体力を残して勝利した！",
                            inline=False
                        )
                        break
                turn = not turn

            if hp1 > 0 and hp2 > 0:
                embed.add_field(
                    name="引き分け",
                    value=(
                        f"{BATTLE_CONFIG['max_turns']}ターン以内に"
                        f"戦いが終わらなかった。\n"
                        f"{user1.name}の体力：{hp1}\n"
                        f"{user2.name}の体力：{hp2}"
                    ),
                    inline=False
                )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error("Error in versus command: %s", e, exc_info=True)
            await interaction.response.send_message(
                f"エラーが発生しました: {e}",
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(JokeCommands(bot))
