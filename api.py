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

@app.route('/ai/call', methods=['POST'])
def ai_call():
    import requests
    try:
        data = request.get_json()
        platform = data.get('platform')
        model = data.get('model')
        api_key = data.get('apiKey')
        prompt = data.get('prompt')

        if not all([platform, api_key, prompt]):
            return jsonify({"error": "Missing required fields"}), 400

        if platform == 'openai':
            print(f"Proxying request to OpenAI: {model}")
            url = 'https://api.openai.com/v1/chat/completions'
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
            body = {
                'model': model or "gpt-4o",
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.1
            }
            response = requests.post(url, headers=headers, json=body)
            if not response.ok:
                print(f"OpenAI Error: {response.status_code} - {response.text}")
            response.raise_for_status()
            ai_data = response.json()
            return jsonify({'content': ai_data['choices'][0]['message']['content']})

        elif platform == 'anthropic':
            print(f"Proxying request to Anthropic: {model}")
            url = 'https://api.anthropic.com/v1/messages'
            headers = {
                'Content-Type': 'application/json',
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01'
            }
            body = {
                'model': model or "claude-3-5-sonnet-20241022",
                'max_tokens': 4096,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.1
            }
            response = requests.post(url, headers=headers, json=body)
            if not response.ok:
                print(f"Anthropic Error: {response.status_code} - {response.text}")
            response.raise_for_status()
            ai_data = response.json()
            return jsonify({'content': ai_data['content'][0]['text']})

        else: # Default to Gemini
            model_name = model or 'gemini-2.0-flash-exp'
            print(f"Proxying request to Gemini: {model_name}")
            url = f'https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}'
            headers = {'Content-Type': 'application/json'}
            body = {
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {'temperature': 0.1}
            }
            response = requests.post(url, headers=headers, json=body)
            if not response.ok:
                print(f"Gemini Error: {response.status_code} - {response.text}")
            response.raise_for_status()
            ai_data = response.json()
            return jsonify({'content': ai_data['candidates'][0]['content']['parts'][0]['text']})

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        error_msg = str(e)
        try:
            error_data = e.response.json()
            print(f"Server-side AI Cache Error Body: {json.dumps(error_data, indent=2)}")
            # Try to get the recursive error message from different AI providers
            if 'error' in error_data:
                if isinstance(error_data['error'], dict):
                    error_msg = error_data['error'].get('message', str(e))
                else:
                    error_msg = error_data['error']
            elif 'message' in error_data:
                error_msg = error_data['message']
        except:
            pass
        return jsonify({"error": error_msg, "status_code": status_code}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/parse_transactions', methods=['POST'])
def parse_transactions_endpoint():
    data = request.get_json()
    statement_text = data.get('text', '')
    regex = data.get('regexPattern', '')
    print(f"Received regex pattern: {regex}")
    #print(f"Statement text length: {statement_text}")
    #txns = parse_bank_statement_with_row(statement_text, regex_pattern=regex if regex else None)
    return jsonify({'transactions': "txns"})

if __name__ == '__main__':
    # For local development only; use a proper WSGI server in production.
    app.run(host='0.0.0.0', port=5000, debug=True)
