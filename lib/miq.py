import os
import textwrap
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps
from typing import Tuple, Optional, List, Dict, Union
import math

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
        self.default_font_size = 72
        self.default_text_color = (255, 255, 255)
        self.default_shadow_color = (0, 0, 0, 220)
        self.default_quote_width = 25
        
        # Style presets
        self.style_presets = {
            "modern": {
                "font_size": 64,
                "text_color": (255, 255, 255),
                "shadow_opacity": 180,
                "gradient_overlay": True,
                "rounded_corners": True,
                "overlay_opacity": 160
            },
            "minimal": {
                "font_size": 72,
                "text_color": (255, 255, 255),
                "shadow_opacity": 100,
                "gradient_overlay": False,
                "rounded_corners": False,
                "overlay_opacity": 120
            },
            "bold": {
                "font_size": 84,
                "text_color": (255, 232, 115),
                "shadow_opacity": 200,
                "gradient_overlay": True,
                "rounded_corners": False,
                "overlay_opacity": 180
            }
        }
        
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
                             shadow_color: Tuple[int, int, int, int],
                             shadow_strength: int = 3):
        """Add text with enhanced shadow and outline effects"""
        x, y = position
        
        # Multiple shadows for stronger effect
        shadow_offsets = [(i, i) for i in range(1, shadow_strength + 1)]
        for offset in shadow_offsets:
            draw.text((x + offset[0], y + offset[1]), 
                     text, font=font, fill=shadow_color)
        
        # Enhanced outline effect
        outline_color = (0, 0, 0, 255)
        outline_positions = []
        outline_size = 2
        
        for i in range(-outline_size, outline_size+1):
            for j in range(-outline_size, outline_size+1):
                if i != 0 or j != 0:  # Skip the center position
                    outline_positions.append((i, j))
        
        for offset_x, offset_y in outline_positions:
            draw.text((x + offset_x, y + offset_y), 
                     text, font=font, fill=outline_color)
        
        # Main text
        draw.text(position, text, font=font, fill=text_color)
    
    def _create_gradient_overlay(self, size: Tuple[int, int], 
                               start_color: Tuple[int, int, int, int],
                               end_color: Tuple[int, int, int, int],
                               direction: str = 'vertical') -> Image.Image:
        """Create a gradient overlay image"""
        gradient = Image.new('RGBA', size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(gradient)
        
        width, height = size
        
        if direction == 'vertical':
            for y in range(height):
                # Calculate the color for this line
                alpha = y / height
                color = (
                    int(start_color[0] * (1 - alpha) + end_color[0] * alpha),
                    int(start_color[1] * (1 - alpha) + end_color[1] * alpha),
                    int(start_color[2] * (1 - alpha) + end_color[2] * alpha),
                    int(start_color[3] * (1 - alpha) + end_color[3] * alpha)
                )
                draw.line([(0, y), (width, y)], fill=color)
        else:  # horizontal
            for x in range(width):
                alpha = x / width
                color = (
                    int(start_color[0] * (1 - alpha) + end_color[0] * alpha),
                    int(start_color[1] * (1 - alpha) + end_color[1] * alpha),
                    int(start_color[2] * (1 - alpha) + end_color[2] * alpha),
                    int(start_color[3] * (1 - alpha) + end_color[3] * alpha)
                )
                draw.line([(x, 0), (x, height)], fill=color)
                
        return gradient

    def _add_profile_image(self, 
                         base_image: Image.Image, 
                         profile_image_path: str,
                         position: str = 'bottom-left',
                         size: int = 120,
                         padding: int = 40) -> Image.Image:
        """Add a profile image to the quote"""
        if not os.path.exists(profile_image_path):
            return base_image
            
        try:
            profile_img = Image.open(profile_image_path).convert("RGBA")
            
            # Resize profile image
            profile_img = profile_img.resize((size, size), Image.LANCZOS)
            
            # Create circular mask
            mask = Image.new('L', (size, size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)
            
            # Apply mask to create circular profile image
            profile_img.putalpha(mask)
            
            # Calculate position
            width, height = base_image.size
            if position == 'bottom-left':
                pos = (padding, height - size - padding)
            elif position == 'bottom-right':
                pos = (width - size - padding, height - size - padding)
            elif position == 'top-left':
                pos = (padding, padding)
            elif position == 'top-right':
                pos = (width - size - padding, padding)
            else:  # center
                pos = ((width - size) // 2, (height - size) // 2)
                
            # Create new image with same size as base image
            result = base_image.copy()
            result.paste(profile_img, pos, profile_img)
            return result
        except Exception as e:
            print(f"Error adding profile image: {str(e)}")
            return base_image
    
    def _apply_rounded_corners(self, image: Image.Image, radius: int = 40) -> Image.Image:
        """Apply rounded corners to an image"""
        circle = Image.new('L', (radius * 2, radius * 2), 0)
        draw = ImageDraw.Draw(circle)
        draw.ellipse((0, 0, radius * 2, radius * 2), fill=255)
        
        width, height = image.size
        alpha = Image.new('L', image.size, 255)
        
        # Paste corner circles
        alpha.paste(circle.crop((0, 0, radius, radius)), (0, 0))
        alpha.paste(circle.crop((radius, 0, radius * 2, radius)), (width - radius, 0))
        alpha.paste(circle.crop((0, radius, radius, radius * 2)), (0, height - radius))
        alpha.paste(circle.crop((radius, radius, radius * 2, radius * 2)), (width - radius, height - radius))
        
        # Convert image to RGBA if it's not already
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
            
        # Apply the alpha mask
        result = image.copy()
        result.putalpha(alpha)
        
        return result
    
    def _add_quote_marks(self, 
                       draw: ImageDraw, 
                       position: Tuple[int, int], 
                       font_path: str, 
                       size: int, 
                       color: Tuple[int, int, int]):
        """Add stylized quote marks"""
        quote_font = ImageFont.truetype(font_path, size)
        draw.text(position, '"', font=quote_font, fill=color)

    def _enhance_background(self, background: Image.Image, style: Dict) -> Image.Image:
        """Apply enhancements to the background image based on style"""
        # Apply contrast and brightness adjustments
        background = ImageEnhance.Contrast(background).enhance(1.2)
        background = ImageEnhance.Brightness(background).enhance(0.85)
        background = ImageEnhance.Color(background).enhance(1.3)  # Adjust saturation
        
        # Apply blur
        background = background.filter(ImageFilter.GaussianBlur(radius=3))
        
        # Create a semi-transparent overlay
        overlay_opacity = style.get('overlay_opacity', 160)
        overlay = Image.new('RGBA', background.size, (0, 0, 0, overlay_opacity))
        background = Image.alpha_composite(background, overlay)
        
        if style.get('gradient_overlay', False):
            # Add gradient overlay
            gradient = self._create_gradient_overlay(
                background.size,
                (0, 0, 0, 0),  # Transparent at top
                (0, 0, 0, 180),  # Dark at bottom
                'vertical'
            )
            background = Image.alpha_composite(background, gradient)
        
        return background
    
    def _adjust_font_size(self, text: str, font_path: str, max_width: int, max_height: int, initial_font_size: int) -> Tuple[ImageFont, int]:
        """Adjust font size to fit text within the specified width and height"""
        font_size = initial_font_size
        font = ImageFont.truetype(font_path, font_size)
        wrapped_text = self._wrap_text(text, width=max_width // font.getsize('A')[0])
        
        while True:
            total_height = len(wrapped_text) * (font_size + 10)
            if total_height <= max_height and all(font.getsize(line)[0] <= max_width for line in wrapped_text):
                break
            font_size -= 2
            font = ImageFont.truetype(font_path, font_size)
            wrapped_text = self._wrap_text(text, width=max_width // font.getsize('A')[0])
        
        return font, font_size

    def create_quote(self, 
                    quote: str, 
                    author: Optional[str] = None, 
                    output_size: Tuple[int, int] = (1080, 1080),
                    font_path: str = None,
                    font_size: int = None,
                    text_color: Tuple[int, int, int] = None,
                    background_image: Image.Image = None,
                    profile_image: str = None,
                    style: Union[str, Dict[str, Union[int, bool]]] = "modern") -> Image.Image:
        """
        Generate a quote image with enhanced Twitter-style design.
        
        Args:
            quote: The quote text
            author: Optional author name
            output_size: Size of output image (width, height)
            font_path: Path to font file
            font_size: Font size for quote text
            text_color: RGB color tuple for text
            background_image: Optional PIL Image to use as background
            profile_image: Optional path to profile image
            style: Either a style preset name ("modern", "minimal", "bold") or a dict of style settings
        """
        # Resolve style settings
        if isinstance(style, str):
            style_settings = self.style_presets.get(style, self.style_presets["modern"])
        else:
            style_settings = style
        
        # Use defaults or provided values
        font_path = font_path or self._get_random_font()
        font_size = font_size or style_settings.get('font_size', self.default_font_size)
        text_color = text_color or style_settings.get('text_color', self.default_text_color)
        shadow_opacity = style_settings.get('shadow_opacity', 180)
        shadow_color = (0, 0, 0, shadow_opacity)
        
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
        
        # Apply style-based enhancements to background
        background = self._enhance_background(background, style_settings)
        
        # Create drawing layer
        draw = ImageDraw.Draw(background)
        
        # Load fonts and adjust font size if necessary
        try:
            quote_font, adjusted_font_size = self._adjust_font_size(quote, font_path, output_size[0] - 100, output_size[1] - 200, font_size)
            author_font = ImageFont.truetype(font_path, adjusted_font_size // 2)
        except Exception as e:
            raise ValueError(f"Error loading font: {str(e)}")
        
        # Calculate positioning
        width, height = output_size

        # Process quote text
        wrapped_quote = self._wrap_text(quote, width=(width - 100) // quote_font.getsize('A')[0])
        total_quote_height = len(wrapped_quote) * (adjusted_font_size + 10)
        
        # Add stylized quote marks
        quote_mark_size = int(adjusted_font_size * 2.5)
        quote_mark_color = text_color
        quote_mark_position = (width // 8, height // 6)
        self._add_quote_marks(draw, quote_mark_position, font_path, quote_mark_size, quote_mark_color)
        
        # Calculate vertical position to center text
        start_y = max((height - total_quote_height) // 2, height // 3)
        
        # Draw quote text with enhanced effects
        current_y = start_y
        for line in wrapped_quote:
            text_width = quote_font.getsize(line)[0]
            position = ((width - text_width) // 2, current_y)
            self._add_text_with_effects(draw, position, line, quote_font, 
                                      text_color, shadow_color,
                                      shadow_strength=style_settings.get('shadow_strength', 3))
            current_y += adjusted_font_size + 10
        
        # Add author if provided
        if author:
            author_text = f"— {author}"
            author_width = author_font.getsize(author_text)[0]
            author_position = ((width - author_width) // 2, current_y + 30)
            self._add_text_with_effects(draw, author_position, author_text, 
                                      author_font, text_color, shadow_color)
        
        # Enhanced vignette effect
        vignette = Image.new('RGBA', output_size, (0, 0, 0, 0))
        vignette_draw = ImageDraw.Draw(vignette)
        
        # Create radial gradient for vignette
        for i in range(100):
            opacity = int(130 * (i / 100))
            box = (i, i, width - i, height - i)
            vignette_draw.rectangle(box, outline=(0, 0, 0, opacity), width=1)
        
        background = Image.alpha_composite(background, vignette)
        
        # Add profile image if provided
        if profile_image:
            background = self._add_profile_image(background, profile_image, 
                                              position='bottom-left', 
                                              size=int(height * 0.12))
        
        # Add watermark
        credit_font_size = adjusted_font_size // 5
        credit_font = ImageFont.truetype(font_path, credit_font_size)
        credit_text = "Powered by Swiftly"
        credit_width = credit_font.getsize(credit_text)[0]
        credit_position = (width - credit_width - 20, height - credit_font_size - 20)
        self._add_text_with_effects(draw, credit_position, credit_text, 
                                  credit_font, (200, 200, 200), (0, 0, 0, 150), 1)
        
        # Apply rounded corners if style specifies
        if style_settings.get('rounded_corners', False):
            background = self._apply_rounded_corners(background, radius=int(min(width, height) * 0.05))
                
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
