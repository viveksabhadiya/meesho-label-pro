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
    <title>VR TRENDZ | SHIPMENT MASTER</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #0f172a; color: white; min-height: 100vh; display: flex; align-items: center; justify-content: center; font-family: sans-serif; }
        .glass { background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(15px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 2rem; width: 100%; max-width: 600px; padding: 3rem; }
        .btn-grad { background: linear-gradient(135deg, #6366f1, #a855f7); transition: 0.3s; }
        .btn-grad:hover { transform: scale(1.02); box-shadow: 0 0 25px rgba(168, 85, 247, 0.5); }
    </style>
</head>
<body>
    <div class="glass shadow-2xl">
        <div class="text-center mb-10">
            <h1 class="text-5xl font-black italic tracking-tighter text-indigo-400">VR <span class="text-white">TRENDZ</span></h1>
            <p class="text-slate-400 text-xs tracking-widest mt-2 uppercase">Automation v3.0</p>
        </div>

        <div id="dropZone" class="border-2 border-dashed border-slate-700 rounded-3xl p-12 text-center cursor-pointer hover:border-indigo-500 hover:bg-white/5 transition-all mb-6">
            <p class="text-slate-300">Click or Drag Meesho PDF</p>
            <input type="file" id="pdfInput" class="hidden" accept="application/pdf">
        </div>

        <button onclick="uploadFile()" id="btn" class="w-full btn-grad py-5 rounded-2xl text-xl font-bold italic tracking-wider">
            START PROCESSING
        </button>

        <div id="status" class="mt-8"></div>
    </div>

    <script>
        const input = document.getElementById('pdfInput');
        document.getElementById('dropZone').onclick = () => input.click();

        async function uploadFile() {
            if (!input.files[0]) return alert("Please select a file!");
            const btn = document.getElementById('btn');
            const status = document.getElementById('status');
            
            btn.disabled = true;
            btn.innerText = "PROCESSING...";
            status.innerHTML = '<div class="flex justify-center"><div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-500"></div></div>';

            const formData = new FormData();
            formData.append('pdf', input.files[0]);

            try {
                const res = await fetch('/process-pdf', { method: 'POST', body: formData });
                const data = await res.json();
                if (res.ok) {
                    status.innerHTML = '<div class="p-4 bg-green-500/20 text-green-400 rounded-xl border border-green-500/30 text-center font-bold uppercase">✓ Processed & Sent to WhatsApp</div>';
                } else {
                    throw new Error(data.message || "Internal Server Error");
                }
            } catch (err) {
                status.innerHTML = `<div class="p-4 bg-red-500/20 text-red-400 rounded-xl border border-red-500/30 font-bold">Error: ${err.message}</div>`;
            } finally {
                btn.disabled = false;
                btn.innerText = "START PROCESSING";
            }
        }
    </script>
</body>
</html>
"""

def extract_data(page):
    text = page.get_text()
    if not re.search(r'\d{10,}', text): return None # QR Code check

    courier = "Other"
    if "Delhivery" in text: courier = "Delhivery"
    elif "Valmo" in text: courier = "Valmo"
    elif "Shadowfax" in text: courier = "Shadowfax"

    acc = "N/A"
    acc_m = re.search(r"If undelivered, return to:\s*\n(.*?)\n", text)
    if acc_m: acc = acc_m.group(1).strip()

    sku = "N/A"
    sku_m = re.search(r"SKU\s*\n(.*?)\n", text)
    if sku_m: sku = sku_m.group(1).strip()

    size = "N/A"
    size_m = re.search(r"Size\s*\n(.*?)\s*\n", text)
    if size_m: size = size_m.group(1).strip()

    color = "N/A"
    color_m = re.search(r"Color\s*\n(.*?)\s*\n", text)
    if color_m: color = color_m.group(1).strip()

    qty = 1
    qty_m = re.search(r"Qty\s*\n(\d+)", text)
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
        valid = []
        for page in doc:
            d = extract_data(page)
            if d: valid.append(d)

        # Sorting: Courier > Account > SKU > Qty
        valid.sort(key=lambda x: (x['c'].lower(), x['a'].lower(), x['s'].lower(), x['q']))

        out = fitz.open()
        sku_sum, cp_sum, acc_sum = {}, {}, {}

        for l in valid:
            page = doc[l['p']]
            # Crop to "as applicable"
            hits = page.search_for("as applicable")
            bottom = hits[0].y1 + 10 if hits else 750
            rect = fitz.Rect(0, 0, 595, bottom)
            np = out.new_page(width=595, height=bottom)
            np.show_pdf_page(np.rect, doc, l['p'], clip=rect)

            # Aggregate
            k = (l['s'], l['sz'], l['cl'])
            sku_sum[k] = sku_sum.get(k, 0) + l['q']
            cp_sum[l['c']] = cp_sum.get(l['c'], 0) + 1
            acc_sum[l['a']] = acc_sum.get(l['a'], 0) + 1

        # --- SUMMARY PAGE ---
        sp = out.new_page(width=595, height=842)
        y = 50
        
        # 1. Order Summary Table
        sp.insert_text((230, y), "Order Summary", fontname="helv-bold", fontsize=14)
        y += 20
        # Headers
        sp.draw_rect(fitz.Rect(50, y, 550, y+20), color=(0,0,0), width=1)
        for i, h in enumerate(["No", "SKU", "Size", "Color", "QTY"]):
            sp.insert_text((55 + [0, 30, 300, 400, 460][i], y+15), h, fontname="helv-bold", fontsize=10)
        y += 20
        # Rows
        for i, ((sku, sz, cl), q) in enumerate(sku_sum.items(), 1):
            sp.insert_text((55, y+15), str(i), fontsize=9)
            sp.insert_text((85, y+15), sku[:50], fontsize=8)
            sp.insert_text((355, y+15), sz, fontsize=9)
            sp.insert_text((455, y+15), cl, fontsize=9)
            sp.insert_text((515, y+15), str(q), fontsize=9)
            sp.draw_rect(fitz.Rect(50, y, 550, y+20), color=(0,0,0), width=0.5)
            y += 20
        sp.insert_text((455, y+15), "Total", fontname="helv-bold")
        sp.insert_text((515, y+15), str(sum(sku_sum.values())), fontname="helv-bold")
        y += 50

        # 2. Courier Summary Table
        sp.insert_text((210, y), "Courier Wise Summary", fontname="helv-bold", fontsize=14)
        y += 20
        sp.draw_rect(fitz.Rect(50, y, 550, y+20), color=(0,0,0), width=1)
        for i, h in enumerate(["No", "Total Order", "Courier Partner"]):
            sp.insert_text((55 + [0, 30, 150][i], y+15), h, fontname="helv-bold", fontsize=10)
        y += 20
        for i, (cp, c) in enumerate(cp_sum.items(), 1):
            sp.insert_text((55, y+15), str(i), fontsize=9)
            sp.insert_text((85, y+15), str(c), fontsize=9)
            sp.insert_text((205, y+15), cp, fontsize=9)
            sp.draw_rect(fitz.Rect(50, y, 550, y+20), color=(0,0,0), width=0.5)
            y += 20
        y += 50

        # 3. Company Summary Table
        sp.insert_text((210, y), "Company Wise Total Order", fontname="helv-bold", fontsize=14)
        y += 20
        sp.draw_rect(fitz.Rect(50, y, 550, y+20), color=(0,0,0), width=1)
        for i, h in enumerate(["No", "Total Order", "Sold By"]):
            sp.insert_text((55 + [0, 30, 150][i], y+15), h, fontname="helv-bold", fontsize=10)
        y += 20
        for i, (acc, c) in enumerate(acc_sum.items(), 1):
            sp.insert_text((55, y+15), str(i), fontsize=9)
            sp.insert_text((85, y+15), str(c), fontsize=9)
            sp.insert_text((205, y+15), acc[:60], fontsize=8)
            sp.draw_rect(fitz.Rect(50, y, 550, y+20), color=(0,0,0), width=0.5)
            y += 20

        path = "/tmp/final.pdf"
        out.save(path)
        send(path)
        return jsonify({"status": "Success"})
    except Exception as e:
        print(f"DEBUG: {str(e)}")
        return jsonify({"status": "Error", "message": str(e)}), 500

def send(p):
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/sendFileByUpload/{API_TOKEN_INSTANCE}"
    with open(p, 'rb') as f:
        requests.post(url, data={'chatId': CHAT_ID, 'caption': '*VR TRENDZ SHIPMENT DONE*'}, files=[('file', (os.path.basename(p), f, 'application/pdf'))])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))