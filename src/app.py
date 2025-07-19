import streamlit as st
from dotenv import load_dotenv
import os
import plotly.express as px
import pandas as pd

"""Main Streamlit app for Strava Run Analyzer."""

from fetch_data import get_recent_runs, get_activity_streams
from analyze import analyze_run_locally, get_ai_suggestions, get_follow_up_suggestion

# --- Helper Functions for Display ---

def display_pace_effort_tab(df, insights):
    """Renders the Pace & Effort visualization tab."""
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Pace Over Time")
        df['color'] = df['is_walking'].map({True: 'Walk', False: 'Run'})
        fig_pace = px.line(df, x='time', y='pace_min_km', color='color', title='Pace (min/km) with Run/Walk Highlights')
        st.plotly_chart(fig_pace, use_container_width=True)
        
        st.subheader("Pace Distribution (Filtered)")
        filtered_pace = df[df['velocity'] > 0.5]['pace_min_km']
        clipped_pace = filtered_pace.clip(3, 20)
        fig_hist = px.histogram(clipped_pace, nbins=30, title="Pace Distribution (3-20 min/km)")
        st.plotly_chart(fig_hist, use_container_width=True)

    with col2:
        st.subheader("Cumulative Average Pace")
        fig_cum_pace = px.line(df, x='distance', y='cumulative_avg_pace', title="Cumulative Avg Pace vs. Distance")
        st.plotly_chart(fig_cum_pace, use_container_width=True)

        if insights.get('hr_zone_distribution') is not None:
            st.subheader("Time in Heart Rate Zones")
            hr_zones = insights['hr_zone_distribution'].reset_index()
            hr_zones.columns = ['Zone', 'Time (seconds)']
            fig_hr = px.bar(hr_zones, x='Zone', y='Time (seconds)', title="Time Spent in Each HR Zone")
            st.plotly_chart(fig_hr, use_container_width=True)

def display_splits_segments_tab(insights, segments):
    """Renders the Splits & Segments visualization tab."""
    col3, col4 = st.columns(2)
    with col3:
        st.subheader("1km Distance Splits")
        if insights.get('distance_splits'):
            splits_df = pd.DataFrame(insights['distance_splits'])
            fig_splits = px.bar(splits_df, x='km_split', y='split_pace', title="Pace per 1km Split")
            st.plotly_chart(fig_splits, use_container_width=True)
        else:
            st.write("Not enough distance data for splits.")

        st.subheader("Run/Walk Segment Timeline")
        if segments is not None and not segments.empty:
            gantt_data = []
            start_time = 0
            for _, row in segments.iterrows():
                gantt_data.append(dict(Task="Run" if row['segment_type'] == 0 else "Walk", Start=start_time, Finish=start_time + row['duration_sec'], Color="Run" if row['segment_type'] == 0 else "Walk"))
                start_time += row['duration_sec']
            fig_gantt = px.timeline(gantt_data, x_start="Start", x_end="Finish", y="Task", color="Color", title="Run/Walk Segments Over Time")
            fig_gantt.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_gantt, use_container_width=True)
        else:
            st.write("No segment data to display timeline.")
            
    with col4:
        st.subheader("Run Segment Burst Analysis")
        run_segments = st.session_state.run_segments
        if not run_segments.empty:
            fig_scatter = px.scatter(run_segments, x='duration_sec', y='avg_pace', title="Run Bursts: Duration vs. Pace")
            st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.write("No run segments detected for burst analysis.")

def display_performance_curves_tab(insights):
    """Renders the Performance Curves visualization tab."""
    st.subheader("Mean Max Pace Curve")
    if insights.get('mean_max_pace'):
        mmp_df = pd.DataFrame(list(insights['mean_max_pace'].items()), columns=['Duration', 'Pace (min/km)'])
        fig_mmp = px.line(mmp_df, x='Duration', y='Pace (min/km)', title="Fastest Average Pace for Given Durations", markers=True)
        st.plotly_chart(fig_mmp, use_container_width=True)
    else:
        st.write("No mean max pace data available.")

