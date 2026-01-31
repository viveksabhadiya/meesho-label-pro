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
    <title>VR TRENDZ | SHIPMENT MASTER PRO</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #020617; color: white; min-height: 100vh; display: flex; align-items: center; justify-content: center; font-family: 'Inter', sans-serif; }
        .glass-card { background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 2.5rem; width: 100%; max-width: 650px; padding: 3.5rem; }
        .btn-grad { background: linear-gradient(135deg, #6366f1, #a855f7); transition: 0.4s; }
        .btn-grad:hover { transform: translateY(-3px); box-shadow: 0 15px 30px -10px rgba(124, 58, 237, 0.6); }
    </style>
</head>
<body>
    <div class="glass-card shadow-2xl">
        <header class="text-center mb-12">
            <h1 class="text-6xl font-black italic tracking-tighter text-indigo-500">VR <span class="text-white">TRENDZ</span></h1>
            <p class="text-slate-500 text-xs tracking-[0.4em] mt-3 uppercase font-bold text-center">Dynamic Courier Sorting System</p>
        </header>

        <div id="dropZone" class="border-2 border-dashed border-slate-800 rounded-[2rem] p-16 text-center cursor-pointer hover:border-indigo-500 hover:bg-white/5 transition-all mb-8">
            <p class="text-slate-400 text-lg">Drop Meesho PDF Here</p>
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
            if (!input.files[0]) return alert("Select PDF!");
            const btn = document.getElementById('mainBtn');
            const status = document.getElementById('status');
            btn.disabled = true;
            status.innerHTML = '<p class="text-indigo-400 animate-pulse font-bold">Sorting All Courier Partners Dynamically...</p>';

            const formData = new FormData();
            formData.append('pdf', input.files[0]);

            try {
                const res = await fetch('/process-pdf', { method: 'POST', body: formData });
                if (res.ok) {
                    status.innerHTML = '<div class="p-6 bg-emerald-500/20 text-emerald-400 rounded-3xl border border-emerald-500/30 font-black italic">✓ DONE: Sent to WhatsApp</div>';
                } else { throw new Error("Processing Error"); }
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
    if not re.search(r'\d{10,}', text): return None

    # --- DYNAMIC COURIER DETECTION ---
    # Meesho labels usually have the courier name in the top right box (Prepaid/COD section)
    courier = "Other"
    # Logic: Search for common labels and extract the line below 'Prepaid' or 'COD'
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if "Prepaid" in line or "collect cash" in line.lower():
            if i + 1 < len(lines):
                courier = lines[i+1].strip()
                break

    # Account / Sold By
    acc = "N/A"
    acc_m = re.search(r"Sold by\s*:\s*(.*?)\n", text, re.IGNORECASE)
    if not acc_m:
        acc_m = re.search(r"If undelivered, return to:\s*\n(.*?)\n", text)
    if acc_m: acc = acc_m.group(1).strip()

    # SKU, Size, Color, Qty
    sku = "N/A"; sku_m = re.search(r"SKU\s*\n(.*?)\n", text)
    if sku_m: sku = sku_m.group(1).strip()

    size = "N/A"; size_m = re.search(r"Size\s*\n(.*?)\n", text)
    if size_m: size = size_m.group(1).strip()

    color = "N/A"; color_m = re.search(r"Color\s*\n(.*?)\n", text)
    if color_m: color = color_m.group(1).strip()

    qty = 1; qty_m = re.search(r"Qty\s*\n(\d+)", text)
    if qty_m: qty = int(qty_m.group(1))

    # Exchange Check
    is_ex = True if "Exchange" in text or "Replacement" in text else False

    return {"p": page.number, "c": courier, "a": acc, "s": sku, "sz": size, "cl": color, "q": qty, "ex": is_ex}

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/process-pdf', methods=['POST'])
def process_pdf():
    try:
        file = request.files['pdf']
        doc = fitz.open(stream=file.read(), filetype="pdf")
        valid_labels = [extract_label_data(p) for p in doc if extract_label_data(p)]

        # --- DYNAMIC SORTING ---
        # Sort by Courier (A-Z), then Account, then SKU
        valid_labels.sort(key=lambda x: (x['c'].lower(), x['a'].lower(), x['s'].lower()))

        out = fitz.open()
        # Aggregation
        sku_s, ex_sku_s = {}, {}
        cp_s, ex_cp_s = {}, {}
        acc_s = {}

        for l in valid_labels:
            page = doc[l['p']]
            hits = page.search_for("as applicable")
            bottom = hits[0].y1 + 10 if hits else 750
            rect = fitz.Rect(0, 0, 595, bottom)
            np = out.new_page(width=595, height=bottom)
            np.show_pdf_page(np.rect, doc, l['p'], clip=rect)

            key = (l['s'], l['sz'], l['cl'])
            if l['ex']:
                ex_sku_s[key] = ex_sku_s.get(key, 0) + l['q']
                ex_cp_s[l['c']] = ex_cp_s.get(l['c'], 0) + 1
            else:
                sku_s[key] = sku_s.get(key, 0) + l['q']
                cp_s[l['c']] = cp_s.get(l['c'], 0) + 1
            acc_s[l['a']] = acc_s.get(l['a'], 0) + 1

        # --- SUMMARY PAGE GENERATION ---
        sp = out.new_page(width=595, height=842)
        y = 40

        def write_table(page, y_pos, title, data, headers, widths, total_label="Total"):
            page.insert_text((230, y_pos), title, fontname="hebo", fontsize=12)
            y_pos += 15
            # Header
            page.draw_rect(fitz.Rect(50, y_pos, 550, y_pos+20), color=(0,0,0), width=1)
            tx = 55
            for i, h in enumerate(headers):
                page.insert_text((tx, y_pos+15), h, fontname="hebo", fontsize=9)
                tx += widths[i]
            y_pos += 20
            # Data
            total_sum = 0
            for idx, (k, val) in enumerate(data.items(), 1):
                page.draw_rect(fitz.Rect(50, y_pos, 550, y_pos+20), color=(0,0,0), width=0.5)
                row = [idx] + (list(k) if isinstance(k, tuple) else [k]) + [val]
                tx = 55
                for j, v in enumerate(row):
                    page.insert_text((tx, y_pos+15), str(v)[:45], fontname="helv", fontsize=8)
                    tx += widths[j]
                total_sum += val if not isinstance(val, tuple) else 0 # Simple sum logic
                y_pos += 20
            # Total row
            page.insert_text((450, y_pos+15), total_label, fontname="hebo", fontsize=9)
            # Calculating total sum correctly for complex dicts
            real_total = sum(data.values())
            page.insert_text((515, y_pos+15), str(real_total), fontname="hebo", fontsize=9)
            return y_pos + 45

        # 1. Normal Orders
        y = write_table(sp, y, "Order Summary", sku_s, ["No", "SKU", "Size", "Color", "QTY"], [30, 250, 80, 80, 30])
        y = write_table(sp, y, "Courier Wise Summary", cp_s, ["No", "Total Order", "Courier Partner"], [30, 100, 300])
        
        # 2. Exchange Orders (Only if they exist)
        if ex_sku_s:
            if y > 600: sp = out.new_page(width=595, height=842); y = 40
            y = write_table(sp, y, "Exchange Order Summary", ex_sku_s, ["No", "SKU", "Size", "Color", "QTY"], [30, 250, 80, 80, 30])
            y = write_table(sp, y, "Exchange Courier Wise Summary", ex_cp_s, ["No", "Total Order", "Courier Partner"], [30, 100, 300])

        # 3. Company Wise
        if y > 600: sp = out.new_page(width=595, height=842); y = 40
        y = write_table(sp, y, "Company Wise Total Order", acc_s, ["No", "Total Order", "Sold By"], [30, 100, 300])

        path = "/tmp/final_vr_shipment.pdf"
        out.save(path)
        send(path)
        return jsonify({"status": "Success"})
    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)}), 500

def send(p):
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/sendFileByUpload/{API_TOKEN_INSTANCE}"
    with open(p, 'rb') as f:
        requests.post(url, data={'chatId': CHAT_ID, 'caption': '*VR TRENDZ: DYNAMIC SHIPMENT READY*'}, files=[('file', ('VR_Trendz.pdf', f, 'application/pdf'))])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)