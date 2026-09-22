# The Founder Times' own image: the pinned Plow cloud base plus the PDF
# toolchain the edition renderer needs.
#
# Why this exists. The base image ships no HTML-to-PDF engine: measured
# inside a running the-plow-times container, `import weasyprint` is a
# ModuleNotFoundError, and there is no `reportlab`/`pypdf` either, no Chrome
# and no wkhtmltopdf. So `render_edition.py --pdf` fails by design there, and
# the agent correctly told its owner it could not produce the paper as a PDF.
# Installing weasyprint is what makes the PDF leg of the fixed template real,
# container-side, with no dependency on a browser on the owner's Mac.
#
# Pinned by digest, exactly like the fleet's `runtime/stack.json`: a mutable
# tag would re-resolve on every pull and change a large unreviewed surface
# under a running agent that holds live credentials. Bump both together.
FROM public.ecr.aws/e1h7x4a2/plow-cloud-agents:base-ef0019372ff8bca593611b31ebd2e08f9f1458ff@sha256:a8a2f97ad78b8192d80a984dce81d3bf5a9a883d18cb7b677704913a09b56aee

# Boot recopies /opt/hermes/plow-seed/config.yaml over the agent home on
# every start. The base seed's model.default is z-ai/glm-5.2; this paper
# stays on anthropic/claude-sonnet-5. merge_pt_seed_config.py stamps
# that id (and its providers.plow.models slot) from runtime/config.yaml
# onto the seed. Do not sed the seed onto another model, and do not pin
# HERMES_MODEL in compose.yml.
#
# plow-init also writes seed['display'] whole on every boot. The base
# seed leaves plow_chat interim messages at the Hermes default (on) and
# long_running_notifications true — measured live after the Sonnet
# recreate: the model named every tool in the owner's DM. Overlay the
# newspaper quiet block onto the seed; copying runtime/config.yaml into
# /var/lib/hermes is not enough (agent-home shadows it).
COPY runtime/config.yaml /tmp/pt-runtime-config.yaml
COPY image/merge_pt_seed_config.py /opt/plow/merge_pt_seed_config.py
RUN /opt/hermes/.venv/bin/python3 /opt/plow/merge_pt_seed_config.py \
      /opt/hermes/plow-seed/config.yaml /tmp/pt-runtime-config.yaml \
 && grep -q 'interim_assistant_messages: false' /opt/hermes/plow-seed/config.yaml \
 && grep -q 'long_running_notifications: false' /opt/hermes/plow-seed/config.yaml \
 && grep -q 'context_file_max_chars: 40000' /opt/hermes/plow-seed/config.yaml

# Boot also recomposes $HOME/SOUL.md from this seed. COPY to the home is
# shadowed by the volume and then overwritten; the newspaper identity has
# to live here or the generic "Plow assistant" seed wins.
COPY runtime/SOUL.md /opt/hermes/plow-seed/SOUL.md

# WeasyPrint's native dependencies. The Python wheel is pure Python but binds
# Pango/Cairo through cffi at import time, so the shared libraries have to be
# present or `import weasyprint` fails with a cffi error that reads like a
# Python problem. Debian 13 (trixie) is the base's own distro; these are its
# package names. fonts-dejavu-core gives the rendered page a guaranteed font
# even with no fontconfig cache, so a fresh container never prints blanks.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libpango-1.0-0 \
      libpangocairo-1.0-0 \
      libpangoft2-1.0-0 \
      libharfbuzz0b \
      libcairo2 \
      libgdk-pixbuf-2.0-0 \
      libffi8 \
      shared-mime-info \
      fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

