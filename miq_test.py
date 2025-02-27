from lib.miq import MakeItQuote
from PIL import Image

# Initialize the MakeItQuote generator
miq = MakeItQuote()

# Define the quote and author
quote = "The only limit to our realization of tomorrow is our doubts of today."
author = "Franklin D. Roosevelt"

# Load a specific background image
background_image_path = "icon_techfishのコピー.png"
background_image = Image.open(background_image_path)

# Generate the quote image
quote_image = miq.create_quote(
    quote=quote,
    author=author,
    background_image=background_image
)

# Convert to RGB before saving as JPEG
quote_image = quote_image.convert("RGB")

# Save the generated quote image
output_path = "quote_image.jpg"
quote_image.save(output_path)

print(f"Quote image saved to {output_path}")