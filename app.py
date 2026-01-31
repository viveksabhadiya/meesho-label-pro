import fitz  # PyMuPDF
import re
import os
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# --- CONFIGURATION (Render Environment Variables me set karein) ---
ID_INSTANCE = os.environ.get("ID_INSTANCE", "7103498692")
API_TOKEN_INSTANCE = os.environ.get("API_TOKEN_INSTANCE", "217a71fbbecb41658e5fffa00451817bbe62ea618ad1461c8d")
CHAT_ID = os.environ.get("CHAT_ID", "919428146028-1606295944@g.us")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VR TRENDZ | Shipment Master Pro</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: radial-gradient(circle at center, #1e1b4b, #0f172a); color: white; min-height: 100vh; font-family: 'Inter', sans-serif; }
        .glass-card { background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 2.5rem; }
        .btn-glow { background: linear-gradient(135deg, #6366f1, #a855f7); transition: all 0.4s ease; box-shadow: 0 0 20px rgba(99, 102, 241, 0.4); }
        .btn-glow:hover { transform: scale(1.02); box-shadow: 0 0 35px rgba(168, 85, 247, 0.6); }
        .loader { width: 48px; height: 48px; border: 5px solid #FFF; border-bottom-color: transparent; border-radius: 50%; display: inline-block; box-sizing: border-box; animation: rotation 1s linear infinite; }
        @keyframes rotation { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="flex flex-col items-center justify-center p-4">
    <div class="w-full max-w-3xl">
        <div class="text-center mb-10">
            <div class="inline-block p-5 bg-white/10 rounded-full mb-6">
                <svg width="50" height="50" viewBox="0 0 100 100" fill="none">
                    <path d="M20 30L50 80L80 30" stroke="#a855f7" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>
                    <circle cx="50" cy="20" r="10" fill="#6366f1"/>
                </svg>
            </div>
            <h1 class="text-6xl font-black italic tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-purple-400">VR TRENDZ</h1>
            <p class="text-indigo-200/50 uppercase tracking-[0.3em] text-sm mt-2">Logistics Intelligence System</p>
        </div>

        <div class="glass-card p-10 shadow-2xl">
            <div id="dropZone" class="border-2 border-dashed border-indigo-500/30 rounded-3xl p-16 text-center cursor-pointer hover:bg-white/5 transition-all">
                <p class="text-xl text-indigo-100/80 mb-2">Drop your Meesho PDF here</p>
                <p class="text-xs text-indigo-300/40 italic">Sorted by Courier > Account > SKU > Qty</p>
                <input type="file" id="pdfInput" class="hidden" accept="application/pdf">
            </div>

            <button onclick="uploadFile()" id="processBtn" class="w-full mt-8 btn-glow py-6 rounded-3xl text-xl font-black uppercase tracking-widest italic">
                Start Automation
            </button>

            <div id="status" class="mt-10 text-center"></div>
        </div>
    </div>

    <script>
        const input = document.getElementById('pdfInput');
        document.getElementById('dropZone').onclick = () => input.click();

        async function uploadFile() {
            if (!input.files[0]) return;
            const btn = document.getElementById('processBtn');
            const status = document.getElementById('status');
            
            btn.disabled = true;
            btn.innerHTML = '<span class="loader"></span>';
            status.innerHTML = '<p class="text-indigo-300 animate-pulse font-bold">Generating Professional Summary Page...</p>';

            const formData = new FormData();
            formData.append('pdf', input.files[0]);

            try {
                const res = await fetch('/process-pdf', { method: 'POST', body: formData });
                if (res.ok) {
                    status.innerHTML = '<div class="p-6 bg-green-500/20 text-green-400 rounded-3xl border border-green-500/30 font-black">✓ SHIPMENT PROCESSED & SENT TO WHATSAPP</div>';
                } else { throw new Error("Processing Failed"); }
            } catch (err) {
                status.innerHTML = `<div class="p-6 bg-red-500/20 text-red-400 rounded-3xl border border-red-500/30 font-bold">Error: ${err.message}</div>`;
            } finally {
                btn.disabled = false;
                btn.innerText = "Start Automation";
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
    if not re.search(r'\d{10,}', text): return None

    # Courier Detection
    courier = "Other"
    if "Delhivery" in text: courier = "Delhivery"
    elif "Valmo" in text: courier = "Valmo"
    elif "Shadowfax" in text: courier = "Shadowfax"
    elif "Ecom" in text: courier = "Ecom Express"

    # Account Name
    account_name = "N/A"
    acc_match = re.search(r"If undelivered, return to:\s*\n(.*?)\n", text)
    if acc_match: account_name = acc_match.group(1).strip()

    # SKU & Size Logic
    sku = "N/A"
    sku_match = re.search(r"SKU\s*\n(.*?)\n", text)
    if sku_match: sku = sku_match.group(1).strip()

    size = "N/A"
    size_match = re.search(r"Size\s*\n(.*?)\s*\n", text)
    if size_match: size = size_match.group(1).strip()

    qty = 1
    qty_match = re.search(r"Qty\s*\n(\d+)", text)
    if qty_match: qty = int(qty_match.group(1))

    return {"page_index": page.number, "courier": courier, "account": account_name, "sku": sku, "size": size, "qty": qty}

def draw_table_header(page, y, title, columns):
    page.insert_text((230, y-10), title, fontsize=12, fontname="helv-bold")
    x_offsets = [50, 80, 400, 500]
    for i, col in enumerate(columns):
        page.insert_text((x_offsets[i], y+15), col, fontsize=10, fontname="helv-bold")
    page.draw_rect(fitz.Rect(50, y, 550, y+25), color=(0,0,0), width=1)
    return y + 25

@app.route('/process-pdf', methods=['POST'])
def process_pdf():
    try:
        file = request.files['pdf']
        doc = fitz.open(stream=file.read(), filetype="pdf")
        valid_labels = []
        for page in doc:
            data = extract_label_data(page)
            if data: valid_labels.append(data)

        # 1. Courier Sorting First
        sorted_labels = sorted(valid_labels, key=lambda x: (x['courier'].lower(), x['account'].lower(), x['sku'].lower(), x['qty']))

        output_doc = fitz.open()
        sku_summary = {} # Key: (SKU, Size)
        courier_summary = {}
        account_summary = {}

        for label in sorted_labels:
            # Dynamic Crop to "as applicable"
            page = doc[label['page_index']]
            text_instances = page.search_for("as applicable")
            bottom_y = text_instances[0].y1 + 10 if text_instances else 750
            
            rect = fitz.Rect(0, 0, 595, bottom_y)
            new_page = output_doc.new_page(width=595, height=bottom_y)
            new_page.show_pdf_page(new_page.rect, doc, label['page_index'], clip=rect)

            # Data Aggregation
            key = (label['sku'], label['size'])
            sku_summary[key] = sku_summary.get(key, 0) + label['qty']
            courier_summary[label['courier']] = courier_summary.get(label['courier'], 0) + 1
            account_summary[label['account']] = account_summary.get(label['account'], 0) + 1

        # --- GENERATE SUMMARY PAGE (Exactly like screenshots) ---
        sum_page = output_doc.new_page(width=595, height=842)
        y = 50

        # Table 1: Order Summary
        y = draw_table_header(sum_page, y, "Order Summary", ["No", "SKU", "Size", "QTY"])
        for i, ((sku, size), qty) in enumerate(sku_summary.items(), 1):
            sum_page.insert_text((55, y+15), str(i), fontsize=9)
            sum_page.insert_text((85, y+15), sku[:55], fontsize=9)
            sum_page.insert_text((405, y+15), size, fontsize=9)
            sum_page.insert_text((505, y+15), str(qty), fontsize=9)
            sum_page.draw_rect(fitz.Rect(50, y, 550, y+20), color=(0,0,0), width=0.5)
            y += 20
        sum_page.insert_text((405, y+15), "Total", fontname="helv-bold")
        sum_page.insert_text((505, y+15), str(sum(sku_summary.values())), fontname="helv-bold")
        y += 40

        # Table 2: Courier Wise Summary
        y = draw_table_header(sum_page, y, "Courier Wise Summary", ["No", "Total Order", "Courier Partner", ""])
        for i, (cp, count) in enumerate(courier_summary.items(), 1):
            sum_page.insert_text((55, y+15), str(i), fontsize=9)
            sum_page.insert_text((85, y+15), str(count), fontsize=9)
            sum_page.insert_text((405, y+15), cp, fontsize=9)
            sum_page.draw_rect(fitz.Rect(50, y, 550, y+20), color=(0,0,0), width=0.5)
            y += 20
        y += 40

        # Table 3: Company Wise Total Order
        y = draw_table_header(sum_page, y, "Company Wise Total Order", ["No", "Total Order", "Sold By", ""])
        for i, (acc, count) in enumerate(account_summary.items(), 1):
            sum_page.insert_text((55, y+15), str(i), fontsize=9)
            sum_page.insert_text((85, y+15), str(count), fontsize=9)
            sum_page.insert_text((405, y+15), acc[:50], fontsize=9)
            sum_page.draw_rect(fitz.Rect(50, y, 550, y+20), color=(0,0,0), width=0.5)
            y += 20

        output_path = "/tmp/vr_trendz_final.pdf"
        output_doc.save(output_path)
        send_to_whatsapp(output_path, "*VR TRENDZ SHIPMENT COMPLETED*")
        return jsonify({"status": "Success"})
    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)}), 500

def send_to_whatsapp(file_path, msg):
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/sendFileByUpload/{API_TOKEN_INSTANCE}"
    with open(file_path, 'rb') as f:
        requests.post(url, data={'chatId': CHAT_ID, 'caption': msg}, files=[('file', (os.path.basename(file_path), f, 'application/pdf'))])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))