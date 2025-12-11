from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import tempfile
import os
from main import parse_pdf
import json

app = Flask(__name__, static_folder=None)
# Enable CORS for development; restrict in production
CORS(app)

@app.route('/')
def serve_index():
    """Serves the main index.html file."""
    return send_from_directory('.', 'index.html')

@app.route('/templates.json')
def serve_templates():
    """Serves the templates.json file."""
    return send_from_directory('.', 'templates.json')

@app.route('/parse', methods=['POST'])
def parse_endpoint():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request; include form field "file"'}), 400

    f = request.files['file']
    if f.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # Save uploaded file to a temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(f.filename)[1]) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name

    try:
        full_text = parse_pdf(tmp_path)
        return jsonify({'ExtractedPdfText': full_text})
       
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

@app.route('/save_templates', methods=['POST'])
def save_templates():
    try:
        new_configs = request.get_json()
        if not new_configs:
            return jsonify({"error": "No data received"}), 400

        with open('templates.json', 'w') as f:
            json.dump(new_configs, f, indent=4)
            
        return jsonify({"message": "Templates saved successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # For local development only; use a proper WSGI server in production.
    app.run(host='0.0.0.0', port=5000, debug=True)
