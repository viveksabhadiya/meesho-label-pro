import fitz  # PyMuPDF
import re
import os
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# --- CONFIGURATION ---
ID_INSTANCE = "7103498692"
API_TOKEN_INSTANCE = "217a71fbbecb41658e5fffa00451817bbe62ea618ad1461c8d"
CHAT_ID = "919428146028-1606295944@g.us"

# Simple HTML UI
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Meesho Label Pro</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #f4f4f9; }
        .card { background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center; width: 400px; }
        input[type="file"] { margin: 20px 0; }
        button { background: #ff4757; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-size: 16px; }
        button:hover { background: #ff6b81; }
        #status { margin-top: 15px; font-weight: bold; color: #2ed573; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Meesho Label Sorter</h2>
        <p>Upload your PDF (Delhivery -> Account -> Qty -> SKU)</p>
        <input type="file" id="pdfInput" accept="application/pdf">
        <br>
        <button onclick="uploadFile()">Process & Send to WhatsApp</button>
        <div id="status"></div>
    </div>

    <script>
        async function uploadFile() {
            const fileInput = document.getElementById('pdfInput');
            const status = document.getElementById('status');
            if (!fileInput.files[0]) return alert("Please select a file!");

            status.innerText = "Processing... Please wait.";
            const formData = new FormData();
            formData.append('pdf', fileInput.files[0]);

            try {
                const response = await fetch('/process-pdf', { method: 'POST', body: formData });
                const result = await response.json();
                status.innerText = result.message;
            } catch (err) {
                status.innerText = "Error uploading file.";
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

def extract_label_data(page):
    text = page.get_text()
    courier = "Delhivery" if "Delhivery" in text else "Other"
    
    # Account Name extraction based on the provided image logic
    account_name = "N/A"
    if "If undelivered, return to:" in text:
        match = re.search(r"If undelivered, return to:\s*\n(.*?)\n", text)
        if match:
            account_name = match.group(1).strip()

    sku_match = re.search(r"SKU\s*\n(.*?)\s*\n", text)
    qty_match = re.search(r"Qty\s*\n(\d+)", text)
    sku = sku_match.group(1).strip() if sku_match else "Unknown"
    qty = int(qty_match.group(1)) if qty_match else 1

    return {"page_index": page.number, "courier": courier, "account": account_name, "sku": sku, "qty": qty}

@app.route('/process-pdf', methods=['POST'])
def process_pdf():
    file = request.files['pdf']
    doc = fitz.open(stream=file.read(), filetype="pdf")
    all_labels = [extract_label_data(page) for page in doc]

    # Custom Sorting Logic: Courier -> Account -> Qty -> SKU
    sorted_labels = sorted(all_labels, key=lambda x: (
        x['courier'] != 'Delhivery', 
        x['account'].lower(),
        x['qty'],
        x['sku'].lower()
    ))

    output_doc = fitz.open()
    for label in sorted_labels:
        output_doc.insert_pdf(doc, from_page=label['page_index'], to_page=label['page_index'])

    output_filename = "/tmp/sorted_labels.pdf" # Render compatible temp path
    output_doc.save(output_filename)
    send_to_whatsapp(output_filename)

    return jsonify({"status": "Success", "message": "Done! Sent to WhatsApp Group."})

def send_to_whatsapp(file_path):
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/sendFileByUpload/{API_TOKEN_INSTANCE}"
    payload = {'chatId': CHAT_ID}
    with open(file_path, 'rb') as f:
        files = [('file', (os.path.basename(file_path), f, 'application/pdf'))]
        requests.post(url, data=payload, files=files)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))