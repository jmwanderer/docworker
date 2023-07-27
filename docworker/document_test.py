from . import document
import unittest
import tempfile
import os

class BasicDocumentTestCase(unittest.TestCase):

  def setUp(self):
    self.document = document.Document()
    self.prompt = "This is a new prompt"
    prompt_id = self.document.prompts.get_prompt_id(self.prompt)
    run_record = self.document.new_run_record(prompt_id)
    self.run_id = run_record.run_id
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
    self.assertIsNotNone(self.document.get_run_record(1))

  def testGetItems(self):
    self.assertIsNotNone(self.document.get_item_by_id(self.run_id,
                                                      self.id1))
    self.assertIsNone(self.document.get_item_by_id(self.run_id, -1))
    
    self.assertIsNotNone(self.document.get_name_by_id(self.run_id,
                                                      self.id1))
    self.assertIsNone(self.document.get_name_by_id(self.run_id, -1))

    name = self.document.get_name_by_id(self.run_id, self.id3)
    self.assertIsNotNone(self.document.get_item_by_name(self.run_id,
                                                        name))
    self.assertIsNone(self.document.get_item_by_name(self.run_id, '00'))
    
    val = self.document.get_names_for_ids(self.run_id, [ self.id1, self.id2 ])
    self.assertIsNotNone(val)
    self.assertTrue(len(val) > 0)    

    val = self.document.get_names_for_ids(self.run_id, [ -1, -1 ])
    self.assertIsNotNone(val)
    self.assertFalse(len(val) > 0)

    val = self.document.get_items_for_ids(self.run_id, [ self.id1, self.id2 ])
    self.assertTrue(len(val) > 0)    

    val = self.document.get_items_for_ids(self.run_id, [ -1, -1 ])
    self.assertFalse(len(val) > 0)    
    
    item = self.document.get_result_item(self.run_id)
    self.assertIsNotNone(item)
    self.assertEqual(item.id(), self.id3)

    name = self.document.get_result_item_name(self.run_id)
    self.assertIsNotNone(name)

    self.assertEqual(self.document.run_record_count(), 1)
    

  def testViewLists(self):
    items = self.document.get_gen_items(self.run_id)
    self.assertTrue(len(items), 2)
    self.assertEqual(items[0].id(), self.id1)
    self.assertEqual(items[1].id(), self.id2)

    items = self.document.get_ordered_items(self.run_id)
    self.assertTrue(len(items), 3)
    self.assertEqual(items[0].id(), self.id3)
    self.assertEqual(items[1].id(), self.id1)
    self.assertEqual(items[2].id(), self.id2)

    items = self.document.get_completion_list(self.run_id)
    self.assertTrue(len(items), 1)
    self.assertEqual(items[0].id(), self.id3)

    (max_depth, entries) = self.document.get_completion_family(self.run_id)
    self.assertEqual(len(entries), 3)
    self.assertEqual(max_depth, 2)
    self.assertEqual(entries[0][0], 1)
    self.assertEqual(entries[0][1].id(), self.id3)    
    self.assertEqual(entries[1][0], 2)
    self.assertEqual(entries[1][1].id(), self.id1)    
    self.assertEqual(entries[2][0], 2)
    self.assertEqual(entries[2][1].id(), self.id2)
    
  def testCounts(self):
    self.assertEqual(self.document.gen_tokens(), 5)
    self.assertEqual(self.document.gen_cost_tokens(), 20)
    # TODO: fix
    self.assertEqual(self.document.doc_tokens(), 0)
    self.assertEqual(self.document.segment_count(self.run_id), 2)
    self.assertEqual(self.document.final_completion_count(), 1)
    
  def testRunState(self):
    self.assertTrue(self.document.is_running(self.run_id))
    self.document.mark_complete_run()
    self.assertFalse(self.document.is_running(self.run_id))

    msg = "a status message"
    self.document.set_status_message(msg)
    self.assertEqual(self.document.get_status_message(), msg)

    self.assertEqual(self.document.get_run_prompt(), self.prompt)

    self.assertEqual(self.document.get_completed_steps(), 0)
    
    self.assertTrue(self.document.run_exists(self.run_id))
    self.assertFalse(self.document.run_exists(0))
    
    self.document.mark_start_run(self.prompt)
    self.assertTrue(self.document.is_running())
    self.document.mark_cancel_run("Canceled")
    self.assertFalse(self.document.is_running())

    completion = self.document.add_new_completion([1, 2], "completion", 10, 20)
    self.document.set_final_result(completion)

    run_record = self.document.get_run_record(self.run_id)
    self.assertIsNotNone(run_record)
    prompt = self.document.run_record_prompt(run_record)
    self.assertIsNotNone(prompt)

    run_record = self.document.get_current_run_record()
    datetime_str = self.document.run_date_time(run_record)
    self.assertIsNotNone(datetime_str)
    

  def testReadFile(self):
    filename = 'PA utility.docx'
    path = os.path.join(os.path.dirname(__file__),
                        'samples/', filename)
    self.document = document.Document()
    with open(path, 'rb') as f:
      self.document.read_file(filename, f, b'')

    self.assertIsNotNone(self.document.get_doc_text())
    self.assertIsNotNone(self.document.name)

    doc_file = os.path.join(self.user_dir.name, filename + '.daf')
    document.save_document(doc_file, self.document)
    self.document = document.load_document(doc_file)

    
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
    self.document = document.Document()
    with open(path, 'rb') as f:
      self.document.read_file(filename, f, b'')
    self.document.mark_start_run("This is a prompt")
    self.document.mark_complete_run()
    self.assertTrue(len(self.document.run_list[0].doc_segments) > 0)
    
                    
