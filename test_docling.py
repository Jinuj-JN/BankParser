from docling.document_converter import DocumentConverter
import sys

try:
    print("Python executable:", sys.executable)
    print("Attempting to instantiate DocumentConverter...")
    converter = DocumentConverter()
    print("Success: DocumentConverter instantiated.")
except Exception as e:
    print("Error:", e)
    sys.exit(1)
