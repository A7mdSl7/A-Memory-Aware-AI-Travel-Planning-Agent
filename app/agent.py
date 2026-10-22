import json, re
from .models import Preferences
from .planner import create_plan, update_step
from .tools import TRAVEL_TOOLS

def extract_explicit_preferences(text: str, current: Preferences) -> Preferences:
    """Conservative extraction: only explicit positive statements update saved values."""
    d=current.model_dump()
    low=text.lower()
    if re.search(r'\b(i like|i love|i enjoy|prefer)\b.{0,30}\bmuseums?\b',low): d['likes_museums']=True
    if re.search(r'\b(i avoid|i hate|don.t like|do not like)\b.{0,35}\bmuseums?\b',low): d['likes_museums']=False
    if re.search(r'\b(no early|avoid early|not early|hate early|don.t do early|do not do early)\b',low): d['avoid_early_mornings']=True
    if re.search(r'\b(i like|i love|i prefer|enjoy)\b.{0,30}\bitalian\b',low):
        if 'Italian' not in d['cuisine_preferences']: d['cuisine_preferences'].append('Italian')
    m=re.search(r'(?:budget|€|eur)\s*(?:of|is|:)?\s*€?([0-9]+)\s*(?:-|to|–)\s*€?([0-9]+)',text,re.I)
    if m: d['budget_min'],d['budget_max']=float(m.group(1)),float(m.group(2))
    return Preferences.model_validate(d)

class TravelAgent:
    def __init__(self, store, settings, force_demo=None):
        self.store,self.settings=store,settings
        self.demo = settings.demo_mode if force_demo is None else force_demo
        self.tools={t.name:t for t in TRAVEL_TOOLS}
        self.llm_agent=None
        if not self.demo and settings.api_key:
            from langchain.agents import create_agent
            from langchain_openai import ChatOpenAI
            self.llm_agent=create_agent(ChatOpenAI(model=settings.model,api_key=settings.api_key),TRAVEL_TOOLS,system_prompt="You are a careful travel planner. Use supplied preference and tool results; state that travel tool data is illustrative mock data. Never invent a budget or claim mock results are live.")
    def respond(self,user_id,thread_id,message):
        prefs=extract_explicit_preferences(message,self.store.get_preferences(user_id))
        self.store.save_preferences(user_id,prefs)
        plan=create_plan(message); logs=[]; outputs={}
        for step in plan.steps:
            if step.id=='load_preferences': update_step(plan,step.id,'running'); outputs['preferences']=prefs.model_dump(); update_step(plan,step.id,'completed',json.dumps(outputs['preferences']))
            elif step.id=='build_itinerary':
                update_step(plan,step.id,'running')
                if self.demo: answer=self._demo_reply(message,prefs,outputs)
                else:
                    history=self.store.get_messages(user_id,thread_id)
                    messages=[{'role':'system','content':f'Saved preferences: {prefs.model_dump_json()}\nAlready executed travel tool results: {json.dumps(outputs,ensure_ascii=False)}'}]
                    messages.extend({'role':m['role'],'content':m['content']} for m in history[-12:])
                    messages.append({'role':'user','content':message})
                    answer=self.llm_agent.invoke({'messages':messages})['messages'][-1].content
                update_step(plan,step.id,'completed',str(answer)[:500])
            else:
                name={'search_flights':'search_flights','search_hotels':'search_hotels','find_attractions':'find_attractions','search_restaurants':'search_restaurants','check_weather':'check_weather'}[step.id]
                from datetime import datetime, timezone
                args=self._args(name,message,prefs); record={'tool_name':name,'arguments':args,'status':'running','started_at':datetime.now(timezone.utc).isoformat()}; logs.append(record); update_step(plan,step.id,'running')
                try:
                    value=self.tools[name].invoke(args); outputs[name]=value; record.update(status='completed',result=value,completed_at=datetime.now(timezone.utc).isoformat()); update_step(plan,step.id,'completed',json.dumps(value,ensure_ascii=False))
                except Exception as e:
                    record.update(status='failed',error=str(e),completed_at=datetime.now(timezone.utc).isoformat()); update_step(plan,step.id,'failed',error=str(e))
        self.store.add_message(user_id,thread_id,'user',message); self.store.add_message(user_id,thread_id,'assistant',answer)
        self.store.add_episode(user_id,{'request':message,'summary':str(answer)[:300]})
        return {'answer':answer,'plan':plan,'tool_logs':logs,'preferences':prefs.model_dump(),'demo':self.demo}
    def _args(self,name,msg,p):
        city=re.search(r'\b(?:in|to|visit)\s+([A-Z][a-zA-Z -]+)',msg)
        place=city.group(1).strip().rstrip('?.!') if city else 'Florence'
        if name=='search_flights': return {'origin':'unspecified','destination':place,'date':'user dates if supplied'}
        if name=='search_hotels': return {'city':place,'budget_max':p.budget_max}
        if name=='find_attractions': return {'city':place,'interests':['museums'] if p.likes_museums else []}
        if name=='search_restaurants': return {'city':place,'cuisine':p.cuisine_preferences[0] if p.cuisine_preferences else 'local'}
        return {'city':place,'date':'user dates if supplied'}
    def _demo_reply(self,msg,p,results):
        if not any(k in msg.lower() for k in ['itinerary','trip','weekend','travel','plan','days']): return 'Demo mode is active. I saved any explicit preferences. Ask for a trip itinerary to see the planning workflow.'
        parts=['**DEMO MODE — deterministic response using illustrative mock travel data.**','',f"### Your Florence trip\n- Preferences used: museums={'yes' if p.likes_museums else 'not specified'}; cuisine={', '.join(p.cuisine_preferences) or 'not specified'}; avoid early mornings={'yes' if p.avoid_early_mornings else 'not specified'}; budget={'not provided' if p.budget_max is None else f'{p.budget_min or 0}–{p.budget_max} {p.currency}' }."]
        if 'search_hotels' in results: parts.append(f"- Stay: {results['search_hotels']['options'][0]['name']} (mock €{results['search_hotels']['options'][0]['nightly_price']}/night).")
        ats=results.get('find_attractions',{}).get('options',[]); meals=results.get('search_restaurants',{}).get('options',[])
        if ats: parts.append(f"- Late morning: {ats[0]['name']}.")
        if meals: parts.append(f"- Dinner: {meals[0]['name']} ({meals[0]['cuisine']}).")
        if results.get('check_weather'): parts.append(f"- Weather: {results['check_weather']['forecast']}.")
        parts.append('\nThese examples are not live availability, prices, or forecasts. Add travel dates and origin for a more specific demo plan.')
        return '\n'.join(parts)
