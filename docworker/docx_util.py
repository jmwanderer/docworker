"""
Utilitiy to work with information from DOCX files and the OpenAI
LLM. This utility supports:
- reading a docx file and intelligently separating into sections
- supporting completions for each section
- completion of the completion results
- saving state
"""
from . import section_util
from . import doc_convert
import pickle
import re
import logging
import datetime
import tempfile
import hashlib
import os
import math
import time
from . import users
import tiktoken
import openai
import sqlite3

INITIAL_PROMPTS = [
  ('Summarize', 'Provide a summary'),  
  ('Summarize Main Points', 'Summarize the main points'),
  ('Summarize with Insights', 'Summarize and give a list of bullet points with key insights and the most important facts'),  
  ('Describe Main Ideas', 'Describe the main ideas'),
  ('Explain Concepts', 'Explain the concepts'),
  ('Explain Importantance', 'Explain why this is important'),
  ('What Should We Know', 'What should we know about this'),
  ('Help Understanding', 'Help me understand this'),
  ('List Target Dates', 'List deliverables and target dates'),
  ('Key Challenges', 'Describe the key challenges to be addressed'),      
  ('Explain Pirate', 'Explain like a pirate'),
  ('Explain Surfer', 'Explain like a surfer'),    
  ('List People', 'List the people that are mentioned'),
  ('List Topics', 'List the topics that are mentioned'),
  ]


class DynamicStatus:
  """
  State of running completion task.
  """
  def __init__(self):
    self.source_items = []
    self.to_run = []
    self.current_results = []    
    self.completed_run = []
    self.prompt = ""
    self.result_id = 0
    self.run_id = 0
    
  def start_run(self, prompt, item_ids):
    self.prompt = prompt
    self.to_run = item_ids.copy()
    self.source_items = item_ids.copy()    

  def next_item(self):
    if len(self.to_run) == 0:
      return None
    return self.to_run[0]

  def pop_item(self):
    id = self.to_run[0]
    self.to_run.pop(0)
    return id

  def skip_remaining_gen(self):
    """
    Detect case where one intermediate result is on the to_run list.
    Does not make sense to re-generate a single result for this process.
    """
    # Check if there is one item and it is not a source_id
    return (len(self.to_run) == 1 and
            not self.to_run[0] in self.source_items)
    
  def note_step_complete(self, result_id=None):
    if result_id is not None:
      self.completed_run.append(result_id)
      self.current_results.append(result_id)

  def next_result_set(self):
    """
    Switch to next set to process and return 
    True if there are more items to process.
    """
    if len(self.current_results) == 1:
      # End condition, one result produced.
      self.result_id = self.current_results[0]
      self.current_results = []
      return False

    if len(self.current_results) > 1:
      # More results to process 
      self.to_run = self.current_results
      self.current_results = []
      return True

    return False

  def is_last_completion(self):
    """
    Return true if the completion to be run will be the last.
    """
    return len(self.to_run) == 0 and len(self.current_results) == 0
    
  def in_additions(self, item_id):
    return (item_id != self.result_id and
            item_id in self.completed_run)

  def get_source_items(self):
    if not hasattr(self, 'source_items'):
      return []

    return self.source_items


class RunRecord:
  """
  Records a user session running a prompt.
  Includes the start time, run id, and (eventually) the final result id
  """

  def __init__(self, run_id, prompt_id, start_time=None):
    self.run_id = run_id
    self.start_time = start_time
    self.stop_time = None
    if self.start_time is None:
      self.start_time = datetime.datetime.now()
    self.result_id = 0
    self.prompt_id = prompt_id
    self.complete_steps = 0
    self.status_message = ""


class TextRecord:
  """
  A unit of text, either a chunk from a document or generated
  by a completion.
  """

  def __init__(self, id, name, text, token_count):
    self.id = id
    self.name = name
    self.text = text
    self.token_count = token_count
  
