# AI Image Generator

A Streamlit-based application that generates images using OpenAI's image generation models (DALL-E 3 and GPT-Image-1) with customizable style guides, templates, and formatting options.

![App Screenshot](https://i.imgur.com/example.png) <!-- Replace with your actual screenshot -->

## Features

- **AI-Powered Image Generation**: Create images using OpenAI's DALL-E 3 and GPT-Image-1 models
- **Style Guides & Theme Packs**: Choose from pre-defined visual styles or themed prompt collections
- **Prompt Enhancement**: Boost your prompt with GPT-4o for more detailed, creative results
- **Multi-Format Export**: Generate different sizes for various social media platforms
- **Template System**: Apply ready-to-use templates like borders, branded corners, quote boxes
- **Branding Options**: Add your own logo as a watermark
- **Secure Access**: Password-protected interface

## Live Demo

Access the app at: [https://your-streamlit-app-url.streamlit.app](https://your-streamlit-app-url.streamlit.app)

## Setup & Installation

### Prerequisites

- Python 3.8+
- OpenAI API key
- Git

### Local Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ai-image-generator.git
   cd ai-image-generator
   ```

2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with your API key and optional password:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   GEN_IMAGE_PASSWORD=your_chosen_password  # Optional for local dev
   ```

4. Run the app:
   ```bash
   streamlit run app.py
   ```

### Streamlit Cloud Deployment

1. Fork this repository to your GitHub account
2. Create a new app on [Streamlit Cloud](https://streamlit.io/cloud)
3. Connect to your GitHub repository
4. Add the following secrets in the Streamlit Cloud dashboard:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   GEN_IMAGE_PASSWORD=your_chosen_password  # For password protection
   ```

## Configuration Files

The app uses two configuration files that you can customize:

### `themes.json`

Contains themed prompt collections for quick selection:

```json
{
  "Holiday Season": [
    "Christmas market scene with snow falling, warm lights, and festive decorations",
    "New Year's Eve celebration with fireworks and champagne glasses"
  ],
  "Product Showcase": [
    "Professional product photography of a luxury item on a minimalist background",
    "Lifestyle product shot in natural setting with soft lighting"
  ]
}
```

### `style_guides.json`

Contains visual style descriptions that influence the image generation:

```json
{
  "70s Retro Cinematic": "Warm vintage feel with earth tones, film grain, and nostalgic lighting reminiscent of 1970s cinema",
  "Bright Studio Pop": "High-key studio lighting with vibrant colors, playful composition, and clean backgrounds"
}
```

## Directory Structure

- `app.py`: Main application file
- `requirements.txt`: Required Python packages
- `assets/`: Directory for storing logos and app assets
- `generated_images/`: Directory where generated images are saved
- `themes.json`: Theme pack configurations
- `style_guides.json`: Style guide configurations

## Usage Notes

1. **Image Storage**: Images are temporarily stored while the app is running. Always use the download buttons to save your images permanently.
2. **API Usage**: This app uses OpenAI's API which incurs costs based on usage. Monitor your API usage.
3. **Password Protection**: If you've set a password, you'll need to enter it to access the app.

## Customization

- **Custom Logo**: Upload your own logo through the UI to add as a watermark
- **New Themes**: Edit the `themes.json` file to add your own themed prompt collections
- **New Styles**: Edit the `style_guides.json` file to add your own visual style guides

## Technologies

- [Streamlit](https://streamlit.io/)
- [OpenAI API](https://openai.com/blog/openai-api)
- [Pillow](https://python-pillow.org/)
- [Python-dotenv](https://github.com/theskumar/python-dotenv)

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgements

- OpenAI for providing the image generation models
- Streamlit for the amazing framework

---

Created by [Your Name](https://github.com/yourusername)
