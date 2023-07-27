from . import document
from . import doc_gen
from . import dw_cli
import unittest
import tempfile
import os


class DwCLITestCase(unittest.TestCase):

  def setUp(self):
    self.user_dir = tempfile.TemporaryDirectory()        
    self.orig_file = 'PA utility.docx'
    self.doc_path = os.path.join(os.path.dirname(__file__),
                                 'samples/', self.orig_file)
    doc_gen.FAKE_AI_COMPLETION=True
    doc_gen.FAKE_AI_SLEEP=0
  
  def tearDown(self):
    self.user_dir.cleanup()    
    pass

  def create_doc(self):
    f = open(self.doc_path, 'rb')
    filename = document.find_or_create_doc(self.user_dir.name,
                                           self.orig_file, f)
    f.close()
    return filename

  def testImportDoc(self):
    dw_cli.import_document(self.user_dir.name, os.path.join(self.doc_path))
    
  def testDumpPrompts(self):
    filename = self.create_doc()
    doc = dw_cli.load_document(self.user_dir.name, filename)
    dw_cli.dump_prompts(doc)

  def testShowDoc(self):
    filename = self.create_doc()
    doc = dw_cli.load_document(self.user_dir.name, filename)
    dw_cli.show_doc(doc)

  def testDocGen(self):
    filename = self.create_doc()
    doc = dw_cli.load_document(self.user_dir.name, filename)
    path = dw_cli.doc_path(self.user_dir.name, filename)
    dw_cli.run_doc_gen(path, doc, "Dummy prompt")

  def testShowResult(self):
    filename = self.create_doc()
    doc = dw_cli.load_document(self.user_dir.name, filename)
    path = dw_cli.doc_path(self.user_dir.name, filename)
    dw_cli.run_doc_gen(path, doc, "Dummy prompt")
    dw_cli.show_result(doc, 1)
    
    
