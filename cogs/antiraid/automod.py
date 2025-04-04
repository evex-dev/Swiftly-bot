import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Literal

class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="automod", description="ギルドの自動モデレーション設定を管理します")
    @app_commands.describe(
        action="自動モデレーションを有効または無効にする",
        moderate="モデレーションするコンテンツの種類",
        roles_to_exclude="自動モデレーションから除外するロール",
        only_for_this_role="このロールにのみ自動モデレーションを適用する"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def automod(
        self, 
        interaction: discord.Interaction, 
        action: Literal["enable", "disable"],
        moderate: Literal["spam", "mentionspam", "discordinvite", "httplink", "mention"],
        roles_to_exclude: Optional[discord.Role] = None,
        only_for_this_role: Optional[discord.Role] = None
    ):
        # 両方のロールオプションが指定された場合はエラー
        if roles_to_exclude and only_for_this_role:
            await interaction.response.send_message("除外ロールと特定ロール限定の設定は同時に使用できません。", ephemeral=True)
            return

        # Discord AutoMod のルールタイプマッピング
        trigger_types = {
            "spam": discord.AutoModRuleTriggerType.spam,
            "mentionspam": discord.AutoModRuleTriggerType.mention_spam,
            "discordinvite": discord.AutoModRuleTriggerType.keyword,
            "httplink": discord.AutoModRuleTriggerType.keyword,
            "mention": discord.AutoModRuleTriggerType.mention_spam
        }

        try:
            # 除外ロールと特定ロールの設定
            exempt_roles = [roles_to_exclude] if roles_to_exclude else []
            
            if action == "enable":
                # 既存のルールを確認して、同じ名前のルールがある場合は削除
                existing_rules = await interaction.guild.fetch_automod_rules()
                for rule in existing_rules:
                    if f"Automod: {moderate}" in rule.name:
                        await rule.delete()

                # 新しいルールを作成
                # 各モデレーションタイプに応じた設定
                if moderate == "discordinvite":
                    # Discordの招待リンクをブロック
                    await interaction.guild.create_automod_rule(
                        name=f"Automod: {moderate}",
                        event_type=discord.AutoModRuleEventType.message_send,
                        trigger_metadata={"keyword_filter": ["discord.gg", "discord.com/invite"]},
                        actions=[{"type": discord.AutoModActionType.block_message}],
                        enabled=True,
                        exempt_roles=exempt_roles,
                        exempt_channels=[],
                        trigger_type=discord.AutoModRuleTriggerType.keyword
                    )
                elif moderate == "httplink":
                    # HTTPリンクをブロック
                    await interaction.guild.create_automod_rule(
                        name=f"Automod: {moderate}",
                        event_type=discord.AutoModRuleEventType.message_send,
                        trigger_metadata={"keyword_filter": ["http://", "https://"]},
                        actions=[{"type": discord.AutoModActionType.block_message}],
                        enabled=True,
                        exempt_roles=exempt_roles,
                        exempt_channels=[],
                        trigger_type=discord.AutoModRuleTriggerType.keyword
                    )
                elif moderate == "mentionspam":
                    # メンションスパムをブロック
                    await interaction.guild.create_automod_rule(
                        name=f"Automod: {moderate}",
                        event_type=discord.AutoModRuleEventType.message_send,
                        trigger_metadata={"mention_limit": 5},
                        actions=[{"type": discord.AutoModActionType.block_message}],
                        enabled=True,
                        exempt_roles=exempt_roles,
                        exempt_channels=[],
                        trigger_type=discord.AutoModRuleTriggerType.mention_spam
                    )
                elif moderate == "spam":
                    # スパムをブロック
                    await interaction.guild.create_automod_rule(
                        name=f"Automod: {moderate}",
                        event_type=discord.AutoModRuleEventType.message_send,
                        trigger_metadata={},
                        actions=[{"type": discord.AutoModActionType.block_message}],
                        enabled=True,
                        exempt_roles=exempt_roles,
                        exempt_channels=[],
                        trigger_type=discord.AutoModRuleTriggerType.spam
                    )
                elif moderate == "mention":
                    # 過剰なメンションをブロック (spam同様の設定だが名前を変えてわかりやすく)
                    await interaction.guild.create_automod_rule(
                        name=f"Automod: {moderate}",
                        event_type=discord.AutoModRuleEventType.message_send,
                        trigger_metadata={"mention_limit": 5},
                        actions=[{"type": discord.AutoModActionType.block_message}],
                        enabled=True,
                        exempt_roles=exempt_roles,
                        exempt_channels=[],
                        trigger_type=discord.AutoModRuleTriggerType.mention_spam
                    )
                
                await interaction.response.send_message(f"`{moderate}` の自動モデレーションを有効にしました。", ephemeral=True)
            
            else:  # action == "disable"
                # 既存のルールを確認して、指定されたタイプのルールを削除
                existing_rules = await interaction.guild.fetch_automod_rules()
                found = False
                for rule in existing_rules:
                    if f"Automod: {moderate}" in rule.name:
                        await rule.delete()
                        found = True
                
                if found:
                    await interaction.response.send_message(f"`{moderate}` の自動モデレーションを無効にしました。", ephemeral=True)
                else:
                    await interaction.response.send_message(f"`{moderate}` の自動モデレーションルールは存在しませんでした。", ephemeral=True)
        
        except discord.Forbidden:
            await interaction.response.send_message("自動モデレーションを設定する権限がありません。", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"エラーが発生しました: {e}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"予期しないエラーが発生しました: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AutoMod(bot))