class Segment:
  """
  A segment of a structured document and a possible completion.
  """

  def __init__(self, text_record):
    self.text_record = text_record

  def id(self):
    return self.text_record.id

  def name(self):
    return self.text_record.name

  def suffix(self):
    m = re.match('.*\s(\d+)', self.name())
    if m:
      return m.group(1)
    return '0'

  def text(self):
    return self.text_record.text

  def token_count(self):
    return self.text_record.token_count

  def is_doc_segment(self):
    return True

  
class Completion:
  """
  A record of generated text that includes the input, prompt, and results.
  """
  def __init__(self, prompt_id, input_ids, text_record, token_cost):
    self.prompt_id = prompt_id
    self.input_ids = input_ids
    self.text_record = text_record
    self.token_cost = token_cost
    self.final_result = False
    
  def id(self):
    return self.text_record.id

  def name(self):
    return self.text_record.name

  def text(self):
    return self.text_record.text

  def token_count(self):
    return self.text_record.token_count

  def prompt_name(self, session):
    return session.get_prompt_name_by_id(self.prompt_id)

  def prompt(self, session):
    return session.get_prompt_by_id(self.prompt_id)

  def match_segment_id(self, id):
    """
    True if completion generated from the doc_segment identified by
    id.
    """
    return (len(self.input_ids) == 1 and self.input_ids[0] == id)

  def is_final_result(self):
    if not hasattr(self, 'final_result'):
      self.final_result = not self.doc_segment_name()
    return self.final_result

  def set_final_result(self):
    self.final_result = True

  def doc_segment_name(self):
    """
    True if the name of the completion implies it was generated for
    a doc segment
    """
    # TOOD: beter way to do this using ids.
    m = re.match('.*(\d+).\d+', self.name())
    if m:
      return m.group(1)
    return None

  def is_doc_segment(self):
    return False
    

