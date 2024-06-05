import streamlit as st
import google.generativeai as genai
import os
import PyPDF2 as pdf
from dotenv import load_dotenv
import json
import mysql.connector
from mysql.connector import Error
import re

# Load environment variables from a .env file
load_dotenv()

# Verify that the environment variables are loaded correctly
print("GOOGLE_APPLICATION_CREDENTIALS:", os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
print("GOOGLE_API_KEY:", os.getenv("GOOGLE_API_KEY"))

# Configure the Google Generative AI
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def get_gemini_response(input_text):
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(input_text)
    return response.text

def input_pdf_text(uploaded_file):
    reader = pdf.PdfReader(uploaded_file)
    text = ""
    for page in range(len(reader.pages)):
        page = reader.pages[page]
        text += str(page.extract_text())
    return text

def extract_email(text):
    email_pattern = r'[a-zA-Z0-9._%+-]+@gmail\.com'
    match = re.search(email_pattern, text)
    return match.group(0) if match else None

def save_response_to_db(response_data, email_resume, jd_match_threshold):
    try:
        connection = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE")
        )
        if connection.is_connected():
            cursor = connection.cursor()
            insert_query = """
            INSERT INTO evaluations (jd_match, missing_keywords, profile_summary, email_resume)
            VALUES (%s, %s, %s, %s)
            """
            cursor.execute(insert_query, (
                response_data["JD Match"],
                json.dumps(response_data["MissingKeywords"]),
                response_data["Profile Summary"],
                email_resume
            ))
            connection.commit()

            if int(response_data["JD Match"].strip('%')) > jd_match_threshold:
                insert_query_jd_match = """
                INSERT INTO jd_match_resumes (jd_match, missing_keywords, profile_summary, email_resume)
                VALUES (%s, %s, %s, %s)
                """
                cursor.execute(insert_query_jd_match, (
                    response_data["JD Match"],
                    json.dumps(response_data["MissingKeywords"]),
                    response_data["Profile Summary"],
                    email_resume
                ))
                connection.commit()

            cursor.close()
            connection.close()

            # Display a pop-up message when a new entry is inserted
            st.success("New entry added successfully!")
    except Error as e:
        return f"Error: {e}"

# Prompt Template
input_prompt = """
Hey Act Like a skilled or very experienced ATS (Application Tracking System)
with a deep understanding of tech field, software engineering, data science, data analyst,
and big data engineer. Your task is to evaluate the resume based on the given job description.
You must consider the job market is very competitive and you should provide 
best assistance for improving the resumes. Assign the percentage Matching based 
on JD and
the missing keywords with high accuracy.
resume:{text}
description:{jd}

I want the response in one single string having the structure
{{"JD Match":"%","MissingKeywords":[],"Profile Summary":""}}
"""

# Streamlit app
st.sidebar.title("Navigation")
selected = st.sidebar.radio("Go to", ["Home", "Application", "How to Use"])

# Home page
if selected == "Home":
    st.title("Smart ATS")
    st.markdown("""
    <style>
    .big-font {
        font-size:30px !important;
        color: #4B8BBE;
    }
    .medium-font {
        font-size:20px !important;
        color: #306998;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<p class="big-font">Welcome to Smart ATS Application!</p>', unsafe_allow_html=True)
    
    st.markdown("""
    **Smart ATS** is an intelligent Application Tracking System designed to enhance the job application process for candidates and recruiters. Our system leverages advanced AI capabilities to evaluate resumes against job descriptions, ensuring that only the most qualified candidates are highlighted.
    """)

    st.markdown('<p class="medium-font">Features:</p>', unsafe_allow_html=True)
    st.write("""
    - **Automated Resume Evaluation**: Upload your resume and get an instant evaluation based on the job description you provide.
    - **Job Description Match**: Receive a percentage match score indicating how well your resume aligns with the job description.
    - **Keyword Analysis**: Identify missing keywords that are crucial for the job position.
    - **Profile Summary**: Get a summary of your profile highlighting strengths and areas of improvement.
    - **Gmail ID Extraction**: Automatically extract your Gmail ID from your resume for streamlined communication.
    - **Database Integration**: Securely save evaluation results in a database for future reference and analysis.
    - **Threshold-Based Filtering**: Resumes with a match percentage above a user-defined threshold are stored separately for easy access.
    """)

# Application page
if selected == "Application":
    st.title("Smart ATS")
    st.text("Improve Your Resume ATS")
    jd = st.text_area("Paste the Job Description")
    uploaded_file = st.file_uploader("Upload Your Resume", type="pdf", help="Please upload the pdf")
    jd_match_threshold = st.number_input("Enter JD Match Threshold", min_value=0, max_value=100, value=50)

    submit = st.button("Submit")

    if submit:
        if uploaded_file is not None:
            text = input_pdf_text(uploaded_file)
            
            # Extract Gmail ID from resume text
            email_resume = extract_email(text)
            
            if email_resume:
                formatted_prompt = input_prompt.format(text=text, jd=jd)
                response = get_gemini_response(formatted_prompt)
                
                # Parse the JSON response
                response_data = json.loads(response)
                
                # Save the response to the database
                db_result = save_response_to_db(response_data, email_resume, jd_match_threshold)
                
                # Display the response in a structured format
                st.subheader("Job Description Match Percentage")
                st.write(response_data["JD Match"])
                
                st.subheader("Missing Keywords")
                st.write(", ".join(response_data["MissingKeywords"]))
                
                st.subheader("Profile Summary")
                st.write(response_data["Profile Summary"])
                
                st.subheader("Gmail ID Extracted from Resume")
                st.write(email_resume)
                
                st.subheader("Database Insertion Status")
                st.write(db_result)
            else:
                st.error("No Gmail ID found in the resume.")
        else:
            st.error("Please upload a resume.")

# How to Use page
if selected == "How to Use":
    st.title("How to Use")
    
    st.markdown("""
    <style>
    .medium-font {
        font-size:20px !important;
        color: #306998;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<p class="medium-font">How to Use Smart ATS:</p>', unsafe_allow_html=True)
    st.write("""
    1. Navigate to the **Application** page using the menu.
    2. Paste the job description in the provided text area.
    3. Upload your resume in PDF format.
    4. Set your desired JD match threshold.
    5. Click on the submit button to get your resume evaluated.
    """)
    
    st.write("For more information, contact us at **info@example.com**.")
    st.write("Visit our website: [Presidio](https://www.presidio.com)")
