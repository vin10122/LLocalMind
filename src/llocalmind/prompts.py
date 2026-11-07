"""The existing concise Qwen chat template, extended to conversation history."""
SYSTEM = (
    "Rispondi nella lingua dell'utente. Sii diretto e conciso: dai la "
    "risposta essenziale senza premesse o ripetizioni. Per domande "
    "semplici bastano una o poche frasi; aggiungi dettagli solo se "
    "servono a rispondere correttamente. Concludi appena hai risposto."
)


def format_conversation(messages):
    if not messages or len(messages) % 2 != 1:
        raise ValueError('La conversazione deve terminare con una domanda')
    parts = [f'<|im_start|>system\n{SYSTEM}<|im_end|>\n']
    for index, message in enumerate(messages):
        role = 'user' if index % 2 == 0 else 'assistant'
        if not isinstance(message,dict) or message.get('role') != role or not isinstance(message.get('content'),str):
            raise ValueError('Ordine dei messaggi non valido')
        if message.get('images'):
            raise ValueError('Questa chat contiene immagini: seleziona Vision locale nelle impostazioni.')
        parts.append(f"<|im_start|>{role}\n{message['content']}<|im_end|>\n")
    parts.append('<|im_start|>assistant\n<think>\n\n</think>\n\n')
    return ''.join(parts)