class Session:
  """
  An instance of work on a structured document.
  """

  def __init__(self):
    self.status = DynamicStatus()
    self.md5_digest = b''
    self.next_run_id = 1
    self.run_list = []     # List of RunRecord instances
    self.name = None
    self.next_text_id = 1
    self.text_records = {}  # key is record_id
    self.doc_segments = []
    self.completions = []
    self.next_prompt_id = 0
    self.prompts = []
    for prompt in INITIAL_PROMPTS:
      self.add_prompt(prompt[0], prompt[1])

  def item_color(self, item):
    if item.is_doc_segment():
      return '#eeeeee'
    elif item.is_final_result():
      #return '#b7d7f5'
      return '#d9e8f6'
    else:
      #return '#efddfd'
      return '#e8e0ee'
    
  def fixup_prompts(self):
    """
    Update / fix prompts
    """
    # Fix up duplicate IDs
    if len(self.prompts) == 0:
      return
    id = self.prompts[0][0]
    new_list = []
    for prompt in self.prompts:
      new_list.append((id, prompt[1], prompt[2]))
      id += 1
    self.prompts = new_list
    self.next_prompt_id = id

    # Add / Change existing prompts
    for (name, value) in INITIAL_PROMPTS:
      prompt = self.get_prompt_by_name(name)
      # Does it exist?
      if prompt is None:
        self.add_prompt(name, value)
      elif prompt[2] != value:
        index = self.prompts.index(prompt)
        self.prompts[index] = (prompt[0], name, value)

  def strip_text(self, text):
    # combine multiple lines into one
    return text.replace('\n', ' ').replace('  ', ' ')

  def max_tokens(self):
    return section_util.TEXT_EMBEDDING_CHUNK_SIZE

  def snippet_text(self, text):
    if text is None:
      return None
    if len(text) < 90:
      return self.strip_text(text)
    return self.strip_text(text[0:45] + " ... " + text[-46:])

  def get_gen_items(self):
    """
    Return list of items associated with a gen run in an
    appropriate order for display.
    """
    # TODO: handle multi-level generation

    source_items = self.status.source_items.copy()
    result = []
    for id in self.status.completed_run:
      if id != self.status.result_id:
        completion = self.get_item_by_id(id)
        for source_id in completion.input_ids:
          source_item = self.get_item_by_id(source_id)
          if source_id in source_items:
            source_items.remove(source_id)
            result.append(source_item)            
        result.append(completion)
    for source_id in source_items:
      result.append(self.get_item_by_id(source_id))
      
    return result


  def get_ordered_items_visit_node(self, node, result):
    result.append(node)
    # TODO - make a BFS(?)
    for id in node.input_ids:
      child = self.get_item_by_id(id)
      # Visit children that were completions created for this node
      if not child.is_doc_segment() and not child.is_final_result():
        self.get_ordered_items_visit_node(child, result)
        
    
  def get_ordered_items(self):
    """
    Return the segments and completions is a logical order
    for display.
    """
    result = []

    # list completions
    for completion in self.completions:
      if completion.is_final_result():
        self.get_ordered_items_visit_node(completion, result)
        
    # add the segments
    for segment in self.doc_segments:
      result.append(segment)
            
    return result

  def comp_family_visit_node(self, depth, completion, result):
    """
    Helper function for get_completion_family.
    Recursively visit all children of the completion, building
    result list and returning the max_depth.
    """
    result.append((depth, completion))
    max = depth
    
    for id in completion.input_ids:
      child = self.get_item_by_id(id)
      # Visit children that were completions created for this node
      count = 0
      if child.is_doc_segment():
        result.append((depth + 1, child))
        count = depth + 1
      elif not child.is_final_result():
        count = self.comp_family_visit_node(depth + 1, child, result)
      if count > max:
        max = count
    return max
  

  def get_completion_family(self, id):
    """
    Return ordered list of for completion tree, with depth for
    every node, and the max depth of the tree.
    
    return: (max, list[])  - list entry: (depth, completion)
    """
    max_depth = 0
    result = []
    completion = self.get_item_by_id(id)
    if completion is None or completion.is_doc_segment():
      return (0, [])
    max_depth = self.comp_family_visit_node(1, completion, result)
    return (max_depth, result)

  def get_completion_family_list(self, id):
    """
    Return a simple list of completions in the family of the
    the specified completion.
    """
    result = []
    (max, list) = self.get_completion_family(id)
    for (depth, item) in list:
      if not item.is_doc_segment():
        result.append(item)
    return result
      

  def get_item_by_name(self, name):
    for segment in self.doc_segments:
      if segment.name() == name:
        return segment
    
    for completion in self.completions:
      if completion.name() == name:
        return completion

    return None

  def get_item_by_id(self, id):
    for segment in self.doc_segments:
      if segment.id() == id:
        return segment
    
    for completion in self.completions:
      if completion.id() == id:
        return completion

    return None
    
  def get_name_by_id(self, id):
    if id in self.text_records.keys():
      return self.text_records[id].name
    return None

  def get_names_for_ids(self, ids):
    names = []
    for id in ids:
      names.append(self.get_name_by_id(id))
    return ', '.join(names)

  def get_items_for_ids(self, ids):
    items = []
    for id in ids:
      name = self.get_name_by_id(id)
      item = self.get_item_by_name(name)
      if item is not None:
        items.append(item)
    return items

  def get_result_item_name(self, run_id=0):
    """
    Return the name of the result item.
    None if no result yet
    """
    item = self.get_result_item(run_id)
    if item is not None:
      return item.name()
    return None
  
  def get_result_item(self, run_id=None):
    """
    Return the final result item of the given completion run.
    """
    run_record = self.get_run_record(run_id)
    if run_record != None:
      return self.get_item_by_id(run_record.result_id)
    return None

  def get_run_record(self, run_id=None):
    """
    Return the matching run_record, or the curret one
    if no ID is specified.
    """
    if run_id is None:
      run_id = self.status.run_id
    # Look for matching run_id
    for run_record in self.run_list:
      if run_record.run_id == run_id:
        return run_record
    return None

  def is_running(self, run_id=None):
    # Time limit on how long a task can be considered running.
    run_record = self.get_run_record(run_id)
    if run_record is not None:    
      return (run_record.start_time is not None and
              run_record.stop_time is None and
              (datetime.datetime.now() -
               run_record.start_time).total_seconds() < 60 * 60)
    return False

  def complete_run(self):
    run_record = self.get_run_record()
    if run_record is not None:
      run_record.stop_time = datetime.datetime.now()
  
  def status_message(self, run_id=None):
    run_record = self.get_run_record(run_id)
    if run_record is not None:
      return run_record.status_message
    return None

  def set_status_message(self, message, run_id=None):
    run_record = self.get_run_record(run_id)
    if run_record is not None:
      run_record.status_message = message

  def prompt(self, run_id=None):
    run_record = self.get_run_record(run_id)
    if run_record is not None:
      return self.get_prompt_by_id(run_record.prompt_id)
    return None

  def completed_steps(self, run_id=None):
    run_record = self.get_run_record(run_id)
    if run_record is not None:
      return run_record.complete_steps
    return 0
    
  def note_step_complete(self, result_id=None):
    run_record = self.get_run_record()
    if run_record is not None:
      run_record.complete_steps += 1
    self.status.note_step_complete(result_id)
    
  def run_exists(self, run_id):
    """
    Return true if the run exists.
    """
    return self.get_run_record(run_id) is not None

  def doc_tokens(self):
    total = 0
    for segment in self.doc_segments:
      total += segment.token_count()
    return total

  def gen_tokens(self):
    total = 0
    for completion in self.completions:
      total += completion.token_count()
    return total
  
  def gen_cost_tokens(self):
    total = 0
    for completion in self.completions:
      total += completion.token_cost
    return total

  def segment_count(self):
    return len(self.doc_segments)

  def final_completion_count(self):
    count = 0
    for completion in self.completions:
      if completion.is_final_result():
        count += 1
    return count
  
  def new_text_record(self, name, text, token_count):
    text_record = TextRecord(self.next_text_id, name, text, token_count)
    self.text_records[self.next_text_id] = text_record
    self.next_text_id += 1
    return text_record

  def add_new_segment(self, text, token_count):
    # name of segment is just Block 1, Block 2, Block 3, ...
    name = "Block " + str(len(self.doc_segments) + 1)
    text_record = self.new_text_record(name, text, token_count)
    segment = Segment(text_record)
    self.doc_segments.append(segment)
    return segment

  def add_new_completion(self, prompt_id, input_ids, text,
                         token_count, token_cost):
    name = self.gen_completion_name(input_ids)
    text_record = self.new_text_record(name, text, token_count)
    completion = Completion(prompt_id, input_ids, text_record, token_cost)
    self.completions.append(completion)
    return completion

  def gen_completion_name(self, input_ids):
    # name of completion is either Generated <seg>.1, ... or
    # Generated 1, Generated 2, ...
    name_prefix = None
    seg_completion = False
    
    # Find if this is a completion for a specific doc segment.
    if len(input_ids) == 1:
      id = input_ids[0]
      for segment in self.doc_segments:
        if segment.text_record.id == id:
          seg_completion = True
          name_prefix = 'Generated ' + segment.suffix() + '.'
          break

    # Generated completion not based on a specific segement
    if name_prefix is None:
      name_prefix = 'Generated '

    # Count the number of instances with the prefix for next name
    count = 0
    for completion in self.completions:
      if (((seg_completion and completion.doc_segment_name()) or
          (not seg_completion and completion.doc_segment_name() is None)) and
          completion.text_record.name.startswith(name_prefix)):
        count += 1
    return name_prefix + str(count+1)

  def get_prompt_set(self):
    return self.prompts

  def get_prompt_id_by_name(self, name):
    for prompt in self.prompts:
      if prompt[1] == name:
        return prompt[0]
    return None

  def get_prompt_by_name(self, name):
    for prompt in self.prompts:
      if prompt[1] == name:
        return prompt
    return None

  def get_prompt_id(self, prompt_str):
    # Find a matching prompt, or create a new one
    for prompt in self.prompts:
      if prompt[2] == prompt_str:
        return prompt[0]
    name = prompt_str[0:max(12, len(prompt) - 1)] + '...'      
    id = self.add_prompt(name, prompt_str)
    return id

  def get_prompt_name_by_id(self, id):
    for prompt in self.prompts:
      if prompt[0] == id:
        return prompt[1]
    return None

  def get_prompt_by_id(self, id):
    for prompt in self.prompts:
      if prompt[0] == id:
        return prompt[2]
    return None

  def start_run(self, prompt, item_ids):
    self.status = DynamicStatus()
    self.status.run_id = self.next_run_id
    self.next_run_id += 1
    self.status.start_run(prompt, item_ids)
    prompt_id = self.get_prompt_id(prompt)    
    run_record = RunRecord(self.status.run_id,
                           prompt_id)
    run_record.status_message = "Running..."    
    self.run_list.append(run_record)

  def cancel_run(self, message):
    self.set_status_message(message)
    self.complete_run()
    self.status.to_run = []
    

  def run_input_tokens(self):
    """
    Return the total number of tokens in the input
    """
    count = 0
    for item_id in self.status.to_run:
      item = self.get_item_by_id(item_id)
      if item is not None:
        count += item.token_count()
    return count
  
  def run_date_time(self, run_record):
    # Return the time without microseconds.
    dt = datetime.datetime(run_record.start_time.year,
                           run_record.start_time.month,
                           run_record.start_time.day,
                           run_record.start_time.hour,
                           run_record.start_time.minute,
                           run_record.start_time.second)
    return dt.isoformat(sep=' ')
  
  def run_record_prompt(self, run_record):
    prompt = self.get_prompt_by_id(run_record.prompt_id)
    if prompt is not None:
      return prompt
    return ""

  def set_final_result(self, completion):
    completion.set_final_result()
    if len(self.run_list) > 0:
      self.run_list[-1].result_id = completion.id()

  def add_prompt(self, name, value):
    id = self.next_prompt_id
    self.prompts.append((id, name, value))
    self.next_prompt_id += 1
    return id
  
  def load_doc(self, name, file, md5_digest):
    self.name = name
    chunks = doc_convert.doc_to_chunks(name, file)
    for chunk in chunks:
      self.add_new_segment(chunk.get_text(), chunk.size)
    self.md5_digest = md5_digest
    
