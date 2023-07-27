from . import document
from . import doc_gen
import unittest
import tempfile
import os


class RunStateTestCase(unittest.TestCase):

  def setUp(self):
    self.run_state = doc_gen.RunState()

  def testSteps(self):
    self.run_state.start_run("a prompt", [ 1, 2, 3], 1)
    self.assertEqual(len(self.run_state.to_run), 3)
    self.assertTrue(self.run_state.next_item())
    self.run_state.pop_item()
    self.assertEqual(len(self.run_state.to_run), 2)
    self.assertFalse(self.run_state.skip_remaining_gen())

    self.run_state.pop_item()
    self.run_state.pop_item()
    self.assertTrue(self.run_state.is_last_completion())
    
    self.run_state.note_step_completed(4)
    self.assertFalse(self.run_state.next_result_set())
    self.assertFalse(self.run_state.in_additions(4))

    


class MiscCoverageTestCase(unittest.TestCase):
  def testPrompt(self):
    self.assertIsNotNone(doc_gen.build_prompt("A prompt"))

  def testPostProcess(self):
    response_record = doc_gen.ResponseRecord("completion", 10, 10, False)
    doc_gen.post_process_completion(response_record)
    response_record = doc_gen.ResponseRecord("completion", 10, 10, True)
    doc_gen.post_process_completion(response_record)    
    
    

class BasicDocGenTestCase(unittest.TestCase):

  def setUp(self):
    self.user_dir = tempfile.TemporaryDirectory()        
    orig_file = 'PA utility.docx'
    path = os.path.join(os.path.dirname(__file__),
                        'samples/', orig_file)
    f = open(path, 'rb')
    self.filename = document.find_or_create_doc(self.user_dir.name,
                                                orig_file, f)
    f.close()
    self.doc_path = self.get_doc_file_path(self.filename)
    self.document = document.load_document(self.doc_path)
    doc_gen.FAKE_AI_COMPLETION=True
    doc_gen.FAKE_AI_SLEEP=0
    
  
  def tearDown(self):
    self.user_dir.cleanup()    
    pass

  def get_doc_file_path(self, doc_name):
    file_name = doc_name + '.daf'
    return os.path.join(self.user_dir.name, file_name)
  
  
  def testInit(self):
    self.assertEqual(len(self.document.run_list), 0)

    
  def testPartialRun(self):
    run_state = doc_gen.start_docgen(self.doc_path,
                                     self.document,
                                     "A prompt")
    self.assertEqual(run_state.run_id, 1)    
    items1 = self.document.get_ordered_items(run_state.run_id)
    self.assertTrue(len(items1) > 1)

    doc_gen.run_next_docgen(self.doc_path, self.document, run_state)
    self.assertIsNotNone(self.document.get_status_message())
    self.assertTrue(len(self.document.get_status_message()) > 0)

    # Mock a final result
    self.assertFalse(run_state.next_result_set())
    completion = self.document.get_item_by_id(run_state.run_id,
                                              run_state.result_id)
    self.document.set_final_result(completion)

    
    items2 = self.document.get_ordered_items(run_state.run_id)    
    self.assertEqual(len(items2), len(items1) + 1)
    
    
    
  def testFullRun(self):
    run_state = doc_gen.start_docgen(self.doc_path,
                                     self.document,
                                     "A prompt")
    count = doc_gen.run_input_tokens(self.document, run_state)
    self.assertTrue(count > 0)
    self.assertTrue(count < 100000)
    
    doc_gen.run_all_docgen(self.doc_path, self.document, run_state)
    # TODO: Consider how we want to get results from the document
    run_record = self.document.get_current_run_record()
    completion = self.document.get_item_by_id(run_record.run_id,
                                              run_record.result_id)
    self.assertIsNotNone(completion)
    self.assertTrue(len(completion.text()) < 1000)
    self.assertFalse(self.document.is_running())
                     

  def testFullTransOpRun(self):
    run_state = doc_gen.start_docgen(self.doc_path,
                                     self.document,
                                     "A prompt",
                                     transOp=True)
    doc_gen.run_all_docgen(self.doc_path, self.document, run_state)
    # TODO: Consider how we want to get results from the document
    run_record = self.document.get_current_run_record()
    completion = self.document.get_item_by_id(run_record.run_id,
                                              run_record.result_id)
    self.assertIsNotNone(completion)
    self.assertTrue(len(completion.text()) > 1000)
    self.assertFalse(self.document.is_running())
