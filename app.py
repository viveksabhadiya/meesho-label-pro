import fitz  # PyMuPDF
import re
import os
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# --- CONFIGURATION ---
ID_INSTANCE = os.environ.get("ID_INSTANCE", "7103498692")
API_TOKEN_INSTANCE = os.environ.get("API_TOKEN_INSTANCE", "217a71fbbecb41658e5fffa00451817bbe62ea618ad1461c8d")
CHAT_ID = os.environ.get("CHAT_ID", "919428146028-1606295944@g.us")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VR TRENDZ | Shipment Master</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        body { font-family: 'Inter', sans-serif; background: #0f172a; color: white; }
        .glass { background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
        .gradient-text { background: linear-gradient(90deg, #818cf8, #c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .btn-grad { background: linear-gradient(90deg, #4f46e5, #7c3aed); transition: 0.3s; }
        .btn-grad:hover { transform: translateY(-2px); box-shadow: 0 10px 20px -10px rgba(124, 58, 237, 0.5); }
    </style>
</head>
<body class="min-h-screen flex flex-col items-center justify-center p-6">
    <div class="max-w-4xl w-full">
        <header class="text-center mb-12">
            <div class="inline-block p-4 rounded-full bg-indigo-500/10 mb-4">
                <svg width="60" height="60" viewBox="0 0 100 100" fill="none">
                    <circle cx="50" cy="50" r="45" stroke="url(#grad)" stroke-width="5"/>
                    <path d="M35 40L50 65L65 40" stroke="white" stroke-width="8" stroke-linecap="round"/>
                    <defs><linearGradient id="grad"><stop stop-color="#818cf8"/><stop offset="1" stop-color="#c084fc"/></linearGradient></defs>
                </svg>
            </div>
            <h1 class="text-6xl font-black tracking-tighter mb-2 italic">VR <span class="gradient-text">TRENDZ</span></h1>
            <p class="text-slate-400 text-lg uppercase tracking-widest">Shipment Logic Pro v2.0</p>
        </header>

        <main class="glass rounded-[2rem] p-10 relative overflow-hidden">
            <div id="dropZone" class="border-2 border-dashed border-slate-700 rounded-2xl p-16 text-center hover:border-indigo-500 transition-all cursor-pointer bg-white/5">
                <p class="text-xl text-slate-300 mb-2">Click or Drag Meesho PDF</p>
                <p class="text-sm text-slate-500">File will be sorted, cropped & sent to WhatsApp</p>
                <input type="file" id="pdfInput" class="hidden" accept="application/pdf">
            </div>

            <button onclick="uploadFile()" id="btn" class="w-full mt-8 btn-grad py-5 rounded-2xl text-xl font-bold shadow-2xl">
                START AUTOMATION
            </button>

            <div id="status" class="mt-8 space-y-4"></div>
        </main>
    </div>

    <script>
        const input = document.getElementById('pdfInput');
        document.getElementById('dropZone').onclick = () => input.click();

        async function uploadFile() {
            if (!input.files[0]) return;
            const btn = document.getElementById('btn');
            const status = document.getElementById('status');
            
            btn.disabled = true;
            btn.innerText = "PROCESSING PDF...";
            status.innerHTML = '<div class="h-1 bg-slate-800 w-full rounded-full overflow-hidden"><div class="h-full bg-indigo-500 animate-[progress_2s_ease-in-out_infinite]" style="width:50%"></div></div>';

            const formData = new FormData();
            formData.append('pdf', input.files[0]);

            try {
                const res = await fetch('/process-pdf', { method: 'POST', body: formData });
                const data = await res.json();
                if (res.ok) {
                    status.innerHTML = '<div class="p-4 bg-emerald-500/20 text-emerald-400 rounded-xl border border-emerald-500/30 text-center font-bold">✓ DONE! PDF & SUMMARY SENT TO WHATSAPP</div>';
                } else { throw new Error(data.message); }
            } catch (err) {
                status.innerHTML = `<div class="p-4 bg-red-500/20 text-red-400 rounded-xl border border-red-500/30">Error: ${err.message}</div>`;
            } finally {
                btn.disabled = false;
                btn.innerText = "START AUTOMATION";
            }
        }
    </script>
</body>
</html>
"""

def extract_label_data(page):
    text = page.get_text()
    
    # 1. QR Code Check (Delete page if no QR)
    # Meesho labels always have barcodes/QR. If no digits or barcodes found, skip.
    if not re.search(r'\d{10,}', text) and len(page.get_images()) == 0:
        return None

    courier = "Other"
    if "Delhivery" in text: courier = "Delhivery"
    elif "Valmo" in text: courier = "Valmo"
    elif "Ecom" in text: courier = "Ecom Express"
    
    account_name = "N/A"
    if courier == "Delhivery":
        match = re.search(r"If undelivered, return to:\s*\n(.*?)\n", text)
        if match: account_name = match.group(1).strip()

    sku = "Unknown"
    sku_match = re.search(r"SKU\s*\n(.*?)\n", text)
    if sku_match: sku = sku_match.group(1).strip()

    qty = 1
    qty_match = re.search(r"Qty\s*\n(\d+)", text)
    if qty_match: qty = int(qty_match.group(1))

    return {"page_index": page.number, "courier": courier, "account": account_name, "sku": sku, "qty": qty, "text": text}

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/process-pdf', methods=['POST'])
def process_pdf():
    try:
        file = request.files['pdf']
        doc = fitz.open(stream=file.read(), filetype="pdf")
        valid_labels = []

        for page in doc:
            data = extract_label_data(page)
            if data: valid_labels.append(data)

        # Sorting: Courier -> Account -> SKU -> Qty
        sorted_labels = sorted(valid_labels, key=lambda x: (
            x['courier'].lower(),
            x['account'].lower(),
            x['sku'].lower(),
            x['qty']
        ))

        output_doc = fitz.open()
        sku_stats = {}

        for label in sorted_labels:
            page = doc[label['page_index']]
            
            # --- DYNAMIC CROP LOGIC ---
            # Search for "as applicable" position to crop exactly there
            text_instances = page.search_for("as applicable")
            if text_instances:
                # Invoice end point mil gaya
                bottom_y = text_instances[0].y1 + 10 
            else:
                # Default agar text nahi mila (Standard Meesho height)
                bottom_y = 750 

            # Create new page with exact cropped height (A4 width = 595)
            rect = fitz.Rect(0, 0, 595, bottom_y)
            new_page = output_doc.new_page(width=595, height=bottom_y)
            new_page.show_pdf_page(new_page.rect, doc, label['page_index'], clip=rect)

            # Stats for Summary
            key = f"{label['sku']}"
            sku_stats[key] = sku_stats.get(key, 0) + label['qty']

        # --- INSERT SUMMARY PAGE AT THE END ---
        summary_page = output_doc.new_page(width=595, height=842)
        summary_page.insert_text((200, 50), "COURIER WISE SUMMARY", fontsize=16, color=(0, 0, 0))
        
        y_pos = 100
        summary_page.insert_text((50, y_pos), "No | SKU Name | Total Qty", fontsize=12)
        y_pos += 20
        summary_page.draw_line((50, y_pos), (550, y_pos))
        
        for i, (sku, total) in enumerate(sku_stats.items(), 1):
            y_pos += 25
            summary_page.insert_text((50, y_pos), f"{i}  | {sku[:40]} | {total}")
            if y_pos > 800: # New page if summary is long
                summary_page = output_doc.new_page(width=595, height=842)
                y_pos = 50

        output_path = "/tmp/vr_trendz_final.pdf"
        output_doc.save(output_path)
        
        # WhatsApp Logic
        summary_text = "*VR TRENDZ SUMMARY*\nTotal SKUs: " + str(len(sku_stats))
        send_to_whatsapp(output_path, summary_text)
        
        return jsonify({"status": "Success"})
    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)}), 500

def send_to_whatsapp(file_path, text_msg):
    # Send PDF
    url_file = f"https://api.green-api.com/waInstance{ID_INSTANCE}/sendFileByUpload/{API_TOKEN_INSTANCE}"
    with open(file_path, 'rb') as f:
        requests.post(url_file, data={'chatId': CHAT_ID}, files=[('file', (os.path.basename(file_path), f, 'application/pdf'))])
    # Send Msg
    url_msg = f"https://api.green-api.com/waInstance{ID_INSTANCE}/sendMessage/{API_TOKEN_INSTANCE}"
    requests.post(url_msg, json={'chatId': CHAT_ID, 'message': text_msg})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))