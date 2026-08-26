from scanner.alert_filter import (
    is_alert_worthy,
    is_critical,
    filter_alerts,
    filter_critical,
    sort_alerts,
)


def test_low_event_not_alert():

    event = {
        "score": 15,
        "label": "LOW",
    }

    assert is_alert_worthy(event) is False
    assert is_critical(event) is False


def test_medium_event_not_alert():

    event = {
        "score": 45,
        "label": "MEDIUM",
    }

    assert is_alert_worthy(event) is False
    assert is_critical(event) is False


def test_alert_threshold():

    event = {
        "score": 60,
        "label": "HIGH",
    }

    assert is_alert_worthy(event) is True
    assert is_critical(event) is False


def test_critical_threshold():

    event = {
        "score": 80,
        "label": "CRITICAL",
    }

    assert is_alert_worthy(event) is True
    assert is_critical(event) is True


def test_filter_alerts():

    events = [
        {
            "score": 15,
            "label": "LOW",
        },
        {
            "score": 45,
            "label": "MEDIUM",
        },
        {
            "score": 60,
            "label": "HIGH",
        },
        {
            "score": 95,
            "label": "CRITICAL",
        },
    ]

    alerts = filter_alerts(events)

    assert len(alerts) == 2
    assert alerts[0]["score"] == 60
    assert alerts[1]["score"] == 95


def test_filter_critical():

    events = [
        {
            "score": 15,
            "label": "LOW",
        },
        {
            "score": 60,
            "label": "HIGH",
        },
        {
            "score": 80,
            "label": "CRITICAL",
        },
        {
            "score": 100,
            "label": "CRITICAL",
        },
    ]

    critical = filter_critical(events)

    assert len(critical) == 2
    assert critical[0]["score"] == 80
    assert critical[1]["score"] == 100


def test_sort_alerts():

    events = [
        {
            "score": 60,
        },
        {
            "score": 100,
        },
        {
            "score": 80,
        },
    ]

    sorted_events = sort_alerts(events)

    assert sorted_events[0]["score"] == 100
    assert sorted_events[1]["score"] == 80
    assert sorted_events[2]["score"] == 60


def test_custom_threshold():

    event = {
        "score": 70,
    }

    assert is_alert_worthy(
        event,
        minimum_score=70
    ) is True

    assert is_alert_worthy(
        event,
        minimum_score=71
    ) is False


if __name__ == "__main__":

    test_low_event_not_alert()
    test_medium_event_not_alert()
    test_alert_threshold()
    test_critical_threshold()
    test_filter_alerts()
    test_filter_critical()
    test_sort_alerts()
    test_custom_threshold()

    print(
        "✅ Alert Filter tests passed"
)
