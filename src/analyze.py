import pandas as pd
import numpy as np
import google.generativeai as genai
import os
import time
from dotenv import load_dotenv

load_dotenv()

# --- Constants ---
WALK_VELOCITY_THRESHOLD = 2.0  # m/s
HR_ZONE_BINS = [0, 0.6, 0.7, 0.8, 0.9, 1.0] # Based on percentage of Max HR
HR_ZONE_LABELS = ['Zone 1 (Warm-up)', 'Zone 2 (Easy)', 'Zone 3 (Aerobic)', 'Zone 4 (Threshold)', 'Zone 5 (Max Effort)']
MMP_DURATIONS = [30, 60, 300]  # Durations in seconds for Mean Max Pace (30s, 1m, 5m)


# Configure Gemini API
try:
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is not set.")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-pro') # Updated model
    GEMINI_ENABLED = True
except (ValueError, TypeError) as e:
    GEMINI_ENABLED = False
    print(f"Warning: Gemini API key not found or invalid ({e}). AI suggestions will be disabled.")

def get_mean_max_pace(df, durations):
    """Calculate the fastest average pace for given durations."""
    mean_max_paces = {}
    for duration in durations:
        # Use rolling window on velocity, then convert max avg velocity to pace
        max_avg_velocity = df['velocity'].rolling(window=duration, min_periods=1).mean().max()
        if max_avg_velocity > 0:
            mean_max_paces[f"{duration}s"] = 1000 / (max_avg_velocity * 60)
        else:
            mean_max_paces[f"{duration}s"] = np.nan
    return mean_max_paces

def get_distance_splits(df):
    """Calculate average pace for each 1km split."""
    if 'distance' not in df.columns or df['distance'].isnull().all():
        return None
    
    df['km_split'] = (df['distance'] / 1000).astype(int)
    splits = df.groupby('km_split').agg(
        split_pace=('pace_min_km', 'mean'),
        split_time_sec=('time', lambda x: x.max() - x.min())
    ).reset_index()
    splits['km_split'] = splits['km_split'] + 1 # 1-indexed splits
    return splits

