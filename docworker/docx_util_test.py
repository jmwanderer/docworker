from . import docx_util
import unittest

LONG_TEXT = """
If I have objects a and b and both reference object obj, what happens when I Pickle and then restore the objects? Will the pickled data 'know' that a and b both referenced the same object and restore everything accordingly, or will the two get two different — and initially equal — objects?
"""

class DocXUtilTestCase(unittest.TestCase):

  def testStripText(self):
    session = docx_util.Session()
    text = session.strip_text('Hi\nall. \nHow are you?')
    self.assertEqual(len(text), 20)

  def testSnippetText(self):
    session = docx_util.Session()
    text = session.snippet_text(None)
    self.assertIsNone(text)

    text = session.snippet_text("This is some more text")
    self.assertEqual(len(text), 22)

    text = session.snippet_text(LONG_TEXT)
    self.assertEqual(len(text), 96)

  def testAddNewSegment(self):
    session = docx_util.Session()
    segment = session.add_new_segment(LONG_TEXT, 20)
    self.assertEqual(segment.name(), 'Block 1')
    self.assertEqual(segment.id(), 1)
    self.assertEqual(segment.text(), LONG_TEXT)
    self.assertEqual(segment.token_count(), 20)

  def testAddNewCompletion(self):
    session = docx_util.Session()
    segment = session.add_new_segment(LONG_TEXT, 20)
    id = segment.text_record.id
    completion = session.add_new_completion(1, [ id ], LONG_TEXT, 20, 30)
    self.assertEqual(completion.name(), 'Generated 1.1')
    self.assertEqual(completion.id(), 2)
    self.assertEqual(completion.text(), LONG_TEXT)
    self.assertEqual(completion.token_count(), 20)
    self.assertEqual(completion.token_cost, 30)
    
  def testMultiAdds(self):
    session = docx_util.Session()
    segment = session.add_new_segment(LONG_TEXT, 20)
    id = segment.text_record.id
    completion = session.add_new_completion(1, [ id ], LONG_TEXT, 20, 30)
    self.assertEqual(completion.text_record.name, 'Generated 1.1')
    segment = session.add_new_segment(LONG_TEXT, 20)
    id = segment.id()
    completion = session.add_new_completion(1, [ id ], LONG_TEXT, 20, 30)
    self.assertEqual(completion.name(), 'Generated 2.1')
    completion = session.add_new_completion(1, [ id ], LONG_TEXT, 20, 30)
    self.assertEqual(completion.text_record.name, 'Generated 2.2')
    c_id = completion.id()
    completion = session.add_new_completion(1, [ c_id ], LONG_TEXT, 20, 30)
    self.assertEqual(completion.name(), 'Generated 1')
    completion = session.add_new_completion(1, [ c_id ], LONG_TEXT, 20, 30)
    self.assertEqual(completion.text_record.name, 'Generated 2')

  def setUpSession(self):
    session = docx_util.Session()
    segment = session.add_new_segment(LONG_TEXT, 20)
    id = segment.text_record.id
    completion = session.add_new_completion(1, [ id ], LONG_TEXT, 20, 30)
    completion.set_final_result()
    
    segment = session.add_new_segment(LONG_TEXT, 20)
    id = segment.text_record.id
    completion = session.add_new_completion(1, [ id ], LONG_TEXT, 20, 30)
    completion.set_final_result()    
    
    segment = session.add_new_segment(LONG_TEXT, 20)
    return session


  def testGetItem(self):
    session = self.setUpSession()
    item = session.get_item_by_name('Block 1')
    self.assertFalse(item is None)
    item = session.get_item_by_name('Generated 1')
    self.assertTrue(item is None)    
    item = session.get_item_by_name('Generated 1.1')
    self.assertFalse(item is None)

  def testGetNameCalls(self):
    session = self.setUpSession()
    item = session.get_name_by_id(1)
    self.assertFalse(item is None)
    items = session.get_items_for_ids([1, 2, 3])
    self.assertEqual(len(items), 3)

  def testTokens(self):
    session = self.setUpSession()
    self.assertEqual(session.doc_tokens(), 60)
    self.assertEqual(session.gen_tokens(), 40)
    self.assertEqual(session.gen_cost_tokens(), 60)
    
  def testGetPrompt(self):
    session = self.setUpSession()
    self.assertEqual(len(session.get_prompt_set()), 13)
    self.assertFalse(session.get_prompt_id_by_name("Explain") is None)

  def testGetOrderedItems(self):
    session = self.setUpSession()
    l = session.get_ordered_items()
    self.assertEqual(len(l), 5)
    self.assertTrue(l[3].is_doc_segment())
    self.assertFalse(l[1].is_doc_segment())    
    
    
class DocXUtilExtTestCase(unittest.TestCase):
  """
  Test complex ordering of completions and segments
  """
  
  def setUpSession(self):
    session = docx_util.Session()

    # Add 5 segments
    segment_ids = []    
    for x in range(0, 5):
      segment = session.add_new_segment(LONG_TEXT, 20)
      segment_ids.append(segment.id())

    # Add completion for each segment
    completion_ids = []
    for id in segment_ids:
      completion = session.add_new_completion(1, [ id ], LONG_TEXT, 20, 30)
      completion_ids.append(completion.id())

    # Add 2nd level completion
    comp1 = session.add_new_completion(1, completion_ids, LONG_TEXT, 20, 30)    

    # Add 5 more segments
    segment_ids = []
    for x in range(0, 5):
      segment = session.add_new_segment(LONG_TEXT, 20)
      segment_ids.append(segment.id())

    # Add completion for each segment
    completion_ids = []
    for id in segment_ids:
      completion = session.add_new_completion(1, [ id ], LONG_TEXT, 20, 30)
      completion_ids.append(completion.id())

    # Add another 2nd level completion
    comp2 = session.add_new_completion(1, completion_ids, LONG_TEXT, 20, 30)    

    # Add final completion
    comp = session.add_new_completion(1, [comp1.id(), comp2.id()],
                                      LONG_TEXT, 20, 30)    
    comp.set_final_result()

    return session

  def testGetOrderedItems(self):
    session = self.setUpSession()
    l = session.get_ordered_items()
    self.assertEqual(len(l), 23)
    self.assertFalse(l[0].is_doc_segment())
    self.assertTrue(l[22].is_doc_segment())    

  def testGetCompletionFamily(self):
    session = self.setUpSession()
    top_node = session.get_ordered_items()[0]    
    (depth, l) = session.get_completion_family(top_node.id())
    self.assertEqual(depth, 4)
    self.assertEqual(len(l), 23)    
