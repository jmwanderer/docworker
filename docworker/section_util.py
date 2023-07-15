"""
Utility to chunk a doc considering the structure of the original document.
Attempts to keep sections and tables together when possible, split between
sections.

TODO:
- handle long lines
"""

import re
import tiktoken
import logging

TEXT_EMBEDDING_CHUNK_SIZE = 3000
MAX_TEXT_LINE_LEN = TEXT_EMBEDDING_CHUNK_SIZE / 2
AI_MODEL = "gpt-3.5-turbo"
AI_MODEL_SIZE = 4097

def chunks_from_structured_file(file):
  """
  Return an iterator of Chunk
  """
  top_section = parse_sections(file)
  #walk_section(top_section)  
  tokenizer = tiktoken.encoding_for_model(AI_MODEL)
  return chunks(top_section, tokenizer)

def get_tokenizer():
  return tiktoken.encoding_for_model(AI_MODEL)

class Chunk:
  """
  Instance of a chunk built from a structured file
  """
  def __init__(self):
    self.reset()
    
  def append(self, line, size):
    self.lines.append(line)
    self.size += size

  def reset(self):
    self.lines = []
    self.size = 0

  def append_chunk(self, chunk):
    for line in chunk.lines:
      self.lines.append(line)
    self.size += chunk.size

  def get_text(self):
    return '\n\n'.join(self.lines)

  
class Section:
  """
  Represents a section in a document that should be kept together
  as much as possible. Has sub-sections and text elements.
  """
  def __init__(self, parent, level):
    self.parent = parent
    self.level = level
    self.elements = []
    self.current_text_element = None

  def is_leaf(self):
    return False;

  def add_text(self, text):
    if self.current_text_element is None:
      self.new_text_block()
    self.current_text_element.add_text(text)

  def append_text(self, text):
    if self.current_text_element is None:
      self.new_text_block()
    self.current_text_element.append_text(text)

  def has_content(self):
    if len(self.elements) == 0:
      return False
    if (len(self.elements) == 1
        and self.elements[0].is_leaf()
        and len(self.elements[0].text_values) < 2):
      return False
    logging.debug("section has content, level = %d", self.level)
    return True

  def new_text_block(self):
    self.current_text_element = TextElement()
    self.elements.append(self.current_text_element)

  def new_sub_section(self, level):
    self.current_text_element = None
    new_section = Section(self, level)
    self.elements.append(new_section)    
    return new_section

  def size(self, tokenizer):
    size = 0
    for child in self.elements:
      size += child.size(tokenizer)
    return size

  def first_line(self):
    if len(self.elements) > 0 and self.elements[0].is_leaf():
      return self.elements[0].first_line()
    return None
    
      
class TextElement:
  """
  Element in a section that contains a set of text.
  Text values should not be split.
  """
  def __init__(self):
    self.text_values = []

  def add_text(self, text):
    if len(text) <= MAX_TEXT_LINE_LEN:
      self.text_values.append(text)
      # TODO: split line

  def append_text(self, text):
    if len(self.text_values) == 0:
      self.add_text(text)
    else:
      if len(self.text_values[-1]) > 0:
        self.text_values[-1] = self.text_values[-1] + '\n'
      self.text_values[-1] = self.text_values[-1] + text        
        

  def is_leaf(self):
    return True;

  def size(self, tokenizer):
    size = 0
    for text in self.text_values:
      tokens = tokenizer.encode(text)
      size += len(tokens)
    return size

  def first_line(self):
    if len(self.text_values) > 0:
      return self.text_values[0]
  

class Document:
  def __init__(self):
    self.doc_lines = []

  def load_file(self, file):
    self.doc_lines = file.readlines()

  def more_lines(self):
    return len(self.doc_lines) > 0
  
  def next_line(self):
    if len(self.doc_lines) == 0:
      return None
    return self.doc_lines.pop(0).strip()

def read_table(doc, section):
  done = False
  while doc.more_lines() and not done:
    line = doc.next_line()
    if line == '</table>':
      done = True
    elif line == '<row>':
      section.add_text('')
    else:
      section.append_text(line)

def find_section_level(section, level):
  if section.parent == None:
    return section
  if section.level < level:
    return section
  return find_section_level(section.parent, level)

def chunks(top_section, tokenizer):
  result = Chunk()
  element_stack = []
  element_stack.append(top_section)

  while len(element_stack) > 0:
    element = element_stack.pop()
    
    # if adding new content is too big and the current result
    # isn't tiney, yield current results
    size = element.size(tokenizer)
    if (result.size > TEXT_EMBEDDING_CHUNK_SIZE / 10 and
        size + result.size > TEXT_EMBEDDING_CHUNK_SIZE):
      # Check for a small current result and a next leaf chunk we will split
      # in any event.
      yield(result)
      result.reset()

    # for a sub-section, add child elements to the stack in reverse
    if not element.is_leaf():
      element.elements.reverse()
      for child in element.elements:
        element_stack.append(child)
      element.elements.reverse()
    else:
      # Add text to results
      for text in element.text_values:
        tokens = tokenizer.encode(text) 
        size = len(tokens)
        if result.size > 0 and size + result.size > TEXT_EMBEDDING_CHUNK_SIZE:
          yield(result)
          result.reset()

        if size > TEXT_EMBEDDING_CHUNK_SIZE:
          raise exception
        result.append(text, size)

  if result.size > 0:
    yield(result)
  result.reset()

def walk_section(section):
  print("%d: %s" % (section.level, section.first_line()))
  for child in section.elements:
    if not child.is_leaf():
      walk_section(child)

def parse_sections(file):
  doc = Document()
  doc.load_file(file)
  top_section = Section(None, -1)
  current_section = top_section

  while doc.more_lines():
    line = doc.next_line().strip()
    # skip blank lines
    if len(line) == 0:
      continue

    if line == '<table>':
      current_section.new_text_block()
      read_table(doc, current_section)
      current_section.new_text_block()    
      continue

    m = re.match('<Title>', line)
    if m is not None:
      level = 0
      if current_section.level != level or current_section.has_content():
        logging.debug('new section: %d: %s', level, line)
        parent = find_section_level(current_section, level)
        current_section = parent.new_sub_section(level)
      continue

    m = re.match('<Heading(\d)>', line)
    if m is not None:
      level = int(m.group(1))
      if current_section.level != level or current_section.has_content():
        logging.debug('new section: %d: %s', level, line) 
        parent = find_section_level(current_section, level)
        current_section = parent.new_sub_section(level)
      continue

    current_section.add_text(line)
  return top_section


def run_test():
  f = open('SCAP.txt')
  for chunk in chunks_from_structured_file(f):
    print("chunk: size = %d" % chunk.size)
    print(chunk.get_text())
  f.close()

if __name__ == "__main__":
  run_test()




    
    
    
    

