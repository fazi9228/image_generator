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
            password = st.secrets["GEN_IMAGE_PASSWORD"]
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

# The rest of your app continues below

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

if 'size_option' not in st.session_state:
    st.session_state['size_option'] = "original"
    
if 'template_option' not in st.session_state:
    st.session_state['template_option'] = "none"

if 'has_generated_image' not in st.session_state:
    st.session_state['has_generated_image'] = False

if 'bulk_download_clicked' not in st.session_state:
    st.session_state['bulk_download_clicked'] = False
    
if 'bulk_download_include_templates' not in st.session_state:
    st.session_state['bulk_download_include_templates'] = True
    
if 'bulk_download_results' not in st.session_state:
    st.session_state['bulk_download_results'] = {}

# Define callback functions
def on_bulk_download_click():
    st.session_state['bulk_download_clicked'] = True

# Load API key from .env and Streamlit secrets as fallback
@st.cache_resource
def get_api_client():
    # First try to load from .env file (local development)
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    
    # If not found in .env, try to get from Streamlit secrets (cloud deployment)
    if not api_key and hasattr(st, "secrets"):
        try:
            api_key = st.secrets["OPENAI_API_KEY"]
        except KeyError:
            api_key = None
    
    if not api_key:
        st.error("Missing OPENAI_API_KEY in .env file or Streamlit secrets")
        st.stop()
    
    return OpenAI(api_key=api_key)

# Initialize the OpenAI client
client = get_api_client()

# Create output directory if it doesn't exist
output_dir = Path("generated_images")
output_dir.mkdir(exist_ok=True, parents=True)

# Create directory for assets
assets_dir = Path("assets")
assets_dir.mkdir(exist_ok=True, parents=True)

# Define default logo path - create a sample logo if not exists
default_logo_path = assets_dir / "logo.png"
if not default_logo_path.exists():
    # Create a simple placeholder logo
    logo = Image.new('RGBA', (200, 100), (255, 255, 255, 0))
    draw = ImageDraw.Draw(logo)
    draw.rectangle([(10, 10), (190, 90)], outline=(0, 0, 0, 255), width=2)
    draw.text((40, 40), "Your Logo", fill=(0, 0, 0, 255))
    logo.save(default_logo_path)

# Load theme packs from JSON file
@st.cache_data
def load_theme_packs():
    theme_packs_path = Path("themes.json")
    try:
        if not theme_packs_path.exists():
            st.warning("Themes file not found. Using default themes.")
            return {
                "Holiday Season": [
                    "Christmas market scene with snow falling, warm lights, and festive decorations",
                    "New Year's Eve celebration with fireworks and champagne glasses"
                ]
            }
        
        with open(theme_packs_path, "r") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading themes: {str(e)}")
        return {"Default Theme": ["Simple prompt example"]}

# Load style guides from JSON file
@st.cache_data
def load_style_guides():
    style_guide_path = Path("style_guides.json")
    try:
        if not style_guide_path.exists():
            st.warning("Style guides file not found. Using default styles.")
            return {
                "No Style (User Prompt Only)": ""
            }
        
        with open(style_guide_path, "r") as f:
            style_guides = json.load(f)
            # Add a "no style" option
            style_guides["No Style (User Prompt Only)"] = ""
            return style_guides
    except Exception as e:
        st.error(f"Error loading style guides: {str(e)}")
        return {"No Style (User Prompt Only)": ""}
    
# Rest of the original app code follows...
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
def add_watermark(image_bytes, logo_path=default_logo_path):
    """Add a watermark/logo to the bottom right of an image"""
    try:
        # Open the generated image
        img = Image.open(io.BytesIO(image_bytes))
        
        # If image is not RGBA, convert it
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Open and resize the logo
        logo = Image.open(logo_path)
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

