import streamlit as st
import os
import json
import base64
import requests
import traceback
import io
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

# Password protection implementation
def get_password():
    """
    Get the password from environment variables or Streamlit secrets
    Returns password or None if not configured
    """
    # First try to load from .env file (local development)
    load_dotenv()
    password = os.getenv("GEN_IMAGE_PASSWORD")
    
    # If not found in .env, try to get from Streamlit secrets (cloud deployment)
    if not password and hasattr(st, "secrets"):
        try:
            password = st.secrets.get("GEN_IMAGE_PASSWORD")
        except KeyError:
            password = None
    
    return password

def password_protection():
    """
    Implement password protection for the Streamlit app
    Returns True if access is granted, False otherwise
    """
    # Get the configured password
    correct_password = get_password()
    
    # If no password is set, allow access
    if not correct_password:
        st.warning("⚠️ No password configured. Set GEN_IMAGE_PASSWORD in .env or Streamlit secrets for security.")
        return True
    
    # Check if authentication has already been completed in this session
    if "password_authenticated" in st.session_state and st.session_state["password_authenticated"]:
        return True
    
    # Display login form
    st.title("🔒 Password Protected")
    st.write("This application requires a password to access.")
    
    # Create password input and submit button
    with st.form("password_form"):
        password = st.text_input("Enter password", type="password")
        submitted = st.form_submit_button("Login")
    
    # Verify password when form is submitted
    if submitted:
        if password == correct_password:
            st.session_state["password_authenticated"] = True
            # Rerun the app to remove the password prompt
            st.rerun()
        else:
            st.error("❌ Incorrect password. Please try again.")
            return False
    
    # If we get here, authentication hasn't happened yet
    return False

# Call the password protection function and only show the rest of the app if it returns True
if not password_protection():
    # If password check fails, stop the app here
    st.stop()