def main():
    """Main function to run the Streamlit app."""
    st.set_page_config(layout="wide")
    st.title("Strava Run Analyzer")

    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'initial_analysis_done' not in st.session_state:
        st.session_state.initial_analysis_done = False
    if 'ai_analysis_done' not in st.session_state:
        st.session_state.ai_analysis_done = False
    if 'data_summary' not in st.session_state:
        st.session_state.data_summary = {}

    # --- Main Buttons and Workflow ---
    fetch_latest_only = st.checkbox("Fetch absolute latest run (ignore time filter)", value=False)

    if st.button("Fetch and Analyze Latest Run"):
        st.session_state.initial_analysis_done = False
        st.session_state.ai_analysis_done = False
        st.session_state.messages = []
        
        runs = get_recent_runs(after_days=7, fetch_latest_only=fetch_latest_only)
        if runs:
            latest = runs[0]
            st.header(f"Analyzing: {latest['name']} ({latest['distance']/1000:.2f} km on {latest['start_date_local']})")
            
            with st.spinner('Analyzing run data...'):
                streams = get_activity_streams(latest['id'])
                df, insights, segments = analyze_run_locally(streams) # Changed function call
                run_segments = segments[segments['segment_type'] == 0] if segments is not None else pd.DataFrame()
                st.session_state.run_segments = run_segments
            
            st.session_state.initial_analysis_done = True
            st.session_state.insights = insights
            st.session_state.df = df
            st.session_state.segments = segments
            st.session_state.data_summary = {k: v for k, v in insights.items() if isinstance(v, (int, float, str, list, dict, type(None)))}
        else:
            st.error("No recent runs found in the last 7 days.")

    # --- Display Area: Visuals and AI are now separate ---
    if st.session_state.initial_analysis_done:
        insights = st.session_state.insights
        df = st.session_state.df
        segments = st.session_state.segments

        st.header("Analysis & Visualizations")
        tab1, tab2, tab3 = st.tabs(["Pace & Effort", "Splits & Segments", "Performance Curves"])
        with tab1:
            display_pace_effort_tab(df, insights)
        with tab2:
            display_splits_segments_tab(insights, segments)
        with tab3:
            display_performance_curves_tab(insights)

        # --- Key Insights and AI Section ---
        st.header("Insights & AI Coach")
        st.write("Here are the key metrics and rule-based suggestions from your run. Click the button below to get personalized AI coaching.")

        # Display rule-based suggestions
        if insights.get('suggestions'):
            for sug in insights['suggestions']:
                st.info(f"Suggestion: {sug}")

        # --- AI Button and Chat Interface ---
        if not st.session_state.ai_analysis_done:
            if st.button("Get AI Suggestions & Start Chat"):
                with st.spinner("Your AI coach is analyzing your run..."):
                    ai_suggestions = get_ai_suggestions(st.session_state.insights)
                    st.session_state.insights['ai_suggestions'] = ai_suggestions
                    st.session_state.ai_analysis_done = True
                    
                    initial_ai_response = "\n".join([f"- {s}" for s in ai_suggestions])
                    st.session_state.messages.append({"role": "assistant", "content": f"Based on your run, here are my suggestions:\n{initial_ai_response}"})
                    st.rerun() # Rerun to display the chat interface immediately

        if st.session_state.ai_analysis_done:
            st.subheader("Chat with AI Coach (Gemini 2.5 Pro)")
            # Display chat messages from history
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            # Accept user input
            if prompt := st.chat_input("Ask a follow-up question about your run..."):
                # Add user message to chat history
                st.session_state.messages.append({"role": "user", "content": prompt})
                # Display user message in chat message container
                with st.chat_message("user"):
                    st.markdown(prompt)

                # Get assistant response
                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        response = get_follow_up_suggestion(st.session_state.messages, st.session_state.data_summary)
                        st.markdown(response)
                    
                    # Add assistant response to chat history
                    st.session_state.messages.append({"role": "assistant", "content": response}) 

if __name__ == "__main__":
    load_dotenv()
    main() 