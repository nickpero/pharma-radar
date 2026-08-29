"""
Pharma Radar — FDA Catalyst Engine

Trasforma una FDA News Item già classificata
in un evento Catalyst compatibile con il
motore di scoring e Trading Intelligence.

Questo modulo NON effettua raccomandazioni
di acquisto o vendita.
"""


# ============================================
# FDA CATEGORY → CATALYST
# ============================================

FDA_CATALYST_MAP = {

    "APPROVAL": {
        "type": "FDA_EVENT",
        "subtype": "FDA_APPROVAL",
        "severity": "HIGH",
        "direction": "CATALYST",
    },

    "REJECTION": {
        "type": "FDA_EVENT",
        "subtype": "FDA_REJECTION",
        "severity": "HIGH",
        "direction": "NEGATIVE",
    },

    "SAFETY": {
        "type": "FDA_EVENT",
        "subtype": "FDA_SAFETY_WARNING",
        "severity": "HIGH",
        "direction": "NEGATIVE",
    },

    "CLINICAL": {
        "type": "FDA_EVENT",
        "subtype": "CLINICAL_RESULTS",
        "severity": "HIGH",
        "direction": "POSITIVE",
    },

    "LABEL": {
        "type": "FDA_EVENT",
        "subtype": "LABEL_EXPANSION",
        "severity": "HIGH",
        "direction": "CATALYST",
    },
}


# ============================================
# DEFAULT EVENT
# ============================================

DEFAULT_EVENT = {
    "type": "FDA_EVENT",
    "subtype": "FDA_UPDATE",
    "severity": "LOW",
    "direction": "UNKNOWN",
}


# ============================================
# CATEGORY PRIORITY
# ============================================

CATEGORY_PRIORITY = [
    "APPROVAL",
    "REJECTION",
    "SAFETY",
    "CLINICAL",
    "LABEL",
]


# ============================================
# BUILD FDA CATALYST
# ============================================

def build_fda_catalyst(news_item):
    """
    Trasforma una FDA News Item in un
    Catalyst Event standardizzato.

    Mantiene i dati originali della news
    attraverso i campi di contesto.
    """

    if not isinstance(news_item, dict):
        raise TypeError(
            "news_item must be a dictionary"
        )

    categories = news_item.get(
        "categories",
        []
    )

    if not isinstance(categories, list):
        categories = list(
            categories or []
        )

    normalized_categories = {
        str(category).upper()
        for category in categories
    }

    # ========================================
    # FIND HIGHEST PRIORITY CATEGORY
    # ========================================

    selected_category = None

    for category in CATEGORY_PRIORITY:

        if category in normalized_categories:

            selected_category = category
            break

    # ========================================
    # DEFAULT
    # ========================================

    if selected_category is None:

        event = dict(
            DEFAULT_EVENT
        )

    else:

        event = dict(
            FDA_CATALYST_MAP[
                selected_category
            ]
        )

    # ========================================
    # CONTEXT
    # ========================================

    event["source"] = news_item.get(
        "source",
        "FDA"
    )

    event["title"] = news_item.get(
        "title",
        ""
    )

    event["summary"] = news_item.get(
        "summary",
        ""
    )

    event["url"] = news_item.get(
        "url"
    )

    event["published_at"] = news_item.get(
        "published_at"
    )

    event["categories"] = list(
        normalized_categories
    )

    event["field"] = None

    event["old_value"] = None

    event["new_value"] = news_item.get(
        "title",
        ""
    )

    return event


# ============================================
# BUILD MULTIPLE CATALYSTS
# ============================================

def build_fda_catalysts(news_items):
    """
    Trasforma una lista di FDA News Items
    in Catalyst Events.
    """

    if not news_items:
        return []

    return [
        build_fda_catalyst(
            item
        )
        for item in news_items
    ]


# ============================================
# FILTER FDA CATALYSTS
# ============================================

def build_relevant_fda_catalysts(
    news_items
):
    """
    Costruisce catalyst soltanto dalle news
    già considerate rilevanti dal FDA News Feed.
    """

    catalysts = []

    for item in news_items:

        priority = str(
            item.get(
                "priority",
                "LOW"
            )
        ).upper()

        if priority not in {
            "EXTREME",
            "HIGH",
        }:
            continue

        catalysts.append(
            build_fda_catalyst(
                item
            )
        )

    return catalysts
