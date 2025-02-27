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
        self.default_font_size = 48
        self.default_text_color = (255, 255, 255)  # White
        self.default_shadow_color = (0, 0, 0, 180)  # Semi-transparent black
        self.default_quote_width = 30  # characters per line
        
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
    
    def _add_text_with_shadow(self, 
                             draw: ImageDraw, 
                             position: Tuple[int, int], 
                             text: str, 
                             font: ImageFont, 
                             text_color: Tuple[int, int, int],
                             shadow_color: Tuple[int, int, int, int],
                             shadow_offset: int = 3):
        """Add text with shadow effect"""
        # Draw shadow
        draw.text((position[0] + shadow_offset, position[1] + shadow_offset), 
                  text, font=font, fill=shadow_color)
        # Draw text
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
        
        Args:
            quote: The quote text
            author: Author name (optional)
            output_size: Size of the output image (width, height)
            font_path: Path to custom font file
            font_size: Font size for the quote
            text_color: RGB color tuple for text
            background_image: PIL Image object for the background
            
        Returns:
            PIL Image object of the generated quote
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
        
        # Apply subtle adjustments to enhance background
        background = ImageEnhance.Brightness(background).enhance(0.7)  # Slightly darken
        background = background.filter(ImageFilter.GaussianBlur(radius=2))  # Slight blur
        
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
        
        # Draw quote text with shadow
        current_y = start_y
        for line in wrapped_quote:
            text_width = quote_font.getlength(line)
            position = ((width - text_width) // 2, current_y)
            self._add_text_with_shadow(draw, position, line, quote_font, 
                                      text_color, self.default_shadow_color)
            current_y += font_size + 10
        
        # Add author if provided
        if author:
            author_text = f"- {author}"
            author_width = author_font.getlength(author_text)
            author_position = ((width - author_width) // 2, current_y + 20)
            self._add_text_with_shadow(draw, author_position, author_text, 
                                      author_font, text_color, self.default_shadow_color)
        
        # Add subtle vignette effect
        overlay = Image.new('RGBA', output_size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        
        # Draw four filled rectangles from each edge with gradient opacity
        for i in range(50):
            opacity = int(100 * (i / 50))
            overlay_draw.rectangle((i, i, width - i, height - i), 
                                 outline=(0, 0, 0, opacity), width=1)
        
        # Composite the vignette effect
        background = Image.alpha_composite(background, overlay)
        
        return background
    
    def save_quote(self, 
                  quote: str, 
                  output_path: str, 
                  author: Optional[str] = None,
                  **kwargs) -> str:
        """
        Generate and save a quote image.
        
        Args:
            quote: The quote text
            output_path: Path to save the image
            author: Author name (optional)
            **kwargs: Additional options to pass to create_quote
            
        Returns:
            Path where the image was saved
        """
        image = self.create_quote(quote, author, **kwargs)
        
        # Convert to RGB before saving as JPEG
        if output_path.lower().endswith('.jpg') or output_path.lower().endswith('.jpeg'):
            image = image.convert('RGB')
        
        image.save(output_path)
        return output_path