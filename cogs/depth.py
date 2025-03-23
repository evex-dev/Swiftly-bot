import discord
from discord.ext import commands
from transformers import pipeline
from PIL import Image
import matplotlib.pyplot as plt
import io

class DepthEstimationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pipe = pipeline(task="depth-estimation", model="depth-anything/Depth-Anything-V2-Large-hf")

    @commands.command(name='震度推定')
    async def depth_estimation(self, ctx):
        if not ctx.message.attachments:
            await ctx.send("画像を添付してください。")
            return

        attachment = ctx.message.attachments[0]
        image_data = await attachment.read()
        image = Image.open(io.BytesIO(image_data))

        # Perform depth estimation
        depth = self.pipe(image)["depth"]

        # Plot the depth map
        plt.imshow(depth, cmap='viridis')
        plt.colorbar()
        plt.title('Depth Estimation')

        # Save the plot to a BytesIO object
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()

        # Send the depth map image
        file = discord.File(buf, filename='depth_estimation.png')
        await ctx.send(file=file)

# Setup function to add the cog to the bot
def setup(bot):
    bot.add_cog(DepthEstimationCog(bot))
