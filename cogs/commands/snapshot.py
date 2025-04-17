import discord
from discord.ext import commands
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import aiohttp
from textwrap import wrap
import re

url_pattern = re.compile(r'https?://\S+|www\.\S+')

def get_rainbow_color(i, total):
    import colorsys
    h = i / total
    r, g, b = colorsys.hsv_to_rgb(h, 1, 1)
    return (int(r*255), int(g*255), int(b*255))

class Snapshot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        content = message.content.strip()
        content_lower = content.lower()
        if content_lower in ("すなっぷ", "snapshot", "すなっぷ rainbow", "snapshot rainbow"):
            rainbow = content_lower.endswith("rainbow")
            if message.reference and message.reference.resolved:
                ref_msg = message.reference.resolved
            elif message.reference:
                try:
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                except Exception:
                    await message.channel.send("返信先のメッセージが取得できませんでした。")
                    return
            else:
                return

            img = await self.create_snapshot_image(ref_msg, rainbow=rainbow)
            buf = BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            file = discord.File(buf, filename="snapshot.png")
            await message.channel.send(file=file)

    async def create_snapshot_image(self, ref_msg: discord.Message, rainbow=False):
        width = 600
        bg_color = (50,51,57)
        text_color = (255,255,255)
        url_color = (64, 156, 255)
        dt_color = (148,149,156)
        padding = 20
        avatar_size = 40

        username_color = ref_msg.author.color.to_rgb() if ref_msg.author.color.value else text_color

        try:
            font_main = ImageFont.truetype("assets/fonts/NotoSansJP-Regular.ttf", 16)
            font_small = ImageFont.truetype("assets/fonts/NotoSansJP-Regular.ttf", 12)
        except:
            font_main = ImageFont.load_default()
            font_small = ImageFont.load_default()

        avatar_url = (
            ref_msg.author.avatar.url
            if getattr(ref_msg.author, "avatar", None)
            else ref_msg.author.default_avatar.url
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(str(avatar_url)) as resp:
                avatar_bytes = await resp.read()
        avatar = Image.open(BytesIO(avatar_bytes)).convert("RGBA").resize((avatar_size, avatar_size))

        mask = Image.new("L", (avatar_size, avatar_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)

        content = ref_msg.content or ""
        default_wrap = 70
        temp_lines = wrap(content, width=default_wrap)
        if len(temp_lines) > 30:
            scale = 1.3
            width = int(width * scale)
            wrap_width = int(default_wrap * scale)
        else:
            wrap_width = default_wrap
        lines = wrap(content, width=wrap_width)

        if lines:
            max_line_width = max(
                font_main.getbbox(line)[2] - font_main.getbbox(line)[0]
                for line in lines
            )
            text_start_x = padding + avatar_size + 15
            desired_width = text_start_x + max_line_width + padding
            if desired_width > width:
                width = desired_width

        bbox_A = font_main.getbbox("A")
        line_height = (bbox_A[3] - bbox_A[1]) + 10

        name_bbox = font_main.getbbox(ref_msg.author.display_name)
        name_height = name_bbox[3] - name_bbox[1]
        name_width = name_bbox[2] - name_bbox[0]

        dt_str = ref_msg.created_at.strftime("%H:%M")
        dt_bbox = font_small.getbbox(dt_str)
        dt_height = dt_bbox[3] - dt_bbox[1]

        total_lines = sum(len(wrap(line, width=wrap_width)) for line in content.splitlines())
        content_height = line_height * total_lines
        height = padding * 2 + name_height + content_height + 15

        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        avatar_y = padding
        img.paste(avatar, (padding, avatar_y), mask)

        x_text = padding + avatar_size + 15
        y_name = padding - 2
        draw.text((x_text, y_name), ref_msg.author.display_name, font=font_main, fill=username_color)
        
        timestamp_x = x_text + name_width + 8
        draw.text((timestamp_x, y_name + 2), dt_str, font=font_small, fill=dt_color)

        content_y = y_name + name_height + 8
        current_y = content_y
        for line in content.splitlines():
            wrapped_lines = wrap(line, width=wrap_width)
            for wrapped_line in wrapped_lines:
                x = x_text
                last_end = 0
                if rainbow:
                    for i, ch in enumerate(wrapped_line):
                        color = get_rainbow_color(i, len(wrapped_line))
                        draw.text((x, current_y), ch, font=font_main, fill=color)
                        ch_width = font_main.getbbox(ch)[2] - font_main.getbbox(ch)[0]
                        x += ch_width
                    current_y += line_height
                else:
                    for m in url_pattern.finditer(wrapped_line):
                        pre = wrapped_line[last_end:m.start()]
                        if pre:
                            draw.text((x, current_y), pre, font=font_main, fill=text_color)
                            pre_width = font_main.getbbox(pre)[2] - font_main.getbbox(pre)[0]
                            x += pre_width
                        url = m.group(0)
                        draw.text((x, current_y), url, font=font_main, fill=url_color)
                        url_width = font_main.getbbox(url)[2] - font_main.getbbox(url)[0]
                        x += url_width
                        last_end = m.end()
                    rest = wrapped_line[last_end:]
                    if rest:
                        draw.text((x, current_y), rest, font=font_main, fill=text_color)
                    current_y += line_height

        credit_text = "swiftlybot.com"
        credit_font = font_small
        credit_bbox = credit_font.getbbox(credit_text)
        credit_width = credit_bbox[2] - credit_bbox[0]
        draw.text(
            (width - credit_width - 10, height - 15), 
            credit_text, 
            font=credit_font, 
            fill=(80, 83, 90)
        )

        return img

async def setup(bot):
    await bot.add_cog(Snapshot(bot))