def load_session(file_name):
  f = open(file_name, 'rb')
  session = pickle.load(f)
  session.fixup_prompts()
  session.name = os.path.basename(session.name)  
  # Fix up new attributes
  if not hasattr(session, 'next_run_id'):
    session.next_run_id = 1
  if not hasattr(session, 'status'):
    session.status = DynamicStatus()
  if not hasattr(session.status, 'result_id'):
    session.status.result_id = 0 
  if not hasattr(session.status, 'run_id'):
    session.status.run_id = 0
  if not hasattr(session, 'run_list'):
    session.run_list = []
    # Add run records
    for completion in session.completions:
      if completion.is_final_result():
        run_record = RunRecord(session.next_run_id)
        run_record.result_id = completion.id()
        session.next_run_id += 1
        session.run_list.append(run_record)
  # Check prompt_id fields on run_record
  for run_record in session.run_list:
    if not hasattr(run_record, "prompt_id"):
      run_record.prompt_id = 0
      item = session.get_item_by_id(run_record.result_id)
      if item is not None:
        run_record.prompt_id = item.prompt_id
    if not hasattr(run_record, "complete_steps"):
      run_record.complete_steps = 0
    if not hasattr(run_record, "status_message"):
      run_record.status_message = ""
    if not hasattr(run_record, "stop_time"):
      run_record.stop_time = None
        
  if not hasattr(session, 'md5_digest'):
    session.md5_digest = b''
    
  return session
  
