# Cognitext: Enhanced Concept Map Generator

Turn Wikipedia into a playground of ideas! We take complex articles and transform them into interactive concept maps that show how ideas connect, bounce off each other, and build deeper understanding.

## New in This Version

- **User-provided API Keys**: Users now enter their own OpenAI API keys instead of relying on a developer key
- **Improved security**: API keys are stored only in the browser session and never saved on servers
- **Better error handling**: Comprehensive validation and feedback for API key issues

## Features

- **Visual Concept Mapping**: Transform complex Wikipedia articles into interactive concept maps
- **Progressive Disclosure**: Focus on high-level concepts first, then expand to see more details
- **Intelligent Analysis**: Automatically identifies primary, secondary, and tertiary concepts
- **Interactive Exploration**: Click, drag, and explore connections between ideas
- **Conversational Interface**: Ask questions about concepts to deepen understanding

## Setup and Running

### Prerequisites
- Python 3.8+
- pip
- OpenAI API key (users will input their own)

### Installation

1. Clone this repository:
```bash
git clone https://github.com/your-username/cognitext.git
cd cognitext
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
streamlit run python/app.py
```

4. Open your browser to the URL provided by Streamlit (usually http://localhost:8501)

### API Key Configuration

The application now requires users to provide their own OpenAI API keys:

1. Create an account on [OpenAI's platform](https://platform.openai.com)
2. Generate an API key in your account dashboard
3. Enter the key in the sidebar of the Cognitext application
4. Click "Validate and Save API Key"

API keys are stored only in the browser session and are not saved on servers.

## Using the Application

1. Enter your OpenAI API key in the sidebar
2. Either:
   - Select one of the pre-generated Wikipedia articles
   - Enter a URL to a Wikipedia article you want to analyze
3. Wait for processing to complete (may take several minutes for new articles)
4. Explore the interactive concept map:
   - Click on nodes to expand their connections
   - Right-click on nodes to see explanations
   - Drag nodes to reorganize the map
5. Use the chatbot to ask questions about concepts and their relationships

## Development Notes

- The application now initializes services only after a valid API key is provided
- Pre-generated examples are still available for quick demos
- API key validation includes basic format checking and a test API call

## Privacy and Security

- User API keys are stored only in the browser's session state
- Keys are never logged, stored in databases, or transmitted beyond the necessary API calls
- The application runs entirely in the user's browser and their own API account

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
