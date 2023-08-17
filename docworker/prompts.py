"""
Logic to manage and present prompts.
"""

# Move to prompts
INITIAL_PROMPTS = [
  ('Summarize', 'Provide a summary', True),  
  ('Summarize Main Points', 'Summarize the main points', True),
  ('Summarize with Insights', 'Summarize and give a list of bullet points with key insights and the most important facts', True),  
  ('Describe Main Ideas', 'Describe the main ideas', True),
  ('Explain Concepts', 'Explain the concepts', True),
  ('List Target Dates', 'List deliverables and target dates', True),
  ('Explain Pirate', 'Explain like a pirate', True),
  ('Explain Surfer', 'Explain like a surfer', True),    
  ('List People', 'List the people that are mentioned', True),
  ('List Topics', 'List the topics that are mentioned', True),
  ('Restate for Clarity', 'Restate for clarity', False),
  ('Rewrite for 5th grader', 'Rewrite for a 5th grader', False),
  ('Translate to Spanish', 'Translate to Spanish', False),
  ('Rewrite using emojis', 'Rewrite using emojis', False),
  ]

class Prompts:
  """
  Manage static and dynamic set of prompts.
  """

  def __init__(self):
    self.next_prompt_id = 0
    self.prompts = []
    for prompt in INITIAL_PROMPTS:
      self.add_prompt(prompt[0], prompt[1], prompt[2])

  def add_prompt(self, name, value, type_consolidate):
    id = self.next_prompt_id
    self.prompts.append((id, name, value, type_consolidate))
    self.next_prompt_id += 1
    return id
  
  def get_prompt_set(self):
    return self.prompts

  def get_initial_prompt_set():
    """
    Static function for prompts with no document
    """
    return [ (1, x[0], x[1], x[2]) for x in INITIAL_PROMPTS ]

  def get_prompt_id_by_name(self, name):
    # Return the ID matching the name, None if not found
    for prompt in self.prompts:
      if prompt[1] == name:
        return prompt[0]
    return None

  def get_prompt_name_by_id(self, id):
    # Return the prompt name matching the id, None if not found        
    for prompt in self.prompts:
      if prompt[0] == id:
        return prompt[1]
    return None
  
  def get_prompt_by_name(self, name):
    # Return the prompt record matching the name, None if not found    
    for prompt in self.prompts:
      if prompt[1] == name:
        return prompt
    return None

  def get_prompt_str_by_id(self, id):
    # Return the prompt record matching the name, None if not found        
    for prompt in self.prompts:
      if prompt[0] == id:
        return prompt[2]
    return None
  
  def get_prompt_id(self, prompt_str, op_flag=True):
    # Find a matching prompt, or create a new one
    for prompt in self.prompts:
      if prompt[2] == prompt_str:
        return prompt[0]
    # TODO: ensure name is unique
    name = prompt_str[0:max(12, len(prompt) - 1)] + '...'      
    id = self.add_prompt(name, prompt_str, op_flag)
    return id

  def fixup_prompts(self):
    """
    Update / fix prompts using the INITIAL PROMPTS
    """
    changed = False

    # Add op_type field if needed
    for index in range(0, len(self.prompts)):
      prompt = self.prompts[index]
      if len(prompt) < 4:
        self.prompts[index] = (prompt[0],
                               prompt[1],
                               prompt[2],
                               True)
    
    # Add / Change existing prompts
    for (name, value, type_cons) in INITIAL_PROMPTS:
      prompt = self.get_prompt_by_name(name)
      # Does it exist?
      if prompt is None:
        self.add_prompt(name, value, type_cons)
        changed = True
      elif prompt[2] != value:
        index = self.prompts.index(prompt)
        self.prompts[index] = (prompt[0], name, value, type_cons)
        changed = True

    return changed

  