# Function to resize image for different output formats
def resize_image(image_bytes, output_size, template=None):
    """
    Resize an image to a different size and optionally apply a template
    
    Args:
        image_bytes: The original image as bytes
        output_size: Tuple of (width, height) or a preset name like 'instagram', 'twitter', etc.
        template: Optional template name to apply
        
    Returns:
        Bytes of the resized/templated image
    """
    try:
        # Common social media sizes
        size_presets = {
            "original": None,  # Keep original size
            "instagram_post": (1080, 1080),
            "instagram_story": (1080, 1920),
            "facebook_post": (1200, 630),
            "twitter_post": (1200, 675),
            "linkedin_post": (1200, 627),
            "email_header": (600, 200),
            "website_banner": (1200, 300),
            "square_thumbnail": (500, 500)
        }
        
        # Get the target size
        target_size = size_presets.get(output_size, output_size)
        
        # Open the original image
        img = Image.open(io.BytesIO(image_bytes))
        
        # If no resizing needed, just return the original
        if target_size is None:
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return buffer.getvalue()
        
        # Resize the image while maintaining aspect ratio
        img_aspect = img.width / img.height
        target_aspect = target_size[0] / target_size[1]
        
        if img_aspect > target_aspect:
            # Image is wider than target, fit to height
            new_height = target_size[1]
            new_width = int(new_height * img_aspect)
            resized_img = img.resize((new_width, new_height), Image.LANCZOS)
            
            # Crop to target width
            left = (new_width - target_size[0]) // 2
            right = left + target_size[0]
            cropped_img = resized_img.crop((left, 0, right, new_height))
        else:
            # Image is taller than target, fit to width
            new_width = target_size[0]
            new_height = int(new_width / img_aspect)
            resized_img = img.resize((new_width, new_height), Image.LANCZOS)
            
            # Crop to target height
            top = (new_height - target_size[1]) // 2
            bottom = top + target_size[1]
            cropped_img = resized_img.crop((0, top, new_width, bottom))
        
        # Apply template if specified
        if template:
            cropped_img = apply_template(cropped_img, template, target_size)
        
        # Convert back to bytes
        buffer = io.BytesIO()
        cropped_img.save(buffer, format="PNG")
        return buffer.getvalue()
    
    except Exception as e:
        if st.session_state.get('debug_mode', False):
            st.error(f"Error resizing image: {str(e)}")
        return image_bytes  # Return original if error