def save_session(file_name, session):
  # Write and rename to avoid a read of a partial write.
  # TODO: write lock what open for writing
  f = open(file_name + '.tmp', 'wb')
  pickle.dump(session, f)
  f.close()
  os.replace(file_name + '.tmp', file_name)


def find_or_create_doc(user_dir, filename, file):
  """
  Returns a doc name or None

  Given a file and filename, find an existing matching file or
  create a new file. 

  May throw exception on failure.
  """
  # Read in file to a tmp file
  tmp_file = tempfile.TemporaryFile()
  tmp_file.write(file.read())
  tmp_file.seek(0, 0)

  # Generate an md5 sum
  md5_digest = hashlib.md5(tmp_file.read()).digest()
  tmp_file.seek(0, 0)

  # Find a matching name and md5_digest, or exit loop with a
  # unique filename
  target_file = filename
  i = 0
  done = False
  while not done:
    file_path = os.path.join(user_dir, target_file + ".daf")
    if os.path.exists(file_path):
      session = load_session(file_path)
      if session.md5_digest == md5_digest:
        done = True
      else:
        # Try a different filename
        i += 1
        target_file = filename + "(%d)" % (i)
      
    else:
      # File does not exist, create it
      done = True
      session = Session()    
      session.load_doc(target_file, tmp_file, md5_digest)
      save_session(file_path, session)
  return target_file
      
      

  # TODO: use hash and equality
    
  
  tmp_file.close()
  return filename



