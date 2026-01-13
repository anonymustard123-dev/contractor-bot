import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import os
import io
import base64
import json
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, Color

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
        
        .pdf-preview {
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            width: 100%;
            height: 600px; /* Taller for better preview */
            margin-top: 20px;
        }
        
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
if 'rationale' not in st.session_state: st.session_state.rationale = ""
if 'shop_list' not in st.session_state: st.session_state.shop_list = []
if 'pdf_b64' not in st.session_state: st.session_state.pdf_b64 = None 

# ==========================================
# 3. LOGIC FUNCTIONS
# ==========================================
def compress_image(image, max_size=(800, 800)):
    img = image.copy()
    if img.mode != 'RGB': img = img.convert('RGB')
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    return img

def generate_shopping_list(result_image, user_request):
    """
    Intelligently identifies ONLY items requested by the user.
    """
    prompt = f"""
    The user requested this specific renovation: "{user_request}".
    Look at the provided image of the result.
    Identify 3-4 specific materials, furniture, or fixtures that correspond ONLY to the user's request. 
    (Do NOT list existing items like walls/windows unless they were changed).
    
    Return a raw JSON list.
    Example: [{{"item": "Wide Plank Oak Flooring", "query": "buy wide plank white oak flooring"}}]
    """
    try:
        response = client.models.generate_content(
            model=TEXT_MODEL_ID, contents=[result_image, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json"))
        return json.loads(response.text)
    except: return []

def generate_design_content(room, category, desc):
    """
    Generates rich text for the PDF report.
    Returns a tuple: (Summary, Rationale)
    """
    prompt = f"""
    Act as a high-end interior designer. 
    Project: {room} renovation focusing on {category}.
    User Request: "{desc}"
    
    Task 1: Write a 1-sentence "Executive Summary" of the transformation.
    Task 2: Write a short paragraph (3-4 sentences) called "Design Rationale" explaining why this new look works (mention mood, lighting, style).
    
    Return JSON: {{ "summary": "...", "rationale": "..." }}
    """
    try:
        response = client.models.generate_content(
            model=TEXT_MODEL_ID, contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = json.loads(response.text)
        return data.get("summary", ""), data.get("rationale", "")
    except:
        return f"Renovation of {room} updating {category}.", "This design modernizes the space while respecting original proportions."

def generate_renovation(input_image, prompt_text):
    """
    The Tightened Generation Prompt
    """
    full_prompt = f"""
    Act as an architectural visualizer. 
    Task: Edit the attached image based on this request: "{prompt_text}"
    
    CRITICAL CONSTRAINTS (DO NOT BREAK):
    1. ZERO GEOMETRY CHANGES: Do not move walls, windows, ceilings, or structural beams. The perspective must match perfectly.
    2. TARGETED IN-PAINTING: Only change the materials or objects specifically mentioned in the request. If the user asks for a new floor, keep the furniture exactly where it is (just change the floor under it).
    3. PHOTOREALISM: The output must look like a real photograph, not a render.
    """
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

# ==========================================
# 4. PDF ENGINE (ENHANCED)
# ==========================================
def create_pdf_report(before_img, after_img, summary_text, rationale_text, shopping_list):
    buffer = io.BytesIO()
    # Margins: top, bottom, left, right
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=40, bottomMargin=40, leftMargin=40, rightMargin=40)
    styles = getSampleStyleSheet()
    story = []
    
    # Custom Styles
    styles.add(ParagraphStyle(name='BrandTitle', parent=styles['Heading1'], fontSize=26, textColor=HexColor('#0f172a'), spaceAfter=10))
    styles.add(ParagraphStyle(name='SectionHeader', parent=styles['Heading2'], fontSize=14, textColor=HexColor('#334155'), spaceBefore=15, spaceAfter=8))
    styles.add(ParagraphStyle(name='BodyText', parent=styles['Normal'], fontSize=11, leading=16, textColor=HexColor('#333333')))
    styles.add(ParagraphStyle(name='LinkText', parent=styles['Normal'], fontSize=11, textColor=HexColor('#2563eb')))

    # 1. HEADER
    story.append(Paragraph("Renovation Proposal", styles['BrandTitle']))
    story.append(Spacer(1, 10))
    story.append(Paragraph(summary_text, styles['BodyText']))
    story.append(Spacer(1, 20))
    
    # 2. VISUALS (Side by Side)
    def prep(img):
        b = io.BytesIO(); img.save(b, format='JPEG', quality=85); b.seek(0)
        # 3.2 inches wide ensures they fit side-by-side on letter paper
        return RLImage(b, width=250, height=200) # Aspect ratio might need tweaks
    
    # Table for side-by-side
    img_data = [[prep(before_img), prep(after_img)], 
                [Paragraph("<b>Original Site</b>", styles['BodyText']), Paragraph("<b>Proposed Design</b>", styles['BodyText'])]]
    
    t = Table(img_data, colWidths=[270, 270])
    t.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,1), (-1,1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 25))
    
    # 3. DESIGN RATIONALE
    story.append(Paragraph("Design Concept", styles['SectionHeader']))
    story.append(Paragraph(rationale_text, styles['BodyText']))
    story.append(Spacer(1, 15))
    
    # 4. MATERIAL SPECIFICATIONS (Smart Shopping List)
    if shopping_list:
        story.append(Paragraph("Material Palette & Specifications", styles['SectionHeader']))
        for item in shopping_list:
            query = item['query'].replace(" ", "+")
            url = f"https://www.google.com/search?q={query}&tbm=shop"
            # Bullet point with clickable link
            link_html = f'<bullet>&bull;</bullet> <b>{item["item"]}</b>: <a href="{url}" color="blue">Find similar styles online</a>'
            story.append(Paragraph(link_html, styles['BodyText']))
    
    story.append(Spacer(1, 20))
    
    # 5. NEXT STEPS
    story.append(Paragraph("Next Steps", styles['SectionHeader']))
    steps = """
    1. <b>Verify Measurements:</b> Confirm site dimensions before ordering materials.
    2. <b>Sample Approval:</b> Order physical samples of the materials listed above.
    3. <b>Contractor Review:</b> Share this visual with your contractor for labor estimates.
    """
    story.append(Paragraph(steps.replace("\n", "<br/>"), styles['BodyText']))
    
    # Build
    doc.build(story)
    
    pdf_bytes = buffer.getvalue()
    b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
    return b64_pdf

