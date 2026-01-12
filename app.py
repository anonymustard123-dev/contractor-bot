import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import os
import io
import base64
import json
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor

# ==========================================
# 1. SETUP & CONFIG
# ==========================================
st.set_page_config(
    page_title="Room Visualizer", 
    page_icon="🏠", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        [data-testid="stToolbar"] {visibility: hidden;}
        
        button { min-height: 50px; margin-top: 10px; }
        .st-emotion-cache-12fmjuu { opacity: 1 !important; }
        
        /* PDF Preview Container */
        .pdf-preview {
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            width: 100%;
            height: 500px;
            margin-top: 20px;
        }
        
        /* Mobile-Friendly Save Button */
        .save-btn {
            display: block;
            background-color: #0f172a;
            color: white !important;
            padding: 15px;
            text-align: center;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            margin-top: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
    </style>
    <link rel="manifest" href="app/static/manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black">
""", unsafe_allow_html=True)

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    st.error("⚠️ API Key missing.")
    st.stop()

client = genai.Client(api_key=api_key)
IMAGE_MODEL_ID = "gemini-3-pro-image-preview"
TEXT_MODEL_ID = "gemini-2.0-flash"

# ==========================================
# 2. STATE MANAGEMENT
# ==========================================
if 'current_view' not in st.session_state: st.session_state.current_view = 'input'
if 'input_img' not in st.session_state: st.session_state.input_img = None
if 'result_img' not in st.session_state: st.session_state.result_img = None
if 'summary' not in st.session_state: st.session_state.summary = ""
if 'shop_list' not in st.session_state: st.session_state.shop_list = []
if 'pdf_b64' not in st.session_state: st.session_state.pdf_b64 = None 

# ==========================================
# 3. UTILITY FUNCTIONS
# ==========================================
def compress_image(image, max_size=(800, 800)):
    img = image.copy()
    if img.mode != 'RGB': img = img.convert('RGB')
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    return img

def generate_shopping_list(input_image):
    prompt = """Analyze this image. Identify 3 main visible materials. Return JSON: [{"item": "Name", "query": "buy Name"}]"""
    try:
        response = client.models.generate_content(
            model=TEXT_MODEL_ID, contents=[input_image, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json"))
        return json.loads(response.text)
    except: return []

def generate_smart_summary(room, category, desc):
    prompt = f"Summarize this {room} {category} renovation in one professional sentence. Notes: {desc}"
    try:
        response = client.models.generate_content(model=TEXT_MODEL_ID, contents=prompt)
        return response.text.strip()
    except: return f"Renovation of {room} updating {category}."

def generate_renovation(input_image, prompt_text):
    full_prompt = f"Act as an architectural visualizer. Edit the image: {prompt_text}. Maintain geometry. Photorealistic."
    try:
        response = client.models.generate_content(
            model=IMAGE_MODEL_ID,
            contents=[input_image, full_prompt],
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"], temperature=0.7)
        )
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    raw_data = part.inline_data.data
                    img_data = raw_data if isinstance(raw_data, bytes) else base64.b64decode(raw_data)
                    return Image.open(io.BytesIO(img_data)), None
        return None, "No visual data returned."
    except Exception as e: return None, str(e)

def create_pdf_report(before_img, after_img, summary_text, shopping_list):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], color=HexColor('#0f172a'), alignment=1, fontSize=24)
    story.append(Paragraph("Renovation Proposal", title_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph("<b>Project Scope:</b>", styles["Heading3"]))
    story.append(Paragraph(summary_text, styles["Normal"]))
    story.append(Spacer(1, 20))
    
    def prep(img):
        b = io.BytesIO(); img.save(b, format='JPEG'); b.seek(0)
        return RLImage(b, width=250, height=200)
    
    data = [[prep(before_img), prep(after_img)], [Paragraph("Current Condition", styles["Normal"]), Paragraph("Proposed Design", styles["Normal"])]]
    t = Table(data, colWidths=[260, 260]); t.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
    story.append(t); story.append(Spacer(1, 25))
    
    if shopping_list:
        story.append(Paragraph("<b>Suggested Materials (Click to Shop):</b>", styles["Heading3"]))
        for item in shopping_list:
            query = item['query'].replace(" ", "+"); url = f"https://www.google.com/search?q={query}&tbm=shop"
            link_text = f'<link href="{url}" color="blue"><u>{item["item"]}</u></link>'
            story.append(Paragraph(f"• {link_text}", styles["Normal"]))
            story.append(Spacer(1, 5))
            
    doc.build(story)
    
    pdf_bytes = buffer.getvalue()
    b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
    return b64_pdf

# ==========================================
# 4. CALLBACKS
# ==========================================
def handle_upload():
    if st.session_state.uploader:
        img = Image.open(st.session_state.uploader)
        st.session_state.input_img = compress_image(img)

def handle_camera():
    if st.session_state.camera:
        img = Image.open(st.session_state.camera)
        st.session_state.input_img = compress_image(img)

def reset_app():
    st.session_state.current_view = 'input'
    st.session_state.input_img = None
    st.session_state.result_img = None
    st.session_state.pdf_b64 = None

# ==========================================
# 5. UI RENDER
# ==========================================
st.markdown('<div class="header-text" style="text-align: center; margin-bottom: 20px;"><h1>🏠 Room Visualizer</h1></div>', unsafe_allow_html=True)

# --- VIEW 1: INPUT ---
if st.session_state.current_view == 'input':
    st.markdown('<div class="room-card">', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📂 Upload", "📸 Camera"])
    with tab1: st.file_uploader("Upload", type=['jpg','png','jpeg'], key="uploader", label_visibility="collapsed", on_change=handle_upload)
    with tab2: st.camera_input("Take Photo", key="camera", on_change=handle_camera)

    if st.session_state.input_img:
        st.image(st.session_state.input_img, caption="Selected Site Photo", width=300)
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1: st.selectbox("Room", ["Living Room","Kitchen","Bathroom","Bedroom","Patio"], key="room_input")
        with c2: st.selectbox("Category", ["Paint","Flooring","Cabinets","Lighting","Full Remodel"], key="cat_input")
        st.text_area("Design Plan:", placeholder="e.g. Modern white oak floors", key="desc_input")
        
        if st.button("✨ Generate Proposal", use_container_width=True):
            with st.spinner("🎨 Creating your design..."):
                r = st.session_state.room_input
                c = st.session_state.cat_input
                d = st.session_state.desc_input
                prompt = f"Renovate {r}. Update {c}. Details: {d}"
                
                res, err = generate_renovation(st.session_state.input_img, prompt)
                
                if res:
                    st.session_state.result_img = res
                    st.session_state.summary = generate_smart_summary(r, c, d)
                    st.session_state.shop_list = generate_shopping_list(res)
                    st.session_state.pdf_b64 = create_pdf_report(st.session_state.input_img, res, st.session_state.summary, st.session_state.shop_list)
                    st.session_state.current_view = 'result'
                    st.rerun()
                elif err:
                    st.error(f"Error: {err}")

    st.markdown('</div>', unsafe_allow_html=True)

# --- VIEW 2: RESULTS ---
elif st.session_state.current_view == 'result':
    st.markdown('<div class="room-card">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1: st.image(st.session_state.input_img, caption="Before", use_container_width=True)
    with col2: st.image(st.session_state.result_img, caption="After", use_container_width=True)
    
    if st.session_state.shop_list:
        with st.expander("🛒 View Material List"):
            for item in st.session_state.shop_list:
                url = f"https://www.google.com/search?q={item['query'].replace(' ', '+')}&tbm=shop"
                st.markdown(f"- [{item['item']}]({url})")

    # --- PWA PDF FIX ---
    if st.session_state.pdf_b64:
        st.write("### 📄 Proposal Report")
        
        # 1. Embed PDF directly (So they see it instantly without leaving)
        pdf_display = f'<iframe src="data:application/pdf;base64,{st.session_state.pdf_b64}" class="pdf-preview"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
        
        # 2. Save Button (WITHOUT target="_blank" to prevent crashing)
        # We use the 'download' attribute which hints iOS to save the file
        href = f'<a href="data:application/pdf;base64,{st.session_state.pdf_b64}" download="proposal.pdf" class="save-btn">💾 Save PDF to Files</a>'
        st.markdown(href, unsafe_allow_html=True)
    
    st.markdown("---")
    
    chat_input = st.chat_input("Refine this design (e.g. 'Make the floor darker')")
    if chat_input:
        with st.spinner("✨ Refining design..."):
            new_res, err = generate_renovation(st.session_state.result_img, chat_input)
            if new_res:
                st.session_state.result_img = new_res
                st.session_state.pdf_b64 = create_pdf_report(st.session_state.input_img, new_res, st.session_state.summary, st.session_state.shop_list)
                st.rerun()
            elif err:
                st.error(err)
    
    st.button("🔄 Start New Project", on_click=reset_app, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
