import os
from flask import Flask, render_template, request, send_file, redirect
import datetime
from bs4 import BeautifulSoup

import markdown2
import urllib.parse

from fpdf import FPDF
import pdfplumber

from dotenv import load_dotenv
import google.generativeai as genai

app = Flask(__name__)
# app.config['UPLOAD_FOLDER'] = 'userFiles'
TEMP_DIR = '/tmp'

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Text Extraction
def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        # Try direct text extraction
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text

        if text.strip():
            return text.strip()
        
    except Exception as e:
        print(f"Direct text extraction failed: {e}")

    return text.strip()

# Upload Resume
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files["resume_pdf"]
        if file and file.filename.endswith(".pdf"):
            file.save(os.path.join(TEMP_DIR, file.filename))
            return render_template("index.html", uploaded=True)
    return render_template("index.html")

# Select Resume for Analysis
@app.route("/resumeAnalysis", methods=["GET"])
def resumeAnalysis():
    files = [
        f for f in os.listdir(TEMP_DIR)
        if f.endswith('.pdf') and not f.startswith("resumeradar_pdf")
    ]
    
    return render_template("resumeAnalysis.html", files=files)

# Analyze Resume
@app.route("/resumeReport", methods=["POST"])
def resumeReport():
    filename = request.form.get("resume_filename")
    pdf_path = os.path.join(TEMP_DIR, filename)
    
    resume_text = extract_text_from_pdf(pdf_path)
    analysis_type = request.form.get("analysis_type")
    job_description = request.form.get("job_description")
    
    if not resume_text:
        return render_template("error.html", error_code="400", message="Resume text is required for this!") # Text extraction from the PDF file is failing.
    if analysis_type in ["resume_jd_analysis", "resume_jd_score"] and not job_description.strip():
        return render_template("error.html", error_code="422", message="Job Description is required for this! Please check and try again.") # Ensure the user is filling out the job description field in the form before submitting.
    
    model = genai.GenerativeModel("gemini-2.0-flash")

    # Resume Analysis
    if analysis_type == "resume_analysis":
        base_prompt = f"""
        You are an experienced HR specialist and career consultant with a deep understanding of hiring practices across diverse industries - including technical, non-technical, creative, healthcare, business, and management roles; review the provided resume and give a professional assessment.

        Your assessment should cover:
            1. How well the resume fits the job role.
            2. list existing skills.
            3. Missing or underdeveloped skills needs to improve.
            4. Recommend relevant skills or certifications to improve the candidate's profile.
            5. Suggest suitable courses or training programs based on gaps identified.
            6. Evaluate the candidate's readiness for a technical role.
            7. List both technical and soft skills found in the resume.
            8. Suggest specific projects the candidate should complete to address gaps.
            9. Highlight key strengths and weaknesses.
            10. Recommendations Summary.

        Resume:
        {resume_text}
        """

    # Resume ATS Score
    elif analysis_type == "resume_analysis_score":
        base_prompt = f"""
        You are a sophisticated ATS (Applicant Tracking System) scanner with deep understanding of hiring criteria. Provide a detailed analysis based on the role provided below including:
        1. Estimated match score (percentage) (Quantified from 0-100%).
        2. A list of relevant keywords or skills that are typically expected for this role.
        3. Which important keywords are missing or underrepresented in my resume.
        4. Suggestions to improve ATS optimization (formatting, wording, etc.).
        5. Detailed improvements needed to better tailor my resume to this role (content, structure, accomplishments, etc.).

        Format the response with clear sections, bullet points for readability, and highlight critical recommendations.
        
        Resume:
        {resume_text}
        """

    # Resume Analysis with Job Description
    elif analysis_type == "resume_jd_analysis":
        base_prompt = f"""
        You are an experienced HR specialist and career consultant with a deep understanding of hiring practices across diverse industries - including technical, non-technical, creative, healthcare, business, and management roles; Compare the candidate's resume with the job description and give a professional assessment.

        Resume:
        {resume_text}

        Job Description:
        {job_description}

        Your assessment should cover:
        1. How well the resume fits the job role
        2. Which skills match the job requirements
        3. Missing or underdeveloped skills
        4. Strengths and weaknesses related to the job
        5. Recommend relevant skills or certifications to improve the candidate's profile
        6. Suggest suitable courses or training programs based on gaps identified.
        7. Evaluate the candidate's readiness for a technical role.
        8. List both technical and soft skills found in the resume.
        9. Suggest specific projects the candidate should complete to address gaps.
        10. Recommendations Summary
        """

    # Resume Analysis, Job Description with ATS Score
    elif analysis_type == "resume_jd_score":
        base_prompt = f"""
        You are a sophisticated ATS (Applicant Tracking System) scanner with deep understanding of hiring criteria. Provide a detailed match analysis including:
        1. Overall match percentage (Quantified from 0-100%).
        2. Profile Summary.
        3. Top 5 matching keywords/skills found in both resume and job description.
        4. Top 5 missing or underemphasized keywords/skills from the job description.
        5. Specific sections to improve for better ATS optimization.
        6. 2-3 concrete suggestions for enhancing the resume's match potential.
        
        Format the response with clear sections, bullet points for readability, and highlight critical recommendations.

        Resume:
        {resume_text}

        Job Description:
        {job_description}
        """    

    response = model.generate_content(base_prompt)

    analysis = response.text.strip()
    formatted_analysis = markdown2.markdown(analysis)
    return render_template("resumeradarResponse.html", analysis=formatted_analysis)

