import streamlit as st
import openai
import json
from dotenv import load_dotenv
import os
import base64
import io
from gtts import gTTS
import speech_recognition as sr
import tempfile
import time
import pandas as pd
import execjs  # For running JavaScript code
from PyPDF2 import PdfReader  # For PDF text extraction
from docx import Document  # For DOCX text extraction

# ✅ Load environment variables
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# ✅ Create the OpenAI client with the API key
client = openai.OpenAI(api_key=api_key)


# Initialize session state
if "conversation" not in st.session_state:
    st.session_state.conversation = []
if "summary" not in st.session_state:
    st.session_state.summary = ""
if "history" not in st.session_state:
    st.session_state.history = []
if "user_name" not in st.session_state:
    st.session_state.user_name = "Guest"
if "leaderboard" not in st.session_state:
    st.session_state.leaderboard = pd.DataFrame(columns=["Name", "Score"])

# Voice input
r = sr.Recognizer()

def voice_to_text():
    with sr.Microphone() as source:
        st.info("Listening for wake word 'Hello Jarvis'...")
        audio = r.listen(source, timeout=5)
        try:
            text = r.recognize_google(audio)
            if "hello jarvis" in text.lower():
                speak_text("Yes sir, how can I help you today?")
                audio2 = r.listen(source, timeout=10)
                command = r.recognize_google(audio2)
                return command
        except:
            return ""
    return ""

# Text-to-speech
def speak_text(text):
    tts = gTTS(text)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        tts.save(fp.name)
        audio_file = open(fp.name, 'rb')
        audio_bytes = audio_file.read()
        st.audio(audio_bytes, format='audio/mp3')

# Live code execution
def run_code(code, language="Python"):
    try:
        if language == "Python":
            exec_globals = {}
            exec(code, exec_globals)
            return exec_globals
        elif language == "JavaScript":
            ctx = execjs.compile(f"function run_code() {{ return eval('{code}'); }}")
            result = ctx.call("run_code")
            return result
    except Exception as e:
        return f"Error: {str(e)}"

# Extract text from PDF
def extract_text_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

# Extract text from DOCX
def extract_text_from_docx(uploaded_file):
    doc = Document(uploaded_file)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

# Resume Analysis
def analyze_resume(resume_text):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a professional resume reviewer."},
            {"role": "user", "content": f"Analyze the following resume and provide feedback for improvement:\n{resume_text}"}
        ],
        max_tokens=500
    )
    feedback = response.choices[0].message.content.strip()
    return feedback

# Streamlit app setup
st.set_page_config(page_title="Interview Preparation Bot", layout="wide")
st.title("Interview Preparation Bot")
st.markdown(f"Welcome *{st.session_state.user_name}*, prepare for your dream job with real-time feedback and smart insights!")

# Sidebar inputs
st.sidebar.header("Choose Interview Preferences")
role = st.sidebar.selectbox("Select your target role:", ["Software Engineer", "Data Analyst", "Product Manager"])
domain = st.sidebar.text_input("Specify domain (optional):", "frontend")
mode = st.sidebar.radio("Choose Interview Mode:", ["Technical", "Behavioral", "FAANG-style Technical"])

# Start Interview
if st.sidebar.button("Start Interview"):
    st.session_state.conversation.clear()
    st.session_state.summary = ""

    if mode == "FAANG-style Technical":
        system_prompt = f"You are a senior FAANG interviewer. Ask advanced DSA/system design questions relevant to the {role} role in the {domain if domain else 'general'} domain. Evaluate each answer thoroughly and provide expert-level feedback with model answers, expected optimal solution, and score out of 10."
    else:
        system_prompt = f"You are an expert interviewer for a {role} role in {domain if domain else 'general'} domain. Conduct a {mode.lower()} interview with 3-5 questions. Evaluate each answer based on clarity, accuracy, and real-world relevance. Give feedback and score (out of 10)."

    st.session_state.conversation.append({"role": "system", "content": system_prompt})

    # 🔥 Immediately ask first question
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=st.session_state.conversation
    )
    first_question = response.choices[0].message.content
    st.session_state.conversation.append({"role": "assistant", "content": first_question})

# Main Q&A flow
if st.session_state.conversation:
    st.markdown("### Interview Q&A")
    col1, col2 = st.columns([3, 1])
    with col1:
        user_input = st.text_input("Your Answer:", key="user_answer")
    with col2:
        if st.button("Use Voice Input"):
            voice_input = voice_to_text()
            if voice_input:
                st.session_state.conversation.append({"role": "user", "content": voice_input})
                st.write(f"*You (via voice):* {voice_input}")
                user_input = voice_input

    # Code execution section
    with col2:
        code_input = st.text_area("Write code to run (optional):", height=200)
        language = st.selectbox("Select Language", ["Python", "JavaScript"])
        if st.button("Run Code") and code_input:
            code_output = run_code(code_input, language)
            st.write("*Code Output:*")
            st.write(code_output)

    if st.button("Submit Answer") and user_input:
        st.session_state.conversation.append({"role": "user", "content": user_input})

        # Get feedback and next question
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=st.session_state.conversation
        )
        reply = response.choices[0].message.content
        st.session_state.conversation.append({"role": "assistant", "content": reply})
        speak_text(reply)

    for msg in st.session_state.conversation[1:]:
        if msg["role"] == "assistant":
            st.markdown(f"*Bot:* {msg['content']}")
        elif msg["role"] == "user":
            st.markdown(f"*You:* {msg['content']}")

# Final summary button
if st.button("Generate Summary Report"):
    summary_prompt = "Generate a detailed summary of the interview session. Mention strengths, areas to improve, and final rating out of 10."
    st.session_state.conversation.append({"role": "user", "content": summary_prompt})
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=st.session_state.conversation
    )
    summary = response.choices[0].message.content
    st.session_state.summary = summary
    st.markdown("## Interview Summary")
    st.markdown(summary)

    try:
        score_line = [line for line in summary.split('\n') if "rating" in line.lower() or "/10" in line][0]
        score = int(''.join(filter(str.isdigit, score_line.split("/")[0])))
        new_row = pd.DataFrame([[st.session_state.user_name, score]], columns=["Name", "Score"])
        st.session_state.leaderboard = pd.concat([st.session_state.leaderboard, new_row], ignore_index=True)
    except:
        pass

    st.session_state.history.append({"name": st.session_state.user_name, "summary": summary})

# Optional download button
if st.session_state.summary:
    if st.download_button("Download Summary as PDF", data=st.session_state.summary, file_name="interview_summary.pdf"):
        st.success("PDF Downloaded Successfully!")

# Leaderboard Display
st.markdown("## Leaderboard")
st.dataframe(st.session_state.leaderboard.sort_values(by="Score", ascending=False))

# History Display
if st.checkbox("Show My Previous Sessions"):
    for i, session in enumerate(st.session_state.history):
        if session["name"] == st.session_state.user_name:
            st.markdown(f"### Session {i+1} Summary:")
            st.markdown(session["summary"])

# Resume Upload Section
st.sidebar.header("Upload Resume")
uploaded_file = st.sidebar.file_uploader("Choose a resume file", type=["pdf", "docx"])

if uploaded_file is not None:
    if uploaded_file.type == "application/pdf":
        resume_text = extract_text_from_pdf(uploaded_file)
    elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        resume_text = extract_text_from_docx(uploaded_file)

    st.write("Analyzing Resume...")
    analysis_result = analyze_resume(resume_text)
    st.markdown("## Resume Feedback")
    st.write(analysis_result)
