import time
import config
import web_server
from core.display import Display
from widgets.metro import MetroWidget
from widgets.weather import WeatherWidget
from widgets.flight import FlightWidget
from widgets.ambient import AmbientWidget

def _pwm_bits_for_mode(mode: str) -> int:
    defaults = {
        "metro": 3,
        "flight": 3,
        "weather": 5,
        "ambient": 5,
    }
    fallback = getattr(config, "MATRIX_PWM_BITS", 3)
    value = getattr(config, f"MATRIX_PWM_BITS_{mode.upper()}", defaults.get(mode, fallback))
    try:
        return max(1, min(11, int(value)))
    except Exception:
        return max(1, min(11, int(fallback)))

def main():
    web_server.start_server()

    display = None
    active_pwm_bits = None

    metro = MetroWidget(config.MATRIX_WIDTH, config.MATRIX_HEIGHT)
    weather = WeatherWidget(config.MATRIX_WIDTH, config.MATRIX_HEIGHT)
    flight = FlightWidget(config.MATRIX_WIDTH, config.MATRIX_HEIGHT)
    ambient = AmbientWidget(config.MATRIX_WIDTH, config.MATRIX_HEIGHT)

    print("Dashboard Started. Press Ctrl+C to exit.")

    try:
        while True:
            mode = web_server.get_display_mode()
            target_pwm_bits = _pwm_bits_for_mode(mode)
            if display is None or target_pwm_bits != active_pwm_bits:
                display = Display(
                    width=config.MATRIX_WIDTH,
                    height=config.MATRIX_HEIGHT,
                    slowdown=config.MATRIX_SLOWDOWN,
                    brightness=config.MATRIX_BRIGHTNESS,
                    pwm_bits=target_pwm_bits,
                )
                active_pwm_bits = target_pwm_bits
                print(f"Display mode={mode}, pwm_bits={target_pwm_bits}")

            display.clear()
            display.set_brightness(web_server.get_brightness())

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
