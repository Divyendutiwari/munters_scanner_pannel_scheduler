import requests

# 1. Upload the file
print("Uploading file...")
with open("mock_production_data.xlsx", "rb") as f:
    files = {"file": ("mock_production_data.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    res = requests.post("http://localhost:8000/upload/", files=files)
    print("Upload Status:", res.status_code)
    print("Upload Response:", res.text)

# 2. Fetch schedule for today
print("\nFetching schedule for 2026-06-24...")
res = requests.get("http://localhost:8000/schedule/?target_date=2026-06-24")
print("Schedule Status:", res.status_code)
data = res.json()
print("Number of items scheduled today:", len(data))
if len(data) > 0:
    print("First item:", data[0])
