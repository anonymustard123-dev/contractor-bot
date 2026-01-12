import streamlit as st
import google.generativeai as genai
from PIL import Image
import os
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==========================================
# 1. SETUP & CONFIG
# ==========================================
st.set_page_config(
    page_title="Room Visualizer", 
    page_icon="🚪", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 🔑 API KEY & MODEL SETUP
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    try:
        api_key = st.secrets["GOOGLE_API_KEY"]
    except:
        st.error("⚠️ API Key missing. Please set GOOGLE_API_KEY in secrets.")
        st.stop()

genai.configure(api_key=api_key)

# Using the experimental model for best image-to-image results
MODEL_ID = "gemini-2.0-flash-exp" 

# ==========================================
# 2. UI STYLING
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    :root {
        --primary: #2563eb; /* Modern Blue */
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
        max-width: 800px !important; /* Slightly wider for side-by-side view */
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

    .header-text h1 {
        font-weight: 800;
        color: var(--text);
        margin: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
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
    div.stButton > button:hover {
        opacity: 0.9;
    }
    
    /* Input styling tweaks */
    .stRadio > label { font-weight: 600; }
    .stSelectbox > label { font-weight: 600; }
    .stTextArea > label { font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. LOGIC: GENERATION & PDF
# ==========================================

def visualize_room(input_image, room_type, category, user_description):
    """
    Generates the image using a strict architectural prompt.
    """
    try:
        model = genai.GenerativeModel(MODEL_ID)
        
        # The Stricter Prompt
        sys_prompt = f"""
        Act as a hyper-realistic architectural visualization AI.
        Your task is to remodel the specific elements listed below in the provided room image.

        Construct Prompts:
        Room Type: {room_type}
        Category of Change: {category}
        Specific Details: {user_description}

        CRITICAL STRUCTURAL & SCALE RULES (Do Not Break):
        1.  **Exact Geometry:** You MUST maintain the exact perspective, camera angle, scale, and proportions of the original photo. Do NOT move walls, windows, doors, ceiling heights, or plumbing fixtures (unless specifically asked to replace a fixture in place like a sink).
        2.  **Realism:** The output must be a photorealistic photograph, not a render. Lighting and shadows must realistically interact with the new materials.
        3.  **Targeted Editing:** Only modify the elements described in the "Specific Details". Everything else (e.g., the view outside a window, adjacent rooms, structural beams) must remain identical to the source image.
        4.  **Scale Accuracy:** New items (like tiles, wood planks, or furniture) must be scaled correctly to the room's dimensions. Do not warp textures.
        """
        
        response = model.generate_content([sys_prompt, input_image])
        
        if response.parts:
            return response.parts[0].image, None
        else:
            return None, "The model replied with text instead of an image. Try refining your description."

    except Exception as e:
        return None, f"Generation Error: {str(e)}"

def create_pdf_report(before_img, after_img, summary_text):
    """
    Generates a PDF comparing before and after with a summary.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=18)
    styles = getSampleStyleSheet()
    story = []

    # 1. Title
    styles.add(ParagraphStyle(name='MainTitle', parent=styles['Heading1'], alignment=1, spaceAfter=20, fontSize=18, color=colors.hexof('#1e293b')))
    story.append(Paragraph("Room Remodel Report", styles['MainTitle']))

    # 2. Summary Section
    styles.add(ParagraphStyle(name='SummaryHeader', parent=styles['Heading2'], spaceAfter=10, fontSize=14, color=colors.hexof('#2563eb')))
    story.append(Paragraph("Scope of Work Summary", styles['SummaryHeader']))
    story.append(Paragraph(summary_text, styles["Normal"]))
    story.append(Spacer(1, 20))

    # 3. Image Preparation Helper
    def prep_image(pil_img, width=250):
        img_byte_arr = io.BytesIO()
        pil_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        # Aspect ratio calculations to keep it proportionate
        aspect = pil_img.height / pil_img.width
        return RLImage(img_byte_arr, width=width, height=width*aspect)

    # 4. Side-by-Side Images Table
    img_before = prep_image(before_img)
    img_after = prep_image(after_img)

    data = [
        [Paragraph("Original Site State", styles["Heading3"]), Paragraph("Proposed Design Solution", styles["Heading3"])],
        [img_before, img_after]
    ]
    
    t = Table(data, colWidths=[260, 260])
    t.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,1), (-1,1), 10),
    ]))
    story.append(t)

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

# ==========================================
# 4. APP INTERFACE
# ==========================================

st.markdown("""
<div class="header-text" style="text-align: center; margin-bottom: 30px;">
    <h1>🚪 Room Visualizer</h1>
    <p>Professional AI Remodeling Proposals</p>
</div>
""", unsafe_allow_html=True)

# --- MAIN INPUT CARD ---
st.markdown('<div class="room-card">', unsafe_allow_html=True)

st.write("### 1. Project Details")
col1, col2 = st.columns(2)
with col1:
    room_type = st.selectbox(
        "Which room are we remodeling?",
        ["Bathroom", "Kitchen", "Bedroom", "Living Room", "Exterior/Patio", "Other"]
    )
with col2:
    category = st.selectbox(
        "What is the primary change?",
        ["Flooring", "Walls/Paint/Wallpaper", "Fixtures (Lights/Plumbing)", "Cabinets/Countertops", "Furniture & Decor", "Full Remodel"]
    )

user_description = st.text_area(
    "Describe the specific changes desired:",
    placeholder="Example: Replace existing floor with wide plank light oak wood. Paint walls Sherwin Williams 'Naval' blue. Add a modern brass chandelier.",
    height=100
)

st.write("### 2. Site Photo")
uploaded_file = st.file_uploader("Upload photo of the current space", type=['jpg', 'png', 'jpeg'])

if uploaded_file and user_description:
    input_image = Image.open(uploaded_file)
    
    st.markdown("---")
    
    if st.button("✨ Generate Visual Proposal"):
        with st.spinner("Analyzing geometry and applying changes..."):
            
            # Run generation
            result_image, error = visualize_room(input_image, room_type, category, user_description)
            
            if error:
                st.error(error)
            elif result_image:
                # Save results to session state
                st.session_state.before_img = input_image
                st.session_state.after_img = result_image
                
                # Create summary text for the report
                summary = f"**Room:** {room_type}<br/>**Category:** {category}<br/>**Details:** {user_description}"
                st.session_state.pdf_bytes = create_pdf_report(input_image, result_image, summary)
                st.session_state.generation_complete = True

st.markdown('</div>', unsafe_allow_html=True)

# --- RESULTS AREA ---
if st.session_state.get('generation_complete'):
    st.markdown('<div class="room-card">', unsafe_allow_html=True)
    st.write("### Proposal Results")
    
    # Side-by-side comparison
    res_col1, res_col2 = st.columns(2)
    with res_col1:
        st.image(st.session_state.before_img, caption="Before", use_container_width=True)
    with res_col2:
        st.image(st.session_state.after_img, caption="After (Proposed)", use_container_width=True)
        
    st.markdown("---")
    
    # PDF Download Button
    st.download_button(
        label="📄 Download PDF Report",
        data=st.session_state.pdf_bytes,
        file_name="remodel_proposal.pdf",
        mime='application/pdf',
        use_container_width=True
    )
    st.markdown('</div>', unsafe_allow_html=True)
