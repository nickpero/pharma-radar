from scanner.trial_scanner import scan
from scanner.state import save_state


def create_baseline():
    print("Creating Pharma Radar baseline...")

    result = scan()

    print()
    print("Baseline created successfully.")
    print(
        f"Relevant trials registered: "
        f"{result['relevant_trials']}"
    )

    # La normale scansione ha già salvato
    # lo stato corrente.
    #
    # Gli eventuali eventi rilevati durante
    # questa prima scansione NON devono
    # essere considerati breaking news.
    #
    # Il file di stato appena creato rappresenta
    # quindi la nostra baseline.

    save_state(
        __import__(
            "scanner.state",
            fromlist=["load_state"]
        ).load_state()
    )


if __name__ == "__main__":
    create_baseline()
