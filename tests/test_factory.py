from docworker.analysis_app import create_app

def test_config():
  assert not create_app().testing
  assert create_app({'TESTING': True}).testing


def test_no_access(client):
  response = client.get('/')
  assert response.status_code == 302
  assert response.location == '/login'

  response = client.get('/doclist')
  assert response.status_code == 302
  assert response.location == '/login'

  response = client.get('/runlist')
  assert response.status_code == 302
  assert response.location == '/login'

  response = client.get('/docview')
  assert response.status_code == 302
  assert response.location == '/login'

  response = client.get('/segview')
  assert response.status_code == 302
  assert response.location == '/login'

  response = client.get('/docgen')
  assert response.status_code == 302
  assert response.location == '/login'

  response = client.get('/generate')
  assert response.status_code == 302
  assert response.location == '/login'

  response = client.get('/genresult')
  assert response.status_code == 302
  assert response.location == '/login'

  response = client.get('/dispatch')
  assert response.status_code == 302
  assert response.location == '/login'

  response = client.get('/export')
  assert response.status_code == 302
  assert response.location == '/login'

  response = client.get('/sel_export')
  assert response.status_code == 302
  assert response.location == '/login'

  response = client.get('/sel_gen')
  assert response.status_code == 302
  assert response.location == '/login'

  response = client.get('/login')
  assert response.status_code == 200
  
  response = client.get('/?authkey=fookey1')
  assert response.status_code == 302
  assert response.location == '/'


def test_access(client, auth):
  auth.login()
  response = client.get('/')
  assert response.status_code == 200
  
