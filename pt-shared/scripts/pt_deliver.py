"""pt-deliver's --script: register_crons.py installs a copy in Hermes's
scripts dir, which Hermes runs every minute with no agent. It only hands off
to post_to_chat.py --flush-outbox, whose stdout Hermes delivers to chat."""
import os
import sys

POST = "/var/lib/hermes/skills/pt-shared/scripts/post_to_chat.py"
os.execv(sys.executable, [sys.executable, POST, "--flush-outbox"])
