from langchain.tools import tool

@tool
def search_flights(origin: str, destination: str, date: str = "flexible") -> dict:
    """Search illustrative mock flight options; these are not live fares."""
    return {"source":"DEMO MOCK DATA","origin":origin,"destination":destination,"date":date,"options":[{"airline":"Example Air","price":180,"currency":"EUR","duration":"2h 10m"}]}
@tool
def search_hotels(city: str, budget_max: float | None = None) -> dict:
    """Find illustrative mock hotels in a city."""
    return {"source":"DEMO MOCK DATA","city":city,"budget_max":budget_max,"options":[{"name":"Central Guesthouse","nightly_price":95,"currency":"EUR"},{"name":"Riverside Hotel","nightly_price":145,"currency":"EUR"}]}
@tool
def find_attractions(city: str, interests: list[str] | None = None) -> dict:
    """Find illustrative mock attractions matching interests."""
    return {"source":"DEMO MOCK DATA","city":city,"interests":interests or [],"options":[{"name":"City History Museum","type":"museum"},{"name":"Riverside Walk","type":"outdoors"},{"name":"Modern Art Gallery","type":"museum"}]}
@tool
def search_restaurants(city: str, cuisine: str = "local") -> dict:
    """Find illustrative mock restaurants by cuisine."""
    return {"source":"DEMO MOCK DATA","city":city,"cuisine":cuisine,"options":[{"name":"Trattoria Example","cuisine":"Italian","price_level":"€€"},{"name":"Market Table","cuisine":"local","price_level":"€"}]}
@tool
def check_weather(city: str, date: str = "upcoming") -> dict:
    """Return illustrative mock weather, not a forecast."""
    return {"source":"DEMO MOCK DATA","city":city,"date":date,"forecast":"Mild and partly cloudy (illustrative)"}

TRAVEL_TOOLS=[search_flights,search_hotels,find_attractions,search_restaurants,check_weather]
