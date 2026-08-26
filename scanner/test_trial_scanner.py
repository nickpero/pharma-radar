from scanner.trial_scanner import make_trial_key


def test_make_trial_key():

    trial = {
        "nct_id": "NCT04428476"
    }

    key = make_trial_key(
        "CAPR",
        "deramiocel",
        trial
    )

    assert key == (
        "CAPR:"
        "deramiocel:"
        "NCT04428476"
    )


def test_make_trial_key_unique():

    trial_1 = {
        "nct_id": "NCT11111111"
    }

    trial_2 = {
        "nct_id": "NCT22222222"
    }

    key_1 = make_trial_key(
        "CAPR",
        "deramiocel",
        trial_1
    )

    key_2 = make_trial_key(
        "CAPR",
        "deramiocel",
        trial_2
    )

    assert key_1 != key_2


def test_make_trial_key_program_difference():

    trial = {
        "nct_id": "NCT12345678"
    }

    key_1 = make_trial_key(
        "CAPR",
        "deramiocel",
        trial
    )

    key_2 = make_trial_key(
        "CAPR",
        "other_program",
        trial
    )

    assert key_1 != key_2


if __name__ == "__main__":

    test_make_trial_key()
    test_make_trial_key_unique()
    test_make_trial_key_program_difference()

    print(
        "✅ Trial Scanner tests passed"
  )
