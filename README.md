# Strava Run Analyzer

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-url.streamlit.app)

A Streamlit web app for analyzing Strava running activities with visualizations and AI-powered suggestions via Gemini.

## Features
- Fetch recent runs from Strava API
- Interactive visualizations: Pace over time, distributions, splits, mean max pace, etc.
- Rule-based insights on pacing and run-walk patterns
- AI suggestions for improving stamina and speed
- Chat interface for follow-up questions

## Setup
1. Clone the repo: `git clone https://github.com/kikugo/strava-run-analyzer.git`
2. cd strava-run-analyzer
3. python -m venv venv
4. source venv/bin/activate
5. pip install -r requirements.txt
6. Copy .env.example to .env and fill in your Strava and Google API keys

## Usage
streamlit run src/app.py
- Click 'Fetch and Analyze Latest Run'
- View visualizations and insights
- Click 'Get AI Suggestions & Start Chat' for AI analysis

## Deployment
- Push to GitHub
- Deploy on Streamlit Sharing: Add secrets from .env

## Screenshots
(Add images here)

## License
MIT 