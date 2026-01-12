import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import os
import io
import base64
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

# Hide Streamlit Menu & Footer
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        [data-testid="stToolbar"] {visibility: hidden;}
        .stDeployButton {display:none;}
    </style>
""", unsafe_allow_html=True)

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    st.error("⚠️ API Key missing. Please check your system variables.")
    st.stop()

client = genai.Client(api_key=api_key)

# Dual Model Setup
IMAGE_MODEL_ID = "gemini-3-pro-image-preview"  # For Rendering
TEXT_MODEL_ID = "gemini-2.0-flash"             # For Summaries

# ==========================================
# 2. UI STYLING
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    :root { --primary: #000000; --text: #1a1a1a; --bg: #ffffff; }
    .stApp { background-color: var(--bg); font-family: 'Inter', sans-serif; color: var(--text); }
    
    .room-card { 
        background: white; 
        border: 1px solid #e5e7eb; 
        border-radius: 12px; 
        padding: 24px; 
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); 
        margin-bottom: 20px; 
    }
    
    .header-text h1 {
        font-weight: 700;
        letter-spacing: -0.02em;
        margin-bottom: 0;
        color: #111;
    }
    
    div.stButton > button { 
        background-color: #0f172a !important; 
        color: white !important; 
        border-radius: 8px !important; 
        height: 50px !important; 
        font-weight: 600 !important; 
        width: 100%; 
        border: none !important;
    }
    div.stButton > button:hover {
        background-color: #1e293b !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. LOGIC: GENERATION & EDITING
# ==========================================

def generate_smart_summary(room_type, category, user_description):
    """ Writes a professional summary using Gemini Flash """
    prompt = f"""
    Act as a professional interior designer. 
    Write a 1-sentence summary of this renovation project for a client report.
    Room: {room_type} | Category: {category} | Details: {user_description}
    Output ONLY the summary sentence.
    """
    try:
        response = client.models.generate_content(model=TEXT_MODEL_ID, contents=prompt)
        return response.text.strip()
    except:
        return f"Renovation of {room_type} featuring updates to {category}."

def generate_renovation(input_image, prompt_text):
    """ 
    Generic Generation Function (Used for both initial Create and Iterative Edit)
    """
    full_prompt = f"""
    Act as a professional architectural visualizer.
    Task: Edit the attached image according to this request: {prompt_text}
    
    STRICT CONSTRAINTS:
    1. Maintain exact camera angle, perspective, and room geometry.
    2. Do not hallucinate new windows, doors, or structural elements.
    3. Output a high-fidelity photorealistic image.
    """
    
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
                    if isinstance(raw_data, bytes):
                        img_data = raw_data
                    else:
                        img_data = base64.b64decode(raw_data)
                    return Image.open(io.BytesIO(img_data)), None
                
        return None, "System processed the request but returned no visual data."

    except Exception as e:
        return None, f"Visualization Error: {str(e)}"

def create_pdf_report(before_img, after_img, summary_text):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('Title', parent=styles['Heading1'], color=HexColor('#0f172a'), alignment=1, fontSize=24)
    story.append(Paragraph("Renovation Proposal", title_style))
    story.append(Spacer(1, 20))

    story.append(Paragraph("<b>Project Scope:</b>", styles["Heading3"]))
    story.append(Paragraph(summary_text, styles["Normal"]))
    story.append(Spacer(1, 24))

    def prep(img):
        b = io.BytesIO()
        img.save(b, format='JPEG')
        b.seek(0)
        return RLImage(b, width=250, height=200)

    data = [[prep(before_img), prep(after_img)], 
            [Paragraph("Current Condition", styles["Normal"]), Paragraph("Proposed Design", styles["Normal"])]]
    
    t = Table(data, colWidths=[260, 260])
    t.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('topPadding', (0,0), (-1,-1), 10)
    ]))
    story.append(t)
    story.append(Spacer(1, 40))
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=HexColor('#94a3b8'), alignment=1)
    story.append(Paragraph("Generated by Room Visualizer AI", footer_style))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ==========================================
# 4. INTERFACE
# ==========================================
st.markdown('<div class="header-text" style="text-align: center; margin-bottom: 30px;"><h1>🏠 Room Visualizer</h1><p style="color:#666;">Professional Renovation Proposals</p></div>', unsafe_allow_html=True)

# --- 1. IMAGE INPUT SECTION ---
st.markdown('<div class="room-card">', unsafe_allow_html=True)

# Tabs for Upload vs Camera
tab1, tab2 = st.tabs(["📂 Upload Photo", "📸 Take Photo"])
input_image = None

with tab1:
    uploaded_file = st.file_uploader("Upload Image", type=['jpg', 'png', 'jpeg'], label_visibility="collapsed")
    if uploaded_file:
        input_image = Image.open(uploaded_file)

with tab2:
    camera_file = st.camera_input("Take a picture")
    if camera_file:
        input_image = Image.open(camera_file)

if input_image:
    st.image(input_image, caption="Selected Site Photo", width=300)

st.markdown('</div>', unsafe_allow_html=True)

# --- 2. DETAILS & GENERATION ---
if input_image:
    st.markdown('<div class="room-card">', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1: room_type = st.selectbox("Room", ["Living Room", "Kitchen", "Bathroom", "Bedroom", "Patio"])
    with col2: category = st.selectbox("Update", ["Paint/Walls", "Flooring", "Cabinets", "Lighting", "Full Remodel"])

    desc = st.text_area("Initial Design Plan:", placeholder="e.g. Change the white walls to a moody charcoal black.")
    
    if st.button("✨ Generate Proposal"):
        with st.spinner("Analyzing geometry and rendering design..."):
            
            # Combine inputs into a single prompt string
            initial_prompt = f"Renovate this {room_type}. Update the {category}. Details: {desc}"
            
            result_image, error = generate_renovation(input_image, initial_prompt)
            
            if error:
                st.error(error)
            elif result_image:
                smart_summary = generate_smart_summary(room_type, category, desc)
                
                # Save to session state
                st.session_state.before = input_image
                st.session_state.after = result_image
                st.session_state.summary = smart_summary
                st.session_state.history = [] # Reset history on new generation
                st.session_state.done = True
                st.rerun() # Force refresh to show results

    st.markdown('</div>', unsafe_allow_html=True)

# --- 3. RESULTS & ITERATIVE EDITING ---
if st.session_state.get('done'):
    st.markdown('<div class="room-card">', unsafe_allow_html=True)
    st.write("### Design Result")
    
    c1, c2 = st.columns(2)
    with c1: st.image(st.session_state.before, caption="Original", use_container_width=True)
    with c2: st.image(st.session_state.after, caption="Proposed Design", use_container_width=True)
    
    st.info(f"**Project Summary:** {st.session_state.summary}")
    
    # PDF Download
    pdf_bytes = create_pdf_report(st.session_state.before, st.session_state.after, st.session_state.summary)
    st.download_button("📄 Download PDF Report", pdf_bytes, "proposal.pdf", "application/pdf", use_container_width=True)
    
    st.markdown("---")
    
    # --- ITERATIVE CHAT INTERFACE ---
    st.write("### 💬 Refine Design")
    st.write("Not quite right? Chat with the visualizer to make tweaks.")
    
    # Chat Input for Refinement
    refinement_prompt = st.chat_input("e.g. 'Make the floor darker' or 'Change the wall color to sage green'")
    
    if refinement_prompt:
        with st.spinner(f"Refining design: '{refinement_prompt}'..."):
            # CRITICAL: We pass the *current result* (st.session_state.after) as the input image
            # This allows "stacking" edits (Image -> Edit 1 -> Edit 2)
            new_result, edit_error = generate_renovation(st.session_state.after, refinement_prompt)
            
            if edit_error:
                st.error(edit_error)
            elif new_result:
                # Update the 'After' image to the new version
                st.session_state.after = new_result
                # Update summary slightly to reflect latest edit
                st.session_state.summary += f" (Revision: {refinement_prompt})"
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
