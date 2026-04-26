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
        
        self.options.gpio_slowdown = 4


        self.options.disable_hardware_pulsing = True

        self.options.pwm_bits = 4
        self.options.pwm_dither_bits = 0
        self.options.brightness = 100
        self.options.drop_privileges = False

        self.matrix = RGBMatrix(options=self.options)
        self.canvas = self.matrix.CreateFrameCanvas()
        self.brightness = 100

    def _clamp_brightness(self, brightness):
        return 100

    def set_brightness(self, brightness):
        brightness = self._clamp_brightness(brightness)
        if brightness == self.brightness:
            return
        self.brightness = brightness
        self.matrix.brightness = brightness

    def clear(self):
        self.canvas.Clear()

    def draw_image(self, image):
        if image.width != self.options.cols or image.height != self.options.rows:
            image = image.resize((self.options.cols, self.options.rows))
        self.matrix.SetImage(image)

    def push(self):
        """Not strictly needed for basic usage, but good for VSync if implemented"""
        pass
