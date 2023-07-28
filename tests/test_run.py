from docworker.analysis_app import get_db
import docworker
from docworker import analysis_app
import time


def test_start_run(app, client, auth, mocker):
  mocker.patch('docworker.doc_gen', 'FAKE_AI_SLEEP', 0)
  auth.login('test1')

  with app.app_context():
    analysis_app.set_logged_in_user('test1')    
    doc= analysis_app.get_document('PA_utility.docx')
    assert doc.get_run_record(1) is None

  response = client.post('/',
                         data={'run': 'run',
                               'prompt': 'a sample prompt',
                               'doc': 'PA_utility.docx',
                               }
                         )
  assert response.status_code == 302
  assert 'run_id=1' in response.location

  time.sleep(1)

  with app.app_context():
    analysis_app.set_logged_in_user('test1')    
    doc = analysis_app.get_document('PA_utility.docx')
    assert not doc.is_running()
    assert doc.get_run_record(1) is not None    
  
  




