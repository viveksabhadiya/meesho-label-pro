import fitz  # PyMuPDF
import re
import os
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# --- CONFIGURATION ---
# Render ke Environment Variables me ye keys zaroor set karein
ID_INSTANCE = os.environ.get("ID_INSTANCE", "7103498692")
API_TOKEN_INSTANCE = os.environ.get("API_TOKEN_INSTANCE", "217a71fbbecb41658e5fffa00451817bbe62ea618ad1461c8d")
CHAT_ID = os.environ.get("CHAT_ID", "919428146028-1606295944@g.us")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VR TRENDZ | SHIPMENT MASTER PRO</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #020617; color: white; min-height: 100vh; display: flex; align-items: center; justify-content: center; font-family: 'Inter', sans-serif; }
        .glass-card { background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 2.5rem; width: 100%; max-width: 650px; padding: 3.5rem; }
        .btn-grad { background: linear-gradient(135deg, #6366f1, #a855f7); transition: 0.4s; }
        .btn-grad:hover { transform: translateY(-3px); box-shadow: 0 15px 30px -10px rgba(124, 58, 237, 0.6); }
        .loader { width: 24px; height: 24px; border: 3px solid #FFF; border-bottom-color: transparent; border-radius: 50%; display: inline-block; animation: rotation 1s linear infinite; }
        @keyframes rotation { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="glass-card shadow-2xl">
        <header class="text-center mb-12">
            <h1 class="text-6xl font-black italic tracking-tighter text-indigo-500">VR <span class="text-white">TRENDZ</span></h1>
            <p class="text-slate-500 text-xs tracking-[0.4em] mt-3 uppercase font-bold">Shipment Master Pro</p>
        </header>

        <div id="dropZone" class="border-2 border-dashed border-slate-800 rounded-[2rem] p-16 text-center cursor-pointer hover:border-indigo-500 hover:bg-white/5 transition-all mb-8">
            <p class="text-slate-400 text-lg">Click or Drag Meesho PDF</p>
            <input type="file" id="pdfInput" class="hidden" accept="application/pdf">
        </div>

        <button onclick="uploadFile()" id="mainBtn" class="w-full btn-grad py-6 rounded-3xl text-2xl font-black italic tracking-widest uppercase shadow-xl">
            Start Automation
        </button>

        <div id="status" class="mt-10 text-center"></div>
    </div>

    <script>
        const input = document.getElementById('pdfInput');
        document.getElementById('dropZone').onclick = () => input.click();

        async function uploadFile() {
            if (!input.files[0]) return alert("Please select a Meesho PDF!");
            const btn = document.getElementById('mainBtn');
            const status = document.getElementById('status');
            
            btn.disabled = true;
            btn.innerHTML = '<span class="loader"></span>';
            status.innerHTML = '<p class="text-indigo-400 animate-pulse font-bold uppercase tracking-widest">Processing & Sorting Labels...</p>';

            const formData = new FormData();
            formData.append('pdf', input.files[0]);

            try {
                const res = await fetch('/process-pdf', { method: 'POST', body: formData });
                const data = await res.json();
                if (res.ok) {
                    status.innerHTML = '<div class="p-6 bg-emerald-500/20 text-emerald-400 rounded-3xl border border-emerald-500/30 font-black uppercase tracking-tighter italic">✓ Success: Sent to WhatsApp Group</div>';
                } else { throw new Error(data.message || "Internal Server Error"); }
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

def extract_label_data(page):
    text = page.get_text()
    if not re.search(r'\d{10,}', text): return None # Filter pages without QR/Barcode

    # Courier Detection
    courier = "Other"
    if "Delhivery" in text: courier = "Delhivery"
    elif "Valmo" in text: courier = "Valmo"
    elif "Shadowfax" in text: courier = "Shadowfax"
    elif "Ecom" in text: courier = "Ecom Express"

    # Account Name (Return Address logic)
    acc = "N/A"
    acc_m = re.search(r"If undelivered, return to:\s*\n(.*?)\n", text)
    if acc_m: acc = acc_m.group(1).strip()

    # Product Details
    sku = "N/A"; sku_m = re.search(r"SKU\s*\n(.*?)\n", text)
    if sku_m: sku = sku_m.group(1).strip()

    size = "N/A"; size_m = re.search(r"Size\s*\n(.*?)\s*\n", text)
    if size_m: size = size_m.group(1).strip()

    color = "N/A"; color_m = re.search(r"Color\s*\n(.*?)\s*\n", text)
    if color_m: color = color_m.group(1).strip()

    qty = 1; qty_m = re.search(r"Qty\s*\n(\d+)", text)
    if qty_m: qty = int(qty_m.group(1))

    return {"p": page.number, "c": courier, "a": acc, "s": sku, "sz": size, "cl": color, "q": qty}

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

        # Advanced Sorting: Courier > Account > SKU > Qty
        valid_labels.sort(key=lambda x: (x['c'].lower(), x['a'].lower(), x['s'].lower(), x['q']))

        out = fitz.open()
        sku_summary, cp_summary, acc_summary = {}, {}, {}

        for l in valid_labels:
            page = doc[l['p']]
            # Dynamic Crop to "as applicable"
            hits = page.search_for("as applicable")
            bottom = hits[0].y1 + 10 if hits else 750
            
            rect = fitz.Rect(0, 0, 595, bottom)
            new_pg = out.new_page(width=595, height=bottom)
            new_pg.show_pdf_page(new_pg.rect, doc, l['p'], clip=rect)

            # Aggregate Data for Tables
            key = (l['s'], l['sz'], l['cl'])
            sku_summary[key] = sku_summary.get(key, 0) + l['q']
            cp_summary[l['c']] = cp_summary.get(l['c'], 0) + 1
            acc_summary[l['a']] = acc_summary.get(l['a'], 0) + 1

        # --- SUMMARY PAGE GENERATION ---
        sp = out.new_page(width=595, height=842)
        y = 50

        def write_row(page, y, data, is_bold=False):
            offsets = [55, 85, 335, 435, 515]
            font = "hebo" if is_bold else "helv"
            for idx, text in enumerate(data):
                page.insert_text((offsets[idx], y+15), str(text), fontname=font, fontsize=9)
            page.draw_rect(fitz.Rect(50, y, 550, y+20), color=(0,0,0), width=0.5)

        # Table 1: Order Summary
        sp.insert_text((230, y-10), "ORDER SUMMARY", fontname="hebo", fontsize=14)
        write_row(sp, y, ["No", "SKU", "Size", "Color", "QTY"], True)
        y += 20
        for i, ((sku, sz, cl), q) in enumerate(sku_summary.items(), 1):
            if y > 780: 
                sp = out.new_page(width=595, height=842)
                y = 50
            write_row(sp, y, [i, sku[:45], sz, cl, q])
            y += 20
        sp.insert_text((435, y+15), "Total", fontname="hebo")
        sp.insert_text((515, y+15), str(sum(sku_summary.values())), fontname="hebo")
        y += 60

        # Table 2: Courier Wise Summary
        if y > 600: sp = out.new_page(width=595, height=842); y = 50
        sp.insert_text((210, y-10), "COURIER WISE SUMMARY", fontname="hebo", fontsize=14)
        write_row(sp, y, ["No", "Total Order", "Courier Partner", "", ""], True)
        y += 20
        for i, (cp, count) in enumerate(cp_summary.items(), 1):
            write_row(sp, y, [i, count, cp, "", ""])
            y += 20
        y += 60

        # Table 3: Company Wise Total Order
        if y > 600: sp = out.new_page(width=595, height=842); y = 50
        sp.insert_text((210, y-10), "COMPANY WISE TOTAL ORDER", fontname="hebo", fontsize=14)
        write_row(sp, y, ["No", "Total Order", "Sold By", "", ""], True)
        y += 20
        for i, (acc, count) in enumerate(acc_summary.items(), 1):
            write_row(sp, y, [i, count, acc[:55], "", ""])
            y += 20

        output_path = "/tmp/vr_trendz_shipment.pdf"
        out.save(output_path)
        
        # Green-API Request
        url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/sendFileByUpload/{API_TOKEN_INSTANCE}"
        with open(output_path, 'rb') as f:
            requests.post(url, data={'chatId': CHAT_ID, 'caption': '*VR TRENDZ: NEW BATCH READY*'}, files=[('file', ('VR_Trendz_Shipment.pdf', f, 'application/pdf'))])
        
        return jsonify({"status": "Success"})
    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))