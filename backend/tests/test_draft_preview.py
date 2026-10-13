import os
import pytest
from app.document_generation.service import DocumentType, render_context
from app.document_generation.preview import draft_preview
from test_seven_documents import semester
from test_assessments import setup, BASE

def flatten(value):
    if isinstance(value,list): return ''.join(flatten(v) for v in value)
    if isinstance(value,dict): return value.get('text','')+flatten(value.get('children',[]))
    return ''

def kinds(value):
    return [n['kind'] for n in value for _ in [0]] + [kind for n in value for kind in kinds(n.get('children',[]))]

@pytest.mark.parametrize('document',list(DocumentType))
def test_templates_become_safe_structured_preview(semester,document):
    result=draft_preview(render_context(semester,document))
    text=flatten(result['blocks'])
    assert 'Discrete Mathematics I' in text
    assert '\\documentclass' not in text and '@@' not in text
    assert 'heading' in kinds(result['blocks'])
    if document==DocumentType.RULES_OF_ASSESSMENT:
        assert 'table' in kinds(result['blocks']) and '110' in text
    if document==DocumentType.COURSEWORK_ASSIGNMENT_INFORMATION:
        assert 'list' in kinds(result['blocks']) and 'Tuesday' in text

def test_escaped_tex_and_html_remain_only_text():
    from app.document_generation.latex import escape
    hostile=r'<img src=x onerror=alert(1)> \input{secret} & # $ % _ ^ ~'
    result=draft_preview(r'\begin{document}\heading{Title}'+escape(hostile)+r'\end{document}')
    assert hostile in flatten(result['blocks'])
    assert set(kinds(result['blocks'])) <= {'heading','text'}

integration=pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS')!='1',reason='Requires local PostgreSQL')

@integration
@pytest.mark.integration
@pytest.mark.parametrize('role',['LECTURER','ADMIN'])
def test_draft_all_documents_current_values_never_saved(setup,role):
    client,h,cid,year,_=setup(role)
    url=f'{BASE}/{cid}'
    before=client.get(url,headers=h).json()
    draft={'metadata':{'academic_year_start':year,'term':'FALL','display_label':'Unsaved semester'},
        'events':[{'event_type':'ENDTERM','venue':'Unsaved venue','writing_start_time':'10:15','writing_end_time':'11:45'}],
        'policies':[{'code':'ENDTERM','topics':'Unsaved topics <script>alert(1)</script>','maximum_score':51}],
        'rules':{'plus_points_rules':'Unsaved bonus rule','plus_points_maximum':5}}
    for document in DocumentType:
        response=client.post(url+f'/documents/{document.value}/preview',headers=h,json=draft)
        assert response.status_code==200,response.text
        assert response.headers['cache-control']=='no-store'
        assert response.json()['label']=='Draft Preview'
    result=client.post(url+'/documents/ENDTERM_TEST_INFORMATION/preview',headers=h,json=draft).json()
    assert 'Unsaved venue' in flatten(result['blocks']) and '<script>alert(1)</script>' in flatten(result['blocks'])
    assert client.get(url,headers=h).json()==before
    assert client.post(url+'/documents/DATES_OF_ASSESSMENTS/preview',headers={'Cookie':h['Cookie']},json=draft).status_code==403
    draft['events'][0]['writing_end_time']='09:00'
    assert client.post(url+'/documents/DATES_OF_ASSESSMENTS/preview',headers=h,json=draft).status_code==422
    assert client.get(url,headers=h).json()==before

@integration
@pytest.mark.integration
@pytest.mark.parametrize('role',['STUDENT','DEMONSTRATOR'])
def test_draft_denied(setup,accounts,role):
    client,_,cid,_,_=setup()
    _,headers=accounts(role)
    for document in DocumentType:
        url=f'{BASE}/{cid}/documents/{document.value}/preview'
        assert client.post(url,headers=headers,json={}).status_code==403
        assert client.post(url,json={}).status_code==401
