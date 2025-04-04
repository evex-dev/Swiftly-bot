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

        # Discord AutoMod のルールタイプ設定用のマッピング
        rule_types = {
            "spam": discord.AutoModRuleActionType.block_message,
            "mentionspam": discord.AutoModRuleActionType.block_message,
            "discordinvite": discord.AutoModRuleActionType.block_message,
            "httplink": discord.AutoModRuleActionType.block_message,
            "mention": discord.AutoModRuleActionType.block_message
        }

        # キーワードに基づいたルールトリガー設定
        trigger_types = {
            "spam": discord.AutoModRuleTriggerType.spam,
            "mentionspam": discord.AutoModRuleTriggerType.mention_spam,
            "discordinvite": discord.AutoModRuleTriggerType.keyword,
            "httplink": discord.AutoModRuleTriggerType.keyword,
            "mention": discord.AutoModRuleTriggerType.mention_spam
        }

        # 特別な設定が必要なルールの追加設定
        trigger_metadata = None
        if moderate == "discordinvite":
            trigger_metadata = discord.AutoModRuleTriggerMetadata(
                keyword_filter=["discord.gg", "discord.com/invite"]
            )
        elif moderate == "httplink":
            trigger_metadata = discord.AutoModRuleTriggerMetadata(
                keyword_filter=["http://", "https://"]
            )
        elif moderate == "mentionspam":
            trigger_metadata = discord.AutoModRuleTriggerMetadata(
                mention_limit=5
            )

        try:
            # 除外ロールと特定ロールの設定
            exempt_roles = [roles_to_exclude.id] if roles_to_exclude else []
            specific_roles = [only_for_this_role.id] if only_for_this_role else []

            if action == "enable":
                # 既存のルールを確認して、同じタイプのルールがある場合は削除
                existing_rules = await interaction.guild.fetch_automod_rules()
                for rule in existing_rules:
                    if rule.trigger_type == trigger_types[moderate]:
                        await rule.delete()

                # 新しいルールを作成
                await interaction.guild.create_automod_rule(
                    name=f"Automod: {moderate}",
                    event_type=discord.AutoModRuleEventType.message_send,
                    trigger_type=trigger_types[moderate],
                    trigger_metadata=trigger_metadata,
                    actions=[discord.AutoModRuleAction(
                        type=rule_types[moderate],
                        metadata=discord.AutoModRuleActionMetadata()
                    )],
                    exempt_roles=exempt_roles,
                    enabled=True,
                    exempt_channels=[],
                )
                await interaction.response.send_message(f"`{moderate}` の自動モデレーションを有効にしました。", ephemeral=True)
            
            else:  # action == "disable"
                # 既存のルールを確認して、指定されたタイプのルールを削除
                existing_rules = await interaction.guild.fetch_automod_rules()
                found = False
                for rule in existing_rules:
                    if rule.trigger_type == trigger_types[moderate]:
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

async def setup(bot):
    await bot.add_cog(AutoMod(bot))
