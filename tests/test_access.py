
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
  auth.login('test1')
  response = client.get('/')
  assert response.status_code == 200

  response = client.get('/doclist')
  assert response.status_code == 200

  response = client.get('/runlist')
  assert response.status_code == 302
  assert response.location == '/'

  response = client.get('/docview')
  assert response.status_code == 302
  assert response.location == '/'

  response = client.get('/segview')
  assert response.status_code == 302
  assert response.location == '/'

  response = client.get('/docgen')
  assert response.status_code == 302
  assert response.location == '/'
  
  response = client.get('/generate')
  assert response.status_code == 302
  assert response.location == '/'
  
  response = client.get('/genresult')
  assert response.status_code == 302
  assert response.location == '/'
  
  response = client.get('/dispatch')
  assert response.status_code == 302
  assert response.location == '/docview'
  
  response = client.get('/export')
  assert response.status_code == 302
  assert response.location == '/'
  
  response = client.get('/sel_export')
  assert response.status_code == 302
  assert response.location == '/'
  
  response = client.get('/sel_gen')
  assert response.status_code == 302
  assert response.location == '/'
  
  response = client.get('/login')
  assert response.status_code == 200

  
def test_access_with_doc(client, auth):
  auth.login('test1')

  response = client.get('/runlist?doc=PA_utility.docx')
  assert response.status_code == 200
  
  response = client.get('/docview?doc=PA_utility.docx')
  assert response.status_code == 200  

  response = client.get('/segview?doc=PA_utility.docx&item=Block+1')
  assert response.status_code == 200  

  response = client.get('/docgen?doc=PA_utility.docx')
  assert response.status_code == 200

  response = client.get('/generate?doc=PA_utility.docx')
  assert response.status_code == 200  

  response = client.get('/genresult?doc=PA_utility.docx')
  assert response.status_code == 200  

  response = client.get('/export?doc=PA_utility.docx')
  assert response.status_code == 200  

  response = client.get('/sel_export?doc=PA_utility.docx')
  assert response.status_code == 200  

  response = client.get('/sel_gen?doc=PA_utility.docx')
  assert response.status_code == 200  
  
