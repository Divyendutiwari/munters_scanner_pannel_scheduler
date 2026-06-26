"""
Generate a demo Excel file with 1 order (5 panels = 10 sheets)
matching the barcode scanner setup (DEMO-01-XX-IN/OUT).
"""
import pandas as pd
import os

# Single order: 5 panels = 10 sheets (matching barcode format DEMO-01-XX-IN/OUT)
orders = [
    {
        "Month": "June",
        "Sales Person": "S-Hyd - Vinay/Sagar",
        "WO.NO.": "WO-DEMO-001",
        "SAP CODE": "SAP-DEMO",
        "CUSTOMER NAME": "Demonstration Corp",
        "DWG NO.": "DEMO-01",
        "CFM": 5000,
        "QTY": 1,
        "FAB Code": "FAB-01",
        "AB/UNIT QTY/ COMP QTY": 1,
        "Panel qty per unit": 5,
        "Total panel qty": 5,
        "NO. OF STROKES": 80,
    },
]

df = pd.DataFrame(orders)

file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_10_orders.xlsx")
df.to_excel(file_path, index=False)

print("=" * 60)
print("  DEMO EXCEL FILE GENERATED")
print("=" * 60)
print(f"  File: {file_path}")
print(f"  Orders: 1")
print(f"  DWG NO: DEMO-01")
print(f"  Total Panels: 5  (= 10 sheets)")
print(f"  Total Strokes: 80 (= 5 panels × 16)")
print()
print("  Barcodes that work with this order:")
print("    DEMO-01-01-IN, DEMO-01-01-OUT")
print("    DEMO-01-02-IN, DEMO-01-02-OUT")
print("    DEMO-01-03-IN, DEMO-01-03-OUT")
print("    DEMO-01-04-IN, DEMO-01-04-OUT")
print("    DEMO-01-05-IN, DEMO-01-05-OUT")
print()
print("  Upload this file via the MES dashboard to begin.")
print("=" * 60)
