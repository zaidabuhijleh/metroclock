import time
import traceback


def main():
    while True:
        try:
            from core.app import MetroClockApp

            app = MetroClockApp.build_default()
            app.run_forever()
            return
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            _show_startup_error(exc)


def _show_startup_error(exc: Exception):
    print(f"Fatal startup error: {exc}", flush=True)
    traceback.print_exc()
    try:
        import config
        from core.display import Display
        from core.status_frame import render_status_frame

        display = Display(
            width=config.MATRIX_WIDTH,
            height=config.MATRIX_HEIGHT,
            slowdown=config.MATRIX_SLOWDOWN,
            brightness=config.MATRIX_BRIGHTNESS,
            pwm_bits=getattr(config, "MATRIX_PWM_BITS_CLOCK", 5),
        )
        frame = render_status_frame(
            config.MATRIX_WIDTH,
            config.MATRIX_HEIGHT,
            ("STARTUP ERR", type(exc).__name__, str(exc)),
        )
        deadline = time.time() + 30
        while time.time() < deadline:
            display.draw_image(frame)
            display.push()
            time.sleep(2)
    except Exception as status_exc:
        print(f"Startup error frame failed: {status_exc}", flush=True)
        time.sleep(30)

if __name__ == "__main__":
    main()
