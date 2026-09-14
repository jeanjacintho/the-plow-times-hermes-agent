"""The only billing-exhaustion line this agent is allowed to show.

Hermes otherwise concatenates the HTTP body, the provider name, a billing
URL and `/model`. Every user-facing billing path in conversation_loop is
rewritten at image build to return this string and nothing else.
"""

BILLING_USER_MESSAGE = (
    "Saldo da inferência acabou. Recarrega os créditos e tenta de novo."
)
