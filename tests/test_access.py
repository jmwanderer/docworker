
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

  response = client.get('/segview')
  assert response.status_code == 302
  assert response.location == '/login'

  response = client.post('/export')
  assert response.status_code == 302
  assert response.location == '/login'

  response = client.get('/login')
  assert response.status_code == 200
  
  response = client.get('/login?authkey=fookey1')
  assert response.status_code == 200


def test_access(client, auth):
  auth.login('test1')
  response = client.get('/')
  assert response.status_code == 200

  response = client.get('/doclist')
  assert response.status_code == 200

  response = client.get('/runlist')
  assert response.status_code == 302
  assert response.location == '/'

  response = client.get('/segview')
  assert response.status_code == 302
  assert response.location == '/'

  response = client.post('/export')
  assert response.status_code == 302
  assert response.location == '/'
  
  response = client.get('/login')
  assert response.status_code == 200

def test_no_login(app, client, auth):
  app.config.update({'NO_USER_LOGIN': True})

  # Validate user redirected to login
  response = client.get('/')
  assert response.status_code == 302
  assert response.location == '/login'

  # Try auto create of user
  response = client.get('/login')
  assert response.status_code == 302
  response = client.get(response.location)
  assert response.status_code == 302
  assert response.location == '/'

  response = client.get('/')
  assert response.status_code == 200

  response = client.get('/doclist')
  assert response.status_code == 200

  response = client.get('/runlist')
  assert response.status_code == 302
  assert response.location == '/'

  response = client.get('/segview')
  assert response.status_code == 302
  assert response.location == '/'

  response = client.post('/export')
  assert response.status_code == 302
  assert response.location == '/'
  
  response = client.get('/login')
  assert response.status_code == 302

 
def test_access_with_doc(client, auth):
  auth.login('test1')

  response = client.get('/runlist?doc=PA_utility.docx')
  assert response.status_code == 200
  
  response = client.get('/segview?doc=PA_utility.docx')
  assert response.status_code == 302

  response = client.get('/segview?doc=PA_utility.docx&item=Block+1')
  assert response.status_code == 302

  response = client.get('/segview?doc=PA_utility.docx&run_id=1&item=Block+1')
  assert response.status_code == 302

  response = client.post('/export',
                         data={ 'doc': 'PA_utility.docx',
                                'run_id': 1
                               })

  assert response.status_code == 200  