def build_prompt(prompt):
  """
  Extend the given prompt to something that is effective for 
  GPT completions.
  """
  return  "You will be provided with text delimited by triple quotes. Using all of the text, " + prompt

  
FAKE_AI_COMPLETION=False

class ResponseRecord:
  def __init__(self,
               text,
               prompt_tokens,
               completion_tokens,
               truncated):
    self.text = text
    self.prompt_tokens = prompt_tokens
    self.completion_tokens = completion_tokens
    self.truncated = truncated
    
               
def run_completion(prompt, text, max_tokens, status_cb=None):

  prompt = build_prompt(prompt)
  
  tokenizer = tiktoken.encoding_for_model(section_util.AI_MODEL)
  text = "\"\"" + text + "\"\"\""

  done = False
  max_try = 5
  count = 0
  wait = 5
  completion = None
  truncated = False
  completion_token_count = 0
  completion_cost = 0
  prompt_tokens = len(tokenizer.encode(prompt))
  text_tokens = len(tokenizer.encode(text))

  # Enusre the total request is less than the max
  limit_tokens =  (section_util.AI_MODEL_SIZE -
                  prompt_tokens - text_tokens - 50)
  if max_tokens == -1 or max_tokens > limit_tokens:
    max_tokens = limit_tokens

  logging.info("prompt tokens: %d, text tokens: %d, max_tokens: %d" %
               (prompt_tokens, text_tokens, max_tokens))

  if FAKE_AI_COMPLETION:
    time.sleep(1)
    return ResponseRecord("Dummy completion, this is filler text.\n" * 80,
                          100, 50, 150)

  logging.info("Running completion: %s", prompt)
  
  while not done:
    try:
      # TODO: set max_tokens to appropriate amount
      start_time = datetime.datetime.now()
      request_timeout = 30 + 10 * count
      response = openai.ChatCompletion.create(
        model=section_util.AI_MODEL,
        max_tokens = max_tokens,
        temperature = 0.1,
        messages=[ {"role": "system", "content": prompt},
                   {"role": "user", "content": text }],
        request_timeout=request_timeout)
      
      completion = response['choices'][0]['message']['content']
      # TODO: use these to detect truncation.
      completion_tokens = response['usage']['completion_tokens']
      prompt_tokens = response['usage']['prompt_tokens']            
      done = True
      if response['choices'][0]['finish_reason'] == "length":
        truncated = True
      end_time = datetime.datetime.now()

    except Exception as err:
      end_time = datetime.datetime.now()
      logging.error(str(err))      
      if status_cb is not None:
        status_cb(str(err))

    logging.info("completion required %d seconds" %
                 (end_time - start_time).total_seconds())
    count += 1
    if count >= max_try:
      done = True
        
    if not done:
      wait_time = wait * math.pow(2, count - 1)
      time.sleep(wait_time)

  return ResponseRecord(completion, prompt_tokens,
                        completion_tokens, truncated)


