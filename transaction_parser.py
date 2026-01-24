import re
import json
import os
def parse_bank_statement_with_sections(txtStatement, regex_config):
    """
    Parses bank statements with sectioned transaction blocks (e.g., CBT style), using section headers to determine credit/debit and sign.
    """
    #with open(txt_path, 'r', encoding='utf-8') as f:
        #text = f.read()

    tx_regex = regex_config["transaction_regex"]
    section_map = regex_config["section_map"]
    # --- NEW: TERMINATION LOGIC ---
    # Retrieve termination pattern from config (default to None if missing)
    termination_pattern = regex_config.get("transaction_termination_regex")
    # ------------------------------
    pattern = re.compile(tx_regex,
    re.MULTILINE
)

# Section mapping
    section_map =regex_config["section_map"]
    transactions = []
    current_section = None
    current_section_id = None
    debitCount = 0
    creditCount = 0
# First, split into blocks by section headers
    lines = txtStatement.splitlines()
    stop_parsing = False  # Flag to kill the loop
    for line in lines:
        line = line.strip()        
        if not line:
           continue
        # --- TERMINATION LOGIC ---
        if termination_pattern and re.search(termination_pattern, line, re.IGNORECASE):
            print(f"STOPPING PARSE at line: {line}")
            stop_parsing = True
            break # Break the loop immediately
        
        if stop_parsing: 
            break
        # -------------------------
    # Detect section headers
        key = line.lower().replace(" ", "")
        #print(f"Processing line: {line} | Key: {key}")
        for sec_id, header in section_map.items():
          if key == header:
            current_section = line
            current_section_id = sec_id
            print(f"Switched to section: {current_section} ({current_section_id})")
            continue
        # Match transaction lines
        match = pattern.match(line)
        if match:
            date = match.group("date")
            amount = (match.group("amount").replace(",", ""))
            amount = amount.replace("-","")
            desc = match.group("desc").strip()
            print("section",current_section_id)
            if current_section_id == "debit":
                amount = amount
                debitCount += 1
            elif current_section_id == "credit":
                creditCount += 1
            amount=float(amount)
            transactions.append({
                "date": date,
                "desc": desc,
                "amount": amount,
                "section": current_section,
                "section_id": current_section_id,
                "type": current_section_id,
            })
    credit_total = sum(t["amount"] for t in transactions if t["section_id"] == "credit")
    debit_total = sum(t["amount"] for t in transactions if t["section_id"] == "debit")
    ending_balance = transactions[-1]["amount"] if transactions else 0   
    output = {
        "bank":"",
        "accountNumber":"",
        "period":"",
        "customer":"",
        "fields": parse_bank_statement(txtStatement, regex_config), 
        "summary":{
            "start": "",
            "end": f"{ending_balance:,.2f}",
            "debits": f"{debit_total:,.2f}",
            "credits": f"{credit_total:,.2f}",
            "debitCount": debitCount,
            "creditCount": creditCount
        },
        "transactions": transactions        
    }

    #print(json.dumps(output, indent=2))
    return output
def parse_bank_statement_with_row(text, regex_config):    
    # 1. Load Regex Patterns
    tx_regex = regex_config["transaction_regex"]
 
    # Helper to clean currency strings to float
    def to_float(s):
        s=normalize_number_string(s)
        return float(s.replace(',', ''))      

    # 3. Extract Transactions
    transactions = []
    total_credit_calc = 0.0
    total_debit_calc = 0.0
    clean_text = '\n'.join(line.strip() for line in text.splitlines())

    termination_pattern = regex_config.get("transaction_termination_regex")
    if termination_pattern:
        term_match = re.search(termination_pattern, clean_text)
        if term_match:
            # Slice the text up to the start of the match
            clean_text = clean_text[:term_match.start()]


    matches = list(re.finditer(tx_regex, clean_text, re.MULTILINE))
    count = 0
    creditCount = 0
    debitCount = 0
    for match in matches:        
        count += 1
        date_raw = match.group("date")
        desc_raw = match.group("desc")
        amount_str = match.group("amount") if "amount" in match.groupdict() else None      
        transtype = 'unknown'
        amount_float = to_float(amount_str.replace('$', ''))
        if amount_float > 0:
                transtype ='credit'
                creditCount += 1
        else: 
                transtype ='debit'   
                debitCount +=  1
        #print(f"Matched Transaction - Date: {date_raw}, Desc: {desc_raw}, Amount: {amount_str}")
        # Format Date: 08/01/2025 (already correct format)
        date_formatted = date_raw

        # Clean Description:
        desc_clean = re.sub(r'\s+', ' ', desc_raw).strip()

        # Math Logic
        amount_float = to_float(amount_str.replace('$', ''))
        if amount_float > 0:
            total_credit_calc += amount_float
        else:
            total_debit_calc += amount_float

        transactions.append({
            "date": date_formatted,
            "desc": desc_clean,
            "amount": amount_str,
            "type": transtype
        })
    # 5. Build Final JSON
    output = {   
        "bank":"",
        "accountNumber":"",
        "period":"",
        "customer":"",  
        "fields": parse_bank_statement(text, regex_config), 
        "summary":{           
            "debits": f"{total_debit_calc:,.2f}",
            "credits": f"{total_credit_calc:,.2f}",
            "debitCount": debitCount,
            "creditCount": creditCount
        },
        "transactions": transactions        
    }
    return output
def parse_bank_statement(text, regex_config):
    accountNumber_regex = regex_config["fields"]["accountNumber_regex"]
    peiod_regex = regex_config["fields"]["period_regex"]
    startBal_regex = regex_config["fields"]["startBalance_regex"]
    endBal_regex = regex_config["fields"]["endBalance_regex"]

    accpattern = re.compile(accountNumber_regex)
    accmatches = accpattern.findall(text)
    period= re.search(peiod_regex, text)

    startbalpattern = re.compile(startBal_regex)
    startbalmatches = startbalpattern.findall(text)

    endbalpattern = re.compile(endBal_regex)
    endbalmatches = endbalpattern.findall(text)  
    stbal=startbalmatches[regex_config["fields"]["startBalance_regex_group"]] if startbalmatches else "0.00"
    endbal=endbalmatches[regex_config["fields"]["endBalance_regex_group"]] if endbalmatches else "0.00"
    return {
        "accountNumber": accmatches[regex_config["fields"]["accountNumber_group"]] if accmatches else "",
        "period": period.group(1) if period else "",
        "startBalance":  stbal ,
        "endBalance":  endbal
    }
    
def normalize_number_string(s: str) -> str:
    s = s.strip()
    if s.endswith("-"):
        return "-" + s[:-1]
    return s
