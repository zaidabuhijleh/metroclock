from rgbmatrix import RGBMatrix, RGBMatrixOptions
import config

class Display:
    def __init__(self, width, height, slowdown, brightness):
        self.options = RGBMatrixOptions()
        self.options.rows = height
        self.options.cols = width
        self.options.chain_length = 1
        self.options.parallel = 1
        self.options.hardware_mapping = config.MATRIX_MAPPING
        
        # --- PI ZERO 2 W FLICKER FIX ---
        
        # 1. SLOWDOWN: Keep this high for stability
        self.options.gpio_slowdown = 4

        # 2. SOFTWARE MODE: Uses the CPU to drive the matrix
        # Since you locked the CPU to "performance" mode, this will be smooth.
        self.options.disable_hardware_pulsing = True
        
        # 3. COLOR DEPTH: Reduced to 4 bits (The Critical Fix)
        # Drops the CPU load significantly. 
        # For retro pixel art, 4 bits (16 shades per color) is plenty.
        self.options.pwm_bits = 2
        self.options.pwm_dither_bits = 0
        self.options.brightness = self._clamp_brightness(brightness)
        self.options.drop_privileges = False
        # -------------------------------

        self.matrix = RGBMatrix(options=self.options)
        self.canvas = self.matrix.CreateFrameCanvas()
        self.brightness = self.options.brightness

    def _clamp_brightness(self, brightness):
        return max(1, min(100, int(brightness)))

    def set_brightness(self, brightness):
        brightness = self._clamp_brightness(brightness)
        if brightness == self.brightness:
            return
        self.brightness = brightness
        self.matrix.brightness = brightness

    def clear(self):
        self.canvas.Clear()

    def draw_image(self, image):
        # Ensure image fits
        if image.width != self.options.cols or image.height != self.options.rows:
            image = image.resize((self.options.cols, self.options.rows))
        self.matrix.SetImage(image)

    def push(self):
        """Not strictly needed for basic usage, but good for VSync if implemented"""
        pass
