from pathlib import Path
import subprocess
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.document_generation import compiler
from app.config import get_settings

@pytest.fixture
def configured(monkeypatch):
    settings=get_settings()
    monkeypatch.setattr(settings,'pdf_compiler_mode','native')
    return settings

def test_fixed_unicode_mapping():
    assert compiler.compiler_source('őűŐŰ–—') == r'\H{o}\H{u}\H{O}\H{U}\textendash{}\textemdash{}'

@pytest.mark.parametrize('mode,status',[('success',200),('failure',422),('timeout',504),('missing',422),('large',413),('glyph',422),('invalid',502),('unavailable',503)])
def test_compiler_bounds_cleanup(configured,monkeypatch,mode,status):
    paths=[]
    def run(args,**kwargs):
        root=Path(kwargs['cwd']);paths.append(root)
        assert '--only-cached' in args and '--untrusted' in args
        assert kwargs['timeout']==30 and 'DATABASE_PASSWORD' not in kwargs['env']
        if mode=='timeout': raise subprocess.TimeoutExpired(args,30)
        if mode=='unavailable': raise FileNotFoundError()
        if mode!='missing': (root/'document.pdf').write_bytes(b'bad' if mode=='invalid' else b'%PDF-1.7\n'+b'x'*(configured.pdf_max_bytes if mode=='large' else 3))
        if mode=='glyph': (root/'document.log').write_text('Missing character: secret document')
        return SimpleNamespace(returncode=1 if mode=='failure' else 0)
    monkeypatch.setattr(compiler.subprocess,'run',run)
    if status==200: assert compiler.compile_pdf('trusted source').startswith(b'%PDF-')
    else:
        with pytest.raises(HTTPException) as error: compiler.compile_pdf('trusted source')
        assert error.value.status_code==status
        assert 'secret' not in error.value.detail
    assert paths and all(not p.exists() for p in paths)
    assert compiler._slot.acquire(blocking=False)
    compiler._slot.release()

def test_busy_and_source_limit(configured):
    compiler._slot.acquire()
    try:
        with pytest.raises(HTTPException) as error: compiler.compile_pdf('source')
        assert error.value.status_code==503
    finally: compiler._slot.release()
    with pytest.raises(HTTPException) as error: compiler.compile_pdf('x'*1_000_001)
    assert error.value.status_code==413

def test_docker_timeout_removes_container(configured,monkeypatch):
    monkeypatch.setattr(configured,'pdf_compiler_mode','docker')
    calls=[]
    def run(args,**kwargs):
        calls.append(args)
        if args[1]=='run':
            assert '--network=none' in args and '--pull=never' in args and compiler.PINNED_IMAGE in args
            raise subprocess.TimeoutExpired(args,30)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(compiler.subprocess,'run',run)
    with pytest.raises(HTTPException) as error: compiler.compile_pdf('source')
    assert error.value.status_code==504
    assert calls[1][1:3]==['rm','-f']

import os
from test_assessments import setup, BASE
from app.document_generation.service import DocumentType
integration=pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS')!='1',reason='Requires local PostgreSQL')

@integration
@pytest.mark.integration
@pytest.mark.parametrize('role',['LECTURER','ADMIN'])
def test_pdf_api_all_documents_read_only(setup,monkeypatch,role):
    client,h,cid,year,_=setup(role)
    before=client.get(f'{BASE}/{cid}',headers=h).json()
    sources=[]
    def compile(source): sources.append(source); return b'%PDF-1.7\nmock'
    monkeypatch.setattr('app.routers.assessments.compile_pdf',compile)
    draft={'metadata':{'academic_year_start':year,'term':'FALL','display_label':'Unsaved label'},'events':[{'event_type':'ENDTERM','venue':'Unsaved hall','rooms':[{'room':'LE 24','groups':['1','4']}]}],'policies':[],'rules':{}}
    for kind in DocumentType:
        response=client.post(f'{BASE}/{cid}/documents/{kind.value}/pdf',headers=h,json=draft)
        assert response.status_code==200,response.text
        assert response.content.startswith(b'%PDF-')
        assert response.headers['content-type']=='application/pdf'
        assert response.headers['cache-control']=='no-store'
        assert response.headers['content-disposition'].endswith('.pdf"')
    assert any('Unsaved hall' in source and 'LE 24' in source for source in sources)
    assert client.get(f'{BASE}/{cid}',headers=h).json()==before
    url=f'{BASE}/{cid}/documents/DATES_OF_ASSESSMENTS/pdf'
    assert client.post(url,headers={'Cookie':h['Cookie']},json=draft).status_code==403
    assert client.post(url,headers=h,json={}).status_code==422
    assert client.post(f'{BASE}/{cid}/documents/INVALID/pdf',headers=h,json=draft).status_code==422
    assert client.post(f'{BASE}/2147483647/documents/DATES_OF_ASSESSMENTS/pdf',headers=h,json=draft).status_code==404

@integration
@pytest.mark.integration
@pytest.mark.parametrize('role',['STUDENT','DEMONSTRATOR'])
def test_pdf_denied(setup,accounts,role):
    client,_,cid,_,_=setup();_,h=accounts(role)
    for kind in DocumentType:
        url=f'{BASE}/{cid}/documents/{kind.value}/pdf'
        assert client.post(url,headers=h,json={}).status_code==403
        assert client.post(url,json={}).status_code==401
