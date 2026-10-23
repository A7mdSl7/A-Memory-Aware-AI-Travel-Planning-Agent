from app.planner import create_plan,update_step
from app.agent import TravelAgent
from app.config import Settings
from app.memory_store import MemoryStore

def test_plan_statuses_and_execution_records(tmp_path):
    plan=create_plan('Plan a weekend itinerary in Florence')
    assert all(s.status=='pending' for s in plan.steps)
    update_step(plan,plan.steps[0].id,'completed')
    assert plan.steps[0].status=='completed'
    settings=Settings(None,'gpt-4.1-mini',tmp_path/'db.sqlite',True)
    agent=TravelAgent(MemoryStore(settings.database_path),settings)
    assert agent.demo is True and agent.llm_agent is None
    out=agent.respond('demo','thread-2','Plan a weekend itinerary in Florence')
    assert out['demo'] and len(out['tool_logs'])>=4
    assert all(x['status']=='completed' and x['result'] for x in out['tool_logs'])
    assert all(s.status=='completed' for s in out['plan'].steps)

def test_new_thread_recalls_database_preferences(tmp_path):
    settings=Settings(None,'gpt-4.1-mini',tmp_path/'db.sqlite',True)
    store=MemoryStore(settings.database_path)
    agent=TravelAgent(store,settings)
    agent.respond('demo','old','I like museums and Italian food, and I avoid early mornings.')
    store2=MemoryStore(settings.database_path)
    out=TravelAgent(store2,settings).respond('demo','new','Plan a weekend itinerary in Florence')
    assert out['preferences']['likes_museums'] is True
    assert out['preferences']['cuisine_preferences']==['Italian']
    assert 'old' != 'new' and store2.get_messages('demo','new')[0]['role']=='user'

def test_tool_failure_is_recorded_and_plan_step_fails(tmp_path):
    settings=Settings(None,'gpt-4.1-mini',tmp_path/'db.sqlite',True)
    agent=TravelAgent(MemoryStore(settings.database_path),settings)
    class BrokenTool:
        def invoke(self,args): raise RuntimeError('sample outage')
    agent.tools['search_hotels']=BrokenTool()
    out=agent.respond('demo','failure-thread','Plan a weekend itinerary in Florence')
    failure=next(x for x in out['tool_logs'] if x['tool_name']=='search_hotels')
    step=next(x for x in out['plan'].steps if x.id=='search_hotels')
    assert failure['status']=='failed' and failure['error']=='sample outage'
    assert failure['started_at'] and failure['completed_at']
    assert step.status=='failed' and step.error=='sample outage'
