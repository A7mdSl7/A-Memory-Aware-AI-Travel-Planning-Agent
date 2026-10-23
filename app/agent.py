import json, re
from .models import Preferences
from .planner import create_plan, update_step
from .tools import TRAVEL_TOOLS

class GeminiConfigurationError(RuntimeError):
    """A requested Gemini mode cannot be initialized with current settings."""

def create_gemini_model(settings):
    """Create the configured Gemini chat model without logging credentials."""
    if not settings.gemini_api_key:
        raise GeminiConfigurationError(
            "Gemini mode was requested, but GEMINI_API_KEY is not configured. "
            "Set the key or enable DEMO_MODE=true."
        )
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=settings.gemini_model, api_key=settings.gemini_api_key)

def extract_explicit_preferences(text: str, current: Preferences) -> Preferences:
    """Conservative extraction: only explicit positive statements update saved values."""
    d=current.model_dump()
    low=text.lower()
    if re.search(r'\b(i like|i love|i enjoy|prefer)\b.{0,30}\bmuseums?\b',low): d['likes_museums']=True
    if re.search(r'\b(i avoid|i hate|don.t like|do not like)\b.{0,35}\bmuseums?\b',low): d['likes_museums']=False
    avoids_early = (
        r"\b(?:avoid|hate|dislike|no)\s+(?:the\s+)?early mornings?(?:\s+activities?)?\b",
        r"\b(?:i\s+)?(?:don't|don.t|do not)\s+(?:like|want|enjoy)\s+(?:doing\s+)?early mornings?(?:\s+activities?)?\b",
        r"\bprefer\s+(?:a\s+)?late starts?\b",
        r"\bnot an early bird\b",
    )
    accepts_early = (
        r"\b(?:i\s+)?(?:like|enjoy|prefer)\s+(?:early mornings?|early starts?)\b",
        r"\b(?:i\s+)?(?:don't|don.t|do not)\s+mind\s+early mornings?\b",
    )
    if any(re.search(pattern, low) for pattern in avoids_early):
        d['avoid_early_mornings']=True
    elif any(re.search(pattern, low) for pattern in accepts_early):
        d['avoid_early_mornings']=False
    cuisines=('Italian','Japanese','Thai','Mexican','Indian','Chinese','French','Mediterranean','Korean','Greek','Spanish','Turkish','Vietnamese')
    cuisine_pattern=r'\b(?:i like|i love|i prefer|i enjoy)\b.{0,35}\b('+'|'.join(c.lower() for c in cuisines)+r')\b'
    match=re.search(cuisine_pattern,low)
    if match:
        cuisine=next(c for c in cuisines if c.lower()==match.group(1))
        if cuisine not in d['cuisine_preferences']: d['cuisine_preferences'].append(cuisine)
    m=re.search(r'(?:budget|€|eur)\s*(?:of|is|:)?\s*€?([0-9]+)\s*(?:-|to|–)\s*€?([0-9]+)',text,re.I)
    if m: d['budget_min'],d['budget_max']=float(m.group(1)),float(m.group(2))
    return Preferences.model_validate(d)

def is_trip_planning_request(message: str) -> bool:
    """Distinguish an actual itinerary request from talking about travel plans."""
    planning_intent = re.search(
        r'\b(?:plan|create|make|build|suggest|recommend)\b.{0,60}\b(?:trip|itinerary|weekend|day[s]?|vacation|holiday)\b'
        r'|\b(?:trip|itinerary|weekend|vacation|holiday)\b.{0,60}\b(?:plan|suggest|recommend|for me)\b',
        message, re.I,
    )
    preference_only = re.search(r'\b(?:remember|save|store)\b.{0,80}\bpreferences?\b', message, re.I)
    return bool(planning_intent and not preference_only)

