import discord
from discord.ext import commands
import torch
from transformers import BertTokenizer, BertForSequenceClassification

# Load the pre-trained BERT model and tokenizer
MODEL_PATH = "prithivMLmods/Spam-Bert-Uncased"
tokenizer = BertTokenizer.from_pretrained(MODEL_PATH)
model = BertForSequenceClassification.from_pretrained(MODEL_PATH)

# Function to predict if a given text is Spam or Ham
def predict_spam(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        prediction = torch.argmax(logits, axis=-1).item()
    return "Spam" if prediction == 1 else "Ham"

class SpamDetection(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name='spamdetect', description="Detect if a message is Spam or Ham.")
    async def spamdetect(self, interaction: discord.Interaction, message: str):
        """Detect if a message is Spam or Ham."""
        result = predict_spam(message)
        embed = discord.Embed(title="Spam Detection", description=f"The message is: {result}", color=discord.Color.blue())
        await interaction.response.send_message(embed=embed)

def setup(bot):
    bot.add_cog(SpamDetection(bot))
