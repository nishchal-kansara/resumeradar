import os
import markdown2

from fpdf import FPDF
import datetime
from bs4 import BeautifulSoup

from flask import Flask, render_template, request, send_file

from dotenv import load_dotenv
import google.generativeai as genai

from PIL import Image
from pdf2image import convert_from_path
import pytesseract
import pdfplumber

from io import BytesIO

app = Flask(__name__)
# app.config['UPLOAD_FOLDER'] = 'uploads'
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

    # Fallback to OCR for image-based PDFs
    print("Falling back to OCR for image-based PDF.")
    try:
        images = convert_from_path(pdf_path)
        for image in images:
            page_text = pytesseract.image_to_string(image)
            text += page_text + "\n"
    except Exception as e:
        print(f"OCR failed: {e}")

    return text.strip()

# Upload Resume
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files["resume_pdf"]
        if file and file.filename.endswith(".pdf"):
            # file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
            file_path = os.path.join(TEMP_DIR, file.filename)  # Save to /tmp on Vercel
            file.save(file_path)
            return render_template("index.html", uploaded=True)
    return render_template("index.html")

# Select Resume
@app.route("/select_resume", methods=["GET"])
def select_resume():
    # files = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if f.endswith('.pdf')]
    files = [f for f in os.listdir(TEMP_DIR) if f.endswith('.pdf')]
    return render_template("select_resume.html", files=files)

# Problem Statement
@app.route("/problem_solution")
def problem_solution():
    return render_template("problem_solution.html")

# Analyze Resume
@app.route("/analyze_resume", methods=["POST"])
def analyze_resume():
    filename = request.form.get("resume_filename")
    # pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    pdf_path = os.path.join(TEMP_DIR, filename)
    resume_text = extract_text_from_pdf(pdf_path)
    if not resume_text:
        return {"error": "Resume text is required for analysis."}

    model = genai.GenerativeModel("gemini-2.0-flash")

    base_prompt = f"""
    You are an experienced HR with technical knowledge in one of these roles: Data Scientist, Data Analyst, DevOps Engineer, Machine Learning Engineer, Prompt Engineer, AI Engineer, Full Stack Web Developer, Big Data Engineer, Marketing Analyst, HR Manager, or Software Developer; review the provided resume and give a professional assessment on job fit, list existing skills, suggest skills to improve, recommend relevant courses, and highlight key strengths and weaknesses.

    Resume:
    {resume_text}
    """

    response = model.generate_content(base_prompt)

    analysis = response.text.strip()
    formatted_analysis = markdown2.markdown(analysis)
    return render_template("resume_analysis.html", analysis=formatted_analysis)

# Analyze Resume with JD
@app.route("/analyze_resume_jd", methods=["POST"])
def analyze_resume_jd():
    filename = request.form.get("resume_filename")
    job_description = request.form.get("job_description")
    # pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    pdf_path = os.path.join(TEMP_DIR, filename)
    resume_text = extract_text_from_pdf(pdf_path)
    if not resume_text:
        return {"error": "Resume text is required for analysis."}
    if not job_description:
        return {"error": "Job Description is required for analysis."}

    model = genai.GenerativeModel("gemini-2.0-flash")

    base_prompt = f"""
    You are an experienced HR with technical knowledge in one of these roles: Data Scientist, Data Analyst, DevOps Engineer, Machine Learning Engineer, Prompt Engineer, AI Engineer, Full Stack Web Developer, Big Data Engineer, Marketing Analyst, HR Manager, or Software Developer; review the provided resume and give a professional assessment on job fit, list existing skills, suggest skills to improve, recommend relevant courses, and highlight key strengths and weaknesses.

    Resume:
    {resume_text}
    """

    if job_description:
        base_prompt += f"""
        Now, compare the candidate's resume with the job description below:

        Job Description:
        {job_description}

        Your analysis should cover:
          -How well the resume fits the job role
          -Which skills match the job requirements
          -Missing or underdeveloped skills
          -Strengths and weaknesses related to the job
          -Recommend relevant skills or certifications to improve the candidate's profile
          -Suggest suitable courses or training programs based on gaps identified.
          -Evaluate the candidate’s readiness for a technical role.
          -List both technical and soft skills found in the resume.
          -Suggest specific projects the candidate should complete to address gaps
        """

    response = model.generate_content(base_prompt)

    analysis = response.text.strip()
    formatted_analysis = markdown2.markdown(analysis)
    return render_template("resume_analysis.html", analysis=formatted_analysis)

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

    # Save PDF to BytesIO
    pdf_output = BytesIO()
    pdf.output(pdf_output)
    
    # Ensure the pointer is at the beginning
    pdf_output.seek(0)

    # Return the PDF as a downloadable file
    return send_file(pdf_output, as_attachment=True, download_name="resume_analysis.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    app.run(debug=True)
