from openai import OpenAI
from cursion import settings
import json






def llm_json(
        system_prompt: str,
        user_prompt: str,
        image_urls: list=[],
        schema: dict=None,
        model: str='gpt-5-mini',
        max_output_tokens: int=3000,
    ) -> dict:
    """
    Sends a JSON-only completion request and
    returns the parsed object.
    """

    if not settings.GPT_API_KEY:
        raise Exception('GPT_API_KEY is not configured')

    client = OpenAI(api_key=settings.GPT_API_KEY)

    text_format = {'type': 'json_object'}
    if schema:
        text_format = {
            'type': 'json_schema',
            'name': schema.get('name', 'response'),
            'schema': schema.get('schema', schema),
            'strict': schema.get('strict', True),
        }

    # The Responses API requires the request input itself to mention JSON
    # when using json_object output mode.
    if text_format.get('type') == 'json_object':
        prompt_text = f'{system_prompt}\n{user_prompt}'.lower()
        if 'json' not in prompt_text:
            user_prompt = (
                'Return a valid JSON object only.\n\n'
                f'{user_prompt}'
            )

    # setup content structure
    content = [{'type': 'input_text', 'text': user_prompt,}]

    # handle images if present
    for url in image_urls:
        content.append({
            'type': 'input_image',
            'image_url': url,
        })

    # send request
    response = client.responses.create(
        model=model,
        instructions=system_prompt,
        input=[{
            'role': 'user',
            'content': content,
        }],
        max_output_tokens=max_output_tokens,
        text={
            'format': text_format
        }
    )

    content = response.output_text
    if not content:
        raise Exception('LLM returned an empty response')

    return json.loads(content)
