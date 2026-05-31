import akshare as ak
import traceback
import time

print("="*60)
print("1. Testing stock_financial_benefit_ths...")
try:
    df = ak.stock_financial_benefit_ths(symbol='000001')
    print(f"Type: {type(df)}")
    if df is not None and not df.empty:
        print(f"Shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
        print("\nFirst 2 rows:")
        print(df.head(2).to_string())
    else:
        print("Empty result")
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()

time.sleep(2)

print("\n" + "="*60)
print("2. Testing stock_financial_cash_ths...")
try:
    df = ak.stock_financial_cash_ths(symbol='000001')
    print(f"Type: {type(df)}")
    if df is not None and not df.empty:
        print(f"Shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
    else:
        print("Empty result")
except Exception as e:
    print(f"Error: {e}")

time.sleep(2)

print("\n" + "="*60)
print("3. Testing stock_financial_debt_ths...")
try:
    df = ak.stock_financial_debt_ths(symbol='000001')
    print(f"Type: {type(df)}")
    if df is not None and not df.empty:
        print(f"Shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
    else:
        print("Empty result")
except Exception as e:
    print(f"Error: {e}")
