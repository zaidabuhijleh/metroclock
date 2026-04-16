from abc import ABC, abstractmethod
from PIL import Image

class Widget(ABC):
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.canvas = Image.new('RGB', (width, height), (0, 0, 0))

    @abstractmethod
    def update(self):
        """
        Logic only: Fetch data from APIs here.
        Do not draw pixels in this function.
        """
        pass

    @abstractmethod
    def draw(self):
        """
        Graphics only: Draw pixels to self.canvas.
        Returns the canvas image.
        """
        pass