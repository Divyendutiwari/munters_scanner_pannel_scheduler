import pandas as pd
import random
import os

# Set seed for reproducibility
random.seed(42)

# Define column names from the image
columns = [
    "Month", "Sales Person", "WO.NO.", "SAP CODE", "CUSTOMER NAME", 
    "DWG NO.", "CFM", "QTY", "FAB Code", "AB/UNIT QTY/ COMP QTY", 
    "Panel qty per unit", "Total panel qty", "NO. OF STROKES"
]

# Base data to populate rows based on the image pattern
months = ["May", "June"]
sales_persons = ["S-Hyd - Dnk/Syed", "S-Hyd - Vinay/Sagar"]
wo_nos = [7494, 7543, 7544, 7545, 7546, 7245, 7344, 7345, 7444, 7346, 7502, 7503]
sap_codes = ["261100147", "261100150", "261100154", "261100140", "261100201"]
customers = ["Micron Electricals", "Airmech Engineers", "Total MNE", "Cello Lus Hvac Systems", "KK Comforts"]
dwg_nos = [
    "FGFM251579-017", "FGFM251579-021", "FGFM251579-022", "FGFM251579-023",
    "FGCV252600-033", "FGCV252600-032", "FGWT262840-050",
    "FGFM252516-003", "FGFM252516-004", "FGFM252516-005", "FGFM252516-006",
    "FGFM252516-011", "FGFM252516-012", "FGFM252516-014", "FGFM252516-016",
    "FGFM252516-018", "FGFM252516-019", "FGFM252516-020", "FGFM252516-021"
]
fab_codes = ["FGFM251579-017-FAB-01", "FGFM252516-003-FAB-01", "FGCV252600-033-FAB-01"]

data = []

# Generate 30 rows of data mimicking the image
for i in range(50):
    month = random.choice(months)
    sales = random.choice(sales_persons)
    wo = random.choice(wo_nos)
    sap = random.choice(sap_codes)
    customer = random.choice(customers)
    dwg = random.choice(dwg_nos)
    cfm = random.randint(10000, 30000)
    qty = random.randint(1, 10)
    fab = random.choice(fab_codes)
    ab_unit = random.randint(1, 10)
    panel_qty_per_unit = random.randint(10, 40)
    total_panel_qty = qty * panel_qty_per_unit
    
    # User specified: all panels are considered thermal, 16 strokes per panel
    # Total strokes = total_panel_qty * 16
    no_strokes = total_panel_qty * 16
    
    data.append([
        month, sales, wo, sap, customer, dwg, cfm, qty, fab, 
        ab_unit, panel_qty_per_unit, total_panel_qty, no_strokes
    ])

df = pd.DataFrame(data, columns=columns)

# We want exactly 800 * 5 = 4000 total panels to have enough data for 5 days of production
# Let's adjust total panels to get a large dataset
# Actually, the user says 800 sheets per day for autofold. We need enough panels.
# A sheet might make multiple panels (nesting). The prompt says: "2 cutouts = 1 panel" 
# For now, let's just create a good amount of mock data.

file_path = 'mock_production_data.xlsx'
df.to_excel(file_path, index=False)
print(f"Successfully created mock excel data at: {os.path.abspath(file_path)}")
