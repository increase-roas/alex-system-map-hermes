"""Emit JSON Schema 2020-12 contracts for catalog consumers."""
from pathlib import Path
import json
R=Path(__file__).resolve().parents[1]
S={'type':'string','minLength':1};A={'type':'array','items':S,'uniqueItems':True};N={'type':['string','null']}
STATE={'category':{'enum':['documented_current','historical','planned','unresolved']},
       'evidence_level':{'enum':['reported','configured','tested','unverified']},
       'observed_condition':{'enum':['working','failing','blocked','unknown']},'observed_at':N}
def obj(props,required=None,extra=False):return dict(type='object',properties=props,required=list(props) if required is None else required,additionalProperties=extra)
def wrap(item):return {'$schema':'https://json-schema.org/draft/2020-12/schema','type':'object','properties':{'schema_version':{'const':'1.0.0'},'records':{'type':'array','items':item}},'required':['schema_version','records'],'additionalProperties':False}
def emit(name,item):
    (R/'schemas'/f'{name}.schema.json').write_text(json.dumps(wrap(item),indent=2)+'\n')
def main():
    emit('components',obj(dict(id=S,name=S,layer_id={'type':'string','pattern':'^layer_0[1-8]$'},kind=S,aliases=A,purpose={'type':'string'},boundary={'type':'string'},**STATE,evidence_ids=A,source_record_ids=A,source_categories_preserved={'type':'boolean'},fit={'type':'string'},account_reference={},resource_type={},source_observed_at={},provider_status={}),['id','name','layer_id','kind','aliases','purpose','boundary',*STATE,'evidence_ids','source_record_ids','source_categories_preserved']))
    emit('relationships',obj(dict(id=S,source_id=S,target_id=S,type=S,label=S,**STATE,evidence_ids=dict(A,minItems=1),resolution=N,source_pointer=N)))
    cell=obj({'column':S,'value':{},'comment':{'type':'string'},'link':N},['column','value'])
    ptr=obj({'source_id':S,'sheet':S,'row':{'type':'integer','minimum':1}})
    emit('evidence',obj(dict(id=S,source_id=S,captured_as_of=S,observed_at=N,scope=S,sheet=S,row={'type':'integer','minimum':1},source_file_id=N,cells={'type':'array','items':cell}),['id','source_id','captured_as_of','observed_at','scope']))
    emit('issues',obj(dict(id=S,kind=S,subject_id=S,summary=S,detail={'type':'string'},status={'enum':['open','resolved','superseded']},evidence_ids=A,severity={'enum':['information','review','critical']})))
    emit('source-records',obj(dict(id=S,record_type=S,label=S,component_id=S,placement_component_id=S,source=ptr,evidence_ids=A,cells={'type':'array','items':cell},coverage_basis=S,full_source=obj({'sheet':S,'row':{'type':'integer','minimum':1}}),full_cells={'type':'array','items':cell},asset_key=S),['id','record_type','label','component_id','placement_component_id','source','evidence_ids','cells','coverage_basis']))
    emit('coverage',obj(dict(record_id=S,record_type=S,component_id=S,placement_component_id=S,source=ptr,coverage_row={'type':'integer','minimum':5})))
    emit('sources',obj(dict(id=S,kind={'enum':['archived_file','package_input','user_reference']},path=S,sha256={'type':'string','pattern':'^[a-f0-9]{64}$'},group=S,relative_path=S,original_path=S,archive=S,archive_member=S,bytes={'type':'integer','minimum':0},reader={},catalog_row={'type':'integer','minimum':1}),['id','kind','sha256']))
    emit('layers',obj({'id':S,'name':S,'order':{'type':'integer','minimum':1,'maximum':8}}))
    emit('table-index',obj({'id':S,'sheet':S,'path':S,'rows':{'type':'integer','minimum':1}}))
if __name__=='__main__':main()
