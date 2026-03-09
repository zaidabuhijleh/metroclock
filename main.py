import time
import config
from core.display import Display
from widgets.metro import MetroWidget
from widgets.weather import WeatherWidget
from widgets.flight import FlightWidget

# --- APP SELECTOR ---
# Set only ONE of these to True at a time
SHOW_METRO = True
SHOW_WEATHER = False
SHOW_FLIGHT = False

def main():
    display = Display(
        width=config.MATRIX_WIDTH, 
        height=config.MATRIX_HEIGHT,
        slowdown=config.MATRIX_SLOWDOWN,
        brightness=config.MATRIX_BRIGHTNESS
    )

    # Initialize Widgets
    metro = MetroWidget(config.MATRIX_WIDTH, config.MATRIX_HEIGHT)
    weather = WeatherWidget(config.MATRIX_WIDTH, config.MATRIX_HEIGHT)
    flight = FlightWidget(config.MATRIX_WIDTH, config.MATRIX_HEIGHT)

    print("Dashboard Started. Press Ctrl+C to exit.")

    try:
        while True:
            display.clear()

            if SHOW_METRO:
                metro.update()
                img = metro.draw()
            elif SHOW_WEATHER:
                weather.update()
                img = weather.draw()
            elif SHOW_FLIGHT:
                flight.update()
                img = flight.draw()
            else:
                # Fallback if all are False
                img = metro.draw() 

            display.draw_image(img)
            display.push()
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main()