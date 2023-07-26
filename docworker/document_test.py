from . import document
import unittest


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
    # TODO: fix
    #self.document.complete_run()
    #self.assertFalse(self.document.is_running(self.run_id))

    msg = "a status message"
    self.document.set_status_message(msg, self.run_id)
    self.assertEqual(self.document.status_message(self.run_id), msg)

    self.assertEqual(self.document.prompt(self.run_id), self.prompt)

    # TODO: fix
    #self.assertEqual(self.document.completed_steps(self.run_id), 0)
    
    # TODO: fix
    # self.document.note_step_compete()

    self.assertTrue(self.document.run_exists(self.run_id))
    self.assertFalse(self.document.run_exists(0))
    

    # TODO: fix
    #self.document.start_run(self.prompt, [self.id1, self.id2])
    #self.document.cancel_run("Canceled")
    #self.set_final_result(compeltion)
    # self.document.run_input_tokens

    run_record = self.document.get_run_record(self.run_id)
    self.assertIsNotNone(run_record)
    prompt = self.document.run_record_prompt(run_record)
    self.assertIsNotNone(prompt)
    

    
    
                    
