from scanner.biotech_universe import (
    _is_biotech_pharma_quote, _to_market_row, get_biotech_universe,
)


class Response:
    def __init__(self, payload):
        self.payload = payload
    def raise_for_status(self):
        return None
    def json(self):
        return self.payload


class Session:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        payload = self.payloads.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return Response(payload)


def screener_payload(quotes, total=None):
    return {"finance": {"result": [{
        "quotes": quotes, "total": len(quotes) if total is None else total,
    }]}}


def quote(symbol, industry="Biotechnology", change=12.5):
    return {
        "symbol": symbol, "shortName": symbol + " Inc.",
        "longName": symbol + " Therapeutics", "industry": industry,
        "sector": "Healthcare", "exchange": "NASDAQ",
        "regularMarketChangePercent": change, "regularMarketPrice": 4.2,
        "regularMarketVolume": 900000, "averageDailyVolume3Month": 300000,
    }


def test_biotech_filter_includes_biotech_and_drugmakers_only():
    assert _is_biotech_pharma_quote(quote("BIO")) is True
    assert _is_biotech_pharma_quote(quote("PHARMA", "Drug Manufacturers - General")) is True
    assert _is_biotech_pharma_quote(quote("BANK", "Banks - Regional")) is False


def test_market_row_has_change_and_volume_ratio():
    row = _to_market_row(quote("BIO", change=23.4))
    assert row["price_change_pct"] == 23.4
    assert row["volume_ratio"] == 3.0
    assert row["market_data_source"] == "YAHOO_FINANCE_SCREENER"


def test_universe_reads_screener_and_filters_unrelated_industries():
    session = Session([screener_payload([
        quote("BIO", change=21.0),
        quote("PHARMA", "Drug Manufacturers - General", 17.0),
        quote("BANK", "Banks - Regional", 99.0),
    ], total=3)])
    result = get_biotech_universe(session=session, max_pages=2, page_size=250)
    assert set(result) == {"BIO", "PHARMA"}
    assert result["BIO"]["price_change_pct"] == 21.0
    assert len(session.calls) == 1

def test_daily_top5_includes_unconfigured_market_candidates():
    from scanner.daily_top5 import build_daily_top5
    watchlist = {"KNOWN": {"company": "Known Bio", "programs": []}}
    broad = {
        "NEWBIO": {
            "ticker": "NEWBIO", "company": "NewBio Therapeutics",
            "short_name": "NewBio", "industry": "Biotechnology",
            "exchange": "NASDAQ", "price_change_pct": 45.0,
            "volume": 500000, "volume_ratio": 4.0, "price": 3.2,
            "market_data_source": "YAHOO_FINANCE_SCREENER",
        }
    }
    rows = build_daily_top5(
        watchlist=watchlist, history={},
        snapshot_fn=lambda ticker: {
            "price_change_pct": 2.0, "volume": 1000,
            "volume_ratio": 1.0, "price": 10.0,
        },
        date_value="2026-10-20",
        universe_fn=lambda: broad,
        include_broad_universe=True,
    )
    assert rows[0]["ticker"] == "NEWBIO"
    assert rows[0]["radar_status"] == "NEW_CANDIDATE"
    assert rows[0]["market_data_source"] == "YAHOO_FINANCE_SCREENER"

def test_market_row_parses_yahoo_formatted_numeric_objects():
    item = quote("WRAPPED")
    item["regularMarketChangePercent"] = {"raw": 31.25, "fmt": "31.25%"}
    item["regularMarketPrice"] = {"raw": 2.5, "fmt": "2.50"}
    item["regularMarketVolume"] = {"raw": 800000, "fmt": "800,000"}
    item["averageDailyVolume3Month"] = {"raw": 200000, "fmt": "200,000"}
    row = _to_market_row(item)
    assert row["price_change_pct"] == 31.25
    assert row["price"] == 2.5
    assert row["volume"] == 800000
    assert row["volume_ratio"] == 4.0