class TravelAgent:
    def __init__(self, store, settings, force_demo=None):
        self.store,self.settings=store,settings
        self.demo = settings.demo_mode if force_demo is None else force_demo
        self.tools={t.name:t for t in TRAVEL_TOOLS}
        self.llm_agent=None
        if not self.demo:
            if not settings.gemini_api_key:
                raise GeminiConfigurationError(
                    "Gemini mode was requested, but GEMINI_API_KEY is not configured. "
                    "Set the key or enable DEMO_MODE=true."
                )
            from langchain.agents import create_agent
            try:
                model = create_gemini_model(settings)
            except ImportError as exc:
                raise GeminiConfigurationError(
                    "Gemini mode was requested, but its optional dependencies are unavailable. "
                    "Install them with `python -m pip install -r requirements-gemini.txt`."
                ) from exc
            self.llm_agent=create_agent(model,TRAVEL_TOOLS,system_prompt="You are a careful travel planner. Use supplied preference and tool results; state that travel tool data is illustrative mock data. Never invent a budget or claim mock results are live. The application has already executed and recorded the planned tools; do not call them again unless new information is required.")
    def respond(self,user_id,thread_id,message):
        # Load the durable user profile before planning; extraction only merges
        # explicit facts from this turn into the retrieved preferences.
        saved_preferences=self.store.get_preferences(user_id)
        prefs=extract_explicit_preferences(message,saved_preferences)
        self.store.save_preferences(user_id,prefs)
        plan=create_plan(message); logs=[]; outputs={}
        planning_request=is_trip_planning_request(message)
        if not planning_request and self.demo:
            # Preference updates are still persisted and shown in plan progress,
            # but must not trigger mock travel searches or an itinerary.
            plan.steps=[step for step in plan.steps if step.id=='load_preferences']
        answer='Your explicit preferences have been saved for future travel plans.'
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
        # City names are not reliably capitalized in chat. Stop at common
        # request clauses so "in Florence for me. Use ..." stays Florence.
        city=re.search(r'\b(?:in|to|visit)\s+([A-Za-z][a-zA-Z -]*?)(?=\s+(?:for me|this weekend|for the weekend|using|use|with|and)\b|[?.!,]|$)',msg,re.I)
        place=city.group(1).strip() if city else 'Florence'
        if name=='search_flights': return {'origin':'unspecified','destination':place,'date':'user dates if supplied'}
        if name=='search_hotels': return {'city':place,'budget_max':p.budget_max}
        if name=='find_attractions': return {'city':place,'interests':['museums'] if p.likes_museums else []}
        if name=='search_restaurants': return {'city':place,'cuisine':p.cuisine_preferences[0] if p.cuisine_preferences else 'local'}
        return {'city':place,'date':'user dates if supplied'}
    def _demo_reply(self,msg,p,results):
        if not is_trip_planning_request(msg):
            return 'Demo mode is active. I saved any explicit preferences. Ask me to plan a trip when you are ready.'

        hotel=results.get('search_hotels',{}).get('options',[{}])[0]
        attractions=results.get('find_attractions',{}).get('options',[])
        restaurants=results.get('search_restaurants',{}).get('options',[])
        city=results.get('search_hotels',{}).get('city','your destination')
        parts=['**DEMO MODE — deterministic itinerary using illustrative mock travel data.**','',f"### Weekend in {city}",f"- Preferences used: museums={'yes' if p.likes_museums else 'not specified'}; cuisine={', '.join(p.cuisine_preferences) or 'not specified'}; avoid early mornings={'yes' if p.avoid_early_mornings else 'not specified'}; budget={'not provided' if p.budget_max is None else f'{p.budget_min or 0}–{p.budget_max} {p.currency}' }."]
        if p.avoid_early_mornings is True:
            parts.append('- Schedule: avoid early starts; begin in the late morning.')
        elif p.avoid_early_mornings is False:
            parts.append('- Schedule: no restriction on early starts is saved.')
        else:
            parts.append('- Schedule preference: not specified.')
        if hotel: parts.append(f"- Stay: {hotel['name']} (mock €{hotel['nightly_price']}/night).")
        if attractions:
            time_label='Late morning' if p.avoid_early_mornings is True else 'First stop'
            parts.append(f"- Saturday {time_label.lower()}: {attractions[0]['name']}.")
        if restaurants: parts.append(f"- Saturday dinner: {restaurants[0]['name']} ({restaurants[0]['cuisine']}).")
        if len(attractions)>1: parts.append(f"- Sunday: Visit {attractions[1]['name']} at a relaxed pace.")
        if len(restaurants)>1: parts.append(f"- Sunday lunch: {restaurants[1]['name']} ({restaurants[1]['cuisine']}).")
        if results.get('check_weather'): parts.append(f"- Weather: {results['check_weather']['forecast']}.")
        parts.append('\nThese examples are not live availability, prices, or forecasts. Add travel dates and origin for a more specific demo plan.')
        return '\n'.join(parts)
