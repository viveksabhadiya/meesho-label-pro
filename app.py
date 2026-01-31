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

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VR Trendz Pro - Label Sorter</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .gradient-bg { background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); }
        .logo-box { background: white; padding: 10px; border-radius: 50%; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    </style>
</head>
<body class="bg-slate-50 min-h-screen">
    <nav class="bg-white shadow-sm p-4 flex items-center justify-center gap-3">
        <div class="logo-box">
            <svg width="40" height="40" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="50" cy="50" r="48" stroke="#4f46e5" stroke-width="4"/>
                <path d="M30 35L50 70L70 35" stroke="#7c3aed" stroke-width="8" stroke-linecap="round"/>
                <path d="M45 25L55 25" stroke="#4f46e5" stroke-width="4" stroke-linecap="round"/>
            </svg>
        </div>
        <h1 class="text-3xl font-black italic text-indigo-700 tracking-tighter">VR TRENDZ</h1>
    </nav>

    <div class="container mx-auto px-4 mt-10 max-w-xl">
        <div class="bg-white rounded-3xl shadow-2xl p-8 border border-indigo-50">
            <div id="dropZone" class="border-4 border-dashed border-indigo-100 rounded-2xl p-10 mb-6 text-center hover:border-indigo-300 transition-all cursor-pointer">
                <p class="text-slate-400 font-medium">Drag & Drop Meesho PDF here</p>
                <input type="file" id="pdfInput" class="hidden" accept="application/pdf">
            </div>
            
            <button onclick="uploadFile()" id="btnProcess" class="w-full gradient-bg text-white font-bold py-4 rounded-2xl shadow-lg hover:scale-[1.02] transition-transform">
                START PROCESSING
            </button>
            
            <div id="status" class="mt-8"></div>
        </div>
    </div>

    <script>
        const pdfInput = document.getElementById('pdfInput');
        document.getElementById('dropZone').onclick = () => pdfInput.click();

        async function uploadFile() {
            const file = pdfInput.files[0];
            if (!file) return alert("Select PDF!");

            const btn = document.getElementById('btnProcess');
            const status = document.getElementById('status');
            btn.disabled = true;
            status.innerHTML = '<div class="flex gap-2 justify-center"><div class="w-4 h-4 bg-indigo-600 rounded-full animate-bounce"></div><p>Sorting & Generating Summary...</p></div>';

            const formData = new FormData();
            formData.append('pdf', file);

            try {
                const response = await fetch('/process-pdf', { method: 'POST', body: formData });
                const result = await response.json();
                if(response.ok) {
                    let summaryHtml = '<div class="bg-green-50 p-4 rounded-xl mt-4"><h3 class="font-bold text-green-800 border-b border-green-200 pb-2 mb-2">Order Summary Sent!</h3>';
                    summaryHtml += '<table class="w-full text-sm text-left">';
                    summaryHtml += '<tr><th class="py-1">SKU</th><th>Qty</th></tr>';
                    for (const [sku, qty] of Object.entries(result.summary.skus)) {
                        summaryHtml += `<tr><td class="py-1">${sku}</td><td>${qty}</td></tr>`;
                    }
                    summaryHtml += '</table></div>';
                    status.innerHTML = summaryHtml;
                } else {
                    throw new Error(result.message);
                }
            } catch (err) {
                status.innerHTML = `<p class="text-red-500 font-bold">Error: ${err.message}</p>`;
            } finally {
                btn.disabled = false;
            }
        }
    </script>
</body>
</html>
"""

def extract_label_data(page):
    text = page.get_text()
    # Courier Identify
    courier = "Other"
    if "Delhivery" in text: courier = "Delhivery"
    elif "Valmo" in text: courier = "Valmo"
    elif "Ecom" in text: courier = "Ecom Express"
    
    # Account Wise only for Delhivery
    account_name = "N/A"
    if courier == "Delhivery" and "If undelivered, return to:" in text:
        match = re.search(r"If undelivered, return to:\s*\n(.*?)\n", text)
        if match: account_name = match.group(1).strip()

    # SKU & Qty (Product Details block)
    sku = "Unknown SKU"
    sku_match = re.search(r"SKU\s*\n(.*?)\n", text)
    if sku_match: sku = sku_match.group(1).strip()

    qty = 1
    qty_match = re.search(r"Qty\s*\n(\d+)", text)
    if qty_match: qty = int(qty_match.group(1))

    return {"page_index": page.number, "courier": courier, "account": account_name, "sku": sku, "qty": qty}

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/process-pdf', methods=['POST'])
def process_pdf():
    try:
        file = request.files['pdf']
        doc = fitz.open(stream=file.read(), filetype="pdf")
        all_labels = [extract_label_data(page) for page in doc]

        # Sorting Logic
        sorted_labels = sorted(all_labels, key=lambda x: (
            x['courier'].lower(),
            x['account'].lower(),
            x['sku'].lower(),
            x['qty']
        ))

        output_doc = fitz.open()
        sku_summary = {}
        account_summary = {}

        for label in sorted_labels:
            # Full Page Crop (Dusri image jesa pura label dikhane ke liye)
            output_doc.insert_pdf(doc, from_page=label['page_index'], to_page=label['page_index'])
            
            # Update Summary Counters
            sku_summary[label['sku']] = sku_summary.get(label['sku'], 0) + label['qty']
            if label['account'] != "N/A":
                account_summary[label['account']] = account_summary.get(label['account'], 0) + 1

        # Summary Text for WhatsApp
        summary_msg = "*📦 VR TRENDZ - ORDER SUMMARY*\n\n"
        summary_msg += "*SKU Wise Breakdown:*\n"
        for sku, count in sku_summary.items():
            summary_msg += f"- {sku}: {count}\n"
        
        if account_summary:
            summary_msg += "\n*Account Wise (Delhivery):*\n"
            for acc, count in account_summary.items():
                summary_msg += f"- {acc}: {count} orders\n"

        output_path = "/tmp/final_labels.pdf"
        output_doc.save(output_path)
        
        # WhatsApp sending
        send_to_whatsapp(output_path, summary_msg)
        
        return jsonify({"status": "Success", "summary": {"skus": sku_summary, "accounts": account_summary}})
    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)}), 500

def send_to_whatsapp(file_path, text_msg):
    # 1. Send File
    file_url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/sendFileByUpload/{API_TOKEN_INSTANCE}"
    with open(file_path, 'rb') as f:
        requests.post(file_url, data={'chatId': CHAT_ID}, files=[('file', (os.path.basename(file_path), f, 'application/pdf'))])
    
    # 2. Send Summary Message
    msg_url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/sendMessage/{API_TOKEN_INSTANCE}"
    requests.post(msg_url, json={'chatId': CHAT_ID, 'message': text_msg})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))