from scanner.fda_feed import get_fda_news


news = get_fda_news(max_items=10)

print()
print("========== LIVE FDA TEST ==========")
print(f"News recuperate: {len(news)}")
print()

for item in news:
    print("TITLE:", item.get("title"))
    print("DATE:", item.get("published_at"))
    print("URL:", item.get("url"))
    print("-----------------------------------")

print("===================================")