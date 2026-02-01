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
    check_tx_regex = regex_config["check_tx_regex"]

    # ------------------------------
    pattern = re.compile(tx_regex, re.MULTILINE)
    check_pattern = re.compile(check_tx_regex, re.MULTILINE)

# Section mapping
    section_map =regex_config["section_map"]
    transactions = []
    current_section = None
    current_section_id = None
    debitCount = 0
    creditCount = 0
    checkCount=0
# First, split into blocks by section headers
    lines = txtStatement.splitlines()
    stop_parsing = False  # Flag to kill the loop
    for line in lines:
        line = line.strip()        
        if not line:
           continue
        # --- TERMINATION LOGIC ---
        normalized_line = re.sub(r"\s+", "", line).lower()
        if termination_pattern and re.search(termination_pattern, normalized_line, re.IGNORECASE):
            print(f"STOPPING PARSE at line: {line}")
            stop_parsing = True
            break # Break the loop immediately
        
        if stop_parsing: 
            break
        # -------------------------
    # --------Detect section headers---------------
        key = line.lower().replace(" ", "")
        #print(f"Processing line: {line} | Key: {key}")
        for sec_id, header in section_map.items():
          if key == header:
            current_section = line
            current_section_id = sec_id
            print(f"Switched to section: {current_section} ({current_section_id})")
            continue
    # ----------------------------------------------      


        # Match transaction lines for credit and debit
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

    # -------- CHECK ACTIVITY (MULTI-COLUMN) --------
        if current_section_id == "check":
            for match in check_pattern.finditer(line):
                date = match.group("date")
                check_no = match.group("check")
                amount = float(match.group("amount").replace(",", ""))

                checkCount += 1

                transactions.append({
                "date": date,
                "check": check_no,
                "amount": amount,
                "desc": f"CHECK {check_no}",
                "section": current_section,
                "section_id": "check",
                "type": "check"
                })
                continue
    # ---------------End if for loop-------------------------------

    credit_total = sum(t["amount"] for t in transactions if t["section_id"] == "credit")
    #debit_total = sum(t["amount"] for t in transactions if t["section_id"] == "debit")
    debit_total = sum(t["amount"]for t in transactions if t["section_id"] in ("debit", "check")
)
    ending_balance = transactions[-1]["amount"] if transactions else 0   
    output = {        
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
def parse_bank_statement_with_row(text, regex_config,section_name):   
    if not section_name:
        section_name ="unknown"
    # 1. Load Regex Patterns
    tx_regex = regex_config["transaction_regex"] #signed amount
    column_tx_regex = regex_config.get("transaction_regex_columns")  # debit/credit columns
  
    pattern = re.compile(tx_regex, re.MULTILINE) if tx_regex else None
    column_pattern = re.compile(column_tx_regex, re.MULTILINE) if column_tx_regex else None

    print("sec:",section_name)
    # Helper to clean currency strings to float
    # Helper to clean currency strings to float
    def to_float(s):
        if not s: 
            return 0.0
        
        s = str(s)
        
        # 1. REMOVE QUOTES (Critical for CSV parsing)
        s = s.replace('"', '').replace("'", "")
        
        # 2. Clean delimiters
        s = s.replace('$', '').replace(',', '').strip()
        
        # 3. Handle trailing negatives
        if s.endswith('-'):
            s = '-' + s[:-1]
            
        try:
            return float(s)
        except ValueError:
            return 0.0              

    # 3. Extract Transactions
    transactions = []
    total_credit_calc = 0.0
    total_debit_calc = 0.0
    creditCount = 0
    debitCount = 0

    clean_text = '\n'.join(line.strip() for line in text.splitlines())

    termination_pattern = regex_config.get("transaction_termination_regex")
    if termination_pattern:
        term_match = re.search(termination_pattern, clean_text)
        if term_match:
            # Slice the text up to the start of the match
            clean_text = clean_text[:term_match.start()]

    
    for line in clean_text.splitlines():
        if not line.strip():
            continue

    # ----------------------------------------------------
    # 1️⃣ COLUMN-BASED (Debit / Credit columns)
    # ----------------------------------------------------

        if column_pattern:
            m = column_pattern.match(line)
            if m:
                debit = m.group("debit")
                credit = m.group("credit")

                if credit and credit.strip():
                    amount = to_float(credit)
                    transtype = "credit"
                    total_credit_calc += amount
                    creditCount += 1

                elif debit and debit.strip():
                    amount = to_float(debit)
                    transtype = "debit"
                    total_debit_calc += amount
                    debitCount += 1

                else:
                    continue  # safety

                transactions.append({
                    "date": m.group("date"),
                    "desc": re.sub(r"\s+", " ", m.group("desc")).strip(),
                    "amount": f"{amount:.2f}",
                    "type": transtype,
                    "section": section_name.replace(" ", "_").lower()
                })
                continue  # 🚨 critical (prevents double parsing)


    # ----------------------------------------------------
    # 2️⃣ SIGNED AMOUNT (existing logic)
    # ----------------------------------------------------

        if pattern:
            match = pattern.match(line)
            if not match:
                continue

            date_raw = match.group("date")
            desc_raw = match.group("desc")
            amount_str = match.group("amount")

            amount_float = to_float(amount_str)

            if amount_float > 0:
                transtype = "credit"
                total_credit_calc += amount_float
                creditCount += 1
            else:
                transtype = "debit"
                total_debit_calc += amount_float
                debitCount += 1

            transactions.append({
                "date": date_raw,
                "desc": re.sub(r"\s+", " ", desc_raw).strip(),
                "amount": amount_str,
                "type": transtype,
                "section": section_name.replace(" ", "_").lower()
            })


    # 5. Build Final JSON
    output = { 
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
    print("Using account number regex:", accountNumber_regex)
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
def parse_multi_account_statement(text, regex_config):
    """
    Splits the PDF text into sections based on account headers and parses each separately.
    Merges consecutive sections with the same account ID.
    Returns a list of account objects.
    """
    split_pattern = regex_config.get("section_split_regex")
    print("Using section split pattern:", split_pattern)
    
    if not split_pattern:
        print("No section split pattern defined, treating as single account statement.")
        return parse_bank_statement_with_row(text, regex_config, "")

    # Split the text
    sections = [s for s in re.split(split_pattern, text) if s.strip()]
    print(f"Found {len(sections)} sections based on split pattern.")
    
    accounts_data = []
    counter = 0

    # Helper to parse currency strings for math operations
    def parse_currency(val):
        if not val: return 0.0
        clean = str(val).replace('$', '').replace(',', '').replace(' ', '')
        if clean.endswith('-'): clean = '-' + clean[:-1]
        try: return float(clean)
        except ValueError: return 0.0

    for section_text in sections:
        counter += 1
        print("sec start***",section_text,"**** sec end")
        # Check if this section has transactions
        # if not re.search(regex_config["transaction_regex"], section_text, re.MULTILINE):
        #     print(f"Skipping section {counter} as it contains no transactions.")
        #     continue    
        # Identify Account Name/ID first
        acc_name_match = re.search(regex_config.get("account_name_regex", ""), section_text)
        current_account_type = "Unknown"
        
        if acc_name_match:
            current_account_type = acc_name_match.group(0).strip()
            print("Found account name:", current_account_type)
        
        # Parse the section data
        account_data = parse_bank_statement_with_row(section_text, regex_config, section_name=current_account_type)
        account_data["accountType"] = current_account_type

        # --- MERGE LOGIC START ---
        # Check if we should merge with the previous account
        if accounts_data and accounts_data[-1].get("accountType") == current_account_type:
            print(f"Merging section {counter} into existing '{current_account_type}' account...")
            previous_data = accounts_data[-1]
            
            # 1. Merge Transactions
            previous_data["transactions"].extend(account_data["transactions"])
            
            # 2. Merge Summaries
            prev_sum = previous_data["summary"]
            curr_sum = account_data["summary"]
            
            # Update Counts
            prev_sum["debitCount"] += curr_sum["debitCount"]
            prev_sum["creditCount"] += curr_sum["creditCount"]
            
            # Update Totals (Parse -> Add -> Re-format)
            total_debits = parse_currency(prev_sum.get("debits")) + parse_currency(curr_sum.get("debits"))
            total_credits = parse_currency(prev_sum.get("credits")) + parse_currency(curr_sum.get("credits"))
            
            prev_sum["debits"] = f"{total_debits:,.2f}"
            prev_sum["credits"] = f"{total_credits:,.2f}"
            
            # 3. Update Ending Balance (The later section usually has the correct final balance)
            if account_data["fields"].get("endBalance") and account_data["fields"]["endBalance"] != "0.00":
                previous_data["fields"]["endBalance"] = account_data["fields"]["endBalance"]
                
        else:
            # New account found, just append
            accounts_data.append(account_data)
        # --- MERGE LOGIC END ---

    return {"accounts": accounts_data}