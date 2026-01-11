import base64
import numpy as np
import cv2
import pandas as pd
import io
import os
from flask import Flask, render_template, request, send_file

app = Flask(__name__, template_folder='.')

def process_walls(file_stream, thresh, min_len, gap, thick):
    file_bytes = np.asarray(bytearray(file_stream.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, 1)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray_inv = cv2.bitwise_not(gray)
    _, binary = cv2.threshold(gray_inv, 200, 255, cv2.THRESH_BINARY)
    
    if thick > 1:
        kernel = np.ones((thick, thick), np.uint8)
        binary = cv2.erode(binary, kernel, iterations=1)
        binary = cv2.dilate(binary, kernel, iterations=1)
    
    edges = cv2.Canny(binary, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=thresh, minLineLength=min_len, maxLineGap=gap)
    
    line_img = img.copy()
    total_pixels = 0
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            cv2.line(line_img, (x1, y1), (x2, y2), (0, 255, 0), 5)
            total_pixels += np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    
    _, buffer = cv2.imencode('.jpg', line_img)
    img_str = base64.b64encode(buffer).decode('utf-8')
    return img_str, total_pixels, img.shape[1]

@app.route('/')
def home():
    return render_template('index.html', page='home')

@app.route('/tool', methods=['GET', 'POST'])
def tool():
    if request.method == 'GET':
        return render_template('index.html', page='tool', params={'thresh':50, 'min_len':100, 'gap':20, 'thick':1})

    if 'file' not in request.files: return "No file"
    file = request.files['file']
    if file.filename == '': return "No file"

    thresh = int(request.form.get('thresh', 50))
    min_len = int(request.form.get('min_len', 100))
    gap = int(request.form.get('gap', 20))
    thick = int(request.form.get('thick', 1))

    img_str, pixels, width_px = process_walls(file, thresh, min_len, gap, thick)
    
    return render_template('index.html', 
                           page='tool', 
                           result=True, 
                           image_data=img_str, 
                           raw_pixels=pixels,       
                           raw_width=width_px,      
                           params={'thresh': thresh, 'min_len': min_len, 'gap': gap, 'thick': thick})

@app.route('/download_report', methods=['POST'])
def download_report():
    try:
        feet = float(request.form.get('final_feet', 0))
        cost = float(request.form.get('final_cost', 0))
        sheets = float(request.form.get('final_sheets', 0))
        paint = float(request.form.get('final_paint', 0))
        
        # New Inputs from JS
        area_sqft = float(request.form.get('final_area', 0))
        item_count = float(request.form.get('final_count', 0))
        
        # Currency & Prices
        currency_sym = request.form.get('currency_symbol', '$')
        unit_sheet = float(request.form.get('unit_price_sheet', 15))
        unit_paint = float(request.form.get('unit_price_paint', 40))
        unit_item = float(request.form.get('unit_price_item', 50))
        
    except:
        return "Error: Data missing."

    # Dynamic Excel Logic
    df = pd.DataFrame({
        "Line Item": [
            "Total Wall Length", 
            "Drywall Sheets (4x8)", 
            "Paint Gallons", 
            "Flooring Area",         # New
            "Fixtures/Items (Count)", # New
            "Labor & Misc", 
            "TOTAL ESTIMATE"
        ],
        "Quantity": [
            f"{feet:.2f} ft", 
            f"{sheets:.0f} sheets", 
            f"{paint:.1f} gal", 
            f"{area_sqft:.2f} sq.ft", # New
            f"{item_count:.0f} items", # New
            "-", 
            "-"
        ],
        "Unit Cost": [
            "-", 
            f"{currency_sym}{unit_sheet:.2f}", 
            f"{currency_sym}{unit_paint:.2f}", 
            "-",                       # Flooring usually implies separate material cost, keeping simple for now
            f"{currency_sym}{unit_item:.2f}", # New
            "-", 
            "-"
        ],
        "Total": [
            "-", 
            f"{currency_sym}{sheets*unit_sheet:.2f}", 
            f"{currency_sym}{paint*unit_paint:.2f}", 
            "-", 
            f"{currency_sym}{item_count*unit_item:.2f}", # New
            "-", 
            f"{currency_sym}{cost:.2f}"
        ]
    })

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='SnapTakeoff Estimate')
    output.seek(0)
    
    return send_file(output, download_name="SnapTakeoff_Quote.xlsx", as_attachment=True)

@app.route('/favicon.ico')
def favicon():
    return send_file('favicon.png', mimetype='image/png')

if __name__ == '__main__':
    app.run(debug=True)