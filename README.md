# AI Chatbot with Google Gemini

A modern, minimalist web application that implements a chatbot using Google's Gemini AI model. The application features a clean, Apple-inspired design with a responsive interface.

## Features

- Real-time chat interface
- Powered by Google Gemini AI
- Modern, responsive design
- Clean and intuitive user interface
- Auto-expanding text input
- Smooth animations and transitions

## Prerequisites

- Python 3.8 or higher
- Google Gemini API key
- Modern web browser

## Installation

1. Clone the repository
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file and add your Google Gemini API key:
   ```
   GOOGLE_API_KEY=your_gemini_api_key_here
   ```

## Running the Application

1. Start the Flask server:
   ```
   python app.py
   ```
2. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

## Project Structure

```
.
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── .env               # Environment variables
└── static/
    ├── index.html     # Main HTML file
    ├── css/
    │   └── styles.css # Stylesheet
    └── js/
        └── main.js    # Frontend JavaScript
```

## Security Notes

- Never commit your `.env` file or expose your API key
- The application uses CORS protection
- All user inputs are sanitized before processing

## License

MIT License
