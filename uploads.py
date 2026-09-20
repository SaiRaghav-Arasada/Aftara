from email.parser import BytesParser
from email.policy import default

def form_data(content_type,body):
 if not content_type.startswith('multipart/form-data'):
  from urllib.parse import parse_qs
  return {k:v[0] for k,v in parse_qs(body.decode(),keep_blank_values=True).items()}
 message=BytesParser(policy=default).parsebytes(('Content-Type: '+content_type+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+body)
 if not message.is_multipart():raise ValueError('Invalid upload form.')
 data={}
 for part in message.iter_parts():
  name=part.get_param('name',header='content-disposition')
  if not name:continue
  payload=part.get_payload(decode=True) or b''
  if part.get_filename():data[name]={'name':part.get_filename(),'content':payload}
  else:data[name]=payload.decode('utf-8')
 return data
