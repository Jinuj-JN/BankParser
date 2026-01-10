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

@app.route('/data/<path:filename>')
def serve_data(filename):
    """Serves files from the data directory."""
    return send_from_directory('data', filename)

def detect_bank(text):
    """Detects the bank by searching for identifiers in the text."""
    try:
        with open('data/templates.json', 'r') as f:
            templates = json.load(f)
        
        # Count matches for each bank to find the best fit
        scores = {}
        for bank_key, template in templates.items():
            if 'identifiers' in template:
                score = 0
                for identifier in template['identifiers']:
                    if identifier.lower() in text.lower():
                        score += 1
                if score > 0:
                    scores[bank_key] = score
        
        if scores:
            # Return the bank with the highest number of identifier matches
            return max(scores, key=scores.get)
    except Exception as e:
        print(f"Detection error: {e}")
    return None

@app.route('/parse', methods=['POST'])
@app.route('/parse1', methods=['POST'])
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
        full_text = parse_pdf(tmp_path,True if request.path == '/parse1' else False)
        detected_bank_key = detect_bank(full_text)
        
        # Load templates to get the detected bank's template
        detected_bank_template = None
        if detected_bank_key:
            with open('data/templates.json', 'r') as f:
                templates = json.load(f)
                detected_bank_template = templates.get(detected_bank_key)

        return jsonify({
            'ExtractedPdfText': full_text,
            'detectedBankKey': detected_bank_key,
            'detectedBankTemplate': detected_bank_template
        })
       
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

        with open('data/templates.json', 'w') as f:
            json.dump(new_configs, f, indent=4)
            
        return jsonify({"message": "Templates saved successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/save_prompts', methods=['POST'])
def save_prompts():
    try:
        new_prompts = request.get_json()
        if not new_prompts:
            return jsonify({"error": "No data received"}), 400

        with open('data/prompts.json', 'w') as f:
            json.dump(new_prompts, f, indent=4)
            
        return jsonify({"message": "Prompts saved successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # For local development only; use a proper WSGI server in production.
    app.run(host='0.0.0.0', port=5000, debug=True)
