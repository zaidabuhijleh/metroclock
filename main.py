import time
import traceback
import config
import web_server
from core.display import Display
try:
    from widgets.weather import WeatherWidget
except Exception as exc:
    WeatherWidget = None
    print(f"Weather widget disabled: {exc}")
try:
    from widgets.flight import FlightWidget
except Exception as exc:
    FlightWidget = None
    print(f"Flight widget disabled: {exc}")
from widgets.ambient import AmbientWidget
from widgets.clock import ClockWidget
try:
    from widgets.sports import SportsWidget
except Exception as exc:
    SportsWidget = None
    print(f"Sports widget disabled: {exc}")
try:
    from widgets.stocks import StocksWidget
except Exception as exc:
    StocksWidget = None
    print(f"Stocks widget disabled: {exc}")

def _pwm_bits_for_mode(mode: str) -> int:
    defaults = {
        "metro": 3,
        "flight": 3,
        "weather": 5,
        "ambient": 5,
        "sports": 5,
        "stocks": 5,
        "clock": 5,
        "clock_widget": 5,
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

    metro = None
    weather = WeatherWidget(config.MATRIX_WIDTH, config.MATRIX_HEIGHT) if WeatherWidget else None
    flight = FlightWidget(config.MATRIX_WIDTH, config.MATRIX_HEIGHT) if FlightWidget else None
    ambient = AmbientWidget(config.MATRIX_WIDTH, config.MATRIX_HEIGHT)
    sports = SportsWidget(config.MATRIX_WIDTH, config.MATRIX_HEIGHT) if SportsWidget else None
    stocks = StocksWidget(config.MATRIX_WIDTH, config.MATRIX_HEIGHT) if StocksWidget else None
    clock = ClockWidget(
        config.MATRIX_WIDTH,
        config.MATRIX_HEIGHT,
        metro,
        weather,
        flight,
        sports,
        stocks,
    )

    print("Dashboard Started. Press Ctrl+C to exit.")

    try:
        while True:
            try:
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
                    clock.update()
                    img = clock.draw()
                elif mode == "weather":
                    if weather is not None:
                        weather.update()
                        img = weather.draw()
                    else:
                        clock.update()
                        img = clock.draw()
                elif mode == "flight":
                    if flight is not None:
                        flight.update()
                        img = flight.draw()
                    else:
                        clock.update()
                        img = clock.draw()
                elif mode == "ambient":
                    ambient.update()
                    img = ambient.draw()
                elif mode == "sports":
                    if sports is not None:
                        sports.update()
                        img = sports.draw()
                    else:
                        clock.update()
                        img = clock.draw()
                elif mode == "stocks":
                    if stocks is not None:
                        stocks.update()
                        img = stocks.draw()
                    else:
                        clock.update()
                        img = clock.draw()
                elif mode == "clock":
                    clock.update()
                    img = clock.draw()
                elif mode == "clock_widget":
                    clock.update()
                    img = clock.draw()
                else:
                    clock.update()
                    img = clock.draw()

                display.draw_image(img)
                display.push()
                time.sleep(0.05)
            except Exception as exc:
                print(f"Render loop error ({web_server.get_display_mode()}): {exc}")
                traceback.print_exc()
                time.sleep(0.25)

    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main()