# Function to apply a template to an image
def apply_template(img, template_name, size):
    """Apply a template to the resized image"""
    
    width, height = size
    
    # Create a copy of the image to work with
    result = img.copy()
    
    # Templates
    if template_name == "white_border":
        # Add a white border
        border_size = min(width, height) // 20  # Border is 5% of the smallest dimension
        bordered = Image.new('RGBA', (width, height), (255, 255, 255, 255))
        inner_width = width - (2 * border_size)
        inner_height = height - (2 * border_size)
        img_resized = img.resize((inner_width, inner_height), Image.LANCZOS)
        bordered.paste(img_resized, (border_size, border_size))
        result = bordered
    
    elif template_name == "branded_corner":
        # Add a branded corner banner
        draw = ImageDraw.Draw(result)
        corner_size = min(width, height) // 6
        draw.polygon([(0, 0), (corner_size, 0), (0, corner_size)], fill=(41, 128, 185, 200))  # Blue corner
        
        # Add text if possible
        try:
            font_size = max(10, corner_size // 3)
            font = ImageFont.truetype("arial.ttf", font_size)
            draw.text((5, 5), "BRANDED", fill=(255, 255, 255, 255), font=font)
        except:
            # If font not available, use default
            draw.text((5, 5), "BRANDED", fill=(255, 255, 255, 255))
    
    elif template_name == "quote_box":
        # Add a quote box at the bottom
        box_height = height // 4
        draw = ImageDraw.Draw(result)
        draw.rectangle([(0, height - box_height), (width, height)], fill=(0, 0, 0, 180))
        
        # Add sample text
        try:
            font_size = max(10, box_height // 3)
            font = ImageFont.truetype("arial.ttf", font_size)
            draw.text((width//10, height - box_height//1.5), "Your quote here", fill=(255, 255, 255, 255), font=font)
        except:
            # If font not available, use default
            draw.text((width//10, height - box_height//1.5), "Your quote here", fill=(255, 255, 255, 255))
    
    elif template_name == "social_ready":
        # Create a social media ready template with space for text
        # Top area for title, bottom for description
        top_height = height // 6
        bottom_height = height // 4
        
        # Create a new image with areas for text
        template = Image.new('RGBA', (width, height), (255, 255, 255, 0))
        
        # Resize original to fit in the middle
        middle_height = height - top_height - bottom_height
        img_resized = img.resize((width, middle_height), Image.LANCZOS)
        
        # Paste the image in the middle
        template.paste(img_resized, (0, top_height))
        
        # Add semi-transparent overlays for text areas
        draw = ImageDraw.Draw(template)
        draw.rectangle([(0, 0), (width, top_height)], fill=(0, 0, 0, 180))
        draw.rectangle([(0, height - bottom_height), (width, height)], fill=(0, 0, 0, 180))
        
        # Add sample text
        try:
            title_font_size = max(12, top_height // 2)
            desc_font_size = max(10, bottom_height // 4)
            
            title_font = ImageFont.truetype("arial.ttf", title_font_size)
            desc_font = ImageFont.truetype("arial.ttf", desc_font_size)
            
            draw.text((width//20, top_height//3), "YOUR TITLE HERE", fill=(255, 255, 255, 255), font=title_font)
            draw.text((width//20, height - bottom_height//1.5), "Your description text here", fill=(255, 255, 255, 255), font=desc_font)
        except:
            # If font not available, use default
            draw.text((width//20, top_height//3), "YOUR TITLE HERE", fill=(255, 255, 255, 255))
            draw.text((width//20, height - bottom_height//1.5), "Your description text here", fill=(255, 255, 255, 255))
        
        result = template
    
    return result

# Function to generate image handling both base64 and URL
def generate_image(prompt, model="gpt-image-1", size="1024x1024", add_logo=False, logo_path=default_logo_path):
    """
    Generate an image using OpenAI API, handles both base64 and URL formats.
    Returns (image_bytes, file_path) or (None, None) if failed.
    """
    try:
        # For debugging
        if st.session_state.get('debug_mode', False):
            st.info(f"Generating image with model: {model}, size: {size}")
            st.info(f"Prompt: {prompt[:100]}...")
        
        # Create a safe filename from the prompt
        prompt_slug = "".join(c if c.isalnum() else "_" for c in prompt[:30].lower())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prompt_slug}_{timestamp}.png"
        file_path = output_dir / filename
        
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
                image_bytes = add_watermark(image_bytes, logo_path)
            
            # Save to file
            with open(file_path, "wb") as f:
                f.write(image_bytes)
                
            return image_bytes, file_path
        
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
                    image_bytes = add_watermark(image_bytes, logo_path)
                
                # Save to file
                with open(file_path, "wb") as f:
                    f.write(image_bytes)
                
                return image_bytes, file_path
            else:
                if st.session_state.get('debug_mode', False):
                    st.error(f"Failed to download image: HTTP {image_response.status_code}")
                return None, None
        
        else:
            if st.session_state.get('debug_mode', False):
                st.error("No image data found in response")
                st.json(str(response))
            return None, None
            
    except Exception as e:
        if st.session_state.get('debug_mode', False):
            st.error(f"Error in generate_image: {str(e)}")
            st.code(traceback.format_exc())
        return None, None

def create_all_formats(image_bytes, base_filename, include_templates=True):
    """
    Create all format variations of an image and save to a dedicated folder
    
    Args:
        image_bytes: Original image as bytes
        base_filename: Base name for files (without extension)
        include_templates: Whether to include template variations
        
    Returns:
        Path to the created folder, list of created files
    """
    # Define all size formats
    size_formats = {
        "original": None,
        "instagram_post": (1080, 1080),
        "instagram_story": (1080, 1920),
        "facebook_post": (1200, 630),
        "twitter_post": (1200, 675),
        "linkedin_post": (1200, 627),
        "email_header": (600, 200),
        "website_banner": (1200, 300),
        "square_thumbnail": (500, 500)
    }
    
    # Define templates to use
    templates = ["none"]
    if include_templates:
        templates.extend(["white_border", "branded_corner", "quote_box", "social_ready"])
    
    # Create timestamp for folder name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Make sure base_filename doesn't have any problematic characters
    safe_base_filename = "".join(c if c.isalnum() else "_" for c in base_filename)
    
    # Create folder for this batch
    folder_name = f"{safe_base_filename}_{timestamp}_formats"
    folder_path = output_dir / folder_name
    folder_path.mkdir(exist_ok=True)
    
    # Track all created files for the zip
    created_files = []
    error_count = 0
    
    # Log progress
    if st.session_state.get('debug_mode', False):
        st.info(f"Creating formats in folder: {folder_path}")
    
    # Process each format
    total_combinations = len(size_formats) * len(templates)
    processed = 0
    
    for size_name, size_dims in size_formats.items():
        for template in templates:
            try:
                # Skip templates for original size
                if size_name == "original" and template != "none":
                    processed += 1
                    continue
                
                # For debugging
                if st.session_state.get('debug_mode', False):
                    st.info(f"Processing {size_name} with template {template} ({processed+1}/{total_combinations})")
                
                # Process the image
                template_to_use = None if template == "none" else template
                processed_image = resize_image(image_bytes, size_name, template_to_use)
                
                # Create filename
                template_suffix = "" if template == "none" else f"_{template}"
                filename = f"{safe_base_filename}_{size_name}{template_suffix}.png"
                file_path = folder_path / filename
                
                # Save the file
                with open(file_path, "wb") as f:
                    f.write(processed_image)
                
                created_files.append(file_path)
                
            except Exception as e:
                error_count += 1
                if st.session_state.get('debug_mode', False):
                    st.error(f"Error processing {size_name} with {template}: {str(e)}")
            
            processed += 1
    
    # Log completion
    if error_count > 0 and st.session_state.get('debug_mode', False):
        st.warning(f"Completed with {error_count} errors out of {total_combinations} combinations")
    
    return folder_path, created_files

# Function to handle image generation without losing state
def generate_and_save_image(prompt, model, size, add_logo, logo_path):
    """Generate an image and save it to session state to maintain across interactions"""
    with st.spinner("Generating your image... This may take up to 20-30 seconds."):
        try:
            # Generate the image
            image_bytes, file_path = generate_image(
                prompt=prompt,
                model=model,
                size=size,
                add_logo=add_logo,
                logo_path=logo_path
            )
            
            if image_bytes and file_path:
                # Store in session state
                st.session_state['current_image'] = {
                    'bytes': image_bytes,
                    'path': file_path
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
    add_logo = st.checkbox("Add Logo to Images", value=False, 
                         help="Add your company logo to the bottom right of generated images")
    
    # Logo upload option (only shown if watermark is enabled)
    if add_logo:
        uploaded_logo = st.file_uploader("Upload Custom Logo (PNG with transparency recommended)", 
                                       type=["png", "jpg", "jpeg"], 
                                       help="Transparent PNG works best")
        if uploaded_logo:
            # Save the uploaded logo
            custom_logo_path = assets_dir / "custom_logo.png"
            with open(custom_logo_path, "wb") as f:
                f.write(uploaded_logo.getvalue())
            st.success("Logo uploaded successfully!")
            logo_path = custom_logo_path
        else:
            logo_path = default_logo_path
            st.info("Using default logo. Upload your own for better results.")
    else:
        logo_path = default_logo_path
    
    # Debug Mode
    st.session_state['debug_mode'] = st.checkbox("Debug Mode", value=False, 
                                              help="Show detailed information for troubleshooting")
    
    # Style Guide Descriptions (moved from main page)
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
    
    # How to Use Guide (moved from main page to sidebar dropdown)
    with st.expander("How to Use This App", expanded=False):
        st.markdown("""
        1. Select a model in the sidebar (GPT-Image-1 or DALL-E 3)
        2. Choose a style guide or theme pack template
        3. Enter your custom image prompt with specific details
        4. Use the "Boost Idea" button to enhance your prompt with GPT-4o
        5. Adjust the style influence slider to control how much the style affects your result
        6. Optionally add your logo for branded content
        7. Click "Generate Image"
        8. Resize and add templates to your generated image using the download options
        9. Use "Generate All Formats" to create all size variations in one click

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
            logo_path=logo_path
        )
        
        if not success:
            st.error("Failed to generate image. Check debug mode for details.")
            
            # Suggest trying the other model
            other_model = "DALL-E 3" if selected_model == "GPT-Image-1" else "GPT-Image-1"
            st.warning(f"Tip: Try using {other_model} model instead - select it in the sidebar.")

# Display image and options if we have a generated image in session state
if st.session_state.get('has_generated_image') and 'current_image' in st.session_state:
    image_bytes = st.session_state['current_image']['bytes']
    file_path = st.session_state['current_image']['path']
    
    st.subheader("Generated Image")
    st.image(image_bytes, caption="Generated Image", use_container_width=True)
    
# Add expandable section for download options
    with st.expander("Download Options - Resize & Templates", expanded=True):
        download_col1, download_col2 = st.columns(2)
        
        with download_col1:
            st.subheader("Size Options")
            # Use session state to preserve selection across interactions
            size_option = st.selectbox(
                "Choose size format:", 
                [
                    "original", 
                    "instagram_post", 
                    "instagram_story", 
                    "facebook_post", 
                    "twitter_post", 
                    "linkedin_post", 
                    "email_header", 
                    "website_banner",
                    "square_thumbnail"
                ],
                index=[
                    "original", 
                    "instagram_post", 
                    "instagram_story", 
                    "facebook_post", 
                    "twitter_post", 
                    "linkedin_post", 
                    "email_header", 
                    "website_banner",
                    "square_thumbnail"
                ].index(st.session_state['size_option']),
                format_func=lambda x: {
                    "original": "Original Size",
                    "instagram_post": "Instagram Post (1080×1080)",
                    "instagram_story": "Instagram Story (1080×1920)",
                    "facebook_post": "Facebook Post (1200×630)",
                    "twitter_post": "Twitter Post (1200×675)",
                    "linkedin_post": "LinkedIn Post (1200×627)",
                    "email_header": "Email Header (600×200)",
                    "website_banner": "Website Banner (1200×300)",
                    "square_thumbnail": "Square Thumbnail (500×500)"
                }.get(x, x),
                key="size_select"
            )
            # Update session state with new selection
            st.session_state['size_option'] = size_option
        
        with download_col2:
            st.subheader("Template Options")
            # Use session state to preserve selection across interactions
            template_option = st.selectbox(
                "Apply template:",
                [
                    "none",
                    "white_border",
                    "branded_corner",
                    "quote_box",
                    "social_ready"
                ],
                index=["none", "white_border", "branded_corner", "quote_box", "social_ready"].index(st.session_state['template_option']),
                format_func=lambda x: {
                    "none": "No Template",
                    "white_border": "White Border",
                    "branded_corner": "Branded Corner",
                    "quote_box": "Quote Box (Bottom)",
                    "social_ready": "Social Media Ready"
                }.get(x, x),
                key="template_select"
            )
            # Update session state with new selection
            st.session_state['template_option'] = template_option
            
        # Preview the resized/templated image
        if size_option != "original" or template_option != "none":
            with st.spinner("Preparing preview..."):
                template = None if template_option == "none" else template_option
                try:
                    # Get stored image from session state
                    current_img_bytes = st.session_state['current_image']['bytes']
                    current_img_path = st.session_state['current_image']['path']
                    
                    # Process the image
                    resized_image = resize_image(current_img_bytes, size_option, template)
                    
                    # Show preview
                    st.subheader("Preview")
                    st.image(resized_image, use_container_width=True)
                    
                    # Generate filename
                    size_name = "original" if size_option == "original" else size_option
                    template_name = "" if template_option == "none" else f"_{template_option}"
                    base_name = current_img_path.stem if hasattr(current_img_path, 'stem') else "image"
                    download_filename = f"{base_name}_{size_name}{template_name}.png"
                    
                    # Download button for the modified version
                    st.download_button(
                        label=f"Download {size_option.replace('_', ' ').title()}{' with Template' if template_option != 'none' else ''}",
                        data=resized_image,
                        file_name=download_filename,
                        mime="image/png",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Error preparing image: {str(e)}")
        
        # Always add download button for original
        st.download_button(
            label="Download Original Image",
            data=image_bytes,
            file_name=file_path.name,
            mime="image/png",
            use_container_width=True
        )
        
# Add bulk format download section
    st.subheader("Bulk Format Download")
    bulk_col1, bulk_col2 = st.columns(2)

    with bulk_col1:
        include_templates = st.checkbox(
            "Include Template Variations", 
            value=st.session_state['bulk_download_include_templates'],
            help="Generate variations with all templates for each size",
            key="include_templates_checkbox"
        )
        st.session_state['bulk_download_include_templates'] = include_templates

    with bulk_col2:
        if st.button("Generate All Formats", on_click=on_bulk_download_click, use_container_width=True):
            pass  # The actual processing is done below based on session state

    # Process bulk download if button was clicked
    if st.session_state['bulk_download_clicked'] and 'current_image' in st.session_state and st.session_state['current_image']:
        with st.spinner("Creating all image formats... This may take a moment."):
            try:
                # Get necessary data from session state
                image_bytes = st.session_state['current_image']['bytes']
                file_path = st.session_state['current_image']['path']
                
                # Get base filename
                base_filename = file_path.stem if hasattr(file_path, 'stem') else "image"
                
                # Create all formats
                folder_path, created_files = create_all_formats(
                    image_bytes, 
                    base_filename,
                    include_templates=st.session_state['bulk_download_include_templates']
                )
                
                # Store results in session state
                st.session_state['bulk_download_results'] = {
                    'success': True,
                    'folder_path': str(folder_path),
                    'num_files': len(created_files),
                    'sample_files': [f.name for f in created_files[:5]],
                    'total_files': len(created_files)
                }
                
                # Reset the clicked state so it doesn't process again on reloads
                st.session_state['bulk_download_clicked'] = False
                
            except Exception as e:
                st.session_state['bulk_download_results'] = {
                    'success': False,
                    'error': str(e)
                }
                st.session_state['bulk_download_clicked'] = False

    # Display results if available
    if 'bulk_download_results' in st.session_state and st.session_state['bulk_download_results']:
        results = st.session_state['bulk_download_results']
        
        if results.get('success'):
            st.success(f"✅ Successfully created {results['num_files']} format variations in: {results['folder_path']}")
            
            # Show a sample of created files
            st.write("Sample of created files:")
            file_list = "\n".join([f"- {f}" for f in results['sample_files']])
            if results['total_files'] > 5:
                file_list += f"\n- ... and {results['total_files'] - 5} more"
            st.code(file_list)
        else:
            st.error(f"Error creating formats: {results.get('error', 'Unknown error')}")
            
    st.success(f"Image successfully generated and saved to: {file_path}")
    
    
# Show previously generated images
st.subheader("Recently Generated Images")
image_files = sorted(Path(output_dir).glob("*.png"), key=os.path.getmtime, reverse=True)[:6]  # Show 6 most recent

if not image_files:
    st.info("No images generated yet. Create your first image above!")
else:
    # Create a grid layout for the gallery - 3 columns
    cols = st.columns(3)
    
    for i, img_path in enumerate(image_files):
        col_idx = i % 3
        with cols[col_idx]:
            # Read the image file directly to avoid Streamlit's warnings
            with open(img_path, "rb") as file:
                file_data = file.read()
            
            # Display image using st.image with use_container_width
            st.image(
                file_data, 
                caption=img_path.name,
                use_container_width=True
            )
            
            # Add download button below the image
            st.download_button(
                label="Download",
                data=file_data,
                file_name=img_path.name,
                mime="image/png",
                key=f"gallery_download_{i}"
            )