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
# 3. LOGIC: GENERATION & SUMMARY
# ==========================================

def generate_smart_summary(room_type, category, user_description):
    """
    Uses a fast text model to write a professional summary of the changes.
    """
    prompt = f"""
    Act as a professional interior designer. 
    Write a 1-sentence summary of this renovation project for a client report.
    Room: {room_type}
    Category: {category}
    User Request: {user_description}
    
    Output ONLY the summary sentence. Make it sound professional and appealing.
    """
    try:
        response = client.models.generate_content(
            model=TEXT_MODEL_ID,
            contents=prompt
        )
        return response.text.strip()
    except:
        return f"Renovation of {room_type} featuring updates to {category}."

def generate_renovation(input_image, room_type, category, user_description):
    """
    Calls the Image Model for the visual update.
    """
    prompt_text = f"""
    Act as a professional architectural visualizer.
    Task: Renovate this {room_type}.
    Category: {category}
    Details: {user_description}
    
    STRICT CONSTRAINTS:
    1. Maintain exact camera angle and room geometry.
    2. Output a high-fidelity photorealistic image.
    """
    
    try:
        response = client.models.generate_content(
            model=IMAGE_MODEL_ID,
            contents=[input_image, prompt_text],
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

    # Clean Header
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], color=HexColor('#0f172a'), alignment=1, fontSize=24)
    story.append(Paragraph("Renovation Proposal", title_style))
    story.append(Spacer(1, 20))

    # Professional Summary Block
    story.append(Paragraph("<b>Project Scope:</b>", styles["Heading3"]))
    story.append(Paragraph(summary_text, styles["Normal"]))
    story.append(Spacer(1, 24))

    # Side-by-Side Images
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
    
    # Disclaimer footer
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

st.markdown('<div class="room-card">', unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1: room_type = st.selectbox("Room", ["Living Room", "Kitchen", "Bathroom", "Bedroom", "Patio"])
with col2: category = st.selectbox("Update", ["Paint/Walls", "Flooring", "Cabinets", "Lighting", "Full Remodel"])

desc = st.text_area("Details:", placeholder="e.g. Change the white walls to a moody charcoal black.")
uploaded_file = st.file_uploader("Upload Site Photo", type=['jpg', 'png', 'jpeg'])

if uploaded_file and desc:
    input_image = Image.open(uploaded_file)
    
    if st.button("✨ Generate Proposal"):
        with st.spinner("Analyzing room geometry and generating design..."):
            
            # Parallel-ish execution: Generate Image AND Text Summary
            result_image, error = generate_renovation(input_image, room_type, category, desc)
            
            if error:
                st.error(error)
            elif result_image:
                # Generate the smart text summary
                smart_summary = generate_smart_summary(room_type, category, desc)
                
                st.session_state.before = input_image
                st.session_state.after = result_image
                st.session_state.summary = smart_summary
                st.session_state.done = True

st.markdown('</div>', unsafe_allow_html=True)

if st.session_state.get('done'):
    st.markdown('<div class="room-card">', unsafe_allow_html=True)
    st.write("### Design Result")
    
    c1, c2 = st.columns(2)
    with c1: st.image(st.session_state.before, caption="Original", use_container_width=True)
    with c2: st.image(st.session_state.after, caption="Proposed Design", use_container_width=True)
    
    st.info(f"**Project Summary:** {st.session_state.summary}")
    
    pdf_bytes = create_pdf_report(st.session_state.before, st.session_state.after, st.session_state.summary)
    st.download_button("📄 Download PDF Report", pdf_bytes, "proposal.pdf", "application/pdf", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
