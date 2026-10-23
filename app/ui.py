import json, uuid, inspect
import gradio as gr
from .config import get_settings
from .memory_store import MemoryStore
from .agent import TravelAgent
from .planner import create_plan

settings=get_settings(); store=MemoryStore(settings.database_path)
if not settings.demo_mode and not settings.gemini_api_key:
    CONFIG_ERROR='Gemini mode is selected but GEMINI_API_KEY is missing. Add it to the project .env or set DEMO_MODE=true.'
else: CONFIG_ERROR=''
agent=TravelAgent(store,settings,force_demo=True if CONFIG_ERROR else None)

def status_text():
    return f"Provider: {'Gemini configured' if settings.gemini_api_key else 'Gemini not configured'} | Mode: {'DEMO — deterministic mock behavior' if agent.demo else 'Gemini agent'}" + (f"\n⚠ {CONFIG_ERROR}" if CONFIG_ERROR else '')
def memories(user):
    if not user.strip(): return '{}'
    return json.dumps(store.get_preferences(user).model_dump(),ensure_ascii=False,indent=2)
def new_thread(): return str(uuid.uuid4())[:8], [], 'No request has been planned yet.', '[]'
def respond(user,thread,message,history):
    if not message.strip(): yield history,'','',memories(user); return
    history=(history or [])+ [{'role':'user','content':message}]
    initial=create_plan(message)
    initial_view='**Plan created before tool execution**\n\n'+'\n'.join(f'⟳ {s.title} — pending' for s in initial.steps)
    yield history,initial_view,'[]',memories(user)
    try:
        out=agent.respond(user.strip() or 'demo-user',thread,message)
        plan=out['plan']; completed=sum(s.status=='completed' for s in plan.steps); percent=round(completed/len(plan.steps)*100) if plan.steps else 100
        pl=f"**Progress: {completed}/{len(plan.steps)} ({percent}%)**\n\n"+'\n'.join(f"{'☑' if s.status=='completed' else '⚠' if s.status=='failed' else '⟳' if s.status=='running' else '☐'} {s.title} — {s.status}" for s in plan.steps)
        tl=json.dumps(out['tool_logs'],ensure_ascii=False,indent=2)
        history.append({'role':'assistant','content':out['answer']})
        yield history,pl,tl,memories(user.strip() or 'demo-user')
    except Exception as e:
        history.append({'role':'assistant','content':f'Agent error: {e}'})
        yield history,'⚠ Request failed. See the chat error.','[]',memories(user.strip() or 'demo-user')

with gr.Blocks(title='MemoryLab | Travel Planner') as demo:
    gr.Markdown('# MemoryLab ✈️\nA memory-aware travel planning agent')
    status=gr.Markdown(status_text())
    with gr.Row():
        user=gr.Textbox(label='Demo user ID',value='demo-user')
        thread=gr.Textbox(label='Conversation thread',value=str(uuid.uuid4())[:8],interactive=False)
        fresh=gr.Button('New conversation')
    with gr.Row():
        with gr.Column(scale=2):
            chat_args={'label':'Travel planning chat','height':460}
            if 'type' in inspect.signature(gr.Chatbot).parameters: chat_args['type']='messages'
            chat=gr.Chatbot(**chat_args)
            msg=gr.Textbox(label='Message',placeholder='Plan a weekend itinerary in Florence…')
            send=gr.Button('Send',variant='primary')
        with gr.Column():
            plan=gr.Markdown('No request has been planned yet.',label='Plan progress')
            tools=gr.Code(value='[]',language='json',label='Tool activity')
            memory=gr.Code(value=memories('demo-user'),language='json',label='Saved user preferences')
            refresh=gr.Button('Refresh saved memory')
            clear=gr.Button('Clear this user’s demo data',variant='stop')
            clear_result=gr.Markdown()
    send.click(respond,[user,thread,msg,chat],[chat,plan,tools,memory]).then(lambda:'',outputs=msg)
    msg.submit(respond,[user,thread,msg,chat],[chat,plan,tools,memory]).then(lambda:'',outputs=msg)
    fresh.click(new_thread,outputs=[thread,chat,plan,tools])
    refresh.click(memories,inputs=user,outputs=memory)
    user.change(memories,inputs=user,outputs=memory)
    def clear_user(user_id):
        if not user_id.strip(): return 'Enter a user ID first.'
        store.clear_user(user_id.strip()); return f'Cleared local data for `{user_id}`.'
    clear.click(clear_user,inputs=user,outputs=clear_result).then(memories,inputs=user,outputs=memory)

if __name__=='__main__': demo.launch()
