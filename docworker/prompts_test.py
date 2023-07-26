from . import prompts
import unittest


class PromptsTestCase(unittest.TestCase):

  def setUp(self):
    self.prompts = prompts.Prompts()
  
  def tearDown(self):
    pass
  
  def testInit(self):
    self.assertTrue(len(self.prompts.get_prompt_set()) > 1)
    self.assertFalse(self.prompts.fixup_prompts())

  def testLookup(self):
    name = self.prompts.get_prompt_name_by_id(1)
    self.assertIsNotNone(name)
    id = self.prompts.get_prompt_id_by_name(name)
    self.assertEqual(id, 1)
    prompt_str = self.prompts.get_prompt_str_by_id(2)
    self.assertIsNotNone(prompt_str)

    name = self.prompts.get_prompt_name_by_id(2)    
    prompt = self.prompts.get_prompt_by_name(name)
    self.assertIsNotNone(prompt)
    self.assertEqual(prompt[0], 2)

  def testNewPrompt(self):
    id1 = self.prompts.get_prompt_id("This is a new prompt")
    id2 = self.prompts.get_prompt_id("This is a new prompt")
    id3 = self.prompts.get_prompt_id("This is another new prompt")
    self.assertEqual(id1, id2)
    self.assertNotEqual(id1, id3)

  def testPromptIds(self):
    id_list = [ x[0] for x in self.prompts.get_prompt_set() ]
    id1 = self.prompts.get_prompt_id("This is a new prompt")
    self.assertFalse(id1 in id_list)




    
  
