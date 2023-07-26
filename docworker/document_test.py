from . import document
import unittest


class BasicDocumentTestCase(unittest.TestCase):

  def setUp(self):
    self.document = document.Document()
    prompt_id = self.document.prompts.get_prompt_id("This is a new prompt")
    run_record = self.document.new_run_record(prompt_id)
    self.run_id = run_record.run_id
    self.id1 = run_record.add_new_segment("segment text", 4).id()
    self.id2 = run_record.add_new_segment("more segment text", 6).id()
    self.id3 = run_record.add_new_completion([self.id1, self.id2],
                                             "completion text", 5, 20).id()
    run_record.result_id = self.id3
  
  def tearDown(self):
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

    
  
