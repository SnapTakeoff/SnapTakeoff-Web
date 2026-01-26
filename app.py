import base64
import io
import os
import json 
from flask import Flask, render_template, request, send_file

app = Flask(__name__, template_folder='.')

# --- IMPROVED IMAGE PROCESSING LOGIC ---
def process_walls(file_stream, thresh, min_len, gap, thick):
    import cv2
    import numpy as np
    # Read file stream into numpy array
    if isinstance(file_stream, bytes):
        file_bytes = np.frombuffer(file_stream, np.uint8)
    else:
        file_bytes = np.asarray(bytearray(file_stream.read()), dtype=np.uint8)
        
    img = cv2.imdecode(file_bytes, 1)
    if img is None: return None, 0, 0

    # 1. Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 2. Gaussian Blur (NEW): Removes texture/noise (carpet patterns)
    # This is critical for complex blueprints to stop detecting floor textures
    gray_blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # 3. Inverse Binary Threshold
    # We target dark pixels (walls). Pixels < 200 become 255 (White), others 0 (Black).
    # This filters out light grey textures effectively.
    _, binary = cv2.threshold(gray_blurred, 200, 255, cv2.THRESH_BINARY_INV)
    
    # 4. Morphological Opening (NEW): Removes small noise specks
    # This deletes isolated pixels that aren't part of a line
    kernel_noise = np.ones((3,3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_noise)

    # 5. User Adjustment (Thickening for detection)
    if thick > 1:
        kernel_thick = np.ones((thick, thick), np.uint8)
        binary = cv2.dilate(binary, kernel_thick, iterations=1)
    
    # 6. Edge Detection
    edges = cv2.Canny(binary, 50, 150)
    
    # 7. Line Detection (HoughLinesP)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=thresh, minLineLength=min_len, maxLineGap=gap)
    
    line_img = img.copy()
    total_pixels = 0
    
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            # Draw Green Line (Thinner width for cleaner visualization)
            cv2.line(line_img, (x1, y1), (x2, y2), (0, 255, 0), 3)
            total_pixels += np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    
    # Encode result
    _, buffer = cv2.imencode('.jpg', line_img)
    img_str = base64.b64encode(buffer).decode('utf-8')
    
    return img_str, total_pixels, img.shape[1]

# --- ROUTES ---

@app.route('/')
def home():
    # Renders the lightweight marketing page
    return render_template('home.html')

@app.route('/tool', methods=['GET', 'POST'])
def tool():
    # Renders the heavy CAD application
    default_params = {'thresh':50, 'min_len':100, 'gap':20, 'thick':1}

    if request.method == 'GET':
        return render_template('tool.html', params=default_params)

    if 'file' not in request.files: return "No file"
    file = request.files['file']
    if file.filename == '': return "No file"

    # Get Params
    thresh = int(request.form.get('thresh', 50))
    min_len = int(request.form.get('min_len', 100))
    gap = int(request.form.get('gap', 20))
    thick = int(request.form.get('thick', 1))

    # Process PDF or Image
    if file.filename.lower().endswith('.pdf'):
        import fitz
        doc = fitz.open(stream=file.read(), filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=200) # Higher DPI for better detection
        img_bytes = pix.tobytes("png")
        # Pass bytes directly to processor
        img_str, pixels, width_px = process_walls(img_bytes, thresh, min_len, gap, thick)
    else:
        # Pass file stream
        img_str, pixels, width_px = process_walls(file, thresh, min_len, gap, thick)
    
    return render_template('tool.html', 
                           result=True, 
                           image_data=img_str, 
                           raw_pixels=pixels,       
                           raw_width=width_px,      
                           params={'thresh': thresh, 'min_len': min_len, 'gap': gap, 'thick': thick})

# --- UTILITY ROUTES ---

@app.route('/download_report', methods=['POST'])
def download_report():
    import pandas as pd
    try:
        feet = float(request.form.get('final_feet', 0))
        cost = float(request.form.get('final_cost', 0))
        sheets = float(request.form.get('final_sheets', 0))
        paint = float(request.form.get('final_paint', 0))
        
        area_breakdown_json = request.form.get('area_breakdown', '[]')
        area_breakdown = json.loads(area_breakdown_json)
        
        count_elec = int(request.form.get('count_elec', 0))
        count_plumb = int(request.form.get('count_plumb', 0))
        count_hvac = int(request.form.get('count_hvac', 0))
        
        unit_elec = float(request.form.get('unit_elec', 0))
        unit_plumb = float(request.form.get('unit_plumb', 0))
        unit_hvac = float(request.form.get('unit_hvac', 0))
        
        currency_sym = request.form.get('currency_symbol', '$')
        unit_sheet = float(request.form.get('unit_price_sheet', 15))
        unit_paint = float(request.form.get('unit_price_paint', 40))
        
    except:
        return "Error: Data missing."

    line_items = ["Total Wall Length", "Drywall Sheets (4x8)", "Paint Gallons"]
    quantities = [f"{feet:.2f} ft", f"{sheets:.0f} sheets", f"{paint:.1f} gal"]
    unit_costs = ["-", f"{currency_sym}{unit_sheet:.2f}", f"{currency_sym}{unit_paint:.2f}"]
    totals = ["-", f"{currency_sym}{sheets*unit_sheet:.2f}", f"{currency_sym}{paint*unit_paint:.2f}"]

    if area_breakdown:
        for room in area_breakdown:
            line_items.append(f"Flooring: {room['name']}")
            quantities.append(f"{room['sqft']} sq.ft")
            unit_costs.append("-")
            totals.append("-")
    else:
        line_items.append("Flooring Area")
        quantities.append(f"{float(request.form.get('final_area', 0)):.2f} sq.ft")
        unit_costs.append("-")
        totals.append("-")

    line_items.extend(["Electrical Fix", "Plumbing Fix", "HVAC/Mech"])
    quantities.extend([f"{count_elec} items", f"{count_plumb} items", f"{count_hvac} items"])
    unit_costs.extend([f"{currency_sym}{unit_elec:.2f}", f"{currency_sym}{unit_plumb:.2f}", f"{currency_sym}{unit_hvac:.2f}"])
    totals.extend([f"{currency_sym}{count_elec*unit_elec:.2f}", f"{currency_sym}{count_plumb*unit_plumb:.2f}", f"{currency_sym}{count_hvac*unit_hvac:.2f}"])

    line_items.extend(["Labor & Misc", "TOTAL ESTIMATE"])
    quantities.extend(["-", "-"])
    unit_costs.extend(["-", "-"])
    totals.extend(["-", f"{currency_sym}{cost:.2f}"])

    df = pd.DataFrame({
        "Line Item": line_items,
        "Quantity": quantities,
        "Unit Cost": unit_costs,
        "Total": totals
    })

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='SnapTakeoff Estimate')
    output.seek(0)
    
    return send_file(output, download_name="SnapTakeoff_Quote.xlsx", as_attachment=True)

@app.route('/favicon.ico')
def favicon():
    # Simple workaround if favicon.png doesn't exist yet
    if os.path.exists('favicon.png'):
        return send_file('favicon.png', mimetype='image/png')
    return "", 204

@app.route('/sitemap.xml')
def sitemap():
    # Replace with your ACTUAL Render URL (Important!)
    base_url = "https://snaptakeoff-web.onrender.com" 
    
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url>
            <loc>{base_url}/</loc>
            <changefreq>weekly</changefreq>
            <priority>1.0</priority>
        </url>
        <url>
            <loc>{base_url}/tool</loc>
            <changefreq>monthly</changefreq>
            <priority>0.8</priority>
        </url>
    </urlset>"""
    
    # We import Response here so you don't have to change your top imports
    from flask import Response 
    return Response(xml, mimetype='application/xml')

if __name__ == '__main__':
    app.run(debug=True)