def post_process_completion(response_record):
  """
  Make any fixups needed to the text after a completion run.
  """

  # Detect trucated output and truncate to the previous period or CR
  if response_record.truncated:
    last_cr = response_record.text.rindex('\n')
    if last_cr == -1:
      return
    logging.info("trucated response. from %d to %d" %
                 (len(response_record.text), last_cr + 1))
    response_record.text = response_record.text[0:last_cr + 1]

    
def start_docgen(file_path, session, prompt, item_ids=None):
  """
  Setup state for a docgen run.
  """
  if not item_ids:
    # Run on all doc segments by default.
    item_ids = []
    for item in session.get_ordered_items():
      if item.is_doc_segment():
        item_ids.append(item.id())

  session.start_run(prompt, item_ids)
  save_session(file_path, session)
  return session.status.run_id

  
def run_all_docgen(file_path, session):
  done = False
  result_id = None
  while not done:
    logging.debug("loop to run a set of docgen ops")      
    # loop to consume all run items
    while session.status.next_item() is not None:
      if session.status.skip_remaining_gen():
        # Skip procesing an already processed item
        id = session.status.pop_item()
        logging.debug("skip unnecessary docgen: %d", id)
        # Add directly to results list for further processing
        session.note_step_complete(id)
      else:
        logging.debug("loop for running docgen")
        run_next_docgen(file_path, session)
        save_session(file_path, session)

    # Done with the to_run queue, check if we process the
    # set of generated results.
    if not session.status.next_result_set():
      # Complete - mark final result and save
      logging.debug("doc gen complete")      
      done = True
      completion = session.get_item_by_id(session.status.result_id)
      if completion is not None:
        session.set_final_result(completion)
        session.set_status_message("")
        session.complete_run()
        completion.set_final_result()
        result_id = completion.id()
        save_session(file_path, session)
  return result_id
        
  
def run_next_docgen(file_path, session):
  tokenizer = section_util.get_tokenizer()
  done = False
  item_id_list = []
  text_list = []
  token_count = 0

  # Pull items until max size would be exceeded
  while not done:
    item_id = session.status.next_item()
    if item_id is None:
      done = True
      continue

    item = session.get_item_by_id(item_id)
    if item is None:
      session.status.pop_item()
      continue
    
    count = len(tokenizer.encode(item.text()))
    if (token_count != 0 and
        count + token_count > section_util.TEXT_EMBEDDING_CHUNK_SIZE):
      logging.debug("max would be hit, count = %d, token_count = %d" %
                    (count, token_count))
      done = True
      continue

    session.status.pop_item()    
    item_id_list.append(item.id())
    text_list.append(item.text())
    token_count += count
    logging.debug("add id %d to source list. count = %d, total = %d" %
                  (item.id(), count, token_count))

  if len(item_id_list) == 0:
    logging.error("No content for docgen")
    return

  # Run a completion
  prompt = session.status.prompt
  prompt_id = session.get_prompt_id(prompt)
  logging.info("run completion with %d items" % len(item_id_list))

  # Update status with last item
  session.set_status_message("%s on %s" %
                             (prompt, item.name()))
  save_session(file_path, session)
  
  err_message = ''
  def status_cb(message):
    err_message = str(message)
    session.set_status_message(str(message))
    save_session(file_path, session)


  # Ensure response is less than 1/2 the size of a request
  # to make progress on consolidation. Except on the last completion.
  max_tokens = int(section_util.TEXT_EMBEDDING_CHUNK_SIZE / 2) - 1
  if session.status.is_last_completion():
    max_tokens = -1

  response_record = run_completion(prompt, '\n'.join(text_list),
                                   max_tokens, status_cb)

  post_process_completion(response_record)
  
  if response_record.text is None:
    text = err_message
  else:
    text = response_record.text
    
  completion = session.add_new_completion(
    prompt_id,
    item_id_list,
    text,
    response_record.completion_tokens,
    response_record.prompt_tokens + response_record.completion_tokens)
  session.note_step_complete(completion.id())

  
    
