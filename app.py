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
    page_icon="🚪", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 🔑 API KEY
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    st.error("⚠️ API Key missing. Please check your system variables.")
    st.stop()

# Initialize Client
client = genai.Client(api_key=api_key)
MODEL_ID = "gemini-2.0-pro-exp-02-05" # Updated to latest stable experimental if 3-preview is fussy

# ==========================================
# 2. UI STYLING
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    :root {
        --primary: #000000;
        --text: #1a1a1a;
        --bg: #ffffff;
    }

    .stApp {
        background-color: var(--bg);
        font-family: 'Inter', sans-serif;
        color: var(--text);
    }
    
    .room-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }

    /* Clean Header */
    .header-text h1 {
        font-weight: 700;
        letter-spacing: -0.02em;
        margin-bottom: 0;
    }
    
    /* Buttons */
    div.stButton > button {
        background-color: #111 !important;
        color: white !important;
        border-radius: 8px !important;
        height: 50px !important;
        font-weight: 600 !important;
        border: none !important;
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. LOGIC: GENERATION
# ==========================================

def generate_renovation(input_image, room_type, category, user_description):
    """
    Calls the AI Model directly with the list [image, text].
    """
    
    prompt_text = f"""
    Act as a professional architectural visualizer.
    Task: Renovate this {room_type}.
    Category: {category}
    Details: {user_description}
    
    STRICT CONSTRAINTS:
    1. Maintain exact camera angle and room geometry.
    2. Do not hallucinate new windows or doors.
    3. Output a photorealistic image.
    """
    
    try:
        # FIX: We pass the list directly. No 'types.Part' wrapper needed.
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[input_image, prompt_text],
            config=types.GenerateContentConfig(
                temperature=0.7
            )
        )
        
        # Handle the Image Response
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    img_data = base64.b64decode(part.inline_data.data)
                    return Image.open(io.BytesIO(img_data)), None
        
        return None, "The system processed the request but returned no image."

    except Exception as e:
        return None, f"Visualization Error: {str(e)}"

def create_pdf_report(before_img, after_img, summary_text):
    """ Generates PDF Report """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('Title', parent=styles['Heading1'], color=HexColor('#111111'), alignment=1)
    story.append(Paragraph("Renovation Report", title_style))
    story.append(Spacer(1, 12))

    story.append(Paragraph(f"<b>Specs:</b> {summary_text}", styles["Normal"]))
    story.append(Spacer(1, 24))

    def prep(img):
        b = io.BytesIO()
        img.save(b, format='JPEG')
        b.seek(0)
        return RLImage(b, width=250, height=200)

    data = [[prep(before_img), prep(after_img)], [Paragraph("Before", styles["Normal"]), Paragraph("Proposed Design", styles["Normal"])]]
    t = Table(data, colWidths=[260, 260])
    t.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
    story.append(t)

    doc.build(story)
    buffer.seek(0)
    return buffer

# ==========================================
# 4. INTERFACE
# ==========================================
st.markdown("""
<div class="header-text" style="text-align: center; margin-bottom: 30px;">
    <h1>🚪 Room Visualizer</h1>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="room-card">', unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    room_type = st.selectbox("Room", ["Kitchen", "Bathroom", "Living Room", "Patio", "Bedroom"])
with col2:
    category = st.selectbox("Update", ["Flooring", "Paint", "Cabinets", "Full Remodel"])

desc = st.text_area("Details:", placeholder="e.g. White oak floors, sage green walls")
uploaded_file = st.file_uploader("Site Photo", type=['jpg', 'png', 'jpeg'])

if uploaded_file and desc:
    input_image = Image.open(uploaded_file)
    
    if st.button("✨ Visualize"):
        with st.spinner("Analyzing structure and generating proposal..."):
            
            result_image, error = generate_renovation(input_image, room_type, category, desc)
            
            if error:
                st.error(error)
            elif result_image:
                st.session_state.before = input_image
                st.session_state.after = result_image
                st.session_state.summary = f"{room_type} | {category} | {desc}"
                st.session_state.done = True

st.markdown('</div>', unsafe_allow_html=True)

if st.session_state.get('done'):
    st.markdown('<div class="room-card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: st.image(st.session_state.before, caption="Original", use_container_width=True)
    with c2: st.image(st.session_state.after, caption="Proposed Design", use_container_width=True)
    
    pdf_bytes = create_pdf_report(st.session_state.before, st.session_state.after, st.session_state.summary)
    st.download_button("Download Report", pdf_bytes, "report.pdf", "application/pdf")
    st.markdown('</div>', unsafe_allow_html=True)
