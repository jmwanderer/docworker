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


def doc_to_chunks(filename: str, file: io.BytesIO) -> [section_util.Chunk]:
  """
  Main function to process a file.
  Uses filename to detect the file type.

  Throws exception on failure.
  """
  (type, encoding)  = mimetypes.guess_type(filename)
  tokenizer = tiktoken.encoding_for_model(section_util.AI_MODEL)  

  if type is None:
    raise DocError("Unknown file type")

  elif type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
    return docx_to_chunks(file)

  elif type == 'application/pdf':
    pages = []
    pdf = pdfplumber.open(file)
    for page in pdf.pages:
      pages.append(page.extract_text_simple())
    text = '\n'.join(pages)
    result = []    
    for chunk  in chunks(text, 
                         section_util.TEXT_EMBEDDING_CHUNK_SIZE,
                         tokenizer):
      entry = section_util.Chunk()
      chunk_text = tokenizer.decode(chunk).strip()
      if len(chunk_text) > 0:
        entry.append(chunk_text, len(chunk))
        result.append(entry)
    return result

  elif type == 'text/plain':
    infile = io.TextIOWrapper(file, encoding='utf-8')
    text = infile.read()
    result = []    
    for chunk  in chunks(text, 
                         section_util.TEXT_EMBEDDING_CHUNK_SIZE,
                         tokenizer):
      entry = section_util.Chunk()
      chunk_text = tokenizer.decode(chunk).strip()
      if len(chunk_text) > 0:
        entry.append(chunk_text, len(chunk))
        result.append(entry)
    return result

  else:
    raise DocError("Unsupported file format: %s" % type)    

  
def docx_to_chunks(file: io.BytesIO) -> [section_util.Chunk]:
    docx_extract = extract_docx.DocXExtract()
    try:
      docx_extract.load_doc(file)
    except Exception as e:
      raise DocError("Not a valid DOCX file")
      in_file = docx_extract.get_result()
    in_file = docx_extract.get_result()
    return section_util.chunks_from_structured_file(in_file)

def chunks(text, n, tokenizer):
  # Split a text into smaller chunks of size n,
  # preferably ending at the end of a sentence.

  tokens = tokenizer.encode(text)
  """Yield successive n-sized chunks from text."""
  i = 0
  while i < len(tokens):
    # Find the nearest end of sentence within a range of 0.5 * n and n tokens
    j = min(i + int(1.0 * n), len(tokens))
    while j > i + int(0.5 * n):
      # Decode the tokens and check for period
      chunk = tokenizer.decode(tokens[i:j])
      if chunk.endswith("."):
        break
      j -= 1

    # If no end of sentence found, use n tokens as the chunk size
    if j == i + int(0.5 * n):
      j = min(i + int(1.0 * n), len(tokens))
      while j > i + int(0.5 * n):
        # Decode the tokens and check for full stop or newline
        chunk = tokenizer.decode(tokens[i:j])
        if chunk.endswith("\n"):
          break
        j -= 1

    # If still no end of sentence found, use n tokens as the chunk size
    if j == i + int(0.5 * n):      
      j = min(i + n, len(tokens))
    yield tokens[i:j]
    i = j

class DocError(Exception):
  pass
