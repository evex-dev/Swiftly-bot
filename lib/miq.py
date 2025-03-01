import os
import textwrap
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from PIL.Image import Resampling
from typing import Tuple, Optional, List, Dict, Union
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import numpy as np


class MakeItQuote:
    def __init__(self, fonts_dir: str = None, backgrounds_dir: str = None):
        """
        Initialize the MakeItQuote generator.

        Args:
            fonts_dir: Directory containing font files
            backgrounds_dir: Directory containing background images
        """
        self.fonts_dir = fonts_dir or os.path.join(
            os.path.dirname(__file__), "../assets/fonts")
        self.backgrounds_dir = backgrounds_dir or os.path.join(
            os.path.dirname(__file__), "../assets/backgrounds")

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

        # Initialize thread pool
        self.executor = ThreadPoolExecutor(max_workers=8)

        # Make sure asset directories exist
        os.makedirs(self.fonts_dir, exist_ok=True)
        os.makedirs(self.backgrounds_dir, exist_ok=True)

        # Initialize cache
        self._font_cache = {}
        self._gradient_cache = {}
        self._background_cache = {}

    @lru_cache(maxsize=32)
    def _get_random_background(self) -> str:
        """Get a random background image path"""
        try:
            backgrounds = [f for f in os.listdir(self.backgrounds_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
            if not backgrounds:
                raise FileNotFoundError("背景画像が見つかりません。")
            return os.path.join(self.backgrounds_dir, random.choice(backgrounds))
        except Exception as e:
            raise ValueError(f"背景画像の取得中にエラーが発生しました: {e}") from e

    @lru_cache(maxsize=32)
    def _get_random_font(self) -> str:
        """Get a random font file path"""
        try:
            fonts = [f for f in os.listdir(self.fonts_dir) if f.lower().endswith((".ttf", ".otf"))]
            if not fonts:
                raise FileNotFoundError("フォントファイルが見つかりません。")
            return os.path.join(self.fonts_dir, random.choice(fonts))
        except Exception as e:
            raise ValueError(f"フォントの取得中にエラーが発生しました: {e}") from e

    def _wrap_text(self, text: str, width: int) -> List[str]:
        """Wrap text to fit specified width"""
        try:
            return textwrap.wrap(text, width=width)
        except Exception as e:
            raise ValueError(f"テキストの折り返し処理中にエラーが発生しました: {e}") from e

    def _add_text_with_effects_parallel(self,
                                    draw: ImageDraw,
                                    position: Tuple[int, int],
                                    text: str,
                                    font: ImageFont,
                                    text_color: Tuple[int, int, int],
                                    shadow_color: Tuple[int, int, int, int],
                                    shadow_strength: int = 3):
        """Add text with enhanced shadow and outline effects using parallel processing"""
        try:
            x, y = position

            def draw_shadow(offset):
                draw.text((x + offset[0], y + offset[1]), text, font=font, fill=shadow_color)

            def draw_outline(pos):
                offset_x, offset_y = pos
                draw.text((x + offset_x, y + offset_y), text, font=font, fill=(0, 0, 0, 255))

            # Create shadow positions
            shadow_offsets = [(i, i) for i in range(1, shadow_strength + 1)]
            outline_positions = [(i, j) for i in range(-1, 2) for j in range(-1, 2) if i != 0 or j != 0]

            # Execute shadow and outline drawing in parallel
            shadow_futures = [self.executor.submit(draw_shadow, offset) for offset in shadow_offsets]
            outline_futures = [self.executor.submit(draw_outline, pos) for pos in outline_positions]

            # Wait for all effects to complete
            for future in shadow_futures + outline_futures:
                future.result()

            # Draw main text
            draw.text(position, text, font=font, fill=text_color)
        except Exception as e:
            raise ValueError(f"テキスト効果の描画中にエラーが発生しました: {e}") from e

    @lru_cache(maxsize=16)
    def _create_gradient_overlay(self, size: Tuple[int, int],
                             start_color: Tuple[int, int, int, int],
                             end_color: Tuple[int, int, int, int],
                             direction: str = "vertical") -> Image.Image:
        """Create a gradient overlay image using numpy for better performance"""
        try:
            width, height = size

            if direction == "vertical":
                gradient = np.linspace(0, 1, height)[:, np.newaxis]
                gradient = np.tile(gradient, (1, width))
            else:  # horizontal
                gradient = np.linspace(0, 1, width)[np.newaxis, :]
                gradient = np.tile(gradient, (height, 1))

            # Create RGBA array
            gradient_array = np.zeros((height, width, 4), dtype=np.uint8)

            for i in range(4):  # For each RGBA channel
                gradient_array[:, :, i] = np.uint8(
                    start_color[i] * (1 - gradient) + end_color[i] * gradient
                )

            return Image.fromarray(gradient_array, 'RGBA')
        except Exception as e:
            raise ValueError(f"グラデーションの生成中にエラーが発生しました: {e}") from e

    def _enhance_background_parallel(self, background: Image.Image, style: Dict) -> Image.Image:
        """Apply enhancements to the background image in parallel"""
        try:
            def apply_enhancements():
                enhanced = ImageEnhance.Contrast(background).enhance(1.2)
                enhanced = ImageEnhance.Brightness(enhanced).enhance(0.85)
                enhanced = ImageEnhance.Color(enhanced).enhance(1.3)
                return enhanced

            def apply_blur(img):
                return img.filter(ImageFilter.GaussianBlur(radius=3))

            # Execute enhancements and blur in parallel
            enhanced_future = self.executor.submit(apply_enhancements)

            # Get enhanced image
            background = enhanced_future.result()

            # Apply blur
            background = apply_blur(background)

            # Create overlay
            overlay_opacity = style.get("overlay_opacity", 160)
            overlay = Image.new("RGBA", background.size, (0, 0, 0, overlay_opacity))
            background = Image.alpha_composite(background.convert('RGBA'), overlay)

            if style.get("gradient_overlay", False):
                # Get or create gradient overlay
                gradient_key = (background.size, "vertical")
                if gradient_key not in self._gradient_cache:
                    self._gradient_cache[gradient_key] = self._create_gradient_overlay(
                        background.size,
                        (0, 0, 0, 0),
                        (0, 0, 0, 180),
                        "vertical"
                    )
                gradient = self._gradient_cache[gradient_key]
                background = Image.alpha_composite(background, gradient)

            return background
        except Exception as e:
            raise ValueError(f"背景画像の処理中にエラーが発生しました: {e}") from e

    def _get_font(self, font_path: str, size: int) -> ImageFont.FreeTypeFont:
        """Get cached font object"""
        try:
            key = (font_path, size)
            if key not in self._font_cache:
                self._font_cache[key] = ImageFont.truetype(font_path, size)
            return self._font_cache[key]
        except Exception as e:
            raise ValueError(f"フォントの読み込み中にエラーが発生しました: {e}") from e

    def _apply_rounded_corners(self, image: Image.Image, radius: int = 40) -> Image.Image:
        """Apply rounded corners to an image"""
        try:
            circle = Image.new("L", (radius * 2, radius * 2), 0)
            draw = ImageDraw.Draw(circle)
            draw.ellipse((0, 0, radius * 2, radius * 2), fill=255)

            width, height = image.size
            alpha = Image.new("L", image.size, 255)

            # Paste corner circles
            alpha.paste(circle.crop((0, 0, radius, radius)), (0, 0))
            alpha.paste(circle.crop((radius, 0, radius * 2, radius)), (width - radius, 0))
            alpha.paste(circle.crop((0, radius, radius, radius * 2)), (0, height - radius))
            alpha.paste(circle.crop((radius, radius, radius * 2, radius * 2)), (width - radius, height - radius))

            # Convert image to RGBA if it's not already
            if image.mode != "RGBA":
                image = image.convert("RGBA")

            # Apply the alpha mask
            result = image.copy()
            result.putalpha(alpha)

            return result
        except Exception as e:
            raise ValueError(f"角丸処理中にエラーが発生しました: {e}") from e

    def _calculate_optimal_font_size(self, text: str, max_width: int, max_height: int, font_path: str, initial_size: int) -> int:
        """Calculate optimal font size to fit text within given dimensions"""
        try:
            # 最小フォントサイズを設定
            min_font_size = 20
            current_size = initial_size

            while current_size > min_font_size:
                font = self._get_font(font_path, current_size)
                # テキストを折り返して各行の幅をチェック
                wrapped_text = self._wrap_text(text, width=(max_width - 100) // max(1, font.getbbox("A")[2]))

                # 全体の高さを計算
                total_height = len(wrapped_text) * (current_size + 10)

                # 最大幅と高さをチェック
                max_line_width = max(font.getbbox(line)[2] for line in wrapped_text)

                if max_line_width <= max_width - 100 and total_height <= max_height * 0.7:
                    return current_size

                current_size -= 5
            return min_font_size
        except Exception as e:
            raise ValueError(f"フォントサイズの計算中にエラーが発生しました: {e}") from e

    def create_quote(self,
                    quote: str,
                    author: Optional[str] = None,
                    output_size: Tuple[int, int] = (1080, 1080),
                    font_path: str = None,
                    font_size: int = None,
                    text_color: Tuple[int, int, int] = None,
                    background_image: Image.Image = None,
                    _: str = None,  # profile_image
                    style: Union[str, Dict[str, Union[int, bool]]] = "modern") -> Image.Image:
        """Generate a quote image with enhanced performance"""
        try:
            # Resolve style settings
            if isinstance(style, str):
                style_settings = self.style_presets.get(style, self.style_presets["modern"])
            else:
                style_settings = style

            # Use defaults or provided values
            font_path = font_path or self._get_random_font()
            text_color = text_color or style_settings.get("text_color", self.default_text_color)
            shadow_opacity = style_settings.get("shadow_opacity", 180)
            shadow_color = (0, 0, 0, shadow_opacity)

            # Process background in parallel
            def prepare_background():
                if background_image is None:
                    background_path = self._get_random_background()
                    try:
                        bg = Image.open(background_path)
                        bg = bg.convert("RGBA")
                        bg = bg.resize(output_size, Resampling.LANCZOS)
                    except Exception as e:
                        raise ValueError(f"背景画像の読み込み中にエラーが発生しました: {e}") from e
                else:
                    bg = background_image.convert("RGBA")
                    bg = bg.resize(output_size, Resampling.LANCZOS)
                return self._enhance_background_parallel(bg, style_settings)

            # Calculate optimal font size if not provided
            if font_size is None:
                initial_size = style_settings.get("font_size", self.default_font_size)
                font_size = self._calculate_optimal_font_size(
                    quote,
                    output_size[0],
                    output_size[1],
                    font_path,
                    initial_size
                )

            # Process fonts in parallel
            def prepare_fonts():
                quote_font = self._get_font(font_path, font_size)
                author_font = self._get_font(font_path, font_size // 2)
                return quote_font, author_font

            # Execute background and font preparation in parallel
            background_future = self.executor.submit(prepare_background)
            fonts_future = self.executor.submit(prepare_fonts)

            # Get results
            background = background_future.result(timeout=60)
            quote_font, author_font = fonts_future.result(timeout=60)

            # Create drawing layer
            draw = ImageDraw.Draw(background)
            width, height = output_size

            # Process quote text
            wrapped_quote = self._wrap_text(quote, width=(width - 100) // max(1, quote_font.getbbox("A")[2]))
            total_quote_height = len(wrapped_quote) * (font_size + 10)

            # Add quote marks
            quote_mark_size = int(font_size * 2.5)
            quote_mark_position = (width // 8, height // 6)
            self._add_text_with_effects_parallel(
                draw, quote_mark_position, '"',
                self._get_font(font_path, quote_mark_size),
                text_color, shadow_color
            )

            # Draw quote text
            start_y = max((height - total_quote_height) // 2, height // 3)
            current_y = start_y

            # Draw text lines in parallel
            def draw_text_line(line_data):
                try:
                    line, y_pos = line_data
                    text_width = quote_font.getbbox(line)[2]
                    position = ((width - text_width) // 2, y_pos)
                    self._add_text_with_effects_parallel(
                        draw, position, line, quote_font,
                        text_color, shadow_color,
                        shadow_strength=style_settings.get("shadow_strength", 2)
                    )
                except Exception as e:
                    raise ValueError(f"テキスト描画中にエラーが発生しました: {e}") from e

            text_lines = [(line, current_y + i * (font_size + 10)) for i, line in enumerate(wrapped_quote)]

            text_futures = [self.executor.submit(draw_text_line, line_data) for line_data in text_lines]

            # Wait for all text drawing to complete
            for future in text_futures:
                future.result()

            current_y += len(wrapped_quote) * (font_size + 10)

            # Add author if provided
            if author:
                try:
                    author_text = f"— {author}"
                    author_width = author_font.getbbox(author_text)[2]
                    author_position = ((width - author_width) // 2, current_y + 30)
                    self._add_text_with_effects_parallel(
                        draw, author_position, author_text,
                        author_font, text_color, shadow_color
                    )
                except Exception as e:
                    raise ValueError(f"著者名の描画中にエラーが発生しました: {e}") from e

            # Add watermark
            try:
                credit_font_size = max(font_size // 5, 12)  # 最小サイズを設定
                credit_font = self._get_font(font_path, credit_font_size)
                credit_text = "Powered by Swiftly"
                credit_width = credit_font.getbbox(credit_text)[2]
                credit_position = (width - credit_width - 20, height - credit_font_size - 20)
                self._add_text_with_effects_parallel(
                    draw, credit_position, credit_text,
                    credit_font, (200, 200, 200), (0, 0, 0, 150), 1
                )
            except Exception as e:
                raise ValueError(f"ウォーターマークの描画中にエラーが発生しました: {e}") from e

            # Apply rounded corners if specified
            if style_settings.get("rounded_corners", False):
                try:
                    background = self._apply_rounded_corners(
                        background, radius=int(min(width, height) * 0.05)
                    )
                except Exception as e:
                    raise ValueError(f"角丸処理中にエラーが発生しました: {e}") from e

            return background

        except Exception as e:
            raise ValueError(f"画像生成中にエラーが発生しました: {e}") from e

    def save_quote(self, quote: str, output_path: str, author: Optional[str] = None, **kwargs) -> str:
        """Generate and save a quote image."""
        try:
            image = self.create_quote(quote, author, **kwargs)

            if output_path.lower().endswith((".jpg", ".jpeg")):
                image = image.convert("RGB")

            image.save(output_path)
            return output_path
        except Exception as e:
            raise ValueError(f"画像の保存中にエラーが発生しました: {e}") from e

    def __del__(self):
        """Cleanup thread pool on deletion"""
        self.executor.shutdown(wait=False)
