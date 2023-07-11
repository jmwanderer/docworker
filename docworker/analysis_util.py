"""
Utilitiy functions for supporting generating web pages
"""

import os
import os.path
from flask import current_app



class ItemsState:
  """
  Helper class to manage the selected sets of 
  segments and completions.
  """
  def __init__(self):
    self.selected_items = []
    self.open_items = []
    self.focus_item = None
    self.tokens = 0    

  def sel_id(self, item):
    return "cl_" + item.name()
  
  def selected_names(self):
    return [ x.name() for x in self.selected_items ]

  def add_selected(self, item):
    """
    return a list of names for selected items with item added
    """
    result = self.selected_items
    if item not in self.selected_items:
      result = self.selected_items.copy()
      result.append(item)
    return [ x.name() for x in result ]

  def del_selected(self, item):
    """
    return a list of names for selected items with item removed
    """
    result = self.selected_items
    if item in self.selected_items:
      result = self.selected_items.copy()
      result.remove(item)
    return [ x.name() for x in result ]

  def move_selected(self, item, delta):
    """
    return a list of names for selected items with item moved
    in the list by delta (typically +1 or -1)
    """
    result = self.selected_items.copy()
    if item in result:
      index = result.index(item)
      index += delta
      if index < 0:
        index = 0
      if index >= len(result):
        index = len(result)
      result.remove(item)
      result.insert(index, item)
    return [ x.name() for x in result ]
    
  def selected(self):
    """
    True if any items are selected.
    """
    return len(self.selected_items) > 0

  def item_selected(self, item):
    """
    True if the specified item is selected.
    """
    return item in self.selected_items

  def item_open(self, item):
    """
    Return true if the specified item is open
    """
    return item in self.open_items

  def add_open(self, item):
    """
    Add the specified item to the list of open items
    and return the list of names for open items.
    """
    result = self.open_items
    if item not in self.open_items:
      result = self.open_items.copy()
      result.append(item)
    return [ x.name() for x in result ]
      
  def del_open(self, item):
    """
    Remove the specified item from the list of open items
    and return the list of names for open items.
    """
    result = self.open_items
    if item in self.open_items:
      result = self.open_items.copy()
      result.remove(item)
    return [ x.name() for x in result ]

  def open_names(self):
    """
    Return a list of names for the open items
    """
    return [ x.name() for x in self.open_items ]    

  def total_tokens(self):
    return self.tokens
  
  def set_state(self, session, selected_names, open_names=[], focus=None):
    """
    Called by the request handler to set the state of 
    selected and open items.
    """
    self.selected_items = []
    self.open_items = []
    self.tokens = 0
    self.focus_item = focus
    
    for name in selected_names:
      item = session.get_item_by_name(name)
      # don't add items twice
      if item is not None and item not in self.selected_items:
        self.selected_items.append(item)
        self.tokens += item.token_count()

    for name in open_names:
      item = session.get_item_by_name(name)      
      # don't add items twice        
      if item is not None and item not in self.open_items:
        self.open_items.append(item)

