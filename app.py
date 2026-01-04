import streamlit as st
from PIL import Image
import cv2
import numpy as np
import pandas as pd
import io

# --- Helper Functions ---
def update_slider(key):
    st.session_state[f"{key}_slider"] = st.session_state[f"{key}_input"]

def update_input(key):
    st.session_state[f"{key}_input"] = st.session_state[f"{key}_slider"]

# --- Vision Logic ---
def process_walls(image_file, threshold_val, min_line_len, max_line_gap, wall_thickness):
    file_bytes = np.asarray(bytearray(image_file.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, 1)
    h, w, c = img.shape
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray_inv = cv2.bitwise_not(gray)
    _, binary = cv2.threshold(gray_inv, 200, 255, cv2.THRESH_BINARY)
    
    if wall_thickness > 1:
        kernel = np.ones((wall_thickness, wall_thickness), np.uint8)
        binary = cv2.erode(binary, kernel, iterations=1)
        binary = cv2.dilate(binary, kernel, iterations=1)
    
    edges = cv2.Canny(binary, 50, 150)
    
    lines = cv2.HoughLinesP(
        edges, 1, np.pi/180, 
        threshold=threshold_val, 
        minLineLength=min_line_len, 
        maxLineGap=max_line_gap
    )
    
    line_img = img.copy()
    total_pixels = 0
    
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            cv2.line(line_img, (x1, y1), (x2, y2), (0, 255, 0), 5)
            length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            total_pixels += length

    final_img = cv2.cvtColor(line_img, cv2.COLOR_BGR2RGB)
    return final_img, total_pixels, w, binary

# --- UI Setup ---
st.set_page_config(page_title="SnapTakeoff", page_icon="🏗️", layout="wide")

defaults = {'min_len': 100, 'thresh': 50, 'gap': 20, 'thick': 1}
for key, val in defaults.items():
    if f'{key}_slider' not in st.session_state: st.session_state[f'{key}_slider'] = val
    if f'{key}_input' not in st.session_state: st.session_state[f'{key}_input'] = val

st.sidebar.title("SnapTakeoff 🏗️")
app_mode = st.sidebar.selectbox("Choose Mode", ["Home", "Upload Blueprint"])

if app_mode == "Home":
    st.title("Welcome to SnapTakeoff")
    st.write("Upload a blueprint to detect walls automatically.")

elif app_mode == "Upload Blueprint":
    st.title("Wall Detector & Cost Estimator")
    
    st.sidebar.markdown("---")
    st.sidebar.header("🔧 Settings")
    
    # Sliders
    st.sidebar.subheader("1. Wall Thickness")
    c1, c2 = st.sidebar.columns([2, 1])
    with c1: st.slider("S", 1, 10, key='thick_slider', label_visibility="collapsed", on_change=update_input, args=('thick',))
    with c2: st.number_input("V", 1, 10, key='thick_input', label_visibility="collapsed", on_change=update_slider, args=('thick',))

    st.sidebar.subheader("2. Min Length")
    c3, c4 = st.sidebar.columns([2, 1])
    with c3: st.slider("S", 50, 500, key='min_len_slider', label_visibility="collapsed", on_change=update_input, args=('min_len',))
    with c4: st.number_input("V", 50, 500, key='min_len_input', label_visibility="collapsed", on_change=update_slider, args=('min_len',))
        
    st.sidebar.subheader("3. Sensitivity")
    c5, c6 = st.sidebar.columns([2, 1])
    with c5: st.slider("S", 20, 200, key='thresh_slider', label_visibility="collapsed", on_change=update_input, args=('thresh',))
    with c6: st.number_input("V", 20, 200, key='thresh_input', label_visibility="collapsed", on_change=update_slider, args=('thresh',))

    st.sidebar.subheader("4. Max Gap Fill")
    c7, c8 = st.sidebar.columns([2, 1])
    with c7: st.slider("S", 5, 100, key='gap_slider', label_visibility="collapsed", on_change=update_input, args=('gap',))
    with c8: st.number_input("V", 5, 100, key='gap_input', label_visibility="collapsed", on_change=update_slider, args=('gap',))

    # Main Area
    uploaded_file = st.file_uploader("Upload a Floor Plan", type=["jpg", "png", "jpeg"])

    if uploaded_file is not None:
        col_left, col_right = st.columns(2)
        
        uploaded_file.seek(0)
        result_img, wall_pixels, img_width_px, debug_img = process_walls(
            uploaded_file, 
            st.session_state['thresh_input'], 
            st.session_state['min_len_input'], 
            st.session_state['gap_input'],
            st.session_state['thick_input']
        )
        
        with col_left:
            st.image(result_img, caption="Final Result", use_container_width=True)
            with st.expander("Show AI 'X-Ray' View"):
                st.image(debug_img, caption="AI Vision", clamp=True, use_container_width=True)
            
        with col_right:
            st.markdown("### 📏 Calibration")
            real_width_ft = st.number_input("Real World Width (Feet):", value=50)
            
            # Calculations
            scale = img_width_px / real_width_ft
            total_feet = wall_pixels / scale
            
            st.success(f"Total Wall Length: **{total_feet:.2f} ft**")
            
            st.markdown("---")
            st.markdown("### 💰 Costs")
            
            wall_height = 8 
            total_sq_ft = total_feet * wall_height
            sheets_needed = total_sq_ft / 32
            drywall_cost = sheets_needed * 15
            paint_gallons = total_sq_ft / 400
            paint_cost = paint_gallons * 40
            total_project_cost = drywall_cost + paint_cost
            
            col_a, col_b = st.columns(2)
            col_a.metric("Drywall Sheets", f"{int(sheets_needed)}", f"${drywall_cost:.2f}")
            col_b.metric("Paint (Gal)", f"{paint_gallons:.1f}", f"${paint_cost:.2f}")

            st.markdown("---")
            
            # --- NEW: Export to Excel ---
            st.write("### 📥 Download Quote")
            
            # Create a Dataframe (Spreadsheet in memory)
            df = pd.DataFrame({
                "Item": ["Wall Length", "Total Area", "Drywall Sheets", "Paint Gallons", "TOTAL ESTIMATE"],
                "Quantity": [f"{total_feet:.2f} ft", f"{total_sq_ft:.2f} sqft", int(sheets_needed), f"{paint_gallons:.1f}", ""],
                "Unit Price": ["-", "-", "$15.00", "$40.00", ""],
                "Total Price": ["-", "-", f"${drywall_cost:.2f}", f"${paint_cost:.2f}", f"${total_project_cost:.2f}"]
            })
            
            # Convert to Excel file in memory
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Estimate')
                
            # The Download Button
            st.download_button(
                label="📄 Download Excel Report",
                data=buffer,
                file_name="SnapTakeoff_Estimate.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )