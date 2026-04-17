import time
import config
import web_server
from core.display import Display
from widgets.metro import MetroWidget
from widgets.weather import WeatherWidget
from widgets.flight import FlightWidget
from widgets.ambient import AmbientWidget

def main():
    web_server.start_server()

    display = Display(
        width=config.MATRIX_WIDTH,
        height=config.MATRIX_HEIGHT,
        slowdown=config.MATRIX_SLOWDOWN,
        brightness=config.MATRIX_BRIGHTNESS
    )

    metro = MetroWidget(config.MATRIX_WIDTH, config.MATRIX_HEIGHT)
    weather = WeatherWidget(config.MATRIX_WIDTH, config.MATRIX_HEIGHT)
    flight = FlightWidget(config.MATRIX_WIDTH, config.MATRIX_HEIGHT)
    ambient = AmbientWidget(config.MATRIX_WIDTH, config.MATRIX_HEIGHT)

    print("Dashboard Started. Press Ctrl+C to exit.")

    try:
        while True:
            display.clear()

            mode = web_server.get_display_mode()
            if mode == "metro":
                metro.update()
                img = metro.draw()
            elif mode == "weather":
                weather.update()
                img = weather.draw()
            elif mode == "flight":
                flight.update()
                img = flight.draw()
            elif mode == "ambient":
                ambient.update()
                img = ambient.draw()
            else:
                img = metro.draw()

            display.draw_image(img)
            display.push()
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main()