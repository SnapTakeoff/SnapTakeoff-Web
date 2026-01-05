import streamlit as st
from PIL import Image
import cv2
import numpy as np
import pandas as pd
import io

# --- 1. DESIGN & CONFIGURATION ---
st.set_page_config(page_title="SnapTakeoff Prime", page_icon="🏗️", layout="wide")

# --- FUTURISTIC CSS OVERLAY ---
st.markdown("""
    <style>
        /* Main Background: Keep it relatively light */
        .stApp {
            background-color: #e8eaf6; 
        }
        
        /* --- THE DARK BAND (Sidebar) --- */
        section[data-testid="stSidebar"] {
            background-color: #0a0e17; /* Deep dark space blue/black */
            border-right: none;
        }
        
        /* Sidebar text needs to be forced light */
        /* REMOVED 'span' from this list so it doesn't kill the logo color */
        section[data-testid="stSidebar"] p, 
        section[data-testid="stSidebar"] label, 
        section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] p {
            color: #c9d1d9 !important;
        }

        /* --- THE FUTURISTIC BOXES (Containers) --- */
        [data-testid="stBorderContainer"] {
            background-color: #161b22; 
            border: 1px solid #00d26a; 
            box-shadow: 0 0 15px rgba(0, 210, 106, 0.3); 
            border-radius: 10px;
        }
        [data-testid="stBorderContainer"] h3 {
             color: #ffffff !important;
             font-family: 'Orbitron', sans-serif;
             letter-spacing: 1px;
        }

        /* --- NEON METRICS --- */
        [data-testid="stMetricValue"] {
            color: #00d26a !important; 
            font-family: 'Courier New', monospace;
            text-shadow: 0 0 5px rgba(0, 210, 106, 0.5);
        }
        [data-testid="stMetricLabel"] {
            color: #8b949e !important;
        }

        /* --- TECH BUTTONS --- */
        .stButton > button {
            background-color: #21262d;
            color: #00d26a;
            border: 1px solid #30363d;
            font-weight: bold;
            transition: all 0.3s ease;
        }
        .stButton > button:hover {
            border-color: #00d26a;
            box-shadow: 0 0 10px #00d26a;
            color: white;
        }
        
        h1 { color: #0a0e17 !important; }

    </style>
""", unsafe_allow_html=True)


# --- 2. LOGIC ---
def update_slider(key): st.session_state[f"{key}_slider"] = st.session_state[f"{key}_input"]
def update_input(key): st.session_state[f"{key}_input"] = st.session_state[f"{key}_slider"]

