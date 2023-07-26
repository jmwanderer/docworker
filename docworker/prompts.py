"""
Logic to manage and present prompts.
"""

# Move to prompts
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

class Prompts:
  """
  Manage static and dynamic set of prompts.
  """

  def __init__(self):
    self.next_prompt_id = 0
    self.prompts = []
    for prompt in INITIAL_PROMPTS:
      self.add_prompt(prompt[0], prompt[1])

  def add_prompt(self, name, value):
    id = self.next_prompt_id
    self.prompts.append((id, name, value))
    self.next_prompt_id += 1
    return id
  
  def get_prompt_set(self):
    return self.prompts

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
  
  def get_prompt_id(self, prompt_str):
    # Find a matching prompt, or create a new one
    for prompt in self.prompts:
      if prompt[2] == prompt_str:
        return prompt[0]
    # TODO: ensure name is unique
    name = prompt_str[0:max(12, len(prompt) - 1)] + '...'      
    id = self.add_prompt(name, prompt_str)
    return id

  def fixup_prompts(self):
    """
    Update / fix prompts using the INITIAL PROMPTS
    """
    changed = False
    
    # Add / Change existing prompts
    for (name, value) in INITIAL_PROMPTS:
      prompt = self.get_prompt_by_name(name)
      # Does it exist?
      if prompt is None:
        self.add_prompt(name, value)
        changed = True
      elif prompt[2] != value:
        index = self.prompts.index(prompt)
        self.prompts[index] = (prompt[0], name, value)
        changed = True

    return changed

  
