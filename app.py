import fitz  # PyMuPDF
import re
import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- CONFIGURATION (Inhe Green-API se bhariye) ---
ID_INSTANCE = "7103498692"
API_TOKEN_INSTANCE = "217a71fbbecb41658e5fffa00451817bbe62ea618ad1461c8d"
CHAT_ID = "919428146028-1606295944"  # WhatsApp Group ID

def extract_label_data(page):
    text = page.get_text()
    
    # Courier Identify karna
    courier = "Delhivery" if "Delhivery" in text else "Other"
    
    # Account Name Extract karna (Blue circle wala logic)
    # "If undelivered, return to:" ke baad wali line read karna
    account_name = "N/A"
    if "If undelivered, return to:" in text:
        match = re.search(r"If undelivered, return to:\s*\n(.*?)\n", text)
        if match:
            account_name = match.group(1).strip()

    # SKU aur Qty Extract karna
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

@app.route('/process-pdf', methods=['POST'])
def process_pdf():
    file = request.files['pdf']
    doc = fitz.open(stream=file.read(), filetype="pdf")
    all_labels = []

    # 1. Sabhi pages se data extract karein
    for page in doc:
        all_labels.append(extract_label_data(page))

    # 2. ADVANCED SORTING LOGIC
    # Priority: Delhivery First -> Account Name -> Qty -> SKU
    sorted_labels = sorted(all_labels, key=lambda x: (
        x['courier'] != 'Delhivery', # Delhivery ko top par rakhega
        x['account'].lower(),
        x['qty'],
        x['sku'].lower()
    ))

    # 3. Naya PDF banana (Cropping logic)
    output_doc = fitz.open()
    for label in sorted_labels:
        # Purane document se sahi page uthakar naye mein add karein
        output_doc.insert_pdf(doc, from_page=label['page_index'], to_page=label['page_index'])

    output_filename = "sorted_labels.pdf"
    output_doc.save(output_filename)

    # 4. WhatsApp Group mein bhejni ki koshish karein
    send_to_whatsapp(output_filename)

    return jsonify({"status": "Success", "message": "PDF Sorted and Sent to WhatsApp"})

def send_to_whatsapp(file_path):
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/sendFileByUpload/{API_TOKEN_INSTANCE}"
    payload = {'chatId': CHAT_ID}
    files = [('file', (os.path.basename(file_path), open(file_path, 'rb'), 'application/pdf'))]
    
    response = requests.post(url, data=payload, files=files)
    return response.json()

if __name__ == '__main__':
    app.run(debug=True)
