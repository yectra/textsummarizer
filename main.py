from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
import PyPDF2
import aiofiles
import docx
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
import nltk
import os
import tempfile

nltk_cache_path = tempfile.mkdtemp()
nltk.data.path.append(nltk_cache_path)

if not os.path.exists(os.path.join(nltk_cache_path, 'tokenizers', 'punkt')):
    nltk.download('punkt', download_dir=nltk_cache_path)

app = FastAPI()

def extract_text_from_pdf(pdf_path):
    text = ""
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfFileReader(file)
        for page_num in range(pdf_reader.numPages):
            page = pdf_reader.getPage(page_num)
            text += page.extractText()
    return text

def extract_text_from_doc(doc_path):
    text = ""
    doc = docx.Document(doc_path)
    for paragraph in doc.paragraphs:
        text += paragraph.text
    return text

def extract_text_from_txt(txt_path):
    with open(txt_path, 'r') as file:
        text = file.read()
    return text

def summarize_text(text, paragraph_length):
    if paragraph_length == 'short':
        max_sentences = 4
    elif paragraph_length == 'medium':
        max_sentences = 8
    elif paragraph_length == 'long':
        max_sentences = 16
    else:
        raise HTTPException(status_code=400, detail="Invalid paragraph length. Please choose 'short', 'medium', or 'long'.")
    
    parser = PlaintextParser.from_string(text, Tokenizer("english"))
    summarizer = LsaSummarizer()
    summary = summarizer(parser.document, max_sentences)
    # Join the list of sentences into a single string
    return " ".join([str(sentence) for sentence in summary])

# Define the summarize_to_bullet_points function
def summarize_to_bullet_points(text, num_points):
    # Clean the input text to remove extra whitespace and newline characters
    cleaned_text = " ".join(text.split())

    # Summarize the cleaned text
    parser = PlaintextParser.from_string(cleaned_text, Tokenizer("english"))
    summarizer = LsaSummarizer()
    summary = summarizer(parser.document, num_points)  

    # Take the first 'num_points' sentences from the summary
    bullet_points = [str(sentence) for sentence in summary]
    sentences = text.split(".")
    return bullet_points

@app.post("/paragraph")
async def summarize_paragraph_from_copy_paste(input_text: str = Form(...), paragraph_length: str = Form(...)):
    return summarize_text(input_text, paragraph_length)


@app.post("/summarize/bullet_points/", response_class=HTMLResponse)
async def summarize_bullet_points_from_text(text: str = Form(...), num_points: int = Form(...)):
    # Summarize the text to bullet points
    bullet_points = summarize_to_bullet_points(text, num_points)
    
    # Format the bullet points with the • character and concatenate with newline characters for line breaks
    bullet_point_text = "\n".join([f"• {sentence}" for sentence in bullet_points])

    return bullet_point_text.strip()

@app.post("/upload", response_class=HTMLResponse)
async def extract_text_from_uploaded_file_and_summarize(
    file: UploadFile = File(...),
    output_format: str = Form(...),
    num_points: int = Form(None),
    paragraph_length: str = Form(None),
):
    if output_format not in ['paragraph', 'bullet_points']:
        raise HTTPException(status_code=400, detail="Invalid output format. Please choose 'paragraph' or 'bullet_points'.")
    if output_format == "paragraph" and (num_points is not None or paragraph_length is None):
        raise HTTPException(status_code=400, detail="For paragraph summarization, please select a paragraph length ('short', 'medium', or 'long').")
    
    if output_format == "bullet_points" and (paragraph_length is not None or num_points is None):
        raise HTTPException(status_code=400, detail="For bullet points summarization, please provide the number of bullet points.")
    
    temp_file_path = f"/tmp/{file.filename}"
    async with aiofiles.open(temp_file_path, "wb") as buffer:
        await buffer.write(await file.read())
        
    # Determine the file type and extract text
    if file.filename.lower().endswith('.pdf'):
        text = extract_text_from_pdf(temp_file_path)
    elif file.filename.lower().endswith('.doc') or file.filename.lower().endswith('.docx'):
        text = extract_text_from_doc(temp_file_path)
    elif file.filename.lower().endswith('.txt'):
        text = extract_text_from_txt(temp_file_path)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    
    # Delete the temporary file
    os.remove(temp_file_path)
    
    if output_format == "bullet_points":
        summarized_text = summarize_to_bullet_points(text, num_points)
        bullet_point_text = "\n".join([f"• {sentence}" for sentence in summarized_text])
        return bullet_point_text.strip()

    elif output_format == "paragraph":
        summarized_text = summarize_text(text, paragraph_length)
        # Return the list of sentences as is
        return summarized_text
    else:
        raise HTTPException(status_code=400, detail="Invalid output format. Please choose 'paragraph' or 'bullet_points'.")
