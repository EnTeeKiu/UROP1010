import os
import pandas as pd
import re

def check_verify_cites_number(verify_text, bid, ask, last, mid):
    if not isinstance(verify_text, str):
        return False
        
    for cents_val in [bid, ask, last, mid]:
        if cents_val <= 0:
            continue
            
        # Cents
        if re.search(r'\b' + str(int(cents_val)) + r'\b', verify_text):
            return True
            
        # Dollars
        dollar_str = f"{cents_val / 100:.2f}"
        if re.search(r'\b' + re.escape(dollar_str) + r'\b', verify_text):
            return True
            
        # Dollars truncated
        dollar_int = str(int(cents_val // 100))
        if re.search(r'\b' + dollar_int + r'\b', verify_text):
            return True
    return False

def analyze_logs(log_dir):
    # Find decision log
    csv_file = None
    for f in os.listdir(log_dir):
        if f.endswith("_decision_log.csv"):
            csv_file = os.path.join(log_dir, f)
            break
            
    if not csv_file:
        print(f"Decision log not found in {log_dir}")
        return None
        
    df = pd.read_csv(csv_file)
    if df.empty:
        print(f"Decision log is empty")
        return None
        
    total_decisions = len(df)
    
    # We need to compute citations using the strict counterpart logic
    citations = 0
    for idx, row in df.iterrows():
        # Depending on agent, the verify text field might differ
        if 'verify_snippet' in row:
            text = row['verify_snippet']
        elif 'reasoning_snippet' in row:
            text = str(row['reasoning_snippet'])
        else:
            text = ""
            
        if check_verify_cites_number(text, row['state_bid'], row['state_ask'], row['state_last'], row['state_mid']):
            citations += 1
            
    print(f"{log_dir} VERIFY Citation Rate: {citations}/{total_decisions} ({citations/total_decisions*100:.1f}%)")
    return citations, total_decisions

if __name__ == '__main__':
    print("--- Field Quality Analysis ---")
    r3_dir = "exp3_reasoning_r3_seed12345"
    json_dir = "exp3_structured_json_seed12345"
    
    if os.path.exists(r3_dir):
        analyze_logs(r3_dir)
    if os.path.exists(json_dir):
        analyze_logs(json_dir)
