from app.tools import TRAVEL_TOOLS

def test_mock_tools_return_structured_data():
    cases=[{'origin':'Cairo','destination':'Rome'}, {'city':'Florence'}, {'city':'Florence','interests':['museums']}, {'city':'Florence','cuisine':'Italian'}, {'city':'Florence'}]
    for tool,args in zip(TRAVEL_TOOLS,cases):
        result=tool.invoke(args)
        assert isinstance(result,dict) and result.get('source')=='DEMO MOCK DATA'