# Build Resume
@app.route("/resumeBuilder", methods=["GET"])
def resumeBuilder():
    files = [
        f for f in os.listdir(TEMP_DIR)
        if f.endswith('.pdf') and not f.startswith("resumeradar_pdf")
    ]

    return render_template("resumeBuilder.html", files=files)

# Rebuild ATS Resume
@app.route("/rebuildATS", methods=["POST"])
def rebuildATS():
    filename = request.form.get("resume_filename")
    pdf_path = os.path.join(TEMP_DIR, filename)
    
    resume_text = extract_text_from_pdf(pdf_path)

    if not resume_text:
        return render_template("error.html", error_code="400", message="Resume text is required for this!") # Text extraction from the PDF file is failing.
    
    model = genai.GenerativeModel("gemini-2.0-flash")

    base_prompt = f"""
    You are a sophisticated ATS (Applicant Tracking System) scanner with deep understanding of hiring criteria, professional resume writer and career expert. The provided resume which may not be ATS-friendly.
    Please analyze and Refine the content into a clean, modern, ATS-compliant resume using the points below:
    1. Use professional formatting. Keep the tone clear and direct.
    2. Use standard resume sections
    3. Ensure formatting is ATS-friendly (no tables, fancy designs).
    4. Use professional language, plain headings and proper bulleting.
    5. Highlight responsibilities and achievements using bullet points.
    6. Emphasize relevant technical and soft skills.
    7. Keep everything concise, relevant, and job-targeted.

    Resume:
    {resume_text}

    At the end, provide:
    1. Complete formatted resume.
    2. Estimated Match Score: (0-100%).
    """ 

    response = model.generate_content(base_prompt)
    
    analysis = response.text.strip()
    formatted_analysis = markdown2.markdown(analysis)
    return render_template("resumeradarResponse.html", analysis=formatted_analysis)

# Build ATS Resume
@app.route("/buildATS", methods=["POST"])
def buildATS():
    model = genai.GenerativeModel("gemini-2.0-flash")
    
    user_data = {
        "user_level": request.form.get("user_level"),
        "name": request.form.get("name"),
        "email": request.form.get("email"),
        "phone": request.form.get("phone", ""),
        "role": request.form.get("role"),
        "education": request.form.get("education"),
        "skills": request.form.get("skills"),
        "projects": request.form.get("projects"),
        "experience": request.form.get("experience", ""),
        "certifications": request.form.get("certifications", ""),
        "soft_skills": request.form.get("soft_skills", "")
    }

    base_prompt = f"""
    You are a sophisticated ATS (Applicant Tracking System) scanner with deep understanding of hiring criteria, professional resume writer and career expert. Build a complete ATS-friendly resume for a {user_data['user_level']} level candidate with Job Role {user_data['role']} using following user information:
    1. Name: {user_data['name']}
    2. Email: {user_data['email']}
    3. Phone: {user_data['phone']}
    4. Education: {user_data['education']}
    5. Skills: {user_data['skills']}
    6. Projects: {user_data['projects']}
    7. Experience: {user_data['experience']}
    8. Certifications: {user_data['certifications']}
    9. Soft Skills: {user_data['soft_skills']}

    -Use professional formatting. Keep the tone clear and direct.
    -Use standard resume sections
    -Ensure formatting is clean and ATS-friendly.
    -Avoid fancy tables, use plain headings and bullet points.
    -Use professional language and proper bulleting.
    """

    response = model.generate_content(base_prompt)
    
    analysis = response.text.strip()
    formatted_analysis = markdown2.markdown(analysis)
    return render_template("resumeradarResponse.html", analysis=formatted_analysis)

# Build Cover Letter
@app.route("/coverLetterBuilder", methods=["GET"])
def coverLetterBuilder():
    files = [
        f for f in os.listdir(TEMP_DIR)
        if f.endswith('.pdf') and not f.startswith("resumeradar_pdf")
    ]

    return render_template("coverLetterBuilder.html", files=files)