# ==========================================
# 5. CALLBACKS
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
# 6. UI RENDER
# ==========================================
st.markdown('<div class="header-text" style="text-align: center; margin-bottom: 20px;"><h1>🏠 Room Visualizer</h1></div>', unsafe_allow_html=True)

# VIEW 1: INPUT
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
                
                # 1. Generate Image
                res, err = generate_renovation(st.session_state.input_img, prompt)
                
                if res:
                    st.session_state.result_img = res
                    # 2. Generate Content (Summary + Rationale)
                    summ, rat = generate_design_content(r, c, d)
                    st.session_state.summary = summ
                    st.session_state.rationale = rat
                    # 3. Generate Smart Shopping List (Uses User Desc + Image)
                    st.session_state.shop_list = generate_shopping_list(res, d)
                    
                    # 4. Create Enhanced PDF
                    st.session_state.pdf_b64 = create_pdf_report(
                        st.session_state.input_img, res, 
                        st.session_state.summary, st.session_state.rationale, 
                        st.session_state.shop_list
                    )
                    st.session_state.current_view = 'result'
                    st.rerun()
                elif err:
                    st.error(f"Error: {err}")

    st.markdown('</div>', unsafe_allow_html=True)

# VIEW 2: RESULTS
elif st.session_state.current_view == 'result':
    st.markdown('<div class="room-card">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1: st.image(st.session_state.input_img, caption="Before", use_container_width=True)
    with col2: st.image(st.session_state.result_img, caption="After", use_container_width=True)
    
    # Display Logic
    st.write("### Design Concept")
    st.write(st.session_state.rationale)
    
    if st.session_state.shop_list:
        with st.expander("🛒 Recommended Materials"):
            for item in st.session_state.shop_list:
                url = f"https://www.google.com/search?q={item['query'].replace(' ', '+')}&tbm=shop"
                st.markdown(f"- **{item['item']}**: [Find Online]({url})")

    # PDF PREVIEW & SAVE
    if st.session_state.pdf_b64:
        st.write("### 📄 Proposal Report")
        pdf_display = f'<iframe src="data:application/pdf;base64,{st.session_state.pdf_b64}" class="pdf-preview"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
        
        href = f'<a href="data:application/octet-stream;base64,{st.session_state.pdf_b64}" download="renovation_proposal.pdf" class="save-btn">💾 Save PDF to Device</a>'
        st.markdown(href, unsafe_allow_html=True)
    
    st.markdown("---")
    
    chat_input = st.chat_input("Refine this design...")
    if chat_input:
        with st.spinner("✨ Refining..."):
            new_res, err = generate_renovation(st.session_state.result_img, chat_input)
            if new_res:
                st.session_state.result_img = new_res
                # Regenerate PDF with new image
                st.session_state.pdf_b64 = create_pdf_report(
                    st.session_state.input_img, new_res, 
                    st.session_state.summary, st.session_state.rationale, 
                    st.session_state.shop_list
                )
                st.rerun()
            elif err:
                st.error(err)
    
    st.button("🔄 Start New Project", on_click=reset_app, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
