from core.app import MetroClockApp


def main():
    app = MetroClockApp.build_default()
    app.run_forever()

if __name__ == "__main__":
    main()
