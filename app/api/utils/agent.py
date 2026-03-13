from rest_framework.authtoken.models import Token
from django.utils import timezone
from ..models import Chat
from cursion import settings
from openai import OpenAI






class Agent():
    """ 
    Generate new respones for the passed 'Chat'.

    Args:
        'chat_id': str

    Use `Agent.respond()` to generate a response to the 
    latest `chat.message`

    Returns:
        None
    """


    def __init__(self, chat_id: str=None) -> None:
        self.chat = Chat.objects.get(id=chat_id)
        self.llm = OpenAI(api_key=settings.GPT_API_KEY)




    def respond(self) -> object:
        """
        Using the latest entry in `chat.message`, and chat 
        history sends a request to the self.llm and 
        appends the response to chat.message.

        Args:
            None
        
        Returns:
            None
        """

        # get user's token
        token_obj = Token.objects.get(user=self.chat.user) if self.chat else None

        # format chat history
        history_parts = []

        # iterate through each message and build chat context
        for m in self.chat.messages:
            author = m.get('author') or m.get('user')
            role = 'assistant' if author == 'agent' else 'user'
            text = m.get('text', '').strip()
            name = 'Agent' if author == 'agent' else self.chat.user.first_name
            history_parts.append(f'[{role.upper()} — {name}]\n{text}')

        # concat into string
        chat_history = '\n\n'.join(history_parts)
        
        # full prompt
        input_string = (
            'BACKGROUND CONTEXT:\n'
            'You are a Software Quality Assurance Engineer.\n'
            # 'Please reference https://docs.cursion.dev for documentation about the Cursion Platform.\n'
            'If necessary, call Cursion MCP tools to complete the task.\n'
            'If responding with `Site`, `Page`, `Scan`, `Test`, `Case`, `CaseRun`, `Flow`, or `FlowRun` objects, ' 
            'include their URL formatted like so: '
            f'"{settings.CLIENT_URL_ROOT}/<object>/<object_id>"\n'
            '\n\n'
            f'CHAT HISTORY:\n{chat_history}'
        )

        # build mcp url
        mcp_base = (settings.MCP_URL_ROOT or '').rstrip('/')
        mcp_url = mcp_base if mcp_base.endswith('/sse') else f'{mcp_base}/sse'

        # call llm
        response = self.llm.responses.create(
            model='gpt-5-mini',
            input=input_string,
            tools=[{
                'type'              : 'mcp',
                'server_label'      : 'cursion-mcp',
                'server_url'        : mcp_url,
                'require_approval'  : 'never',
                'authorization'     : f'Token {token_obj.key}'
            }]
        )

        # add response message
        messages = self.chat.messages
        messages.append({
            'author': 'agent', 
            'time_created': str(timezone.now()),
            'text': response.output_text
        })
        self.chat.messages = messages
        self.chat.save()

        # return updated chat
        return self.chat
    