@app.route("/coverLetterBuild", methods=["POST"])
def coverLetterBuild():
    filename = request.form.get("resume_filename")
    pdf_path = os.path.join(TEMP_DIR, filename)
    
    resume_text = extract_text_from_pdf(pdf_path)
    build_type = request.form.get("build_type")
    job_description = request.form.get("job_description")
    
    if not resume_text:
        return render_template("error.html", error_code="400", message="Resume text is required for this!") # Text extraction from the PDF file is failing.
    if build_type in ["coverLetterJD"] and not job_description.strip():
        return render_template("error.html", error_code="422", message="JJob Description is required for this! Please check and try again.") # Ensure the user is filling out the job description field in the form before submitting.
    
    model = genai.GenerativeModel("gemini-2.0-flash")

    # Cover Letter (Resume)
    if build_type == "coverLetterResume":
        base_prompt = f"""
        You have a deep understanding of hiring criteria, and you are an professional resume writer and career consultant. Based on the provided resume, write a professional cover letter that highlights the candidate's skills, experience, and qualifications. Make it concise, clear, and tailored to showcase the strengths listed in the resume.

        Resume:
        {resume_text}
        """

    # Cover Letter (Resume + Job Description)
    elif build_type == "coverLetterJD":
        base_prompt = f"""
        You have a deep understanding of hiring criteria, and you are an professional resume writer and career consultant. Based on the provided resume and job description, write a personalized cover letter. The letter should address the key qualifications required for the role and highlight the candidate's relevant skills and experiences as per the job description.

        Resume:
        {resume_text}

        Job Description:
        {job_description}
        """ 

    response = model.generate_content(base_prompt)

    analysis = response.text.strip()
    formatted_analysis = markdown2.markdown(analysis)
    return render_template("resumeradarResponse.html", analysis=formatted_analysis)

# Mock Interview Preparation
@app.route("/mockInterviewPreparation", methods=["GET"])
def mockInterviewPreparation():
    files = [
        f for f in os.listdir(TEMP_DIR)
        if f.endswith('.pdf') and not f.startswith("resumeradar_pdf")
    ]

    return render_template("mockInterviewPreparation.html", files=files)

@app.route("/mockInterview", methods=["POST"])
def mockInterview():
    filename = request.form.get("resume_filename")
    pdf_path = os.path.join(TEMP_DIR, filename)
    
    resume_text = extract_text_from_pdf(pdf_path)
    interview_type = request.form.get("interview_type")
    job_description = request.form.get("job_description")
    
    if not resume_text:
        return render_template("error.html", error_code="400", message="Resume text is required for this!") # Text extraction from the PDF file is failing.
    if interview_type in ["mockInterviewResumeJD"] and not job_description.strip():
        return render_template("error.html", error_code="422", message="Job Description is required for this! Please check and try again.") # Ensure the user is filling out the job description field in the form before submitting.
    
    model = genai.GenerativeModel("gemini-2.0-flash")

    # Mock Interview Preparation (Resume)
    if interview_type == "mockInterviewResume":
        base_prompt = f"""
        You are a professional interviewer and career consultant skilled in evaluating candidates across various domains - including technical, non-technical, creative, healthcare, business, and management roles; Based on the provided resume - generate a mock interview session including:
        1. Ask 12-15 realistic questions that assess technical, behavioral, and domain-specific strengths.
        2. Provide sample answers a top-performing candidate would likely give. 
        3. Keep tone and flow similar to a real-life interview.
        4. Vary questions according to experience level, domain, and skills listed in the resume.

        Resume:
        {resume_text}
        """

    # Mock Interview Preparation (Resume + Job Description)
    elif interview_type == "mockInterviewResumeJD":
        base_prompt = f"""
        You are a professional interviewer designing a job-specific mock interview and career consultant skilled in evaluating candidates across various domains - including technical, non-technical, creative, healthcare, business, and management roles; Based on the provided resume and job description - generate a mock interview session including:
        1. Ask 12-15 realistic questions that assess technical, behavioral, and domain-specific strengths.
        2. Provide sample answers a top-performing candidate would likely give. 
        3. Align the questions with the skills, tools, responsibilities, and keywords mentioned in the job description.
        4. Keep tone and flow similar to a real-life interview.
        
        Resume:
        {resume_text}

        Job Description:
        {job_description}
        """ 

    response = model.generate_content(base_prompt)

    analysis = response.text.strip()
    formatted_analysis = markdown2.markdown(analysis)
    return render_template("resumeradarResponse.html", analysis=formatted_analysis)

# Career Opportunities
@app.route("/careerOpportunities")
def careerOpportunities():
    return render_template("careerOpportunities.html")

