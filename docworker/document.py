"""
Classes to represent a document and doc generation runs for
that document.
"""
from . import prompts
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
    m = re.match('.*\\s(\\d+)', self.name())
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
    # TODO: Consider removing the prompt id
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
    m = re.match('.*(\\d+).\\d+', self.name())
    if m:
      return m.group(1)
    return None

  def is_doc_segment(self):
    return False


class RunRecord:
  """
  Represents a run of a completion task.
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

    self.next_text_id = 1
    self.text_records = {}  # key is record_id
    self.doc_segments = []
    self.completions = []

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

  def add_new_completion(self, input_ids, text,
                         token_count, token_cost):
    name = self.gen_completion_name(input_ids)
    text_record = self.new_text_record(name, text, token_count)
    completion = Completion(self.prompt_id, input_ids, text_record, token_cost)
    self.completions.append(completion)
    return completion

  # TODO: convert
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

  
class Document:
  """
  An instance of work on an imporsted document.
  """

  def __init__(self):
    # TODO: fix
    #self.status = RunState()
    self.md5_digest = b''
    self.next_run_id = 1
    self.run_list = []     # List of RunRecord instances
    self.name = None
    self.prompts = prompts.Prompts()

  def get_prompt_set(self):
    return self.prompts.get_prompt_set()
    
  def item_color(self, item):
    if item.is_doc_segment():
      return '#eeeeee'
    elif item.is_final_result():
      #return '#b7d7f5'
      return '#d9e8f6'
    else:
      #return '#efddfd'
      return '#e8e0ee'
    
  # TODO: move to utils
  def strip_text(self, text):
    # combine multiple lines into one
    return text.replace('\n', ' ').replace('  ', ' ')

  def max_tokens(self):
    return section_util.TEXT_EMBEDDING_CHUNK_SIZE

  # TODO: move to utils
  def snippet_text(self, text):
    if text is None:
      return None
    if len(text) < 90:
      return self.strip_text(text)
    return self.strip_text(text[0:45] + " ... " + text[-46:])

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

  def get_item_by_name(self, run_id, name):
    record = self.get_run_record(run_id)
    if record is None:
      return None
    return record.get_item_by_name(name)

  def get_item_by_id(self, run_id, id):
    record = self.get_run_record(run_id)
    if record is None:
      return None
    return record.get_item_by_id(id)

  def get_name_by_id(self, run_id, id):
    record = self.get_run_record(run_id)
    if record is None:
      return None
    return record.get_name_by_id(id)
    
    if id in self.text_records.keys():
      return self.text_records[id].name
    return None

  def get_names_for_ids(self, run_id, ids):
    names = []
    record = self.get_run_record(run_id)
    if record is not None:
      for id in ids:
        name = record.get_name_by_id(id)
        if name is not None:
          names.append(name)
    return ', '.join(names)

  def get_items_for_ids(self, run_id, ids):
    items = []
    record = self.get_run_record(run_id)
    if record is not None:
      for id in ids:
        item = record.get_item_by_id(id)
      if item is not None:
        items.append(item)
    return items

  def get_result_item(self, run_id=None):
    """
    Return the final result item of the given completion run.
    """
    run_record = self.get_run_record(run_id)
    if run_record != None:
      return run_record.get_item_by_id(run_record.result_id)
    return None
  
  def get_result_item_name(self, run_id=0):
    """
    Return the name of the result item.
    None if no result yet
    """
    item = self.get_result_item(run_id)
    if item is not None:
      return item.name()
    return None
  
  def run_record_count(self):
    """
    Return the number of runs.
    """
    return len(self.run_list)
  

  # TODO: convert  
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

  # TODO: convert  
  def get_ordered_items_visit_node(self, node, result):
    result.append(node)
    # TODO - make a BFS(?)
    for id in node.input_ids:
      child = self.get_item_by_id(id)
      # Visit children that were completions created for this node
      if not child.is_doc_segment() and not child.is_final_result():
        self.get_ordered_items_visit_node(child, result)
        
  # TODO: convert      
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

  # TODO: convert    
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
  

  # TODO: convert    
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

  # TODO: convert    
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

  def combine_results(self):
    # combine the results of all items on the complete run list
    # and make it the final result
    item_id_list = []
    text_list = []
    while self.status.next_item():
      id = self.status.pop_item()
      item_id_list.append(id)
      completion = self.get_item_by_id(id)
      text_list.append(completion.text() + '\n')

    prompt = self.status.prompt
    prompt_id = self.get_prompt_id(prompt)
    text = '\n'.join(text_list)
    tokenizer = tiktoken.encoding_for_model(section_util.AI_MODEL)    
    text_tokens = len(tokenizer.encode(text))
    
    completion = self.add_new_completion(
      prompt_id,
      item_id_list,
      '\n'.join(text_list), text_tokens, 0)
    self.note_step_complete(completion.id())

  def run_exists(self, run_id):
    """
    Return true if the run exists.
    """
    return self.get_run_record(run_id) is not None

  # TODO: convert
  def doc_tokens(self):
    total = 0
    for segment in self.doc_segments:
      total += segment.token_count()
    return total

  # TODO: convert  
  def gen_tokens(self):
    total = 0
    for completion in self.completions:
      total += completion.token_count()
    return total

  # TODO: convert  
  def gen_cost_tokens(self):
    total = 0
    for completion in self.completions:
      total += completion.token_cost
    return total

  # TODO: convert  
  def segment_count(self):
    return len(self.doc_segments)

  # TODO: convert  
  def final_completion_count(self):
    count = 0
    for completion in self.completions:
      if completion.is_final_result():
        count += 1
    return count

  def new_run_record(self, prompt_id):
    run_record = RunRecord(self.next_run_id, prompt_id)
    self.next_run_id += 1
    self.run_list.append(run_record)
    return run_record
                    
  def start_run(self, prompt, item_ids):
    prompt_id = self.get_prompt_id(prompt)                        
    run_record = self.new_run_record(prompt_id)
    run_record.status_message = "Running..."

    self.status = RunState()
    self.status.run_id = run_record.run_id
    self.status.start_run(prompt, item_ids)


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

  def load_doc(self, name, file, md5_digest):
    self.name = name
    chunks = doc_convert.doc_to_chunks(name, file)
    for chunk in chunks:
      self.add_new_segment(chunk.get_text(), chunk.size)
    self.md5_digest = md5_digest

    
def load_document(file_name):
  f = open(file_name, 'rb')
  document = pickle.load(f)
  document.fixup_prompts()
  document.name = os.path.basename(document.name)  
  # Fix up new attributes
  if not hasattr(document, 'next_run_id'):
    document.next_run_id = 1
  if not hasattr(document, 'status'):
    document.status = RunState()
  if not hasattr(document.status, 'result_id'):
    document.status.result_id = 0 
  if not hasattr(document.status, 'run_id'):
    document.status.run_id = 0
  if not hasattr(document, 'run_list'):
    document.run_list = []
    # Add run records
    for completion in document.completions:
      if completion.is_final_result():
        run_record = RunRecord(document.next_run_id)
        run_record.result_id = completion.id()
        document.next_run_id += 1
        document.run_list.append(run_record)
  # Check prompt_id fields on run_record
  for run_record in document.run_list:
    if not hasattr(run_record, "prompt_id"):
      run_record.prompt_id = 0
      item = document.get_item_by_id(run_record.result_id)
      if item is not None:
        run_record.prompt_id = item.prompt_id
    if not hasattr(run_record, "complete_steps"):
      run_record.complete_steps = 0
    if not hasattr(run_record, "status_message"):
      run_record.status_message = ""
    if not hasattr(run_record, "stop_time"):
      run_record.stop_time = None
        
  if not hasattr(document, 'md5_digest'):
    document.md5_digest = b''
    
  return document
  
def save_document(file_name, document):
  # Write and rename to avoid a read of a partial write.
  # TODO: write lock what open for writing
  f = open(file_name + '.tmp', 'wb')
  pickle.dump(document, f)
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
      document = load_document(file_path)
      if document.md5_digest == md5_digest:
        done = True
      else:
        # Try a different filename
        i += 1
        target_file = filename + "(%d)" % (i)
      
    else:
      # File does not exist, create it
      done = True
      document = Document()    
      document.load_doc(target_file, tmp_file, md5_digest)
      save_document(file_path, document)
  return target_file
      
      

  # TODO: use hash and equality
    
  
  tmp_file.close()
  return filename

