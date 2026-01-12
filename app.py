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

# --- PWA & UI OVERRIDES ---
# 1. Hide Streamlit Chrome
# 2. Inject PWA Manifest Link (Points to static/manifest.json)
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        [data-testid="stToolbar"] {visibility: hidden;}
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
# 2. LOGIC: GENERATION & SHOPPING
# ==========================================

def generate_shopping_list(input_image):
    """
    Identifies materials and returns a JSON list for monetization.
    """
    prompt = """
    Analyze this interior design image. Identify the 3 main visible materials or fixtures 
    (e.g., 'White Oak Flooring', 'Matte Black Sconce', 'Carrara Marble Counter').
    
    Return ONLY a raw JSON object with this exact structure:
    [
        {"item": "Material Name", "query": "buy Material Name online"},
        {"item": "Material Name 2", "query": "buy Material Name 2 online"},
        {"item": "Material Name 3", "query": "buy Material Name 3 online"}
    ]
    """
    try:
        response = client.models.generate_content(
            model=TEXT_MODEL_ID,
            contents=[input_image, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json" # Forces valid JSON output
            )
        )
        return json.loads(response.text)
    except:
        return []

def generate_smart_summary(room_type, category, user_description):
    prompt = f"Act as an interior designer. Summarize this {room_type} {category} project in one professional sentence. User notes: {user_description}"
    try:
        response = client.models.generate_content(model=TEXT_MODEL_ID, contents=prompt)
        return response.text.strip()
    except:
        return f"Renovation of {room_type} updating {category}."

def generate_renovation(input_image, prompt_text):
    full_prompt = f"Act as an architectural visualizer. Edit the image: {prompt_text}. Maintain geometry. Photorealistic."
    try:
        response = client.models.generate_content(
            model=IMAGE_MODEL_ID,
            contents=[input_image, full_prompt],
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                temperature=0.7,
            )
        )
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    raw_data = part.inline_data.data
                    img_data = raw_data if isinstance(raw_data, bytes) else base64.b64decode(raw_data)
                    return Image.open(io.BytesIO(img_data)), None
        return None, "No visual data returned."
    except Exception as e:
        return None, str(e)

def create_pdf_report(before_img, after_img, summary_text, shopping_list):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], color=HexColor('#0f172a'), alignment=1, fontSize=24)
    story.append(Paragraph("Renovation Proposal", title_style))
    story.append(Spacer(1, 12))

    # Summary
    story.append(Paragraph("<b>Project Scope:</b>", styles["Heading3"]))
    story.append(Paragraph(summary_text, styles["Normal"]))
    story.append(Spacer(1, 20))

    # Images
    def prep(img):
        b = io.BytesIO()
        img.save(b, format='JPEG')
        b.seek(0)
        return RLImage(b, width=250, height=200)

    data = [[prep(before_img), prep(after_img)], 
            [Paragraph("Current Condition", styles["Normal"]), Paragraph("Proposed Design", styles["Normal"])]]
    
    t = Table(data, colWidths=[260, 260])
    t.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
    story.append(t)
    story.append(Spacer(1, 25))

    # --- SHOPPING LIST (MONETIZATION) ---
    if shopping_list:
        story.append(Paragraph("<b>Suggested Materials (Click to Shop):</b>", styles["Heading3"]))
        for item in shopping_list:
            # Create a clickable Wayfair/Google Shopping search link
            query = item['query'].replace(" ", "+")
            url = f"https://www.google.com/search?q={query}&tbm=shop"
            
            # ReportLab XML Link Syntax
            link_text = f'<link href="{url}" color="blue"><u>{item["item"]}</u></link>'
            story.append(Paragraph(f"• {link_text}", styles["Normal"]))
            story.append(Spacer(1, 5))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ==========================================
# 3. INTERFACE
# ==========================================
st.markdown('<div class="header-text" style="text-align: center; margin-bottom: 20px;"><h1>🏠 Room Visualizer</h1></div>', unsafe_allow_html=True)

# --- INPUTS ---
st.markdown('<div class="room-card">', unsafe_allow_html=True)
tab1, tab2 = st.tabs(["📂 Upload", "📸 Camera"])
input_image = None

with tab1:
    u_file = st.file_uploader("Upload", type=['jpg', 'png', 'jpeg'], label_visibility="collapsed")
    if u_file: input_image = Image.open(u_file)
with tab2:
    c_file = st.camera_input("Take Photo")
    if c_file: input_image = Image.open(c_file)

if input_image:
    st.image(input_image, caption="Site Photo", width=300)
st.markdown('</div>', unsafe_allow_html=True)

if input_image:
    st.markdown('<div class="room-card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: room = st.selectbox("Room", ["Living Room", "Kitchen", "Bathroom", "Bedroom", "Patio"])
    with c2: cat = st.selectbox("Category", ["Paint", "Flooring", "Cabinets", "Lighting", "Full Remodel"])
    
    desc = st.text_area("Design Plan:", placeholder="e.g. Modern white oak floors")
    
    if st.button("✨ Generate Proposal"):
        with st.spinner("Designing & Sourcing Materials..."):
            prompt = f"Renovate {room}. Update {cat}. Details: {desc}"
            
            # 1. Generate Image
            res_img, err = generate_renovation(input_image, prompt)
            
            if res_img:
                # 2. Generate Summary & Shopping List (Parallel-ish)
                summ = generate_smart_summary(room, cat, desc)
                shop_list = generate_shopping_list(res_img) # Pass the NEW image to identify new materials
                
                st.session_state.before = input_image
                st.session_state.after = res_img
                st.session_state.summary = summ
                st.session_state.shop = shop_list
                st.session_state.done = True
                st.rerun()
            elif err:
                st.error(err)
    st.markdown('</div>', unsafe_allow_html=True)

# --- RESULTS ---
if st.session_state.get('done'):
    st.markdown('<div class="room-card">', unsafe_allow_html=True)
    st.write("### Proposal")
    
    col1, col2 = st.columns(2)
    with col1: st.image(st.session_state.before, caption="Before", use_container_width=True)
    with c2: st.image(st.session_state.after, caption="After", use_container_width=True)
    
    # Display Shopping List UI
    if st.session_state.shop:
        st.write("#### 🛒 Material List")
        for item in st.session_state.shop:
            url = f"https://www.google.com/search?q={item['query'].replace(' ', '+')}&tbm=shop"
            st.markdown(f"- [{item['item']}]({url})")

    pdf_data = create_pdf_report(st.session_state.before, st.session_state.after, st.session_state.summary, st.session_state.shop)
    st.download_button("📄 Download PDF (with Links)", pdf_data, "proposal.pdf", "application/pdf", use_container_width=True)
    
    st.markdown("---")
    chat_prompt = st.chat_input("Refine this design (e.g. 'Make the floor darker')")
    if chat_prompt:
        with st.spinner("Refining..."):
            new_img, _ = generate_renovation(st.session_state.after, chat_prompt)
            if new_img:
                st.session_state.after = new_img
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
