import requests

key = None
with open(r"C:\mandi_bot\.env", "r") as f:
    for line in f:
        line = line.strip()
        if line.startswith("DATA_GOV_API_KEY="):
            key = line.split("=", 1)[1]
            break

url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
params = {
    "api-key": key,
    "format": "json",
    "limit": 10,
    "filters[state.keyword]": "Haryana"
}

r = requests.get(url, params=params, timeout=15)
print("Status:", r.status_code)
data = r.json()
print("Total records available:", data.get("total", "?"))
print("Records returned:", len(data.get("records", [])))
print()
for rec in data.get("records", [])[:5]:
    print(rec)