def analyze_run_locally(streams):
    """Performs all local analysis without calling the AI model."""
    if not streams or not streams.get('time', {}).get('data'):
        return pd.DataFrame(), {'error': 'No stream data available for analysis.'}, None

    time_data = streams.get('time', {}).get('data', [])
    velocity_data = streams.get('velocity_smooth', {}).get('data', [])
    heartrate_data = streams.get('heartrate', {}).get('data', [])

    # Find max length (usually time)
    max_len = len(time_data)

    # Pad shorter arrays with np.nan
    velocity_data = velocity_data + [np.nan] * (max_len - len(velocity_data))
    heartrate_data = heartrate_data + [np.nan] * (max_len - len(heartrate_data))

    # Make sure to handle the new 'distance' stream
    distance_data = streams.get('distance', {}).get('data', [])
    distance_data = distance_data + [np.nan] * (max_len - len(distance_data))
    df = pd.DataFrame({
        'time': time_data,
        'distance': distance_data,
        'velocity': velocity_data,
        'heartrate': heartrate_data
    })

    # Ensure heartrate is numeric
    df['heartrate'] = pd.to_numeric(df['heartrate'], errors='coerce')

    df['pace_min_km'] = np.where(df['velocity'] > 0, 1000 / (df['velocity'] * 60), np.nan)
    # Use constant for walk detection
    df['is_walking'] = df['velocity'] < WALK_VELOCITY_THRESHOLD

    # Calculate cumulative pace
    df['cumulative_avg_pace'] = df['pace_min_km'].expanding().mean()

    # --- Pre-calculate all metrics safely before building dictionaries ---
    df['segment_type'] = df['is_walking'].astype(int)
    df['segment_group'] = (df['segment_type'] != df['segment_type'].shift()).cumsum()

    # Calculate heart rate zones if data is available
    if df['heartrate'].notna().any():
        max_hr = df['heartrate'].max()
        bins = [val * max_hr for val in HR_ZONE_BINS]
        # Ensure the last bin includes max_hr
        bins[-1] = max_hr + 1
        df['hr_zone'] = pd.cut(df['heartrate'], bins=bins, labels=HR_ZONE_LABELS, right=False)
        hr_zone_distribution = df.dropna(subset=['hr_zone']).groupby('hr_zone')['time'].count()
    else:
        hr_zone_distribution = None

    segments = df.groupby(['segment_group', 'segment_type']).agg(
        duration_sec=('time', lambda x: x.max() - x.min()),
        avg_pace=('pace_min_km', 'mean')  # Add this
    ).reset_index()

    run_segments = segments[segments['segment_type'] == 0]
    walk_segments = segments[segments['segment_type'] == 1]

    # Safely calculate all values
    avg_pace_val = df['pace_min_km'].mean()
    pace_fluctuation_val = df['pace_min_km'].std()
    walk_count_val = len(walk_segments)
    avg_run_duration_min_val = (run_segments['duration_sec'].mean() / 60) if not run_segments.empty else 0
    avg_walk_duration_min_val = (walk_segments['duration_sec'].mean() / 60) if not walk_segments.empty else 0
    avg_hr_val = df['heartrate'].mean() if df['heartrate'].notna().any() else None
    max_hr_val = df['heartrate'].max() if df['heartrate'].notna().any() else None

    # --- New Analysis Calculations ---
    mean_max_pace_data = get_mean_max_pace(df, durations=MMP_DURATIONS)
    distance_splits_data = get_distance_splits(df)

    # --- Build insights and suggestions dictionary ---
    insights = {
        'avg_pace': avg_pace_val,
        'pace_fluctuation': pace_fluctuation_val,
        'walk_count': walk_count_val,
        'avg_run_duration_min': avg_run_duration_min_val,
        'avg_walk_duration_min': avg_walk_duration_min_val,
        'avg_heart_rate': avg_hr_val,
        'max_heart_rate': max_hr_val,
        'hr_zone_distribution': hr_zone_distribution, # Add HR zones to insights
        'suggestions': [],
        'ai_suggestions': [],
        'mean_max_pace': mean_max_pace_data,
        'distance_splits': distance_splits_data.to_dict('records') if distance_splits_data is not None else None,
    }

    # Rule-based suggestions
    if walk_count_val > 3:
        insights['suggestions'].append(f"Frequent walks ({walk_count_val}) detected. Try 3:1 run:walk intervals to build stamina.")
    if pace_fluctuation_val > 1.5:
        insights['suggestions'].append("High pace variation. Start slower to maintain steady effort.")

    return df, insights, segments

def get_ai_suggestions(insights):
    """Generates initial suggestions from Gemini based on pre-computed insights."""
    if not GEMINI_ENABLED:
        return ["AI features are disabled. Please check your API key."]

    data_summary = {k: v for k, v in insights.items() if isinstance(v, (int, float, str, list, dict, type(None)))}
    
    prompt = (
        f"Analyze this run data: {data_summary}. User does 5K/10K runs, often with short, high-stamina bursts then walks. "
        "Suggest new pacing strategies or routines to improve endurance and speed. Keep to 2-4 concise, actionable bullet points."
    )
    try:
        response = model.generate_content(prompt)
        ai_suggestions = [s.strip() for s in response.text.split('\n') if s.strip() and s.startswith('*')]
        return [s.lstrip('* ').strip() for s in ai_suggestions]
    except Exception as e:
        print(f"Gemini API error: {e}")
        return ["AI suggestions unavailable due to an API error."]

def get_follow_up_suggestion(chat_history, data_summary):
    """Generates a follow-up response from Gemini based on conversation history."""
    if not GEMINI_ENABLED:
        return "AI features are disabled. Please check your API key."

    # Combine history into a single prompt context
    context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])

    prompt = (
        f"You are a running coach AI. Based on the initial run data ({data_summary}) "
        f"and the conversation so far, answer the user's latest question.\n\n"
        f"Conversation History:\n{context}\n\n"
        "Provide a concise and helpful response to the last user message."
    )

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini follow-up error: {e}")
        return "Sorry, I encountered an error trying to generate a follow-up response." 