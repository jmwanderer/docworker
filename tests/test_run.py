from docworker.analysis_app import get_db
import docworker
from docworker import analysis_app
import time


def test_start_run(app, client, auth, mocker):
  mocker.patch('docworker.docx_util', 'FAKE_AI_SLEEP', 0)
  auth.login('test1')

  with app.app_context():
    analysis_app.set_logged_in_user('test1')    
    session = analysis_app.get_session('PA_utility.docx')
    assert session.get_run_record(1) is None

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
    session = analysis_app.get_session('PA_utility.docx')
    assert not session.is_running()
    assert session.get_run_record(1) is not None    
  
  