# Set page config
st.set_page_config(
    page_title="AI Image Generator",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'user_prompt' not in st.session_state:
    st.session_state['user_prompt'] = ""

if 'current_image' not in st.session_state:
    st.session_state['current_image'] = {}

if 'has_generated_image' not in st.session_state:
    st.session_state['has_generated_image'] = False

# Helper function for safely displaying images
def safe_display_image(image_data, caption=None, use_container_width=True):
    """
    Safely display an image with error handling
    
    Args:
        image_data: Image as bytes or file path
        caption: Optional caption for the image
        use_container_width: Whether to use full container width
    """
    try:
        # First try direct display if image_data is bytes
        if isinstance(image_data, bytes):
            st.image(image_data, caption=caption, use_container_width=use_container_width)
            return True
            
        # If it's a dict with 'bytes' key (your session state format)
        elif isinstance(image_data, dict) and 'bytes' in image_data:
            if isinstance(image_data['bytes'], bytes):
                st.image(image_data['bytes'], caption=caption, use_container_width=use_container_width)
                return True
            else:
                st.error("Invalid image data format in dictionary")
                return False
                
        else:
            st.error(f"Unsupported image data type: {type(image_data)}")
            return False
            
    except Exception as e:
        st.error(f"Error displaying image: {str(e)}")
        if st.session_state.get('debug_mode', False):
            st.error(f"Image data type: {type(image_data)}")
            if isinstance(image_data, bytes):
                st.error(f"Image data length: {len(image_data)} bytes")
        return False

# Load API key from .env and Streamlit secrets as fallback
@st.cache_resource
def get_api_client():
    """
    Get OpenAI API client with proper error handling for both local and cloud deployment
    """
    # First try to load from .env file (local development)
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    
    # If not found in .env, try to get from Streamlit secrets (cloud deployment)
    if not api_key and hasattr(st, "secrets"):
        try:
            api_key = st.secrets.get("OPENAI_API_KEY")
        except Exception as e:
            st.error(f"Error accessing Streamlit secrets: {str(e)}")
            api_key = None
    
    if not api_key:
        st.error("Missing OPENAI_API_KEY in .env file or Streamlit secrets")
        st.info("Please add your OpenAI API key to access image generation features")
        st.stop()
    
    try:
        # Initialize with minimal parameters to avoid version conflicts
        client = OpenAI(api_key=api_key)
        
        # Test connection with a simple operation
        # We're using a try/except here because we don't want to 
        # make an actual API call if we can avoid it
        try:
            # Just access an attribute to make sure the client is working
            _ = client.api_key
            return client
        except Exception as e:
            st.error(f"Error verifying OpenAI client: {str(e)}")
            st.stop()
            
    except TypeError as e:
        # Special handling for the proxies error
        if "unexpected keyword argument 'proxies'" in str(e):
            st.error("OpenAI client version compatibility issue detected.")
            st.info("Try updating your requirements.txt to: 'openai>=1.0.0,<2.0.0'")
            st.stop()
        else:
            st.error(f"Error initializing OpenAI client: {str(e)}")
            st.info("Please check your API key and try again")
            st.stop()
    except Exception as e:
        st.error(f"Error initializing OpenAI client: {str(e)}")
        st.info("Please check your API key and try again")
        st.stop()

# Initialize the OpenAI client
client = get_api_client()

# Load theme packs from JSON
@st.cache_data
def load_theme_packs():
    default_themes = {
        "Holiday Season": [
            "Christmas market scene with snow falling, warm lights, and festive decorations",
            "New Year's Eve celebration with fireworks and champagne glasses"
        ],
        "Product Showcase": [
            "Professional product photography of a luxury item on a minimalist background",
            "Lifestyle product shot in natural setting with soft lighting"
        ],
        "Corporate & Business": [
            "Modern office workspace with clean design and subtle technology elements",
            "Professional business meeting with diverse team collaborating"
        ]
    }
    
    try:
        # First check if themes are in Streamlit secrets (for cloud deployment)
        if hasattr(st, "secrets") and "themes" in st.secrets:
            try:
                return json.loads(st.secrets["themes"])
            except Exception as e:
                if st.session_state.get('debug_mode', False):
                    st.error(f"Error parsing themes from secrets: {str(e)}")
        
        # Then try loading from local file (for local development)
        theme_packs_path = Path("themes.json")
        if theme_packs_path.exists():
            with open(theme_packs_path, "r") as f:
                return json.load(f)
    except Exception as e:
        if st.session_state.get('debug_mode', False):
            st.error(f"Error loading themes: {str(e)}")
    
    # Return default themes if all else fails
    return default_themes

# Load style guides from JSON
@st.cache_data
def load_style_guides():
    default_styles = {
        "No Style (User Prompt Only)": "",
        "70s Retro Cinematic": "Warm vintage feel with earth tones, film grain, and nostalgic lighting reminiscent of 1970s cinema",
        "Bright Studio Pop": "High-key studio lighting with vibrant colors, playful composition, and clean backgrounds"
    }
    
    try:
        # First check if styles are in Streamlit secrets (for cloud deployment)
        if hasattr(st, "secrets") and "style_guides" in st.secrets:
            try:
                styles = json.loads(st.secrets["style_guides"])
                # Add a "no style" option if not present
                if "No Style (User Prompt Only)" not in styles:
                    styles["No Style (User Prompt Only)"] = ""
                return styles
            except Exception as e:
                if st.session_state.get('debug_mode', False):
                    st.error(f"Error parsing style guides from secrets: {str(e)}")
        
        # Then try loading from local file (for local development)
        style_guide_path = Path("style_guides.json")
        if style_guide_path.exists():
            with open(style_guide_path, "r") as f:
                style_guides = json.load(f)
                # Add a "no style" option
                if "No Style (User Prompt Only)" not in style_guides:
                    style_guides["No Style (User Prompt Only)"] = ""
                return style_guides
    except Exception as e:
        if st.session_state.get('debug_mode', False):
            st.error(f"Error loading style guides: {str(e)}")
    
    # Return default styles if all else fails
    return default_styles

def build_prompt(user_prompt, selected_style, style_guides, style_influence):
    """
    Build a prompt that properly balances user input and style guide
    """
    if selected_style == "No Style (User Prompt Only)" or style_influence == 0:
        # Just use the user's prompt directly
        return user_prompt
    
    # Get the style guide text
    style_guide = style_guides[selected_style]
    
    # Adjust based on influence level
    if style_influence <= 30:
        # Very low influence: User prompt dominates, style is just a light suggestion
        return f"{user_prompt} (Optional visual reference: {style_guide})"
    elif style_influence <= 50:
        # Low influence: User prompt is primary with style as secondary reference
        return f"{user_prompt} Incorporate a subtle hint of this style: {style_guide}"
    elif style_influence <= 70:
        # Medium influence: Balanced approach
        return f"Create an image showing: {user_prompt}. Use this visual style as a reference: {style_guide}"
    elif style_influence <= 90:
        # High influence: Style guides the look but content is from user prompt
        return f"Using the visual aesthetics of this style: {style_guide}. Create an image that shows: {user_prompt}"
    else:
        # Very high influence: Style dominates but includes user prompt content 
        return f"Create an image in this exact style: {style_guide}. The image should include: {user_prompt}"

# Function to enhance/boost the user's prompt with GPT-4o
def boost_prompt(original_prompt):
    """Enhance the user's prompt with more creative details using GPT-4o"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # Using GPT-4o for better results
            messages=[
                {"role": "system", "content": "You are a creative prompt enhancer for image generation. Your job is to take a basic image prompt and enhance it with more descriptive language, interesting details, and artistic elements. Keep the original intent but make it more vivid."},
                {"role": "user", "content": f"Enhance this image prompt for AI image generation, adding rich details but preserving the core idea (keep it under 200 words): '{original_prompt}'"}
            ],
            max_tokens=300
        )
        enhanced_prompt = response.choices[0].message.content.strip()
        return enhanced_prompt
    except Exception as e:
        if st.session_state.get('debug_mode', False):
            st.error(f"Error boosting prompt with GPT-4o: {str(e)}")
        return original_prompt  # Return original if there's an error
    
# Function to add watermark/logo to images
def add_watermark(image_bytes, logo_bytes=None):
    """Add a watermark/logo to the bottom right of an image"""
    try:
        # Open the generated image
        img = Image.open(io.BytesIO(image_bytes))
        
        # If image is not RGBA, convert it
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Check if we have a logo to add
        if logo_bytes is None:
            # Create a simple text-based watermark instead
            draw = ImageDraw.Draw(img)
            try:
                # Try to use a font if available
                font = ImageFont.truetype("arial.ttf", 20)
                draw.text((img.width - 150, img.height - 30), "AI Generated", fill=(255, 255, 255, 180), font=font)
            except:
                # Fall back to default font
                draw.text((img.width - 150, img.height - 30), "AI Generated", fill=(255, 255, 255, 180))
        else:
            # Open and resize the logo
            logo = Image.open(io.BytesIO(logo_bytes))
            logo_width = img.width // 8  # Adjust size as needed
            logo_height = int((logo.height / logo.width) * logo_width)
            logo = logo.resize((logo_width, logo_height))
            
            # If logo has transparency, preserve it
            if logo.mode == 'RGBA':
                # Position at bottom right
                position = (img.width - logo_width - 20, img.height - logo_height - 20)
                # Create a new composite image
                new_img = Image.new('RGBA', img.size, (0, 0, 0, 0))
                new_img.paste(img, (0, 0))
                new_img.paste(logo, position, logo)
                img = new_img
            else:
                # Convert logo to RGBA for transparency
                logo = logo.convert('RGBA')
                # Position at bottom right
                position = (img.width - logo_width - 20, img.height - logo_height - 20)
                # Create a new composite image
                new_img = Image.new('RGBA', img.size, (0, 0, 0, 0))
                new_img.paste(img, (0, 0))
                new_img.paste(logo, position, logo)
                img = new_img
        
        # Convert back to bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception as e:
        if st.session_state.get('debug_mode', False):
            st.error(f"Error adding watermark: {str(e)}")
        return image_bytes  # Return original if there's an error

# Function to generate image handling both base64 and URL
def generate_image(prompt, model="gpt-image-1", size="1024x1024", add_logo=False, logo_bytes=None):
    """
    Generate an image using OpenAI API, handles both base64 and URL formats.
    Returns image_bytes or None if failed.
    """
    try:
        # For debugging
        if st.session_state.get('debug_mode', False):
            st.info(f"Generating image with model: {model}, size: {size}")
            st.info(f"Prompt: {prompt[:100]}...")
        
        # Generate the image
        response = client.images.generate(
            model=model,
            prompt=prompt,
            n=1,
            size=size
        )
        
        # Check for base64 data first (for gpt-image-1)
        if hasattr(response, 'data') and response.data and hasattr(response.data[0], 'b64_json') and response.data[0].b64_json:
            if st.session_state.get('debug_mode', False):
                st.info("Using base64 encoded image data")
            
            # Decode the base64 data
            image_bytes = base64.b64decode(response.data[0].b64_json)
            
            # Apply watermark if requested
            if add_logo:
                image_bytes = add_watermark(image_bytes, logo_bytes)
                
            return image_bytes
        
        # Fall back to URL (for dall-e-3)
        elif hasattr(response, 'data') and response.data and hasattr(response.data[0], 'url') and response.data[0].url:
            if st.session_state.get('debug_mode', False):
                st.info(f"Using URL: {response.data[0].url}")
            
            # Download the image
            image_response = requests.get(response.data[0].url)
            
            if image_response.status_code == 200:
                image_bytes = image_response.content
                
                # Apply watermark if requested
                if add_logo:
                    image_bytes = add_watermark(image_bytes, logo_bytes)
                
                return image_bytes
            else:
                if st.session_state.get('debug_mode', False):
                    st.error(f"Failed to download image: HTTP {image_response.status_code}")
                return None
        
        else:
            if st.session_state.get('debug_mode', False):
                st.error("No image data found in response")
                st.json(str(response))
            return None
            
    except Exception as e:
        if st.session_state.get('debug_mode', False):
            st.error(f"Error in generate_image: {str(e)}")
            st.code(traceback.format_exc())
        return None

# Function to handle image generation without losing state
def generate_and_save_image(prompt, model, size, add_logo, logo_bytes=None):
    """Generate an image and save it to session state to maintain across interactions"""
    with st.spinner("Generating your image... This may take up to 20-30 seconds."):
        try:
            # Generate the image
            image_bytes = generate_image(
                prompt=prompt,
                model=model,
                size=size,
                add_logo=add_logo,
                logo_bytes=logo_bytes
            )
            
            if image_bytes:
                # Verify the image bytes are valid by attempting to open with PIL
                try:
                    test_img = Image.open(io.BytesIO(image_bytes))
                    # If we get here, the image is valid
                    test_img.close()
                except Exception as e:
                    if st.session_state.get('debug_mode', False):
                        st.error(f"Generated image data is not valid: {str(e)}")
                    return False
                
                # Store in session state - make a new copy of the bytes to ensure it's isolated
                st.session_state['current_image'] = {
                    'bytes': bytes(image_bytes),
                    'prompt': prompt
                }
                st.session_state['has_generated_image'] = True
                return True
            else:
                return False
        except Exception as e:
            if st.session_state.get('debug_mode', False):
                st.error(f"Error in generate_image: {str(e)}")
                st.code(traceback.format_exc())
            return False
        
# Load data from files
theme_packs = load_theme_packs()
style_guides = load_style_guides()

# Sidebar for configuration
with st.sidebar:
    st.title("Configuration")
    
    # API Model Selection
    st.subheader("Model Selection")
    model_options = {
        "DALL-E 3": "dall-e-3",  # Better quality, URL-based
        "GPT-Image-1": "gpt-image-1"  # Base64-based
    }
    selected_model = st.selectbox("Choose Model", list(model_options.keys()), index=1)  # Default to GPT-Image-1
    model_id = model_options[selected_model]
    
    # Image Size
    st.subheader("Image Properties")
    image_size = st.selectbox(
        "Image Size", 
        ["1024x1024", "1024x1792", "1792x1024"],
        help="Square, Portrait, or Landscape"
    )
    
    # Logo/Watermark option
    st.subheader("Branding")
    add_logo = st.checkbox("Add Watermark to Images", value=False, 
                         help="Add a watermark to generated images")
    
    # Logo upload option (only shown if watermark is enabled)
    logo_bytes = None
    if add_logo:
        uploaded_logo = st.file_uploader("Upload Custom Logo (PNG with transparency recommended)", 
                                       type=["png", "jpg", "jpeg"], 
                                       help="Transparent PNG works best")
        if uploaded_logo:
            logo_bytes = uploaded_logo.getvalue()
            st.success("Logo uploaded successfully!")
            
            # Show preview of the logo
            st.image(logo_bytes, caption="Logo Preview", width=100)
        else:
            st.info("No logo uploaded. A text watermark will be used.")
    
    # Debug Mode
    st.session_state['debug_mode'] = st.checkbox("Debug Mode", value=False, 
                                              help="Show detailed information for troubleshooting")
    
    # Enhanced debug mode
    if st.session_state.get('debug_mode', False):
        st.sidebar.subheader("Debug Information")
        
        # Show streamlit version
        import streamlit as st_version
        st.sidebar.info(f"Streamlit version: {st_version.__version__}")
        
        # Show OpenAI package version
        try:
            import openai as openai_version
            st.sidebar.info(f"OpenAI package version: {openai_version.__version__}")
        except (ImportError, AttributeError):
            st.sidebar.warning("Could not determine OpenAI package version")
        
        # Display current session state keys
        st.sidebar.subheader("Session State Keys")
        st.sidebar.code(str(list(st.session_state.keys())))
        
        # Check Streamlit secrets
        if hasattr(st, "secrets"):
            st.sidebar.success("✅ Streamlit secrets are available")
            # Show only that secrets exist, not their values
            st.sidebar.info(f"Secret keys found: {list(st.secrets.keys())}")
        else:
            st.sidebar.error("❌ No Streamlit secrets found")
    
    # Style Guide Descriptions
    with st.expander("Style Guide Descriptions", expanded=False):
        st.markdown("""
        - **70s Retro Cinematic**: Warm, vintage feel with earth tones and nostalgic lighting
        - **Vintage Editorial Amber**: 70s editorial style with burnt orange and warm directional lighting
        - **Bright Studio Pop**: High-key studio lighting with vibrant colors and playful composition
        - **Flash Cinematic Editorial**: Harsh flash photography with sculptural shadows and surreal feel
        - **Vibrant Pop Art**: High-contrast, glossy finish with vivid primary colors and exaggerated composition
        - **Moody 70s Still Life**: Dramatic shadows and muted tones with retro styling
        - **High-Contrast Action B&W**: Black and white action photography with motion blur and gritty textures
        - **Futuristic Sports Editorial**: High-contrast sports imagery with blue rim lighting and futuristic feel
        """)
    
    # How to Use Guide
    with st.expander("How to Use This App", expanded=False):
        st.markdown("""
        1. Select a model in the sidebar (GPT-Image-1 or DALL-E 3)
        2. Choose a style guide or theme pack template
        3. Enter your custom image prompt with specific details
        4. Use the "Boost Idea" button to enhance your prompt with GPT-4o
        5. Adjust the style influence slider to control how much the style affects your result
        6. Optionally add a watermark for branded content
        7. Click "Generate Image"
        8. Download your generated image

        **Tip**: If one model doesn't work, try the other one. GPT-Image-1 and DALL-E 3 have different capabilities and may respond differently to the same prompt.
        """)
    
    # About section
    st.markdown("---")
    st.markdown("### About")
    st.markdown("This app uses OpenAI's image generation models to create images based on text prompts and style guides.")
    
    
# Main content area
st.title("🎨 AI Image Generator")
st.write("Generate images using your prompts with optional style guides and themes")

# Tabs for different input methods
tab1, tab2 = st.tabs(["Custom Prompt", "Theme Packs"])

with tab1:
    # Style visualization 
    st.subheader("Choose a Style Guide")
    
    # Create emoji/icon indicators for each style to give a visual hint
    style_icons = {
        "70s Retro Cinematic": "🎬 🕰️",
        "Vintage Editorial Amber": "📸 🧡",
        "Bright Studio Pop": "💫 🎨",
        "Flash Cinematic Editorial": "📷 ⚡",
        "Vibrant Pop Art": "🎭 🌈",
        "Moody 70s Still Life": "🥀 🏺",
        "High-Contrast Action B&W": "⚫ ⚪",
        "Futuristic Sports Editorial": "🏎️ 🔵"
    }
    
    # Get all style names and remove "No Style"
    style_names = list(style_guides.keys())
    if "No Style (User Prompt Only)" in style_names:
        style_names.remove("No Style (User Prompt Only)")
    
    # First option is always "No Style"
    selected_style = st.radio(
        "Select a style guide or 'No Style' to use only your prompt:",
        ["No Style (User Prompt Only)"] + style_names,
        format_func=lambda x: x if x == "No Style (User Prompt Only)" else f"{x} {style_icons.get(x, '')}"
    )
    
    # User prompt input with boost button
    st.subheader("Your Custom Image Prompt")
    
    # Create columns for prompt input and boost button
    prompt_col, boost_col = st.columns([5, 1])
    
    with prompt_col:
        # Use the stored prompt from session state if available
        user_prompt = st.text_area(
            "Describe what you want in the image:", 
            value=st.session_state['user_prompt'],
            height=100, 
            placeholder="Be specific about what you want to see in the image..."
        )
        # Update session state with current prompt
        st.session_state['user_prompt'] = user_prompt
    
    with boost_col:
        # Add vertical space to align with the text area
        st.write("")
        st.write("")
        boost_button = st.button("✨ Boost Idea", use_container_width=True)
    
    # Handle boost button
    if boost_button and user_prompt:
        with st.spinner("Enhancing your prompt with GPT-4o..."):
            boosted_prompt = boost_prompt(user_prompt)
            # Display the boosted prompt
            st.success("Prompt enhanced with GPT-4o!")
            st.subheader("Enhanced Prompt:")
            user_prompt = st.text_area("You can edit this further if you like:", value=boosted_prompt, height=150)
            # Update session state with the boosted prompt
            st.session_state['user_prompt'] = user_prompt
    
    # Style influence slider (only show if a style is selected)
    if selected_style != "No Style (User Prompt Only)":
        style_influence = st.slider(
            "Style Guide Influence", 
            min_value=0, 
            max_value=100, 
            value=30,
            help="0% = ignore style guide, 100% = prioritize style guide over your prompt"
        )
    else:
        style_influence = 0

with tab2:
    st.subheader("Theme Packs for Marketing Campaigns")
    st.write("Choose from pre-made prompt templates perfect for different marketing needs")
    
    # Theme pack selection
    selected_theme = st.selectbox("Select a Theme Pack", list(theme_packs.keys()))
    
    # Display prompts from the selected theme
    st.write(f"**{selected_theme} Prompts:**")
    
    # Create a grid layout for theme prompts
    theme_cols = st.columns(2)
    
    # Display each prompt with a "Use This" button
    for i, prompt in enumerate(theme_packs[selected_theme]):
        col_idx = i % 2
        with theme_cols[col_idx]:
            st.write(f"{i+1}. {prompt}")
            if st.button(f"Use Prompt #{i+1}", key=f"theme_prompt_{i}"):
                # Store the selected prompt in session state and rerun
                st.session_state['user_prompt'] = prompt
                st.rerun()
                
# Generate button (outside tabs to be always visible)
if st.button("Generate Image", type="primary", use_container_width=True):
    if not user_prompt:
        st.error("Please enter a prompt first.")
    else:
        # Build the prompt based on style influence
        full_prompt = build_prompt(user_prompt, selected_style, style_guides, style_influence)
        
        # For debugging - show the full prompt being sent
        if st.session_state.get('debug_mode', False):
            with st.expander("View full prompt sent to API"):
                st.text(full_prompt)
        
        # Generate the image and save to session state
        success = generate_and_save_image(
            prompt=full_prompt,
            model=model_id,
            size=image_size,
            add_logo=add_logo,
            logo_bytes=logo_bytes
        )
        
        if not success:
            st.error("Failed to generate image. Check debug mode for details.")
            
            # Suggest trying the other model
            other_model = "DALL-E 3" if selected_model == "GPT-Image-1" else "GPT-Image-1"
            st.warning(f"Tip: Try using {other_model} model instead - select it in the sidebar.")

# Display image if we have a generated image in session state
if st.session_state.get('has_generated_image') and 'current_image' in st.session_state:
    try:
        image_bytes = st.session_state['current_image'].get('bytes')
        prompt = st.session_state['current_image'].get('prompt', 'Generated image')
        
        if image_bytes and isinstance(image_bytes, bytes):
            st.subheader("Generated Image")
            
            # Use the safe display function instead of directly using st.image
            safe_display_image(image_bytes, caption=prompt)
            
            # Generate a filename based on the prompt
            prompt_slug = "".join(c if c.isalnum() else "_" for c in prompt[:30].lower())
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            download_filename = f"{prompt_slug}_{timestamp}.png"
            
            # Download button for the image
            st.download_button(
                label="Download Image",
                data=image_bytes,
                file_name=download_filename,
                mime="image/png",
                use_container_width=True
            )
            
            # Add a note about storage
            st.info("⚠️ Note: This image is temporarily stored in your browser session. Please download it if you want to keep it permanently.")
            
            # Show the prompt used
            with st.expander("View prompt used for this image"):
                st.write(prompt)
        else:
            st.warning("Image data is not available or in an invalid format.")
            if st.session_state.get('debug_mode', False):
                st.write(f"Image data type: {type(image_bytes) if image_bytes else 'None'}")
                if isinstance(st.session_state['current_image'], dict):
                    st.write(f"Keys in current_image: {list(st.session_state['current_image'].keys())}")
    except Exception as e:
        st.error(f"Error displaying generated image: {str(e)}")
        if st.session_state.get('debug_mode', False):
            st.code(traceback.format_exc())