# Install into the hermes venv, because that is the `python3` skills actually
# get. Three approaches that look right and are not, all measured on this
# base and this running container:
#   * `uv pip install --system`: reports the environment as /usr but installs
#     to /usr/lib/python3.13/site-packages, which Debian's python3 does not
#     have on sys.path (it uses /usr/lib/python3/dist-packages), so the
#     install succeeds and `import weasyprint` still fails.
#   * `--target /usr/local/lib/python3.13/dist-packages` against
#     /usr/bin/python3 (the previous fix here): that path IS on the *system*
#     python's sys.path, and `docker exec ... sh -l -c 'python3 -c "import
#     weasyprint"'` (a login shell) succeeds -- but the login flag resets
#     PATH to the container's default, dropping `/opt/hermes/.venv/bin`.
#     The skill's own `python3
#     render_edition.py ...` runs as a plain command, not a login shell, and
#     the real container PATH (`agent.env` / the running container's env) is
#     `/opt/hermes/bin:/opt/hermes/.venv/bin:...:/usr/bin:...` -- the hermes
#     venv wins, `import weasyprint` fails there, and the PDF leg silently
#     no-ops (best-effort) while the chat edition still ships as plain text.
#     Confirmed live: `docker exec hermes-the-plow-times sh -c 'python3 -c
#     "import weasyprint"'` (a plain, non-login shell) is a
#     ModuleNotFoundError on that image.
#   * The fix is to install where the PATH that is actually used points:
#     the hermes venv's own site-packages, via `--python
#     /opt/hermes/.venv/bin/python3` with no `--target` override (a normal
#     venv install, no PEP 668 fight).
#
# pydyf is pinned alongside weasyprint, not left to resolver choice: measured
# on this base, weasyprint 62.3 declares only `pydyf>=0.10.0`, so a fresh
# install pulls pydyf 0.12.1, whose Stream API moved and makes every
# write_pdf() die with "AttributeError: 'super' object has no attribute
# 'transform'". 0.10.0 is the version 62.3 was written against.
#
# The build check renders a PDF through a PLAIN `sh -c`, not a login shell
# (`-l`) and not an explicit interpreter path -- `python3 -c "..."` exactly
# as the skill
# invokes it -- so a PATH regression like the one above fails the build
# instead of shipping quietly.
ARG WEASYPRINT_VERSION=62.3
ARG PYDYF_VERSION=0.10.0
ARG PYYAML_VERSION=6.0.3
# BOTH interpreters, because which one `python3` means depends on the shell.
# Measured live on 2026-09-16, after the venv-only install shipped:
#   `sh -c 'command -v python3'`      -> /opt/hermes/.venv/bin/python3   (weasyprint 62.3)
#   `bash -lc 'command -v python3'`   -> /usr/bin/python3                (ModuleNotFoundError)
# The LOGIN shell drops /opt/hermes/bin and /opt/hermes/.venv/bin from PATH,
# and the agent's terminal tool runs its commands through one -- so the skill
# got "weasyprint is not installed", took the documented text fallback, and
# the owner was handed a wall of text instead of the newspaper PDF, twice, on
# a machine where the venv could render that same edition.json to a valid
# 29KB PDF. The note above was right that the venv is one of the pythons the
# skills get; it was wrong that it is the only one.
#
# /usr/local/lib/python3.13/dist-packages is on the SYSTEM python's sys.path
# (verified in the running container) and both interpreters are 3.13.5, so
# one wheel set is valid for both.
RUN uv pip install --python /opt/hermes/.venv/bin/python3 \
      "weasyprint==${WEASYPRINT_VERSION}" "pydyf==${PYDYF_VERSION}" "PyYAML==${PYYAML_VERSION}" \
 && uv pip install --python /usr/bin/python3 \
      --target /usr/local/lib/python3.13/dist-packages \
      "weasyprint==${WEASYPRINT_VERSION}" "pydyf==${PYDYF_VERSION}" "PyYAML==${PYYAML_VERSION}" \
 && probe="import yaml, weasyprint; weasyprint.HTML(string='<p>build probe</p>').write_pdf('/tmp/probe.pdf'); import os; os.remove('/tmp/probe.pdf'); print('weasyprint', weasyprint.__version__)" \
 && sh -c "python3 -c \"$probe\"" \
 && bash -lc "python3 -c \"$probe\"" \
 && bash -c "python3 -c \"$probe\""

# Identity and skills. SOUL.md replaces the base's; first boot re-asserts
# root ownership, which is what the trailing chmod answers. Skills land at
# /opt/hermes/skills so the base runtime reconciles them into whichever home
# this image boots — a COPY under /var/lib/hermes/skills is shadowed by the
# agent-home volume after first create.
COPY runtime/SOUL.md /var/lib/hermes/SOUL.md
COPY runtime/USER.md /var/lib/hermes/memories/USER.md
COPY runtime/config.yaml /var/lib/hermes/config.yaml
COPY LICENSE /usr/share/doc/the-plow-times/
COPY pt-dashboard/ /opt/hermes/skills/pt-dashboard/
COPY pt-edition/   /opt/hermes/skills/pt-edition/
COPY pt-intake/    /opt/hermes/skills/pt-intake/
COPY pt-print/     /opt/hermes/skills/pt-print/
COPY pt-priority/  /opt/hermes/skills/pt-priority/
COPY pt-research/  /opt/hermes/skills/pt-research/
COPY pt-setup/     /opt/hermes/skills/pt-setup/
COPY pt-shared/    /opt/hermes/skills/pt-shared/

RUN find /opt/hermes/skills -mindepth 1 -type d -exec chmod 0755 {} + \
 && find /opt/hermes/skills -mindepth 1 -type f ! -perm -u+x -exec chmod 0644 {} + \
 && find /opt/hermes/skills -mindepth 1 -type f -perm -u+x -exec chmod 0755 {} + \
 && chmod 0644 /var/lib/hermes/SOUL.md /var/lib/hermes/config.yaml \
      /var/lib/hermes/memories/USER.md \
 && install -d -o 10000 -g 10000 -m 0700 /var/lib/hermes/pt

COPY image/cont-init.d/02-copy-plow-credentials /etc/cont-init.d/02-copy-plow-credentials
RUN chmod 0755 /etc/cont-init.d/02-copy-plow-credentials

# Hermes' billing wall concatenates the HTTP body, the provider name, a
# billing URL and `/model`. Pin one user-facing line and fail the build if
# the base digest moved those functions.
COPY image/hermes/billing_user_message.py /opt/hermes/agent/billing_user_message.py
COPY image/hermes/patch_billing_user_message.py /opt/plow/patch_billing_user_message.py
RUN /opt/hermes/.venv/bin/python3 /opt/plow/patch_billing_user_message.py \
      /opt/hermes/agent/conversation_loop.py \
 && chmod 0644 /opt/hermes/agent/billing_user_message.py

# After each paper, rotate the owner's plow_chat session so the next
# "send me the paper" does not re-ingest Latch dumps from this turn.
COPY image/hermes/plow_seal_session.py /opt/hermes/plow_seal_session.py
COPY image/hermes/patch_seal_session.py /opt/plow/patch_seal_session.py
RUN /opt/hermes/.venv/bin/python3 /opt/plow/patch_seal_session.py \
      /opt/hermes/gateway/run_turn.py \
 && /opt/hermes/.venv/bin/python3 /opt/plow/patch_seal_session.py \
      /opt/hermes/gateway/response_filters.py \
 && chmod 0644 /opt/hermes/plow_seal_session.py
