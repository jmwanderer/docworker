from docworker.analysis_app import create_app
import tempfile

def test_config():
  instance_path = tempfile.TemporaryDirectory()
  app = create_app(instance_path=instance_path.name)    
  assert not app.testing
  app = create_app({'TESTING': True}, instance_path=instance_path.name)    
  assert app.testing
  

