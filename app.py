import streamlit as st
import google.generativeai as genai
from PIL import Image
import os

# ==========================================
# 1. SETUP & CONFIG
# ==========================================
st.set_page_config(
    page_title="Nano Banana Architect", 
    page_icon="🍌", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 🔑 API KEY & MODEL SETUP
# Get key from: https://aistudio.google.com/
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    try:
        api_key = st.secrets["GOOGLE_API_KEY"]
    except:
        st.error("⚠️ API Key missing. Please set GOOGLE_API_KEY in secrets.")
        st.stop()

genai.configure(api_key=api_key)

# 🚨 CRITICAL: This must match your model name exactly
# If 'gemini-2.5-flash-image' fails, try 'gemini-2.0-flash-exp'
MODEL_ID = "gemini-2.0-flash-exp" 

# ==========================================
# 2. UI STYLING (The "Un-Streamlit" Look)
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap');
    
    :root {
        --primary: #FFD700; /* Banana Yellow */
        --text: #1a1a1a;
        --bg: #fafafa;
    }

    .stApp {
        background-color: var(--bg);
        font-family: 'Space Grotesk', sans-serif;
        color: var(--text);
    }

    /* Clean up the UI */
    #MainMenu, header, footer {visibility: hidden;}
    .block-container {
        padding-top: 2rem !important;
        max-width: 600px !important;
        margin: 0 auto;
    }

    /* Custom Card */
    .banana-card {
        background: white;
        border: 2px solid #f0f0f0;
        border-radius: 24px;
        padding: 24px;
        box-shadow: 0 10px 30px -10px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }

    /* Header */
    .header-text h1 {
        font-weight: 700;
        letter-spacing: -0.05em;
        margin: 0;
    }
    .header-text p {
        color: #666;
        font-size: 0.9rem;
        margin-top: 5px;
    }
    
    /* Buttons */
    div.stButton > button {
        background-color: #111 !important;
        color: white !important;
        border-radius: 14px !important;
        height: 55px !important;
        font-weight: 600 !important;
        border: none !important;
        width: 100%;
        transition: transform 0.2s;
    }
    div.stButton > button:hover {
        transform: scale(1.02);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. LOGIC: NATIVE IMAGE-TO-IMAGE
# ==========================================

def visualize_with_banana(input_image, trade_prompt):
    """
    Uses the native multimodal capabilities of Gemini 2.5 Flash Image.
    We pass the image + text prompt, and ask for an image response.
    """
    try:
        model = genai.GenerativeModel(MODEL_ID)
        
        # The prompt is engineered to force structural accuracy
        # We tell it to act as a 'reskinner' not a 'generator'
        sys_prompt = f"""
        Act as an architectural visualizer. 
        Task: Renovate the room in the attached image to be: {trade_prompt}.
        
        CRITICAL ACCURACY RULES:
        1. You must output an IMAGE.
        2. Do NOT move any walls, windows, doors, or ceiling beams.
        3. Keep the exact camera angle and perspective.
        4. Only change the materials (flooring, paint, cabinets) and furniture style.
        5. If there is plumbing (sinks/toilets), keep them in the exact same location.
        """
        
        # Call the model with the image and the prompt
        response = model.generate_content([sys_prompt, input_image])
        
        # Check if we got an image back (Gemini returns images as 'parts')
        # Note: The response structure for images in Gemini varies by version.
        # This handles the standard 'multimodal' return.
        if response.parts:
            return response.parts[0].image, None
        else:
            return None, "The model replied with text instead of an image. Try refining the prompt."

    except Exception as e:
        return None, f"Banana Error: {str(e)}"

# ==========================================
# 4. APP INTERFACE
# ==========================================

st.markdown("""
<div class="header-text" style="text-align: center; margin-bottom: 30px;">
    <h1>🍌 Nano Visualizer</h1>
    <p>Using Experimental Model: <code>{}</code></p>
</div>
""".format(MODEL_ID), unsafe_allow_html=True)

# --- MAIN CARD ---
st.markdown('<div class="banana-card">', unsafe_allow_html=True)

# Trade Selector
trade = st.selectbox(
    "What are we installing?",
    ["Paver Patio", "Modern Driveway", "Luxury Pool", "Hardwood Floors", "Modern Kitchen", "Marble Bathroom"]
)

# Photo Upload
uploaded_file = st.file_uploader("Upload Site Photo", type=['jpg', 'png', 'jpeg'])

if uploaded_file:
    # Display Input
    input_image = Image.open(uploaded_file)
    st.image(input_image, caption="Original Site", use_container_width=True)
    
    st.markdown("---")
    
    # Generate Button
    if st.button("✨ Visualize Renovation"):
        with st.spinner("Processing with Gemini..."):
            
            # Map friendly names to detailed prompts
            prompts = {
                "Paver Patio": "A high-end backyard renovation with stone paver patio, fire pit, and professional landscaping.",
                "Modern Driveway": "A modern concrete paver driveway with clean lines and curb appeal.",
                "Luxury Pool": "A luxury inground pool with blue water and stone coping.",
                "Hardwood Floors": "Interior renovation with wide-plank oak hardwood floors.",
                "Modern Kitchen": "Modern kitchen with white shaker cabinets, quartz countertops, and gold hardware.",
                "Marble Bathroom": "Luxury spa bathroom with white marble tile and frameless glass shower."
            }
            
            # Run the specific prompt
            result_image, error = visualize_with_banana(input_image, prompts[trade])
            
            if error:
                st.error(error)
            elif result_image:
                st.image(result_image, caption="AI Proposal", use_container_width=True)
                st.success("Visualization Complete")

st.markdown('</div>', unsafe_allow_html=True)