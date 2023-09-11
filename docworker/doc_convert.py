"""
Function to take a file, covert the file to text, and return
content divided into chunks
"""

from . import section_util
from . import extract_docx
import io
import mimetypes
import tiktoken
import logging
import pdfplumber


def read_file(filename: str, file: io.BytesIO) -> str:
  """
  Reads a Text, DOCX, or PDF.
  Uses filename to detect the file type.

  Throws exception on failure.
  """
  (type, encoding)  = mimetypes.guess_type(filename)

  if type is None:
    raise DocError("Unknown file type")

  elif type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':

    docx_extract = extract_docx.DocXExtract()
    try:
      docx_extract.load_doc(file)
    except Exception as e:
      raise DocError("Not a valid DOCX file")
      in_file = docx_extract.get_result()
    in_file = docx_extract.get_result()
    text = in_file.read()
    return text

  elif type == 'application/pdf':
    pages = []
    pdf = pdfplumber.open(file)
    for page in pdf.pages:
      pages.append(page.extract_text_simple())
    text = '\n'.join(pages)
    return text

  elif type == 'text/plain':
    infile = io.TextIOWrapper(file, encoding='utf-8')
    text = infile.read()
    return text

  else:
    raise DocError("Unsupported file format: %s" % type)    

def clean_text(text: str):
  """
  Break text into lines and perform steps to clean up.
  """
  step1 = text.split('\n')
  step2 = []
  for line in step1:
    l2 = line.strip()
    if len(l2) > 0:
      step2.append(l2)
  return '\n'.join(step2)
  
def token_count(text: str):
  tokenizer = tiktoken.encoding_for_model(section_util.AI_MODEL)  
  return len(tokenizer.encode(text))

def chunk_text(text: str, chunk_size, overlap):
  """
  Divide text into sections no larger than chunk size along natural
  breaks. Overlap sections by overlap percent.
  """
  result = []
  if text is None:
    return result
  
  tokenizer = tiktoken.encoding_for_model(section_util.AI_MODEL)  
  text = clean_text(text)
  
  for chunk  in chunks(text, 
                       chunk_size,
                       tokenizer,
                       overlap):
    entry = section_util.Chunk()
    chunk_text = tokenizer.decode(chunk).strip()
    if len(chunk_text) > 0:
      entry.append(chunk_text, len(chunk))
      result.append(entry)
  return result
  
def docx_to_chunks(file: io.BytesIO) -> [section_util.Chunk]:
    docx_extract = extract_docx.DocXExtract()
    try:
      docx_extract.load_doc(file)
    except Exception as e:
      raise DocError("Not a valid DOCX file")
      in_file = docx_extract.get_result()
    in_file = docx_extract.get_result()
    return section_util.chunks_from_structured_file(in_file)

def chunks(text, n, tokenizer, overlap):
  # Split a text into smaller chunks of size n,
  # preferably ending at the end of a sentence.

  tokens = tokenizer.encode(text)
  """Yield successive n-sized chunks from text."""
  i = 0
  while i < len(tokens):
    # Find the nearest end of sentence within a range of 0.5 * n and n tokens

    j = min(i + int(1.0 * n), len(tokens))
    # Check for last section
    if i + n > len(tokens):
      j = len(tokens)
    else:
      # Reverse search for a natural break.
      j = rsearch_break(tokens, i, n, tokenizer)
    yield tokens[i:j]

    # If there is an overlap, start next chunk before end of current
    if overlap > 0 and j != len(tokens):
      delta = int((j - i) * overlap)
      # Search for break in portion between 3/2 and 1/2 delta prior to end.
      j = rsearch_break(tokens, j - int(3 * delta / 2), delta, tokenizer)
    i = j 

def rsearch_break(tokens, start, n, tokenizer):
  # Look for period - CR
  j = rsearch_break_str(tokens, start, n, ".\n", tokenizer)

  # If no period / CR found, just look for a period 
  if j == start + int(0.5 * n):
    j = rsearch_break_str(tokens, start, n, ".", tokenizer)
    
  # If no end of sentence found, use a CR
  if j == start + int(0.5 * n):
    j = rsearch_break_str(tokens, start, n, "\n", tokenizer)

  # If still no end of sentence found, use n tokens as the chunk size
  if j == start + int(0.5 * n):      
    j = min(start + n, len(tokens))

  return j
 
def rsearch_break_str(tokens, start, n, break_str, tokenizer):
  """
  Perform a reverse search on the tokens to find the break string.
  Starting at start + n, search backward up to 50% of the section to 
  match the break string. If found, return the end of the section.
  If not found, returns n / 2

  """
  j = min(start + n, len(tokens))
  while j > start + int(0.5 * n):
    # Decode the tokens and check for period
    # TODO: consider optimizing this and call only once
    chunk = tokenizer.decode(tokens[start:j])
    if chunk.endswith(break_str):
      logging.debug("broke chunk on %s: %d", break_str, j)
      break
    j -= 1
  return j



class DocError(Exception):
  pass