def process_walls(image_file, threshold_val, min_line_len, max_line_gap, wall_thickness):
    file_bytes = np.asarray(bytearray(image_file.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, 1)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray_inv = cv2.bitwise_not(gray)
    _, binary = cv2.threshold(gray_inv, 200, 255, cv2.THRESH_BINARY)
    if wall_thickness > 1:
        kernel = np.ones((wall_thickness, wall_thickness), np.uint8)
        binary = cv2.erode(binary, kernel, iterations=1)
        binary = cv2.dilate(binary, kernel, iterations=1)
    edges = cv2.Canny(binary, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=threshold_val, minLineLength=min_line_len, maxLineGap=max_line_gap)
    line_img = img.copy()
    total_pixels = 0
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            cv2.line(line_img, (x1, y1), (x2, y2), (0, 210, 106), 6)
            total_pixels += np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    return cv2.cvtColor(line_img, cv2.COLOR_BGR2RGB), total_pixels, img.shape[1], binary

# --- 3. UI LAYOUT ---
defaults = {'min_len': 100, 'thresh': 50, 'gap': 20, 'thick': 1}
for key, val in defaults.items():
    if f'{key}_slider' not in st.session_state: st.session_state[f'{key}_slider'] = val
    if f'{key}_input' not in st.session_state: st.session_state[f'{key}_input'] = val

# --- LOGO CHANGE (FIXED) ---
st.sidebar.markdown(
    """
    <div style='margin-top: 10px; margin-bottom: 20px; font-size: 40px; font-weight: 800; color: white; line-height: 1;'>
        Snap<span style='color: #FFD700 !important;'>Takeoff</span>
    </div>
    """, 
    unsafe_allow_html=True
)

app_mode = st.sidebar.selectbox("", ["Home", "Upload"])

if app_mode == "Home":
    st.title("Welcome.")
    st.markdown("""
    ### AI-Powered Blueprint Analysis Active.
    
    This system uses advanced computer vision to scan architectural schematics and generate immediate material requirements.
    
    **Status:** Ready for blueprint upload.
    """)

elif app_mode == "Upload":
    st.title("Estimate Protocol Initiated")
    
    st.sidebar.markdown("---")
    st.sidebar.caption("SENSOR CALIBRATION")
    st.sidebar.write("**1. Wall Thickness Filter**")
    c1, c2 = st.sidebar.columns([3, 1])
    with c1: st.slider("", 1, 10, key='thick_slider', label_visibility="collapsed", on_change=update_input, args=('thick',))
    with c2: st.number_input("", 1, 10, key='thick_input', label_visibility="collapsed", on_change=update_slider, args=('thick',))
    st.sidebar.write("**2. Minimum Signal Length**")
    c3, c4 = st.sidebar.columns([3, 1])
    with c3: st.slider("", 50, 500, key='min_len_slider', label_visibility="collapsed", on_change=update_input, args=('min_len',))
    with c4: st.number_input("", 50, 500, key='min_len_input', label_visibility="collapsed", on_change=update_slider, args=('min_len',))
    st.sidebar.write("**3. Detection Sensitivity**")
    c5, c6 = st.sidebar.columns([3, 1])
    with c5: st.slider("", 20, 200, key='thresh_slider', label_visibility="collapsed", on_change=update_input, args=('thresh',))
    with c6: st.number_input("", 20, 200, key='thresh_input', label_visibility="collapsed", on_change=update_slider, args=('thresh',))
    st.sidebar.write("**4. Gap Fill Protocol**")
    c7, c8 = st.sidebar.columns([3, 1])
    with c7: st.slider("", 5, 100, key='gap_slider', label_visibility="collapsed", on_change=update_input, args=('gap',))
    with c8: st.number_input("", 5, 100, key='gap_input', label_visibility="collapsed", on_change=update_slider, args=('gap',))

    uploaded_file = st.file_uploader("Initialize Blueprint Scan (Drop File)", type=["jpg", "png", "jpeg"])

    if uploaded_file is not None:
        col_img, col_data = st.columns([1.5, 1])
        uploaded_file.seek(0)
        final_img, wall_pixels, img_w, debug_img = process_walls(
            uploaded_file, st.session_state['thresh_input'], st.session_state['min_len_input'], st.session_state['gap_input'], st.session_state['thick_input']
        )
        
        with col_img:
            with st.container(border=True):
                st.subheader("Target Confirmation")
                st.image(final_img, use_container_width=True)
            with st.expander("View Sensor Data (X-Ray)"):
                st.image(debug_img, use_container_width=True)

        with col_data:
            with st.container(border=True):
                st.subheader("📏 Calibration Data")
                st.info(f"Sensor Width: {img_w} px")
                real_width_ft = st.number_input("Real World Width (ft)", value=50, step=1)
                scale = img_w / real_width_ft
                total_feet = wall_pixels / scale
                st.metric(label="Total Linear Feet Detected", value=f"{total_feet:.2f} ft")
            
            with st.container(border=True):
                st.subheader("💰 Resource Allocation")
                sheets = (total_feet * 8) / 32
                paint = (total_feet * 8) / 400
                cost_drywall = sheets * 15
                cost_paint = paint * 40
                c_a, c_b = st.columns(2)
                c_a.metric("Drywall Units", f"{int(sheets)}", f"${cost_drywall:.0f}")
                c_b.metric("Paint / Gal", f"{paint:.1f}", f"${cost_paint:.0f}")
                st.divider()
                st.markdown(f"<h3 style='text-align: center; color: #00d26a;'>Total Estimate: ${cost_drywall + cost_paint:.2f}</h3>", unsafe_allow_html=True)

                df = pd.DataFrame({
                    "Item": ["Wall Length (ft)", "Drywall Sheets", "Paint Gallons", "ESTIMATED COST"],
                    "Quantity": [total_feet, sheets, paint, 1],
                    "Cost": ["-", f"${cost_drywall:.2f}", f"${cost_paint:.2f}", f"${cost_drywall + cost_paint:.2f}"]
                })
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df.to_excel(writer, index=False)
                st.download_button("📥 Export Mission Data (XLSX)", data=buffer, file_name="SnapTakeoff_Mission_Quote.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)