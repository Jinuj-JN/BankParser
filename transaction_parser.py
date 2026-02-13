import re
import json
import os

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

#Extract the date pattern from transaction regex."""
def get_date_pattern_from_config(transaction_regex):
# Look for (?P<date>...) pattern

    if not transaction_regex or not isinstance(transaction_regex, str):
        return r'\d{1,2}/\d{1,2}'  # Default pattern

    match = re.search(r'\(\?P<date>([^)]+)\)', transaction_regex)
    if match:
        date_pattern = match.group(1)
        # Clean up the pattern for use in transaction start detection
        date_pattern = date_pattern.replace('\\', '\\\\')
        return date_pattern
    return r'\d{1,2}/\d{1,2}'  # Default


def parse_account_statement_with_sections(txtStatement, regex_config):
    accounts_single_data = [] 
    current_account_type = "Section Account" 
    account_single_data = parse_bank_statement_with_sections(txtStatement, regex_config)
    account_single_data["accountType"] = current_account_type 
    accounts_single_data.append(account_single_data)
    return {"accounts": accounts_single_data}


def parse_bank_statement_with_sections(txtStatement, regex_config):
    """
    Parses bank statements with sectioned transaction blocks (e.g., CBT style), using section headers to determine credit/debit and sign.
    """
                  
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
        if current_section_id == "check":
            found_check = False  # Initialize the variable

            for match in check_pattern.finditer(line):
                if match:
                    found_check = True
                    # print(f"Full match: {match.group(0)}")
                    # print(f"Date group: '{match.group('date')}'")
                    # print(f"Check group: '{match.group('check') if match.group('check') else 'None'}'")
                    # print(f"Amount group: '{match.group('amount')}'")
                    # print(f"All groups: {match.groups()}")
                    date = match.group("date")
                    check_no = match.group("check") if match.group("check") else ""
                    amount = to_float(match.group("amount").replace(",", ""))
                    
                    checkCount += 1
                    
                    # transactions.append({
                    #     "date": date,
                    #     "check": check_no,
                    #     "amount": amount,
                    #     "desc": f"CHECK {check_no}" if check_no else "CHECK",
                    #     "section": current_section,
                    #     "section_id": "check",
                    #     "type": "check"
                    # })
                    
                    transactions.append({
                    "date": date,
                    "desc": f"CHECK {check_no}" if check_no else "CHECK",
                    "amount": amount,
                    "type": "check",
                    "section_id": "check"
                    })

            
            # If we found a check, skip other processing for this line
            if found_check:
                continue

    # -------- CHECK ACTIVITY (MULTI-COLUMN) --------

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
            amount=to_float(amount)
            transactions.append({
                "date": date,
                "desc": desc,
                "amount": amount,
                "section": current_section,
                "section_id": current_section_id,
                "type": current_section_id,
            })

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
    section_map = regex_config.get("section_map", {})
    #tx_regex = regex_config["transaction_regex"] #signed amount
    tx_regex = regex_config.get("transaction_regex") #signed amount
    column_tx_regex = regex_config.get("transaction_regex_columns")  # debit/credit columns
  
    pattern = re.compile(tx_regex, re.MULTILINE) if tx_regex else None
    column_pattern = re.compile(column_tx_regex, re.MULTILINE) if column_tx_regex else None

    # ----------------------------------------------------
    # CHECK variables
    # ----------------------------------------------------
    
    check_tx_regex = regex_config.get("check_tx_regex")
    check_pattern = re.compile(check_tx_regex) if check_tx_regex else None

    print("sec:",section_name)
    

    # ------------------------------------multi line logic-----------------------

    # if tx_regex and isinstance(tx_regex, str):
    # # Use transaction_regex if available
    #     date_pattern = get_date_pattern_from_config(tx_regex)
    #     print(f"Extracted date pattern from transaction_regex: {date_pattern}")
    # elif column_tx_regex and isinstance(column_tx_regex, str):
    #     # Fall back to column_tx_regex if transaction_regex is not available
    #     date_pattern = get_date_pattern_from_config(column_tx_regex)
    #     print(f"Extracted date pattern from column_tx_regex: {date_pattern}")
    # else:
    #     print(f"Using default date pattern: {date_pattern}")

    # date_pattern = get_date_pattern_from_config(tx_regex)
    # print(f"Extracted date pattern: {date_pattern}")

    # ------------------------------------multi line logic-----------------------

    # 3. Extract Transactions
    transactions = []
    total_fee_calc=0.0
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
        line_lower = line.lower()
        
        for section_id, header in section_map.items():
            if re.search(rf"\b{re.escape(header.lower())}\b", line_lower):
                section_name = header
                continue


    # ----------------------------------------------------
    # 1️⃣ CHECKS PAID (multi-column, same line)
    # ----------------------------------------------------

        check_section = section_map.get("check", "").lower()
        found_check = False

        if check_pattern and check_section and check_section in section_name.lower():
           for m in check_pattern.finditer(line):
                if m:
                    found_check=True
                    check_no = m.group("check")
                    date_raw = m.group("date")
                    amount = to_float(m.group("amount"))

        # Checks are always debits
                if found_check:
                    total_debit_calc += amount
                    debitCount += 1

                    transactions.append({
                    "date": date_raw.replace("-", "/"),
                    "desc": f"CHECK {check_no}",
                    "amount": f"-{amount:.2f}",
                    "type": "check",
                    "section": section_name.replace(" ", "_").lower()
                    })

        if found_check:
              continue  # 🚨 prevents double parsing

    #
    # Fee section
    #
        
        fee_cfg = regex_config.get("fee", {})
        fee_enabled = fee_cfg.get("FeeEnabled", False)

        is_fee_transaction = False

        if fee_enabled:
            is_fee = any(k in line_lower for k in fee_cfg.get("FeeKeywords", []))
            is_bank_fee = any(k in line_lower for k in fee_cfg.get("BankFeeIndicators", []))
            is_merchant_fee = any(k in line_lower for k in fee_cfg.get("MerchantIndicators", []))

            is_fee_transaction = (
            is_fee and
            (is_bank_fee or not is_merchant_fee)
            )

    # ----------------------------------------------------
    # 1️⃣ COLUMN-BASED (Debit / Credit columns)
    # ----------------------------------------------------

        if column_pattern:
            m = column_pattern.match(line)
            if m:
                
                groups = m.groupdict()
                debit = groups.get("debit") or groups.get("withdrawal")
                credit = groups.get("credit") or groups.get("deposit")

                if credit and credit.strip():
                    amount = to_float(credit)
                    
                    if is_fee_transaction:
                        transtype = "fee"    
                        total_fee_calc += amount
                    else:    
                        transtype = "credit"
                        total_credit_calc += amount
                        creditCount += 1

                elif debit and debit.strip():
                    amount = to_float(debit)
                    
                    if is_fee_transaction:
                        transtype = "fee"    
                        total_fee_calc += amount
                    else:    
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
                
                if is_fee_transaction:
                    transtype = "fee"
                    total_fee_calc += amount_float
                else:
                    transtype = "credit"
                    total_credit_calc += amount_float
                    creditCount += 1
            else:

                if is_fee_transaction:
                    transtype = "fee"
                    total_fee_calc += amount_float
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
            "creditCount": creditCount,
            "fees": f"{total_fee_calc:,.2f}"
        },
        "transactions": transactions        
    }
    return output
