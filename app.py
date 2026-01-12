import streamlit as st
import google.generativeai as genai
import replicate
from PIL import Image
import os
import io
import requests
import base64
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.colors import HexColor  # <--- FIX: Correct import for PDF colors

# ==========================================
# 1. SETUP & CONFIG
# ==========================================
st.set_page_config(
    page_title="Contractor AI Pro", 
    page_icon="🏗️", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 🔑 API KEYS
google_key = os.getenv("GOOGLE_API_KEY")
replicate_key = os.getenv("REPLICATE_API_TOKEN")

if not google_key:
    st.error("⚠️ Google API Key missing. Add GOOGLE_API_KEY to Railway variables.")
    st.stop()
    
if not replicate_key:
    st.error("⚠️ Replicate API Token missing. Add REPLICATE_API_TOKEN to Railway variables.")
    st.stop()

genai.configure(api_key=google_key)

# ==========================================
# 2. UI STYLING
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    :root {
        --primary: #2563eb;
        --text: #1e293b;
        --bg: #f8fafc;
    }

    .stApp {
        background-color: var(--bg);
        font-family: 'Inter', sans-serif;
        color: var(--text);
    }

    #MainMenu, header, footer {visibility: hidden;}
    .block-container {
        padding-top: 2rem !important;
        max-width: 900px !important;
        margin: 0 auto;
    }

    .room-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
    }

    /* Buttons */
    div.stButton > button {
        background-color: var(--primary) !important;
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
# 3. LOGIC: DEPTH-AWARE ENGINE
# ==========================================

def get_architectural_prompt(input_image, room_type, category, user_description):
    """
    STEP 1: Use Google Gemini 1.5 Flash to analyze the image and write a prompt.
    """
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    Act as an architectural photographer. Analyze this image of a {room_type}.
    Your goal is to write a text prompt for an image generator to remodel this room.
    
    The user wants to change: {category}
    Specific Details: {user_description}
    
    CRITICAL: 
    1. Describe the scene geometry briefly (e.g. "A bedroom with window on left").
    2. Then describe the NEW materials/furniture in high detail.
    3. Output ONLY the English text prompt.
    """
    
    try:
        response = model.generate_content([prompt, input_image])
        return response.text
    except Exception as e:
        return f"A photorealistic {room_type} with {user_description}"

def generate_depth_render(prompt, input_image):
    """
    STEP 2: Use Replicate (Flux Depth Dev) to generate the image.
    We use 'control_image' (Depth Map) to keep the original structure strictly locked.
    """
    # Convert PIL image to base64 for Replicate (Required for Depth models)
    buffered = io.BytesIO()
    input_image.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    data_uri = f"data:image/jpeg;base64,{img_str}"
    
    try:
        # We use Flux-Depth-Dev because it understands 3D space
        output = replicate.run(
            "black-forest-labs/flux-depth-dev",
            input={
                "prompt": prompt,
                "control_image": data_uri, # This locks the walls/furniture in place
                "strength": 0.85, 
                "guidance": 10,
                "num_inference_steps": 28, 
                "output_format": "jpg"
            }
        )
        # Replicate returns a list of URLs.
        image_url = output[0]
        
        # Download the result
        res = requests.get(image_url)
        return Image.open(io.BytesIO(res.content)), None
        
    except Exception as e:
        return None, str(e)

def create_pdf_report(before_img, after_img, summary_text):
    """ Generates PDF Report with Fixed Color Logic """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=18)
    styles = getSampleStyleSheet()
    story = []

    # <--- FIX: Use HexColor explicitly here --->
    title_style = ParagraphStyle('MainTitle', parent=styles['Heading1'], alignment=1, spaceAfter=20, fontSize=18, textColor=HexColor('#1e293b'))
    story.append(Paragraph("Renovation Proposal", title_style))

    story.append(Paragraph("Project Summary", styles['Heading2']))
    story.append(Paragraph(summary_text, styles["Normal"]))
    story.append(Spacer(1, 20))

    def prep_image(pil_img):
        img_byte_arr = io.BytesIO()
        pil_img.save(img_byte_arr, format='JPEG')
        img_byte_arr.seek(0)
        aspect = pil_img.height / pil_img.width
        # Cap height to prevent page overflow
        return RLImage(img_byte_arr, width=250, height=250*aspect)

    img_before = prep_image(before_img)
    img_after = prep_image(after_img)

    data = [[img_before, img_after], [Paragraph("Current Site", styles["Normal"]), Paragraph("Proposed Design", styles["Normal"])]]
    t = Table(data, colWidths=[260, 260])
    t.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
    story.append(t)

    doc.build(story)
    buffer.seek(0)
    return buffer

# ==========================================
# 4. APP INTERFACE
# ==========================================

st.markdown("""
<div class="header-text" style="text-align: center; margin-bottom: 30px;">
    <h1>🏗️ Contractor AI Pro</h1>
    <p>Powered by Gemini (Vision) + Flux (Depth Control)</p>
</div>
""", unsafe_allow_html=True)

# --- INPUT CARD ---
st.markdown('<div class="room-card">', unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    room_type = st.selectbox("Room Type", ["Bathroom", "Kitchen", "Living Room", "Patio/Exterior", "Bedroom"])
with col2:
    category = st.selectbox("Upgrade Category", ["Flooring", "Paint/Walls", "Cabinets", "Full Remodel", "Landscaping"])

user_description = st.text_area("Describe the new look:", placeholder="e.g., White marble floors, navy blue cabinets, gold hardware")
uploaded_file = st.file_uploader("Upload Site Photo", type=['jpg', 'png', 'jpeg'])

if uploaded_file and user_description:
    input_image = Image.open(uploaded_file)
    
    if st.button("✨ Generate Proposal"):
        with st.spinner("1/2: Analyzing Site (Gemini)..."):
            # Step 1: Get prompt from Google
            design_prompt = get_architectural_prompt(input_image, room_type, category, user_description)
            
        with st.spinner("2/2: Rendering Proposal (Flux Depth)..."):
            # Step 2: Generate image with Replicate
            result_image, error = generate_depth_render(design_prompt, input_image)
            
            if error:
                st.error(f"Rendering Error: {error}")
            elif result_image:
                st.session_state.before_img = input_image
                st.session_state.after_img = result_image
                st.session_state.summary = f"**Room:** {room_type}<br/>**Plan:** {user_description}"
                st.session_state.pdf_bytes = create_pdf_report(input_image, result_image, st.session_state.summary)
                st.session_state.generation_complete = True

st.markdown('</div>', unsafe_allow_html=True)

# --- RESULTS ---
if st.session_state.get('generation_complete'):
    st.markdown('<div class="room-card">', unsafe_allow_html=True)
    st.write("### Design Proposal")
    
    c1, c2 = st.columns(2)
    with c1:
        st.image(st.session_state.before_img, caption="Before", use_container_width=True)
    with c2:
        st.image(st.session_state.after_img, caption="After", use_container_width=True)
        
    st.markdown("---")
    st.download_button("📄 Download PDF Proposal", data=st.session_state.pdf_bytes, file_name="proposal.pdf", mime='application/pdf', use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
