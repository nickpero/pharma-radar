from scanner.test_phase5_2_final import test_strength, test_interpretations, test_safe_unknown


def test_phase5_2():
    test_strength()
    test_interpretations()
    test_safe_unknown()


if __name__ == "__main__":
    test_phase5_2()
    print("Phase 5.2 final tests passed")
