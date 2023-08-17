from . import document
import unittest
import tempfile
import os

LONG_TEXT = """
If I have objects a and b and both reference object obj, what happens when I Pickle and then restore the objects? Will the pickled data 'know' that a and b both referenced the same object and restore everything accordingly, or will the two get two different — and initially equal — objects?
"""

class BasicDocumentTestCase(unittest.TestCase):

  def setUp(self):
    self.doc = document.Document()
    self.doc.doc_text = "Document test"
    self.prompt = "This is a new prompt"
    prompt_id = self.doc.prompts.get_prompt_id(self.prompt)
    run_record = self.doc.new_run_record(prompt_id,
                                         document.OP_TYPE_CONSOLIDATE)
    self.run_id = run_record.run_id
    # Add more segments for testing
    self.id1 = run_record.add_new_segment("segment text", 4).id()
    self.id2 = run_record.add_new_segment("more segment text", 6).id()
    self.id3 = run_record.add_new_completion([self.id1, self.id2],
                                             "completion text", 5, 20).id()
    run_record.result_id = self.id3
    self.user_dir = tempfile.TemporaryDirectory()    
  
  def tearDown(self):
    self.user_dir.cleanup()    
    pass
  
  def testInit(self):
    self.assertIsNotNone(self.doc.get_run_record(1))

  def testStripText(self):
    text = self.doc.strip_text('Hi\nall. \nHow are you?')
    self.assertEqual(len(text), 20)

  def testSnippetText(self):
    text = self.doc.snippet_text(None)
    self.assertIsNone(text)
    text = self.doc.snippet_text("This is some more text")
    self.assertEqual(len(text), 22)
    text = self.doc.snippet_text(LONG_TEXT)
    self.assertEqual(len(text), 96)
    
  def testGetItems(self):
    self.assertIsNotNone(self.doc.get_item_by_id(self.run_id,
                                                      self.id1))
    self.assertIsNone(self.doc.get_item_by_id(self.run_id, -1))
    
    self.assertIsNotNone(self.doc.get_name_by_id(self.run_id,
                                                      self.id1))
    self.assertIsNone(self.doc.get_name_by_id(self.run_id, -1))

    name = self.doc.get_name_by_id(self.run_id, self.id3)
    self.assertIsNotNone(self.doc.get_item_by_name(self.run_id,
                                                        name))
    self.assertIsNone(self.doc.get_item_by_name(self.run_id, '00'))
    
    val = self.doc.get_names_for_ids(self.run_id, [ self.id1, self.id2 ])
    self.assertIsNotNone(val)
    self.assertTrue(len(val) > 0)    

    val = self.doc.get_names_for_ids(self.run_id, [ -1, -1 ])
    self.assertIsNotNone(val)
    self.assertFalse(len(val) > 0)

    val = self.doc.get_items_for_ids(self.run_id, [ self.id1, self.id2 ])
    self.assertTrue(len(val) > 0)    

    val = self.doc.get_items_for_ids(self.run_id, [ -1, -1 ])
    self.assertFalse(len(val) > 0)    
    
    item = self.doc.get_result_item(self.run_id)
    self.assertIsNotNone(item)
    self.assertEqual(item.id(), self.id3)

    name = self.doc.get_result_item_name(self.run_id)
    self.assertIsNotNone(name)

    self.assertEqual(self.doc.run_record_count(), 1)
    

  def testViewLists(self):
    items = self.doc.get_gen_items(self.run_id)
    self.assertTrue(len(items), 2)
    self.assertEqual(items[1].id(), self.id1)
    self.assertEqual(items[2].id(), self.id2)

    items = self.doc.get_ordered_items(self.run_id)
    self.assertTrue(len(items), 3)
    self.assertEqual(items[0].id(), self.id3)
    self.assertEqual(items[2].id(), self.id1)
    self.assertEqual(items[3].id(), self.id2)

    items = self.doc.get_recent_gen_item(self.run_id)
    self.assertTrue(len(items), 2)
    self.assertEqual(items[0].id(), self.id3)
    self.assertEqual(items[1].id(), self.id1)    

    items = self.doc.get_completion_list(self.run_id)
    self.assertTrue(len(items), 1)
    self.assertEqual(items[0].id(), self.id3)

    (max_depth, entries) = self.doc.get_completion_family(self.run_id)
    self.assertEqual(len(entries), 3)
    self.assertEqual(max_depth, 2)
    self.assertEqual(entries[0][0], 1)
    self.assertEqual(entries[0][1].id(), self.id3)    
    self.assertEqual(entries[1][0], 2)
    self.assertEqual(entries[1][1].id(), self.id1)    
    self.assertEqual(entries[2][0], 2)
    self.assertEqual(entries[2][1].id(), self.id2)
    
  def testCounts(self):
    self.assertEqual(self.doc.gen_tokens(), 5)
    self.assertEqual(self.doc.gen_cost_tokens(), 20)
    self.assertEqual(self.doc.get_completion_cost(), 20)
    self.assertEqual(self.doc.get_completion_cost(self.run_id), 20)
    self.assertEqual(self.doc.get_doc_token_count(), 0)
    self.assertEqual(self.doc.segment_count(self.run_id), 3)
    self.assertEqual(self.doc.final_completion_count(), 1)

  def testSourceText(self):
    self.assertIsNotNone(self.doc.get_src_text())
    self.assertIsNotNone(self.doc.get_src_text(self.run_id))    

    
  def testRunState(self):
    self.assertTrue(self.doc.is_running(self.run_id))
    self.doc.mark_complete_run()
    self.assertFalse(self.doc.is_running(self.run_id))

    msg = "a status message"
    self.doc.set_status_message(msg)
    self.assertEqual(self.doc.get_status_message(), msg)

    self.assertEqual(self.doc.get_run_prompt(), self.prompt)

    self.assertEqual(self.doc.get_completed_steps(), 0)
    
    self.assertTrue(self.doc.run_exists(self.run_id))
    self.assertFalse(self.doc.run_exists(0))
    
    self.doc.mark_start_run(self.prompt)
    self.assertTrue(self.doc.is_running())
    self.doc.mark_cancel_run("Canceled")
    self.assertFalse(self.doc.is_running())

    completion = self.doc.add_new_completion([1, 2], "completion", 10, 20)
    self.doc.set_final_result(completion)

    run_record = self.doc.get_run_record(self.run_id)
    self.assertIsNotNone(run_record)
    prompt = self.doc.run_record_prompt(run_record)
    self.assertIsNotNone(prompt)

    run_record = self.doc.get_current_run_record()
    datetime_str = self.doc.run_date_time(run_record)
    self.assertIsNotNone(datetime_str)
    

  def testReadFile(self):
    filename = 'PA utility.docx'
    path = os.path.join(os.path.dirname(__file__),
                        'samples/', filename)
    self.doc = document.Document()
    with open(path, 'rb') as f:
      self.doc.read_file(filename, f, b'')

    self.assertIsNotNone(self.doc.get_doc_text())
    self.assertIsNotNone(self.doc.name)

    doc_file = os.path.join(self.user_dir.name, filename + '.daf')
    document.save_document(doc_file, self.doc)
    self.doc = document.load_document(doc_file)

    
  def testFindOrCreate(self):
    filename = 'PA utility.docx'
    path = os.path.join(os.path.dirname(__file__),
                        'samples/', filename)
    f = open(path, 'rb')
    filename1 = document.find_or_create_doc(self.user_dir.name, filename, f)
    f.close()
    self.assertIsNotNone(filename1)

    f = open(path, 'rb')
    filename2 = document.find_or_create_doc(self.user_dir.name, filename, f)    
    f.close()
    self.assertEqual(filename1, filename2)
    
    filename = 'PA Agenda.docx'
    path = os.path.join(os.path.dirname(__file__),
                        'samples/', filename)
    f = open(path, 'rb')
    filename3 = document.find_or_create_doc(self.user_dir.name, filename, f)
    f.close()
    self.assertNotEqual(filename1, filename3)

    
  def testRunWithData(self):
    filename = 'PA utility.docx'
    path = os.path.join(os.path.dirname(__file__),
                        'samples/', filename)
    self.doc = document.Document()
    with open(path, 'rb') as f:
      self.doc.read_file(filename, f, b'')
    self.doc.mark_start_run("This is a prompt")
    self.doc.mark_complete_run()
    self.assertTrue(len(self.doc.run_list[0].doc_segments) > 0)
    
                    
