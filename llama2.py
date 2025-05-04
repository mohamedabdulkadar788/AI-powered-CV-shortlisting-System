import streamlit as st
import subprocess
import fitz  # PyMuPDF
from docx import Document
import re
import chardet
import os
import shutil

# ---------- File Parsing Functions ----------

def extract_text_from_pdf(file):
    try:
        text = ""
        pdf = fitz.open(stream=file.read(), filetype="pdf")
        for page in pdf:
            text += page.get_text("text")
        return text, None
    except Exception as e:
        return None, f"Error extracting text from PDF: {e}"

def extract_text_from_docx(file):
    try:
        doc = Document(file)
        text = "\n".join(para.text for para in doc.paragraphs)
        return text, None
    except Exception as e:
        return None, f"Error extracting text from DOCX: {e}"

def decode_file_content(file_data):
    try:
        result = chardet.detect(file_data)
        encoding = result['encoding'] or 'utf-8'
        return file_data.decode(encoding), None
    except Exception as e:
        return None, f"Error decoding file content: {e}"

def clean_and_structure_text(text):
    try:
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n', text)
        return text.strip()
    except Exception:
        return text or ""

# ---------- LLaMA Prompt Runner ----------

def run_llama_prompt(prompt):
    try:
        # Check if the ollama CLI is accessible
        if not shutil.which("ollama"):
            return None, "LLaMA CLI (ollama) is not installed or not found in PATH."

        result = subprocess.run(
            ["ollama", "run", "llama3.2:latest", prompt],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip(), None
        else:
            err = result.stderr.strip() if result.stderr else "Unknown LLaMA subprocess error"
            return None, f"LLaMA Error: {err}"
    except Exception as e:
        return None, f"Unexpected error: {e}"

# ---------- Skills Extraction ----------

def extract_skills(jd_text):
    prompt = f"""
    Extract all the skills mentioned in the following job description, including technical, tools, and soft skills.

    Job Description:
    {jd_text}

    Skills:
    """
    return run_llama_prompt(prompt)

# ---------- CV Processing ----------

def process_cv_with_llama(jd_text, cv_text, min_experience):
    prompt = f"""
    Job Description:
    {jd_text}

    CV:
    {cv_text}

    Question:
    Shortlist the CV only if the following are all true:
    1. Analyze the CV's job title by reading the whole CV. Make sure that the title in JD matches with the analyzed job title of CVs
    2. Experience >= {min_experience} years.
    3. All technical skills in JD matches exactly with the CV.
    4. Soft skills in JD are reflected in CV.

    If not shortlisted, explain why and suggest improvements.
    If shortlisted, explain why and highlight matches.
    I need accurate shortlisting of candidates.

    Output:
    """
    return run_llama_prompt(prompt)

# ---------- Streamlit UI ----------

def main():
    st.title("AI-Powered JD & CV Shortlisting System")

    # Input Job Description
    job_description = st.text_area("Paste Job Description", height=200)

    # Minimum Experience Input
    min_experience = st.number_input(
        "Minimum Years of Experience",
        min_value=0,
        max_value=50,
        step=1,
        value=0
    )

    # Extract Skills Button
    if st.button("Extract Skills"):
        if job_description.strip():
            with st.spinner("Extracting skills..."):
                skills, error = extract_skills(job_description)
                if skills:
                    st.success("Skills extracted:")
                    st.write(skills)
                else:
                    st.error(error)
        else:
            st.warning("Please enter a Job Description.")

    # Upload CVs
    uploaded_files = st.file_uploader(
        "Upload up to 5 CVs (PDF, DOCX, or TXT)",
        type=["pdf", "docx", "doc", "txt"],
        accept_multiple_files=True
    )

    if uploaded_files and len(uploaded_files) > 5:
        st.warning("Only the first 5 files will be processed.")
        uploaded_files = uploaded_files[:5]

    # Shortlisting
    if st.button("Shortlist Candidates"):
        if not job_description.strip():
            st.warning("Please enter a Job Description.")
        elif not uploaded_files:
            st.warning("Please upload at least one CV.")
        else:
            jd_text = job_description.strip()

            for file in uploaded_files:
                st.markdown(f"### Processing: `{file.name}`")
                try:
                    # Extract CV text
                    if file.name.endswith(".pdf"):
                        cv_text, error = extract_text_from_pdf(file)
                    elif file.name.endswith(".docx") or file.name.endswith(".doc"):
                        cv_text, error = extract_text_from_docx(file)
                    elif file.name.endswith(".txt"):
                        file_data = file.read()
                        cv_text, error = decode_file_content(file_data)
                    else:
                        error = "Unsupported file format."
                        cv_text = None

                    if error:
                        st.error(f"{file.name}: {error}")
                        continue

                    if not cv_text:
                        st.error(f"{file.name}: Empty or unreadable content.")
                        continue

                    # Clean CV text
                    cv_text = clean_and_structure_text(cv_text)

                    # Run LLaMA shortlisting
                    response, err = process_cv_with_llama(jd_text, cv_text, min_experience)

                    if err:
                        st.error(f"{file.name}: {err}")
                    elif response and "shortlisted" in response.lower():
                        st.success(f"✅ {file.name} is shortlisted!")
                        st.write(response)
                    else:
                        st.warning(f"❌ {file.name} is not shortlisted.")
                        st.write(response or "No explanation returned.")
                except Exception as e:
                    st.error(f"{file.name}: Unexpected error - {e}")

main()