def parse_bank_statement(text, regex_config):
    accountNumber_regex = regex_config["fields"]["accountNumber_regex"]
    print("Using account number regex:", accountNumber_regex)
    period_regex = regex_config["fields"]["period_regex"]
    startBal_regex = regex_config["fields"]["startBalance_regex"]
    endBal_regex = regex_config["fields"]["endBalance_regex"]

    accpattern = re.compile(accountNumber_regex)
    accmatches = accpattern.findall(text)
    period= re.search(period_regex, text)

    startbalpattern = re.compile(startBal_regex)
    startbalmatches = startbalpattern.findall(text)

    endbalpattern = re.compile(endBal_regex)
    endbalmatches = endbalpattern.findall(text)  
    stbal=startbalmatches[regex_config["fields"]["startBalance_regex_group"]] if startbalmatches else "0.00"
    endbal=endbalmatches[regex_config["fields"]["endBalance_regex_group"]] if endbalmatches else "0.00"
    return {
        "bankName": regex_config["name"],
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
        accounts_single_data = [] 
        current_account_type = "Single Account" 
        account_single_data = parse_bank_statement_with_row(text, regex_config, "")
        account_single_data["accountType"] = current_account_type 
        accounts_single_data.append(account_single_data)
        return {"accounts": accounts_single_data} 
        #return parse_bank_statement_with_row(text, regex_config, "")

    # Split the text
    #sections = [s for s in re.split(split_pattern, text) if s.strip()]

    all_sections = re.split(split_pattern, text)
    sections = [s.strip() for s in all_sections[1:] if s.strip()]  # Skip first

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
        #if not re.search(regex_config.get("transaction_regex"), section_text, re.MULTILINE):
            #print(f"Skipping section {counter} as it contains no transactions.")
            #continue    
        
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