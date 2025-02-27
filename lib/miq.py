import os
import textwrap
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from typing import Tuple, Optional, List

class MakeItQuote:
    def __init__(self, fonts_dir: str = None, backgrounds_dir: str = None):
        """
        Initialize the MakeItQuote generator.
        
        Args:
            fonts_dir: Directory containing font files
            backgrounds_dir: Directory containing background images
        """
        self.fonts_dir = fonts_dir or os.path.join(os.path.dirname(__file__), "../assets/fonts")
        self.backgrounds_dir = backgrounds_dir or os.path.join(os.path.dirname(__file__), "../assets/backgrounds")
        
        # Default settings
        self.default_font_size = 72  # Increased from 56 for bolder text
        self.default_text_color = (255, 255, 255)  # White
        self.default_shadow_color = (0, 0, 0, 220)  # More opaque black
        self.default_quote_width = 25  # Characters per line
        
        # Make sure asset directories exist
        os.makedirs(self.fonts_dir, exist_ok=True)
        os.makedirs(self.backgrounds_dir, exist_ok=True)

    def _get_random_background(self) -> str:
        """Get a random background image path"""
        backgrounds = [f for f in os.listdir(self.backgrounds_dir) 
                      if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if not backgrounds:
            raise FileNotFoundError("No background images found.")
        return os.path.join(self.backgrounds_dir, random.choice(backgrounds))
    
    def _get_random_font(self) -> str:
        """Get a random font file path"""
        fonts = [f for f in os.listdir(self.fonts_dir) 
                if f.lower().endswith(('.ttf', '.otf'))]
        if not fonts:
            raise FileNotFoundError("No font files found.")
        return os.path.join(self.fonts_dir, random.choice(fonts))
    
    def _wrap_text(self, text: str, width: int) -> List[str]:
        """Wrap text to fit specified width"""
        return textwrap.wrap(text, width=width)
    
    def _add_text_with_effects(self, 
                             draw: ImageDraw, 
                             position: Tuple[int, int], 
                             text: str, 
                             font: ImageFont, 
                             text_color: Tuple[int, int, int],
                             shadow_color: Tuple[int, int, int, int]):
        """Add text with enhanced shadow and outline effects"""
        x, y = position
        
        # Multiple shadows for stronger effect
        shadow_offsets = [(5, 5), (4, 4), (3, 3), (2, 2)]  # Added more shadow layers
        for offset in shadow_offsets:
            draw.text((x + offset[0], y + offset[1]), 
                     text, font=font, fill=shadow_color)
        
        # Enhanced outline effect
        outline_color = (0, 0, 0, 255)
        outline_positions = [
            (-2, -2), (-1, -2), (0, -2), (1, -2), (2, -2),
            (-2, -1), (-1, -1), (0, -1), (1, -1), (2, -1),
            (-2, 0),  (-1, 0),          (1, 0),  (2, 0),
            (-2, 1),  (-1, 1),  (0, 1),  (1, 1),  (2, 1),
            (-2, 2),  (-1, 2),  (0, 2),  (1, 2),  (2, 2)
        ]  # Increased outline thickness
        
        for offset_x, offset_y in outline_positions:
            draw.text((x + offset_x, y + offset_y), 
                     text, font=font, fill=outline_color)
        
        # Main text
        draw.text(position, text, font=font, fill=text_color)
    
    def create_quote(self, 
                    quote: str, 
                    author: Optional[str] = None, 
                    output_size: Tuple[int, int] = (1080, 1080),
                    font_path: str = None,
                    font_size: int = None,
                    text_color: Tuple[int, int, int] = None,
                    background_image: Image.Image = None) -> Image.Image:
        """
        Generate a quote image.
        """
        # Use defaults or provided values
        font_path = font_path or self._get_random_font()
        font_size = font_size or self.default_font_size
        text_color = text_color or self.default_text_color
        
        # Create base image from background
        if background_image is None:
            background_path = self._get_random_background()
            try:
                background = Image.open(background_path)
                background = background.convert("RGBA")
                background = background.resize(output_size, Image.LANCZOS)
            except Exception as e:
                raise ValueError(f"Error loading background image: {str(e)}")
        else:
            background = background_image.convert("RGBA")
            background = background.resize(output_size, Image.LANCZOS)
        
        # Create a black background with more opacity
        black_background = Image.new('RGBA', output_size, (0, 0, 0, 180))
        
        # Composite the black background with the main background
        background = Image.alpha_composite(background, black_background)
        
        # Apply stronger adjustments to enhance background
        background = ImageEnhance.Contrast(background).enhance(1.2)
        background = background.filter(ImageFilter.GaussianBlur(radius=2))
        
        # Create drawing layer
        draw = ImageDraw.Draw(background)
        
        # Load fonts
        try:
            quote_font = ImageFont.truetype(font_path, font_size)
            author_font = ImageFont.truetype(font_path, font_size // 2)
        except Exception as e:
            raise ValueError(f"Error loading font: {str(e)}")
        
        # Process quote text
        wrapped_quote = self._wrap_text(quote, self.default_quote_width)
        total_quote_height = len(wrapped_quote) * (font_size + 10)
        
        # Calculate positioning
        width, height = output_size
        start_y = (height - total_quote_height) // 2
        
        # Draw quote text with enhanced effects
        current_y = start_y
        for line in wrapped_quote:
            text_width = quote_font.getlength(line)
            position = ((width - text_width) // 2, current_y)
            self._add_text_with_effects(draw, position, line, quote_font, 
                                      text_color, self.default_shadow_color)
            current_y += font_size + 10
        
        # Add author if provided
        if author:
            author_text = f"- {author}"
            author_width = author_font.getlength(author_text)
            author_position = ((width - author_width) // 2, current_y + 20)
            self._add_text_with_effects(draw, author_position, author_text, 
                                      author_font, text_color, self.default_shadow_color)
        
        # Enhanced vignette effect
        overlay = Image.new('RGBA', output_size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        
        for i in range(100):
            opacity = int(150 * (i / 100))
            overlay_draw.rectangle((i, i, width - i, height - i), 
                                 outline=(0, 0, 0, opacity), width=1)
        
        background = Image.alpha_composite(background, overlay)
        
        # Add "Powered by Swiftly" text in bottom right
        credit_font_size = font_size // 4  # Make it smaller than the author text
        credit_font = ImageFont.truetype(font_path, credit_font_size)
        credit_text = "Powered by Swiftly"
        credit_width = credit_font.getlength(credit_text)
        credit_position = (width - credit_width - 20, height - credit_font_size - 20)
        self._add_text_with_effects(draw, credit_position, credit_text, 
                                  credit_font, text_color, self.default_shadow_color)
        
        return background
    
    def save_quote(self, 
                  quote: str, 
                  output_path: str, 
                  author: Optional[str] = None,
                  **kwargs) -> str:
        """
        Generate and save a quote image.
        """
        image = self.create_quote(quote, author, **kwargs)
        
        if output_path.lower().endswith(('.jpg', '.jpeg')):
            image = image.convert('RGB')
        
        image.save(output_path)
        return output_path