# Explore Career Opportunities
@app.route("/exploreOpportunities", methods=["POST"])
def exploreOpportunities():
    user_level = request.form.get('user_level', '')
    role = request.form.get('role', '')
    work_type = request.form.get('work_type', '')
    country = request.form.get('country', '')
    state = request.form.get('state', '')

    # If Remote, skip location
    location = 'Remote' if work_type.lower() == 'remote' else f'{state} {country}'.strip()

    # Build full role title
    role_query = f"{role} {user_level}".strip()

    # Build Google query
    google_query = f'site:linkedin.com/jobs "{role_query}" "{work_type}" "{location}" '

    # Clean & encode the search string
    cleaned_query = " ".join(google_query.split())
    encoded_query = urllib.parse.quote_plus(cleaned_query)

    # Redirect to search results
    search_url = f"https://www.google.com/search?q={encoded_query}"

    return render_template("resumeradarQueryResponse.html", search_url=search_url)

# Find People
@app.route("/findPeople")
def findPeople():
    return render_template("findPeople.html")

# Find Right People
@app.route("/findRightPeople", methods=["POST"])
def findRightPeople():
    skill = request.form.get('skill', '')
    role = request.form.get('role', '')
    state = request.form.get('state', '')

    # LinkedIn
    linkedin = f'https://www.google.com/search?q=+"{role}"+"{state}" -intitle:"profiles" -inurl:"dir/+"+site:in.linkedin.com/in/+OR+site:in.linkedin.com/pub/'

    # GitHub
    github = f'http://www.google.com/search?q=site:github.com+"joined on" -intitle:"at master" -inurl:"tab" -inurl:"jobs." -inurl:"articles"+"{skill}"+"{state}"'

    return render_template("resumeradarQueryResponse.html", linkedin=linkedin, github=github)

# About Project
@app.route("/aboutProject")
def aboutProject():
    return render_template("aboutProject.html")

# Contact Us
@app.route("/contactUs")
def contactUs():
    return render_template("contactUs.html")

# Generate PDF
@app.route('/download_pdf', methods=['POST'])
def download_pdf():
    analysis_html = request.form.get('analysis', '')

    class PDF(FPDF):
        def header(self):
            self.add_font('Poppins-Bold', '', 'fonts/Poppins-Bold.ttf', uni=True)
            self.set_font('Poppins-Bold', '', 10)
            self.set_left_margin(15)
            self.set_right_margin(15)
            self.cell(0, 10, "ResumeRadar", border=0, align="R")
            self.ln(8)

        def footer(self):
            self.set_y(-15)
            self.add_font('Poppins-Bold', '', 'fonts/Poppins-Bold.ttf', uni=True)
            self.set_font('Poppins-Bold', '', 10)
            self.cell(0, 10, "Developed by Insight Strikers", border=0, align="L")
            self.cell(0, 10, f"{self.page_no()}", border=0, align="R")

    # Parse HTML
    soup = BeautifulSoup(analysis_html, "html.parser")

    # Setup PDF
    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font('Poppins-Regular', '', 'fonts/Poppins-Regular.ttf', uni=True)
    pdf.add_font('Poppins-Bold', '', 'fonts/Poppins-Bold.ttf', uni=True)
    pdf.set_font('Poppins-Regular', '', 8)
    pdf.set_text_color(0, 0, 0)

    # Render content
    for elem in soup.contents:
        if elem.name == 'p':
            for child in elem.children:
                if child.name == 'strong':
                    pdf.set_font('Poppins-Bold', '', 8)
                    pdf.write(5, child.get_text(strip=True) + ' ')
                    pdf.set_font('Poppins-Regular', '', 8)
                elif child.string:
                    pdf.write(5, child.string.strip() + ' ')
            pdf.ln(8)

        elif elem.name == 'ul':
            for li in elem.find_all('li'):
                pdf.cell(5, 5, u'\u2022', 0, 0)
                for child in li.children:
                    if child.name == 'strong':
                        pdf.set_font('Poppins-Bold', '', 8)
                        pdf.write(5, child.get_text(strip=True) + ' ')
                        pdf.set_font('Poppins-Regular', '', 8)
                    elif child.string:
                        pdf.write(5, child.string.strip() + ' ')
                pdf.ln(6)
            pdf.ln(2)

    # Save PDF
    timestamp = datetime.datetime.now().strftime("%H%M%S%d%m%Y")
    output_path = os.path.join(TEMP_DIR, f"resumeradar_pdf_{timestamp}.pdf")
    # output_path = f"E:/CE_79_Nishchal_Kansara/Python_Project/ResumeRadar1/userFiles/resumeradar_pdf_{timestamp}.pdf"
    pdf.output(output_path)

    return send_file(output_path, as_attachment=True)

if __name__ == "__main__":
    if not os.path.exists('userFiles'):
        os.makedirs('userFiles')
    app.run(debug=True)
