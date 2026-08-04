from outcomeos_api.mvp import store


def main() -> None:
    store.load()
    print(f"OutcomeOS demo worker one-shot checked {store.path}")


if __name__ == "__main__":
    main()
