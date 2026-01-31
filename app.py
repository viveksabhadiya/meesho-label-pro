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

# Professional UI like tools4free
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VR Trendz - Meesho Label Sorter</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .gradient-bg { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .drop-zone { border: 2px dashed #cbd5e0; transition: all 0.3s ease; }
        .drop-zone:hover { border-color: #667eea; background: #f7fafc; }
    </style>
</head>
<body class="bg-gray-100 min-h-screen font-sans">
    <nav class="bg-white shadow-md p-4 mb-8">
        <div class="container mx-auto">
            <h1 class="text-2xl font-bold text-indigo-600">VR Trendz</h1>
        </div>
    </nav>

    <div class="container mx-auto px-4 max-w-2xl">
        <div class="bg-white rounded-xl shadow-lg p-8 text-center">
            <h2 class="text-3xl font-extrabold text-gray-800 mb-4">Meesho Label Crop & Sort</h2>
            <p class="text-gray-600 mb-8">Advanced Sorting: Courier > Account (Delhivery) > SKU > Qty</p>
            
            <div id="dropZone" class="drop-zone rounded-lg p-12 mb-6 cursor-pointer">
                <div class="text-gray-500">
                    <svg class="mx-auto h-12 w-12 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
                    </svg>
                    <p class="text-lg font-medium">Click to upload or drag & drop PDF</p>
                    <p class="text-sm">Only Meesho Label PDFs allowed</p>
                </div>
                <input type="file" id="pdfInput" class="hidden" accept="application/pdf">
            </div>

            <button onclick="uploadFile()" id="btnProcess" class="w-full gradient-bg text-white font-bold py-4 rounded-lg text-lg shadow-md hover:opacity-90 transition duration-300">
                PROCESS & SEND TO WHATSAPP
            </button>

            <div id="status" class="mt-6 text-sm font-semibold"></div>
        </div>
    </div>

    <script>
        const dropZone = document.getElementById('dropZone');
        const pdfInput = document.getElementById('pdfInput');
        const status = document.getElementById('status');

        dropZone.onclick = () => pdfInput.click();

        async function uploadFile() {
            const file = pdfInput.files[0];
            if (!file) { alert("Please select a file first!"); return; }

            const btn = document.getElementById('btnProcess');
            btn.disabled = true;
            btn.innerText = "PROCESSING...";
            status.className = "mt-6 text-sm font-semibold text-blue-600";
            status.innerText = "Reading labels and sorting... Please wait.";

            const formData = new FormData();
            formData.append('pdf', file);

            try {
                const response = await fetch('/process-pdf', { method: 'POST', body: formData });
                const result = await response.json();
                
                if(response.ok) {
                    status.className = "mt-6 text-sm font-semibold text-green-600";
                    status.innerText = "✓ Success! Sorted PDF sent to your WhatsApp Group.";
                } else {
                    throw new Error(result.message || "Upload failed");
                }
            } catch (err) {
                status.className = "mt-6 text-sm font-semibold text-red-600";
                status.innerText = "Error: " + err.message;
            } finally {
                btn.disabled = false;
                btn.innerText = "PROCESS & SEND TO WHATSAPP";
            }
        }
    </script>
</body>
</html>
"""

def extract_label_data(page):
    text = page.get_text()
    
    # Courier Name
    courier = "Other"
    if "Delhivery" in text: courier = "Delhivery"
    elif "Ecom" in text: courier = "Ecom Express"
    elif "Shadowfax" in text: courier = "Shadowfax"
    
    # Account Name (For Delhivery only)
    account_name = "ZZZ" # Default high value for sorting
    if courier == "Delhivery" and "If undelivered, return to:" in text:
        match = re.search(r"If undelivered, return to:\s*\n(.*?)\n", text)
        if match:
            account_name = match.group(1).strip()

    # SKU & Qty (Cleaning logic)
    sku_match = re.search(r"SKU\s*\n(.*?)\s*\n", text)
    qty_match = re.search(r"Qty\s*\n(\d+)", text)
    
    sku = sku_match.group(1).strip() if sku_match else "Unknown"
    qty = int(qty_match.group(1)) if qty_match else 1

    return {
        "page_index": page.number,
        "courier": courier,
        "account": account_name,
        "sku": sku,
        "qty": qty
    }

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/process-pdf', methods=['POST'])
def process_pdf():
    try:
        if 'pdf' not in request.files:
            return jsonify({"status": "Error", "message": "No file uploaded"}), 400
            
        file = request.files['pdf']
        doc = fitz.open(stream=file.read(), filetype="pdf")
        all_labels = [extract_label_data(page) for page in doc]

        # --- FINAL SORTING LOGIC ---
        # 1. Courier (A-Z)
        # 2. Account Name (Only meaningful for Delhivery)
        # 3. SKU (A-Z)
        # 4. Quantity (1, 2, 3...)
        sorted_labels = sorted(all_labels, key=lambda x: (
            x['courier'].lower(),
            x['account'].lower(),
            x['sku'].lower(),
            x['qty']
        ))

        output_doc = fitz.open()
        
        # --- CROP LOGIC (A4 to 4x6 Label) ---
        # Meesho labels are usually at the top or bottom half. 
        # Here we extract the exact page content and fit it to a 4x6 frame.
        for label in sorted_labels:
            page = doc[label['page_index']]
            # Meesho label usually occupies top half: (0, 0, 595, 420) for A4
            # We insert it into a 4x6 (288 x 432 pts) target
            new_page = output_doc.new_page(width=288, height=432)
            # Crop logic: Taking the top half of A4 and fitting to 4x6
            rect = fitz.Rect(0, 0, 595, 420) 
            new_page.show_pdf_page(new_page.rect, doc, label['page_index'], clip=rect)

        output_path = "/tmp/vr_trendz_labels.pdf"
        output_doc.save(output_path)
        
        # Send to WhatsApp
        send_to_whatsapp(output_path)
        
        return jsonify({"status": "Success", "message": "Sorted & Cropped!"})
    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)}), 500

def send_to_whatsapp(file_path):
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/sendFileByUpload/{API_TOKEN_INSTANCE}"
    payload = {'chatId': CHAT_ID}
    with open(file_path, 'rb') as f:
        files = [('file', (os.path.basename(file_path), f, 'application/pdf'))]
        requests.post(url, data=payload, files=files)

if __name__ == '__main__':
    # For local testing, use port 5000
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))