
import pdfplumber
import argparse
import os
import json


def parse_pdf(file_path):
    """Extract text from `file_path`, run the ParserFactory and return
    (parsed_dict | None, full_text).
    """
    full_text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"

    

    return full_text


if __name__ == "__main__":
    # Set up the argument parser to accept a file path
    parser = argparse.ArgumentParser(
        description="Parse a bank statement PDF and extract its text."
    )
    parser.add_argument("file_path", help="The path to the PDF file to parse.")
    args = parser.parse_args()

    if os.path.exists(args.file_path):
        extracted_text = parse_pdf(args.file_path)
        print(extracted_text)
    else:
        print(f"Error: File not found at '{args.file_path}'")