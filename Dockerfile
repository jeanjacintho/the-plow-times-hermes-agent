# The Plow Times' own image: the pinned Plow cloud base plus the PDF
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
FROM public.ecr.aws/e1h7x4a2/plow-cloud-agents@sha256:bfd4980f361a551e62569f8c2eb717c1076d0b8be3a0499b869eaece151336a4

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
#     python's sys.path, and `docker exec ... sh -lc python3 -c "import
#     weasyprint"` succeeds -- but `-lc` resets PATH to the container's
#     default, dropping `/opt/hermes/.venv/bin`. The skill's own `python3
#     render_edition.py ...` runs as a plain command, not a login shell, and
#     the real container PATH (`agent.env` / the running container's env) is
#     `/opt/hermes/bin:/opt/hermes/.venv/bin:...:/usr/bin:...` -- the hermes
#     venv wins, `import weasyprint` fails there, and the PDF leg silently
#     no-ops (best-effort) while the chat edition still ships as plain text.
#     Confirmed live: `docker exec hermes-the-plow-times sh -c 'python3 -c
#     "import weasyprint"'` (no `-l`) is a ModuleNotFoundError on that image.
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
# The build check renders a PDF through a PLAIN `sh -c`, not `sh -lc` and not
# an explicit interpreter path -- `python3 -c "..."` exactly as the skill
# invokes it -- so a PATH regression like the one above fails the build
# instead of shipping quietly.
ARG WEASYPRINT_VERSION=62.3
ARG PYDYF_VERSION=0.10.0
RUN uv pip install --python /opt/hermes/.venv/bin/python3 \
      "weasyprint==${WEASYPRINT_VERSION}" "pydyf==${PYDYF_VERSION}" \
 && sh -c "python3 -c \"import weasyprint; weasyprint.HTML(string='<p>build probe</p>').write_pdf('/tmp/probe.pdf'); import os; os.remove('/tmp/probe.pdf'); print('weasyprint', weasyprint.__version__)\""
